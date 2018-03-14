# AWS ECS Automation
Collection of solutions to automate AWS ECS related tasks

## ECR Deployment Trigger
Lambda function that will create a CloudWatch event rule which will be triggered as soon as a Docker image is pushed to ECR and deploys it automatically to a ECS Cluster.
