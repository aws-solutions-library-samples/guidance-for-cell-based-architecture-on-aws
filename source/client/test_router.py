import requests
import unittest
import jwt
from testlibs import users_table, get_cf_output, get_public_key
import client_lib

tc = unittest.TestCase()


class TestClient(client_lib.Client):
    def __init__(self, router, username):
        super().__init__(router, username)
        self.expected_status = None

    def check_request_status(self, r):
        expected = self.expected_status
        self.expected_status = None
        if expected != None:
            tc.assertEqual(r.status_code, expected)
        else:
            super().check_request_status(r)


class Test_Router(unittest.TestCase):
    server = '127.0.0.1:8080'

    def userid(self):
        return self._testMethodName

    def apikey(self):
        return self._testMethodName + '--APIKEY'

    def setUp(self):
        self.users = list()
        self.users.append(self.userid())
        self.client = TestClient(self.server, self.userid())
        self.client.apikey = self.apikey()

    def addUser(self, username=None, apikey=None):
        if username == None:
            username = self.userid()
        if apikey == None:
            apikey = self.apikey()
        self.users.append(username)
        users_table.put_item(
            Item={
                'username': username,
                'apikey': apikey,
                'cell': 'sandbox',
            }
        )

    def test_register2(self):
        c = TestClient(self.server, self.userid())
        c.register()
        item = users_table.get_item(Key={'username': self.userid()})
        self.assertTrue('Item' in item)
        self.assertTrue('cell' in item['Item'])
        self.assertTrue('apikey' in item['Item'])
        self.assertTrue(c.apikey != None)

    def test_register_and_login(self):
        self.addUser('test2@test.com')
        r = requests.post('http://' + self.server + '/login',
                          json={'username': 'test2@test.com', 'apikey': self.apikey()})
        self.assertEqual(r.status_code, 200)
        token = jwt.decode(r.json()['token'], get_public_key(), algorithms="RS256")
        self.assertEqual(token['username'], 'test2@test.com')
        self.assertEqual(token['cell'], 'sandbox')

    def test_register_and_login2(self):
        self.addUser(self.userid())
        self.client.login()
        token = jwt.decode(self.client.token, get_public_key(), algorithms="RS256")
        self.assertEqual(token['username'], self.userid())
        self.assertEqual(token['cell'], 'sandbox')
        self.assertIsNotNone(self.client.dnsNameCell)

    def test_login_fail(self):
        self.addUser('test3')
        r = requests.post(self.server + '/login', json={'username': 'test3', 'apikey': '1'})
        self.assertEqual(r.status_code, 401)

    def test_register_twice(self):
        self.addUser('test')
        r = requests.post(self.server + '/register', json={'username': 'test', 'apikey': '123'})
        self.assertEqual(r.status_code, 409)

    def test_register_twice2(self):
        self.client.register()
        self.client.expected_status = 409
        try:
            self.client.register()
        except requests.exceptions.JSONDecodeError:
            pass

    def test_validate(self):
        self.addUser()
        r = requests.post(self.server + '/login',
                          json={'username': self.userid(), 'apikey': self.apikey()})
        self.assertEqual(r.status_code, 200)
        token = r.json()['token']
        r = requests.get(self.server + '/validate', headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['username'], self.userid())

    # @unittest.skip("Not implemented yet")
    def test_url_in_login(self):
        self.addUser('test5')
        r = requests.post(self.server + '/login',
                          json={'username': 'test5', 'apikey': self.apikey()})
        dns_name_cell = get_cf_output('Cellular-Cell-sandbox', 'dnsName')
        self.assertEqual(r.json()['dns_name_cell'], dns_name_cell)

    def tearDown(self):
        for user in self.users:
            users_table.delete_item(Key={'username': user})


server_remote = get_cf_output('Cellular-Router', 'dnsName')
server_local = '127.0.0.1:8080'
Test_Router.server = server_local

if __name__ == '__main__':
    unittest.main()
