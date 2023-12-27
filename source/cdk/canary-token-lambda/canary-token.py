import jwt
import logging
import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

def get_jwt_public_key():
    secretsmanager = boto3.client('secretsmanager')
    response = secretsmanager.get_secret_value(
        SecretId='cellsJwtPublicKey'
    )
    return response['SecretString']

def generate_jwt(cellid):
    tokenDict = {
        'username': 'canary',
        'cell': cellid,
    }
    return jwt.encode(tokenDict, get_jwt_public_key(), algorithm="RS256")

def handler(event, context):
    log.info("Starting")
    log.info(event)
    return {
        'token': generate_jwt(event['cellid'])
    }
