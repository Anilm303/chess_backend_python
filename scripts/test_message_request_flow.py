import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.models.user import get_users, save_users, User
from app.models.message import Message, get_messages, save_messages
import json

# Setup users
users = get_users()
if 'alice' not in users:
    users['alice'] = {
        'username': 'alice',
        'email': 'alice@example.com',
        'first_name': 'Alice',
        'last_name': 'Example',
        'password_hash': 'x',
        'profile_image': None,
        'bio': '',
        'created_at': '2026-01-01T00:00:00',
        'last_seen': '2026-01-01T00:00:00'
    }
if 'bob' not in users:
    users['bob'] = {
        'username': 'bob',
        'email': 'bob@example.com',
        'first_name': 'Bob',
        'last_name': 'Example',
        'password_hash': 'x',
        'profile_image': None,
        'bio': '',
        'created_at': '2026-01-01T00:00:00',
        'last_seen': '2026-01-01T00:00:00'
    }

# Ensure not friends
users['alice']['friends'] = [f for f in users.get('alice', {}).get('friends', []) if f != 'bob']
users['bob']['friends'] = [f for f in users.get('bob', {}).get('friends', []) if f != 'alice']
save_users(users)
print('Users prepared. friends lists cleaned.')

# Alice sends message to Bob
success, result = Message.send_message('alice', 'bob', text='Hello Bob from Alice')
print('Message send success:', success)
if success:
    msg = result.to_dict()
    print('Message id:', msg['id'], 'initial status:', msg['status'])
    # Mimic server route logic: if not friends, mark as request
    users = get_users()
    sender_friends = set(users.get('alice', {}).get('friends', []))
    if 'bob' not in sender_friends:
        messages = get_messages()
        if msg['id'] in messages:
            messages[msg['id']]['status'] = 'request'
            save_messages(messages)
            print('Message status set to request')

# Inspect messages.json for pending requests
messages = get_messages()
pending = [m for m in messages.values() if m.get('receiver') == 'bob' and m.get('status') == 'request']
print('Pending requests for bob:', len(pending))
if pending:
    print('Sample pending:', pending[0]['id'], pending[0]['text'])

# Simulate bob accepting the request
# Add mutual friends
users = get_users()
cur_friends = set(users['bob'].get('friends', []))
req_friends = set(users['alice'].get('friends', []))
cur_friends.add('alice')
req_friends.add('bob')
users['bob']['friends'] = sorted(list(cur_friends))
users['alice']['friends'] = sorted(list(req_friends))
save_users(users)

# Deliver pending
messages = get_messages()
delivered_ids = []
for mid, m in list(messages.items()):
    if m.get('sender') == 'alice' and m.get('receiver') == 'bob' and m.get('status') == 'request':
        messages[mid]['status'] = 'delivered'
        delivered_ids.append(mid)
if delivered_ids:
    save_messages(messages)
print('Delivered ids after accept:', delivered_ids)

# Verify friends saved
users = get_users()
print('Alice friends:', users['alice'].get('friends'))
print('Bob friends:', users['bob'].get('friends'))

