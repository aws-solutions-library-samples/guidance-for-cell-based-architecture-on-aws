import routing
from flask import Flask, request, jsonify
from flask_httpauth import HTTPTokenAuth

app = Flask(__name__)
auth = HTTPTokenAuth(scheme='Bearer')


@auth.verify_token
def verify_token(token):
    # Token is the user name. For a production environment, replace this with an authorisation mechanism such as JWT
    return token


@app.route('/')
def hello_world():
    return 'Hey, we have Flask in a Docker container!'


@app.route('/cells')
def cells():
    return jsonify(routing.get_cells())


@app.route('/register', methods=['POST'])
def register():
    r = request.get_json()
    username = r['username']
    if routing.get_user(username) is not None:
        return "User already exists", 409
    routing.create_user(username)
    return jsonify({
        'status': 'Sucess',
        'username': username
    })


@app.route('/login', methods=['POST'])
def login():
    r = request.get_json()
    user = routing.get_user(r['username'])
    if user is None:
        return "Login failed", 401
    return jsonify({
        'dns_name_cell': routing.get_dns_name(user['cell']),
    })


@app.route('/validate')
@auth.login_required
def validate():
    return jsonify({
        'username': auth.current_user()
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)