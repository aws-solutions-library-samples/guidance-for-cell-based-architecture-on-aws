import unittest
from testlibs import get_cf_output, users_table
from client import Client


class TestClient(Client):
    def __init__(self, router, username):
        super().__init__(router, username)


class MyTestCase(unittest.TestCase):
    def setUp(self):
        server = 'http://' + get_cf_output('Cellular-Router', 'dnsName')
        self.client = Client(server, self._testMethodName)

    def test_put_and_get(self):
        self.client.register()
        self.client.login()
        self.client.put('key1', 'value2')
        res = self.client.get('key1')
        self.assertEqual(res, 'value2')

    def tearDown(self):
        # TODO delete items
        self.client.delete('key1')
        users_table.delete_item(Key={'username': self.client.username})


if __name__ == '__main__':
    unittest.main()
