import os
import fire
import yaml
import cellular
import requests
from datetime import datetime

cdkRequireApproval = 'broadening'
if 'cdkRequireApproval' in os.environ:
    cdkRequireApproval = os.environ['cdkRequireApproval']

# The following classes build the CLI actions. Each class and function in a
# class corresponds to an action.


class Cell(object):
    def list(self):
        cells = cellular.get_cells()
        print(yaml.dump(cells))

    def create(self, name, stage='prod'):
        """Calls the stepfunction to create a new cell"""
        arn = cellular.get_cf_output('Cellular-Router', 'createcellfunction')
        bucket = cellular.get_cf_output(
            'Cellular-Router', 'bucketRegionalDomainName')
        imageuri = cellular.get_cf_output('Cellular-Repos', 'repoCellUri')
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        cellular.start_sfn(arn, {
            'cellId': name,
            'templateUrl': 'https://{}/template_cell.yaml'.format(bucket),
            'stage': stage,
            'imageuri': imageuri,
        }, name='create-cell-{}-{}'.format(name, now))

    def delete(self, name):
        cellular.delete_cell(name)

    def update(self, *cells):
        """Calls the stepfunction to update multiple cells"""
        if len(cells) == 0:
            print('No cells to update')
            return
        arn = cellular.get_cf_output('Cellular-Router', 'updatecellsfunction')
        bucket = cellular.get_cf_output(
            'Cellular-Router', 'bucketRegionalDomainName')
        cellular.start_sfn(arn, {
            # 'cellIds': [{'cellId': 'cell1'}, {'cellId': 'cell2'}],
            'cellIds': list(cells),
            'templateUrl': 'https://{}/template_cell.yaml'.format(bucket),
        }, name='update-cells-{}'.format(datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))

    def build(self, deploy=False):
        """Builds the cell container and pushed it to the repo. Deploy restarts
        containers in all cells, thereby pulling the lasted image from ECR. """
        repo = cellular.get_cf_output('Cellular-Repos', 'repoCellUri')
        cellular.build_repo(repo, 'cell-container')
        if deploy:
            for cell in cellular.get_cells():
                cellular.recreate_containers(cell['stackName'])
                print('Restarting container for ' + cell['cell_id'])

    def runlocal(self):
        """Run the cell container in a locally (using docker run).
        Useful for rapid testing."""
        cellular.run_local('cell-container', {
            'tableName': cellular.get_cf_output('Cellular-Cell-sandbox', 'ddbTableName'),
        })

    def generate_template(self, noupload=False):
        """Recreate the Cfn template used to create cells and upload it to S3."""
        cellular.generate_template(not noupload)

    def deploysandbox(self):
        """Deploy the Sandbox cell directly via the cdk CLI (Use only for updates).
        Doesn't interact with DDB table and doesn't supply parameters. """
        imageuri = cellular.get_cf_output('Cellular-Repos', 'repoCellUri')
        cellular.run_cmd('cdk deploy Cellular-Cell-sandbox ' +
                         '--require-approval {} '.format(cdkRequireApproval) +
                         '--parameters cellid=sandbox ' +
                         '--parameters imageuri='+imageuri, 'cdk')


class Router(object):
    def build(self, deploy=False):
        """Builds the cell container and pushed it to the repo. 
        --deploy restarts the container, thereby pulling the
        last image from ECR. """
        repo = cellular.get_cf_output('Cellular-Repos', 'repoRoutingUri')
        cellular.build_repo(repo, 'routing-container')
        if deploy:
            cellular.recreate_containers('Cellular-Router')
            print('Restarting container')

    def runlocal(self):
        """Run the router container in a locally (using docker run). Useful for rapid testing."""
        cellular.run_local('routing-container', {
            'cellsTableName': cellular.get_cf_output('Cellular-Router', 'cellsTable'),
            'usersTableName': cellular.get_cf_output('Cellular-Router', 'usersTable'),
        })

    def deploy(self):
        imageuri = cellular.get_cf_output('Cellular-Repos', 'repoRoutingUri')
        cellular.run_cmd('cdk deploy Cellular-Router '
                         '--require-approval {} '.format(cdkRequireApproval) +
                         '--parameters imageuri={}'.format(imageuri), 'cdk')

    def getdnsname(self):
        print(cellular.get_cf_output('Cellular-Router', 'dnsName'))


class Setup:
    def deploy(self, createcells=False):
        """Deploy the solution to a new region or account."""
        cellular.run_cmd('npm ci', 'cdk')
        cellular.run_cmd('npm run build', 'cdk')
        cellular.run_cmd('cdk bootstrap', 'cdk')
        # cellular.run_cmd('cdk deploy Cellular-Repos', 'cdk')
        Repos().deploy()
        Router().build()
        Cell().build()
        Router().deploy()
        cellular.generate_template()
        Cell().create('sandbox', 'sandbox')
        if createcells:
            Cell().create('cell1')
            Cell().create('cell2')

    def destroy(self):
        for c in cellular.get_cells():
            cellular.destroy_stack(c['stackName'])
        cellular.destroy_stack('Cellular-Router')
        cellular.destroy_stack('Cellular-Repos')

    def tagnodelete(self):
        cellular.tagnodelete()

    def allowingress(self, ip='myip'):
        """Add an IP v4 address to the prefix list to allow inbound traffic.
        Per default gets your IP address from https://checkip.amazonaws.com"""
        if ip == 'myip':
            ip = requests.get('https://checkip.amazonaws.com').text.strip()
        cellular.allow_ingress(ip)


class Repos:
    def deploy(self):
        cellular.run_cmd('cdk deploy Cellular-Repos '
                         '--require-approval {} '.format(cdkRequireApproval), 'cdk')


class Canary:
    def startall(self):
        cellular.start_stop_canaries('start')

    def stopall(self):
        cellular.start_stop_canaries('stop')

    def check(self, *cells):
        arn = cellular.get_cf_output(
            'Cellular-Router', 'checkcanarystatemachine')
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        cellular.start_sfn(arn, {
            'cellIds': list(cells),
            'waitseconds': 0,
        }, name='check-canary-{}'.format(now))


class Function:
    def call(self):
        """Invoke a lambda function for testing."""
        cellular.invoke_lambda()


class User:
    def get(self, username):
        user = cellular.get_user(username)
        if user is None:
            'User "{}" does not exist'.format(username)
        print(user)

    def list(self):
        for u in cellular.get_users()['Items']:
            print(u['username'])

    def cell(self, username):
        user = cellular.get_user(username)
        if user is None:
            'User "{}" does not exist'.format(username)
        print(user['cell'])


class Main:
    def cell(self):
        return Cell

    def router(self):
        return Router

    def function(self):
        return Function

    def repos(self):
        return Repos

    def user(self):
        return User

    def setup(self):
        return Setup

    def canary(self):
        return Canary


if __name__ == '__main__':
    fire.Fire(Main)
