import sys
import boto3
import json
import subprocess
import os
from pathlib import Path

if 'AWS_REGION' in os.environ:
    region = os.environ['AWS_REGION']
    # print('Using region ' + region)
    boto3.setup_default_session(region_name=region)

if 'CDK_DOCKER' in os.environ:
    docker = os.environ['CDK_DOCKER']
    # print('Using docker alternative ' + docker)
else:
    docker = 'docker'


cloudformation = boto3.client('cloudformation')
dynamodb = boto3.resource('dynamodb')
stepfunction = boto3.client('stepfunctions')
s3 = boto3.client('s3')
ecs = boto3.client('ecs')
ec2 = boto3.client('ec2')
aws_lambda = boto3.client('lambda')
synthetics = boto3.client('synthetics')


def run_cmd(cmd, dir=''):
    print()
    print('+ "{}" in directory "{}"'.format(cmd, dir))
    cwd = str(Path(__file__).parent.parent) + '/' + dir
    try:
        subprocess.run(cmd, shell=True, check=True, cwd=cwd)
    except subprocess.CalledProcessError:
        print('Command returned non-zero exit status.')
        sys.exit(1)


def get_cf_output(stackname, key):
    response = cloudformation.describe_stacks(StackName=stackname)
    outputs = response["Stacks"][0]["Outputs"]
    for output in outputs:
        if output["OutputKey"] == key:
            return output["OutputValue"]
    raise Exception(
        '"{}" does not exist for stack "{}"'.format(key, stackname))


def recreate_containers(stack_name):
    ecs.update_service(
        cluster=get_cf_output(stack_name, 'clusterName'),
        service=get_cf_output(stack_name, 'serviceName'),
        forceNewDeployment=True
    )


def get_cells():
    cells_table = dynamodb.Table(
        get_cf_output('Cellular-Router', 'cellsTable'))
    return cells_table.scan()['Items']


def build_repo(repo, dir):
    run_cmd(
        f'''aws ecr get-login-password |
        {docker} login --username AWS --password-stdin {repo}''')
    run_cmd(f'{docker} build -t {repo}:latest .', dir=dir)
    run_cmd(f'{docker} push {repo}:latest')


def get_aws_env():
    env = dict()
    for key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
                'AWS_SESSION_TOKEN']:
        if os.environ[key]:
            env[key] = os.environ[key]
    return env


def run_local(dir, env):
    run_cmd(f'{docker} build --tag {dir} .', dir)
    command = [docker, 'run', '-i', '-t', '-p', '80:80']
    env['AWS_DEFAULT_REGION'] = boto3.session.Session().region_name
    env.update(get_aws_env())
    for k, v in env.items():
        command.append('-e')
        command.append('{}={}'.format(k, v))
    command.append(dir)
    try:
        run_cmd(' '.join(command), dir)
    except KeyboardInterrupt:
        pass


def start_sfn(arn, input={}, name=None):
    res = stepfunction.start_execution(
        stateMachineArn=arn,
        name=name,
        input=json.dumps(input),
    )
    print(res)


def delete_cell(cell_id):
    cells_table = dynamodb.Table(
        get_cf_output('Cellular-Router', 'cellsTable'))
    item = cells_table.get_item(Key={'cell_id': cell_id})
    if 'Item' not in item:
        raise Exception('Cell "{}" does not exist'.format(cell_id))
    print('Deleting DDB table item for cell')
    cells_table.delete_item(Key={'cell_id': cell_id})
    stack_name = item['Item']['stackName']
    print('Requesting deletion of stack "{}"'.format(stack_name))
    cloudformation.delete_stack(StackName=stack_name)


def generate_template(upload=True):
    run_cmd('cdk synth Cellular-Cell-sandbox > templates/template_cell.yaml',
            'cdk')
    bucket = get_cf_output('Cellular-Router', 'bucketName')
    if upload:
        for p in Path('source/cdk/templates').glob('*.yaml'):
            print('Uploading ' + p.name)
            s3.upload_file(str(p), bucket, p.name)


def tagnodelete():
    res = aws_lambda.list_functions()
    for f in res['Functions']:
        name = f['FunctionName']
        if name.startswith('cwsyn-cell-canary-'):
            print('Tagging function "{}"'.format(name))
            aws_lambda.tag_resource(
                Resource=f['FunctionArn'],
                Tags={
                    "auto-delete": "no"
                }
            )


def invoke_lambda():
    r = aws_lambda.invoke(
        FunctionName='cellCanaryToken',
        Payload=json.dumps({"cellid": "test"}),
        # Payload='{ "cellid": "test" }',
    )
    print(json.load(r['Payload']))


def start_stop_canaries(action):
    res = synthetics.describe_canaries()
    for c in res['Canaries']:
        name = c['Name']
        if name.startswith('cell-canary-'):
            if action == 'start':
                print('Starting canary "{}"'.format(name))
                synthetics.start_canary(Name=name)
            elif action == 'stop':
                print('Stopping canary "{}"'.format(name))
                synthetics.stop_canary(Name=name)
            else:
                raise Exception('Unknown action "{}"'.format(action))


def destroy_stack(stack_name):
    cloudformation.delete_stack(StackName=stack_name)


def get_user(username):
    users_table = dynamodb.Table(
        get_cf_output('Cellular-Router', 'usersTable'))
    result = users_table.get_item(Key={'username': username})
    if 'Item' in result:
        return result['Item']
    return None


def get_users():
    users_table = dynamodb.Table(
        get_cf_output('Cellular-Router', 'usersTable'))
    users = users_table.scan()
    return users

def allow_ingress(ip):
    prefixListID = get_cf_output('Cellular-Repos', 'inboundPrefixListId')
    lists = ec2.describe_managed_prefix_lists(
        Filters=[{
            'Name': 'prefix-list-id',
            'Values': [
                prefixListID,
            ]
        },
    ],)
    version = lists['PrefixLists'][0]['Version']
    print(version+1)
    ec2.modify_managed_prefix_list(
        PrefixListId=prefixListID,
        AddEntries=[
            {
                'Cidr': ip+'/32',
            },
        ],
        CurrentVersion = version
    )