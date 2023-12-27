import unittest
import requests.exceptions
from testlibs import get_cf_output, dynamodb, get_private_key
from boto3.dynamodb.conditions import Key
import jwt
import client_lib

cell_table = dynamodb.Table(get_cf_output('Cellular-Cell-sandbox', 'ddbTableName'))


class TestClient(client_lib.Client):
    server = '127.0.0.1:8080'

    def __init__(self, username, password):
        super().__init__(None, username, password)
        self.dnsNameCell = TestClient.server
        tokenDict = {
            'username': username,
            'cell': 'Sandbox',
        }
        self.token = jwt.encode(tokenDict, get_private_key(), algorithm="RS256")


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(self._testMethodName, self._testMethodName + '123')

    def test_put(self):
        self.client.put('key', 'value')
        item = cell_table.get_item(Key={
            'username': self.client.username,
            'key': 'key',
        })
        self.assertTrue('Item' in item)
        self.assertEqual('value', item['Item']['value'])

    def test_put_and_get(self):
        self.client.put('key', 'value')
        res = self.client.get('key')
        self.assertEqual('value', res)

    def test_put_and_get2(self):
        self.client.put('key1', 'value1')
        self.client.put('key2', 'value2')
        self.assertEqual('value1', self.client.get('key1'))
        self.assertEqual('value2', self.client.get('key2'))

    def test_get_non_existing(self):
        with self.assertRaises(KeyError):
            self.client.get('key1')

    def test_delete(self):
        self.client.put('key4', 'value')
        self.client.delete('key4')
        with self.assertRaises(KeyError):
            self.client.get('key4')

    def tearDown(self):
        rows = cell_table.query(
            KeyConditionExpression=Key('username').eq(self.client.username),
        )
        with cell_table.batch_writer() as writer:
            for item in rows['Items']:
                writer.delete_item(Key={
                    'username': item['username'],
                    'key': item['key'],
                })


server_remote = get_cf_output('Cellular-Router', 'dnsName')
server_local = '127.0.0.1:8080'
TestClient.server = server_local

if __name__ == '__main__':
    unittest.main()
