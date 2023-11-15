import jwt
import logging

log = logging.getLogger()
log.setLevel(logging.INFO)

def generate_jwt(cellid):
    tokenDict = {
        'username': 'canary',
        'cell': cellid,
    }
    return jwt.encode(tokenDict, 'secret', algorithm="HS256")

def handler(event, context):
    log.info("Starting")
    log.info(event)
    return {
        'token': generate_jwt(event['cellid'])
    }
