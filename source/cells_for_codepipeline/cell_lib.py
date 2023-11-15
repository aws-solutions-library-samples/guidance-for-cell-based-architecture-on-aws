import boto3
import os
import json

dynamodb = boto3.resource('dynamodb')
codepipeline = boto3.client('codepipeline')
stepfunction = boto3.client('stepfunctions')


class CellClient():
    def __init__(self):
        self.init_config()

    def init_config(self):
        self.cells_table = dynamodb.Table(os.environ['cellsTable'])
        self.step_function_arn = os.environ['updateCellsFunctionArn']
        self.template_bucket_name = os.environ['templateBucketName']

    def list_cells(self):
        cells = self.cells_table.scan()['Items']
        return [c['cell_id'] for c in cells if c['cell_id'] != 'Sandbox']

    def update_cells(self, job_id):
        stepfunction.start_execution(
            stateMachineArn=self.step_function_arn,
            name='update-{}'.format(job_id),
            input=json.dumps({
                'cellIds': self.list_cells(),
                'templateUrl': 'https://{}/template_cell.yaml'.format(self.template_bucket_name),
                'pipeline_id': job_id
            }),
        )
