import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):

    region_name = "eu-west-2"

    # Create a Secrets Manager client
    session = boto3.session.Session(profile_name='tradesales')
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response['SecretString']
    return secret

import boto3
import json

def save_tokens_to_secrets(secret_name: str, tokens: dict):
    """Save updated tokens to AWS Secrets Manager."""
    session = boto3.session.Session(profile_name='tradesales')

    client = session.client('secretsmanager')
    client.put_secret_value(
        SecretId=secret_name,
        SecretString=json.dumps(tokens)
    )