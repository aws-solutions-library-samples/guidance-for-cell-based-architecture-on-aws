from flask import Flask, request, jsonify
import os
import boto3
import jwt
from flask_httpauth import HTTPTokenAuth

app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')

table_name = os.environ.get('tableName')
cell_id = os.environ.get('cellId')
dynamodb = boto3.resource('dynamodb')
ddb_table = dynamodb.Table(table_name)


@auth.verify_token
def verify_token(token):
    code = jwt.decode(token, 'secret', algorithms="HS256")
    print(code, flush=True)
    # Todo check that this is the right cell.
    return code['username']


@app.route('/')
def hello_world():
    return 'Hey, we have Flask in a Docker container! (V2)'


@app.route('/put', methods=['POST'])
@auth.login_required
def put():
    print(request.get_data(), flush=True)
    r = request.get_json()
    print(r, flush=True)
    ddb_table.put_item(
        Item={
            'username': auth.current_user(),
            'key': r['key'],
            'value': r['value'],
        }
    )
    return "Success"


@app.route('/get', methods=['POST'])
@auth.login_required
def get():
    r = request.get_json()
    item = ddb_table.get_item(Key={
        'username': auth.current_user(),
        'key': r['key'],
    })
    if 'Item' not in item:
        return 'Item not found', 404
    return jsonify({
        'value': item['Item']['value']
    })


@app.route('/delete', methods=['POST'])
@auth.login_required
def delete():
    r = request.get_json()
    ddb_table.delete_item(Key={
        'username': auth.current_user(),
        'key': r['key'],
    })
    return "Success"


@app.route('/validate', methods=['POST', 'GET'])
@auth.login_required
def validate():
    return jsonify({
        'username': auth.current_user(),
        'cellid': cell_id,
    })


@app.route('/env')
def env():
    return table_name


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)