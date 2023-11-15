import unittest
import boto3
from cells_for_codepipeline.cell_lib import CellClient

dynamodb = boto3.resource('dynamodb')
cloudformation = boto3.client('cloudformation')
stepfunction = boto3.client('stepfunctions')


def get_cf_output(stackname, key):
    response = cloudformation.describe_stacks(StackName=stackname)
    outputs = response["Stacks"][0]["Outputs"]
    for output in outputs:
        if output["OutputKey"] == key:
            return output["OutputValue"]
    raise Exception(
        '"{}" does not exist for stack "{}"'.format(key, stackname))


class TestClient(CellClient):
    def init_config(self):
        self.cells_table = dynamodb.Table(
            get_cf_output('Cellular-Router', 'cellsTable'))
        self.step_function_arn = get_cf_output(
            'Cellular-Router', 'updatecellsfunction')
        self.template_bucket_name = get_cf_output(
            'Cellular-Router', 'bucketName')


class Test_Handler(unittest.TestCase):
    def test_test(self):
        client = TestClient()
        cells = client.list_cells()
        self.assertTrue('Sandbox' not in cells)
        self.assertTrue(len(cells) >= 2)


if __name__ == '__main__':
    unittest.main()
