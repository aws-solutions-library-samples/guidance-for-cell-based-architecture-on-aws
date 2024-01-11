import requests


class Client:
    def __init__(self, router, username):
        self.router = router
        self.username = username
        self.dnsNameCell = None

    def request(self, uri, data=None):
        try:
            r = requests.post('http://' + self.router + uri, json=data, timeout=5)
        except requests.exceptions.ConnectTimeout:
            print('Request timed out. Did you allow inbound traffic from your external IP? (See README.md)')
            exit(1)
        self.check_request_status(r)
        return r

    def request_cell(self, uri, data=None):
        if not self.dnsNameCell:
            raise Exception('Not logged in.')
        r = requests.post('http://' + self.dnsNameCell + uri, json=data, timeout=5,
                          headers={'Authorization': 'Bearer ' + self.username})
        self.check_request_status(r)
        return r

    def check_request_status(self, r):
        r.raise_for_status()

    def register(self):
        r = self.request('/register', {'username': self.username})

    def login(self):
        r = self.request('/login', {
            'username': self.username,
        })
        j = r.json()
        self.dnsNameCell = j['dns_name_cell']

    def put(self, key, value):
        self.request_cell('/put', data={'key': key, 'value': value})

    def get(self, key):
        try:
          res = self.request_cell('/get', data={'key': key})
        except requests.exceptions.HTTPError as e:
          # 404 is a normal case here - return an error
          if e.response.status_code == 404:
            raise KeyError
          else:
            raise e

        return res.json()['value']

    def delete(self, key):
        self.request_cell('/delete', data={'key': key})

    def validate(self):
        return self.request_cell('/validate')
