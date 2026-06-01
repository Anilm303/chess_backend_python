import urllib.request, json, sys

BASE = 'http://127.0.0.1:8000'

def post(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=data, headers={'Content-Type':'application/json'})
    return urllib.request.urlopen(req).read().decode('utf-8')

def get(path):
    req = urllib.request.Request(BASE + path)
    return urllib.request.urlopen(req).read().decode('utf-8')

if __name__ == '__main__':
    try:
        print('Registering smoketest user...')
        print(post('/api/auth/register', {
            'username':'smoketest',
            'email':'smoketest@example.com',
            'first_name':'Smoke',
            'last_name':'Test',
            'password':'pass123'
        }))
    except Exception as e:
        print('Register error:', e)

    try:
        print('\nFetching /api/messages/users...')
        print(get('/api/messages/users'))
    except Exception as e:
        print('Get users error:', e)

    try:
        print('\nCalling /api/auth/login to retrieve token...')
        login = json.loads(post('/api/auth/login', {'username':'smoketest','password':'pass123'}))
        print('Login response:', login)
        token = login.get('access_token')
        if token:
            req = urllib.request.Request(BASE + '/api/friends/contacts')
            req.add_header('Authorization', f'Bearer {token}')
            print('\nProtected friends/contacts response:')
            print(urllib.request.urlopen(req).read().decode('utf-8'))
    except Exception as e:
        print('Login/friends error:', e)
