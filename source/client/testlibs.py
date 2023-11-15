import boto3

cf_client = boto3.client('cloudformation')

def get_cf_output(stackname, key):
    response = cf_client.describe_stacks(StackName=stackname)
    outputs = response["Stacks"][0]["Outputs"]
    for output in outputs:
        if output["OutputKey"] == key:
            return output["OutputValue"]
    raise Exception('"{}" does not exist for stack "{}"'.format(key, stackname))


dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table(get_cf_output('Cellular-Router', 'usersTable'))