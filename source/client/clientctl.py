import os
import sys
from client_lib import Client
import fire

if not 'routerurl' in os.environ:
    print('Evironment variable "routerurl" not set.')
    print('Please use, .e.g.:')
    print('export routerurl=$(./cellularctl router getdnsname)')
    sys.exit(1)
routerurl = os.environ['routerurl']

def login(username):
    c = Client(routerurl, username)
    c.login()
    return c

class Exec:
    def validate(self, username):
        c = login(username)
        print(c.validate().json())

    def put(self, username, key, value):
        c = login(username)
        c.put(key, value)

    def get(self, username, key):
        c = login(username)
        print(c.get(key))

    def delete(self, username, key):
        c = login(username)
        c.delete(key)

    def getcell(self, username):
        c = login(username)
        print(c.validate().json()['cellid'])


class Main:
    def register(self, username):
        '''Registers a new users, optionally can specify the cell.
        Will create file "username.apikey"'''
        c = Client(routerurl, username)
        c.register()

    def exec(self):
        '''Execute a command against the server. Each command first logs in to the router.
        Each command uses "username.apikey" from the current working directory.'''
        return Exec


if __name__ == '__main__':
    fire.Fire(Main)
