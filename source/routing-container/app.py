import routing
import jwt
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth

app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')


@auth.verify_token
def verify_token(token):
    code = jwt.decode(token, 'secret', algorithms="HS256")
    print(code, flush=True)
    # Todo check that this is the right cell.
    return code['username']


@app.route('/')
def hello_world():
    return 'Hey, we have Flask in a Docker container!'


@app.route('/cells')
def cells():
    return jsonify(routing.get_cells())


@app.route('/register', methods=['POST'])
def register():
    r = request.get_json()
    print(r, flush=True)
    username = r['username']
    if routing.get_user(username) is not None:
        return "User already exists", 409
    apikey = routing.create_user(username)
    return jsonify({
        'status': 'Sucess',
        'username': username,
        'apikey': apikey,
    })


@app.route('/login', methods=['POST'])
def login():
    r = request.get_json()
    user = routing.get_user(r['username'])
    if user is None:
        return "Login failed", 401
    print('User: '+str(user))
    print('Request: '+str(r))
    if user['apikey'] != r['apikey']:
        return "Login failed", 401
    tokenDict = {
        'username': user['username'],
        'cell': user['cell']
    }
    token = jwt.encode(tokenDict, 'secret', algorithm="HS256")
    return jsonify({
        'dns_name_cell': routing.get_dns_name(user['cell']),
        'token': token,
    })


@app.route('/validate')
@auth.login_required
def validate():
    return jsonify({
        'username': auth.current_user()
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)