import boto3
import os

def get_role_base_client(client_type):
    """Create client - federation access to an AWS resource"""

    sts_default_provider_chain = boto3.client('sts')

    session_duration_seconds=os.getenv('SESSION_DURATION', 3600)
    role_to_assume_arn=os.getenv('AWS_ROLE_ARN')
    role_session_name=os.getenv('AWS_SESSION_NAME', 'test_session')
    web_identity_token=open(os.getenv('AWS_WEB_IDENTITY_TOKEN_FILE')).read()

    response=sts_default_provider_chain.assume_role_with_web_identity(
        DurationSeconds=session_duration_seconds,
        RoleArn=role_to_assume_arn,
        RoleSessionName=role_session_name,
        WebIdentityToken=web_identity_token,
    )

    creds=response['Credentials']

    role_base_client = boto3.client(
        client_type,
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken'],
    )

    return role_base_client