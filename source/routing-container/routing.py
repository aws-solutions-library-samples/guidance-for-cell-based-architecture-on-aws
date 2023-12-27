import os
import boto3
import random
from boto3.dynamodb.conditions import Attr
import secrets

dynamodb = boto3.resource('dynamodb')
cloudformation = boto3.client('cloudformation')
secretsmanager = boto3.client('secretsmanager')
cells_table = dynamodb.Table(os.environ.get('cellsTableName'))
users_table = dynamodb.Table(os.environ.get('usersTableName'))


def get_cf_output(stackname, key):
    response = cloudformation.describe_stacks(StackName=stackname)
    outputs = response["Stacks"][0]["Outputs"]
    for output in outputs:
        if output["OutputKey"] == key:
            return output["OutputValue"]
    raise Exception(
        '"{}" does not exist for stack "{}"'.format(key, stackname))


def get_cells():
    res = cells_table.scan(
        FilterExpression=Attr('stackStatus').eq('active'),
        ProjectionExpression='cell_id'
    )
    return res['Items']


def assign_cell():
    cells = cells_table.scan(
        FilterExpression=Attr('stackStatus').eq(
            'active') & Attr('stage').eq('prod'),
        ProjectionExpression='cell_id'
    )
    return random.choice(cells['Items'])['cell_id']


def get_user(username):
    item = users_table.get_item(Key={'username': username})
    if 'Item' in item:
        return item['Item']
    return None


def get_dns_name(cell_id):
    cell = cells_table.get_item(Key={'cell_id': cell_id})
    stackname = cell['Item']['stackName']
    return get_cf_output(stackname, 'dnsName')


def create_user(username):
    apikey = secrets.token_urlsafe(10)
    users_table.put_item(
        Item={
            'username': username,
            'apikey': apikey,
            'cell': assign_cell()
        }
    )
    return apikey

def get_jwt_private_key():
    response = secretsmanager.get_secret_value(
        SecretId='cellsJwtPrivateKey'
    )
    return response['SecretString']

def get_jwt_public_key():
    response = secretsmanager.get_secret_value(
        SecretId='cellsJwtPublicKey'
    )
    return response['SecretString']