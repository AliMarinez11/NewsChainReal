import boto3
import json

def lambda_handler(event, context):
    ssm = boto3.client('ssm')
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        command = f"/home/ec2-user/run_summarize.sh {key}"
        response = ssm.send_command(
            InstanceIds=['i-04a9aa8364e1b5c31'],  # Replace with EC2 instance ID
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': [command]}
        )
        print(f"Triggered EC2 command: {command}, CommandId: {response['Command']['CommandId']}")
    return {'statusCode': 200, 'body': json.dumps('Triggered EC2')}
