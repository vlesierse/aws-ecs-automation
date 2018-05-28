import os
import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    cluster = os.environ['CLUSTER']
    tagLatest = os.environ['TAG_LATEST'] == 'true'
    deployLatest = os.environ['DEPLOY_LATEST'] == 'true'
    if tagLatest and deployLatest: deployLatest = False

    region = event['region']
    ecs = boto3.client('ecs', region_name=region)
    ecr = boto3.client('ecr', region_name=region)

    repositoryName = event['detail']['responseElements']['image']['repositoryName']
    registryId = event['detail']['responseElements']['image']['registryId']
    image = f'{registryId}.dkr.ecr.{region}.amazonaws.com/{repositoryName}'
    imageTag = event['detail']['responseElements']['image']['imageId']['imageTag']
    imageManifest = event['detail']['responseElements']['image']['imageManifest']

    def get_task_definitions():
        response = ecs.list_task_definition_families(status='ACTIVE')
        families = response['families']
        while ('nextToken' in response):
            response = ecs.list_task_definition_families(nextToken=response['nextToken'])
            families.append(response['families'])

        taskDefinitions = [ecs.describe_task_definition(taskDefinition=family)['taskDefinition'] for family in families]
        return [
            taskDefinition for taskDefinition in taskDefinitions
            if any([
                c for c in taskDefinition['containerDefinitions']
                if
                    (c['image'].startswith(image) and not c['image'].endswith(f':{imageTag}'))
                    or (deployLatest and c['image'].endswith(f':latest'))
                ])
        ]

    def update_task_definition(taskDefinition, newTaskDefinitions, image, imageTag):
        family = taskDefinition['family']
        containerDefinitions = taskDefinition['containerDefinitions']
        print(f'Update task definition: {family}')
        [
            update_container_definition(containerDefinition, image, imageTag)
            for containerDefinition in containerDefinitions
            if containerDefinition['image'].startswith(image)
        ]

        response = ecs.register_task_definition(
            family=family,
            taskRoleArn=taskDefinition['taskRoleArn'],
            containerDefinitions=containerDefinitions,
            volumes=taskDefinition['volumes'],
            placementConstraints=taskDefinition['placementConstraints'],
            requiresCompatibilities=taskDefinition['compatibilities'])
        oldTaskDefinitionArn = taskDefinition['taskDefinitionArn']
        newTaskDefinitionArn = response['taskDefinition']['taskDefinitionArn']
        newTaskDefinitions[strip_arn(oldTaskDefinitionArn)] = newTaskDefinitionArn
        return newTaskDefinitionArn

    def update_container_definition(containerDefinition, image, imageTag):
        print(f'Update container definition to {image}:{imageTag}')
        containerDefinition['image'] = f'{image}:{imageTag}'

    def get_services(cluster):
        response = ecs.list_services(cluster=cluster)
        service_arns = response['serviceArns']
        while ('nextToken' in response):
            response = ecs.list_services(cluster=cluster, nextToken=response['nextToken'])
            service_arns.append(response['serviceArns'])
        return [
            service for service in ecs.describe_services(cluster=cluster, services=service_arns)['services']
            if service['status'] == 'ACTIVE'
        ]

    def update_service(service, newTaskDefinitionArn):
        serviceArn = service['serviceArn']
        print(f'Update service {serviceArn} with {newTaskDefinitionArn}')
        ecs.update_service(cluster=cluster, service=serviceArn, taskDefinition=newTaskDefinitionArn)
    
    def tag_latest():
         print(f'Tag {image}:{imageTag} with latest')
         try:
             ecr.put_image(registryId=registryId, repositoryName=repositoryName, imageManifest=imageManifest, imageTag='latest')
         except ClientError as e:
            if e.response['Error']['Code'] != 'ImageAlreadyExistsException':
                raise
            print(f'Image {image}:{imageTag} is already tagged with latest')
         

    def strip_arn(arn):
        return arn[:arn.rindex(":")]

    # Update Task Definitions
    taskDefinitions = get_task_definitions()

    newTaskDefinitions = {}
    [update_task_definition(taskDefinition, newTaskDefinitions, image, imageTag) for taskDefinition in taskDefinitions]

    if newTaskDefinitions:
        services = get_services(cluster)
        # Update Services
        [
            update_service(service, newTaskDefinitions[strip_arn(service['taskDefinition'])])
            for service in services
            if strip_arn(service['taskDefinition']) in newTaskDefinitions.keys()
        ]
        if tagLatest: tag_latest()
