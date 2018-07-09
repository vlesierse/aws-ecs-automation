# Load Balancer Failover
This Lambda function will orchestrate a failover when an AWS CloudWatch Alarm triggers. When it returns OK it will failback.

## Installation
For the installation of this Lambda function you need to take the following steps.

### Prepare
Use Python 3.6 and [Virtualenv](https://virtualenv.pypa.io/en/stable) to install your virtual environment get the required packages.

```sh
virtualenv -p python3 --no-site-packages --distribute .env && source .env/bin/activate && pip install -r requirements.txt
```

### S3 Bucket
As S3 bucket is required as destination for the AWS SAM package. If you don't have one already, create one:

```sh
aws s3 mb s3://your-aws-sam-bucket
```

### Package
Use the AWS CLI to create and upload the AWS SAM package to S3:

```sh
aws cloudformation package --template-file template.yml --output-template-file template-packaged.yml --s3-bucket your-aws-sam-bucket
```

### Deploy
Use the AWS CLI to deploy the AWS SAM package using CloudFormation: 

```sh
aws cloudformation deploy --capabilities CAPABILITY_IAM --template-file template-packaged.yml --stack-name <YOUR STACK NAME> --parameter-overrides LoadBalancer=<YOUR LOAD BALANCER> TargetGroup=<YOUR TARGET GROUP> FallbackTargetGroup=<YOUR FALLBACK TARGET GROUP>
```
