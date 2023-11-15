import json
import http.client
import urllib.parse
import os
import requests
import jwt
import boto3
import logging as logger
#from aws_synthetics.selenium import synthetics_webdriver as syn_webdriver
#from aws_synthetics.common import synthetics_logger as logger

dnsNameCell = os.environ.get('dnsName')
cellid = os.environ.get('cellid')

def generate_jwt():
    tokenDict = {
        'username': 'canary',
        'cell': cellid,
    }
    return jwt.encode(tokenDict, 'secret', algorithm="HS256")

def getJwt():
    aws_lambda = boto3.client('lambda')
    r = aws_lambda.invoke(
        FunctionName='cellCanaryToken',
        Payload=json.dumps({ 'cellid': cellid }),
    )
    print(json.load(r['Payload']))

def main():
    logger.info("Canary successfully executed")
    data = {'key': 'canary_test', 'value': 'value'}
    r = requests.post('http://' + dnsNameCell + '/put', json=data,
                      headers={'Authorization': 'Bearer ' + generate_jwt()})
    r.raise_for_status()


def handler(event, context):
    logger.info("Selenium Python API canary")
    main()