from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.message import Message
from app.models.group import GroupChat
from app.models.user import User
from app.security import (
    rate_limit,
    require_json_body,
    validate_bio,
    validate_message_text,
    validate_media_type,
    validate_name,
    validate_username,
)

messaging_bp = Blueprint('messaging', __name__)

@messaging_bp.route('/users', methods=['GET'])
@jwt_required()
def get_all_users():
    """Get list of all registered users (excluding current user) with profile info"""
    current_user = get_jwt_identity()
    users = User.get_all_users()
    
    # Remove current user and return user info with profile
    user_list = []
    for username, user_data in users.items():
        if username != current_user:
            user_list.append({
                'username': username,
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
                'email': user_data.get('email', ''),
                'profile_image': user_data.get('profile_image'),  # Base64 or None
                'bio': user_data.get('bio', ''),
                'is_online': User.is_online(username),
                'last_seen': user_data.get('last_seen', ''),
            })
    
    return jsonify({
        'success': True,
        'users': user_list
    }), 200

@messaging_bp.route('/user/<username>', methods=['GET'])
@jwt_required()
def get_user_profile(username):
    """Get detailed user profile"""
    user = User.get_by_username(username)
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    return jsonify({
        'success': True,
        'user': user.to_dict()
    }), 200

@messaging_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_current_user_profile():
    """Get current user profile"""
    username = get_jwt_identity()
    user = User.get_by_username(username)
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    return jsonify({
        'success': True,
        'user': user.to_dict()
    }), 200

@messaging_bp.route('/profile/update', methods=['PUT'])
@jwt_required()
@rate_limit(limit=15, window_seconds=60, scope='profile_update')
def update_profile():
    """Update user profile (bio, profile image, name)"""
    username = get_jwt_identity()
    data, error_response = require_json_body()
    if error_response:
        return error_response
    
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    bio = data.get('bio')
    profile_image = data.get('profile_image')  # Base64 string

    if first_name is not None:
        valid_first_name, first_name_or_message = validate_name(first_name, 'First name')
        if not valid_first_name:
            return jsonify({'success': False, 'message': first_name_or_message}), 400
        first_name = first_name_or_message

    if last_name is not None:
        valid_last_name, last_name_or_message = validate_name(last_name, 'Last name')
        if not valid_last_name:
            return jsonify({'success': False, 'message': last_name_or_message}), 400
        last_name = last_name_or_message

    if bio is not None:
        _, bio = validate_bio(bio)
    
    success, message = User.update_profile(
        username,
        first_name=first_name,
        last_name=last_name,
        bio=bio,
        profile_image=profile_image
    )
    
    if not success:
        return jsonify({'success': False, 'message': message}), 400
    
    return jsonify({
        'success': True,
        'message': message,
        'user': User.get_by_username(username).to_dict()
    }), 200

@messaging_bp.route('/send', methods=['POST'])
@jwt_required()
@rate_limit(limit=20, window_seconds=60, scope='direct_message_send')
def send_message():
    """Send a message to another user (text, image, or video)"""
    sender = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    receiver = ''
    message_type = 'text'
    text = ''
    media_base64 = None
    media_bytes = None
    reply_to_id = None
    timestamp = None

    if 'media' in request.files:
        receiver = request.form.get('receiver', '').strip()
        message_type = request.form.get('message_type', 'video')
        text = request.form.get('text', '').strip()
        reply_to_id = request.form.get('reply_to_id')
        timestamp = request.form.get('timestamp')
        uploaded_file = request.files.get('media')
        if uploaded_file:
            media_bytes = uploaded_file.read()
    else:
        receiver = data.get('receiver', '').strip()
        message_type = data.get('message_type', 'text')
        text = data.get('text', '').strip()
        media_base64 = data.get('media_base64')
        reply_to_id = data.get('reply_to_id')  # optional quoted message id
        timestamp = data.get('timestamp')
    
    if not receiver:
        return jsonify({'success': False, 'message': 'Receiver is required'}), 400

    valid_receiver, receiver_or_message = validate_username(receiver)
    if not valid_receiver:
        return jsonify({'success': False, 'message': receiver_or_message}), 400
    
    message_type = str(message_type or 'text').strip().lower()
    if message_type not in ['text', 'image', 'video', 'call']:
        return jsonify({'success': False, 'message': 'Invalid message type'}), 400
    
    if message_type == 'text' and not text:
        return jsonify({'success': False, 'message': 'Message text is required'}), 400

    if message_type == 'text':
        valid_text, text_or_message = validate_message_text(text)
        if not valid_text:
            return jsonify({'success': False, 'message': text_or_message}), 400
        text = text_or_message
    
    # For media messages, require either uploaded file bytes or base64 payload
    if message_type in ['image', 'video'] and not (media_bytes or media_base64):
        return jsonify({'success': False, 'message': f'{message_type} data is required'}), 400

    if message_type in ['image', 'video'] and media_base64 is not None:
        if not isinstance(media_base64, str) or not media_base64.strip():
            return jsonify({'success': False, 'message': f'{message_type} data is required'}), 400
    
    if media_bytes is not None:
        success, result = Message.send_message_bytes(
            sender,
            receiver_or_message,
            text=text,
            message_type=message_type,
            media_bytes=media_bytes,
            reply_to_id=reply_to_id,
            timestamp=timestamp,
        )
    else:
        success, result = Message.send_message(
            sender,
            receiver_or_message,
            text=text,
            message_type=message_type,
            media_base64=media_base64,
            reply_to_id=reply_to_id,
            timestamp=timestamp,
        )
    
    if not success:
        return jsonify({'success': False, 'message': result}), 400

    try:
        from app.websocket import _emit_to_username
        message_payload = result.to_dict()
        delivered = _emit_to_username(receiver, 'message_received', message_payload)
        if delivered:
            Message.mark_as_delivered(result.id)
            _emit_to_username(sender, 'message_delivered', {
                'message_id': result.id,
                'message_ids': [result.id],
                'conversation_with': receiver_or_message,
                'sender_username': sender,
                'receiver_username': receiver_or_message,
                'status': 'delivered',
            })
    except Exception as e:
        print(f'Error emitting message_received socket event: {e}')
    
    return jsonify({
        'success': True,
        'message': 'Message sent successfully',
        'data': result.to_dict()
    }), 201

@messaging_bp.route('/conversation/<username>', methods=['GET'])
@jwt_required()
def get_conversation(username):
    """Get conversation between current user and specified user"""
    current_user = get_jwt_identity()
    
    # Verify both users exist
    if not User.get_by_username(current_user):
        return jsonify({'success': False, 'message': 'Current user not found'}), 404
    
    valid_username, username_or_message = validate_username(username)
    if not valid_username:
        return jsonify({'success': False, 'message': username_or_message}), 400

    if not User.get_by_username(username_or_message):
        return jsonify({'success': False, 'message': f'User {username_or_message} not found'}), 404
    
    # Get conversation
    messages = Message.get_conversation(current_user, username_or_message)
    
    return jsonify({
        'success': True,
        'messages': messages
    }), 200

@messaging_bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """Get list of users current user has messaged with last message"""
    current_user = get_jwt_identity()
    
    # Get all unique users this user has messaged
    user_list = Message.get_all_conversations(current_user)
    
    # Get user details for each with last message
    users = User.get_all_users()
    conversations = []
    
    for username in user_list:
        if username in users:
            user_data = users[username]
            last_msg = Message.get_last_message(current_user, username)
            
            conversations.append({
                'username': username,
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
                'email': user_data.get('email', ''),
                'profile_image': user_data.get('profile_image'),
                'bio': user_data.get('bio', ''),
                'is_online': User.is_online(username),
                'last_message': last_msg['text'] if last_msg else '',
                'last_message_time': last_msg['timestamp'] if last_msg else '',
                'last_seen': user_data.get('last_seen', ''),
                'unread_count': Message.unread_count_between(current_user, username),
            })
    
    return jsonify({
        'success': True,
        'conversations': conversations
    }), 200

@messaging_bp.route('/mark-read/<message_id>', methods=['PUT'])
@jwt_required()
@rate_limit(limit=60, window_seconds=60, scope='mark_message_read')
def mark_as_read(message_id):
    """Mark a message as read"""
    message = Message.mark_as_read(message_id)

    if not message:
        return jsonify({'success': False, 'message': 'Message not found'}), 404

    try:
        from app.websocket import _emit_to_username
        _emit_to_username(message['sender'], 'message_read', {
            'message_ids': [message_id],
            'reader_username': get_jwt_identity(),
            'sender_username': message['sender'],
            'conversation_with': message['receiver'],
            'read_at': message.get('timestamp'),
        })
    except Exception as e:
        print(f'Error emitting message_read socket event: {e}')
    
    return jsonify({'success': True, 'message': 'Message marked as read'}), 200


@messaging_bp.route('/conversation/<username>/mark-read', methods=['PUT'])
@jwt_required()
@rate_limit(limit=60, window_seconds=60, scope='mark_conversation_read')
def mark_conversation_read(username):
    current_user = get_jwt_identity()
    valid_username, username_or_message = validate_username(username)
    if not valid_username:
        return jsonify({'success': False, 'message': username_or_message}), 400
    changed_ids = Message.mark_conversation_as_read(current_user, username_or_message)

    if changed_ids:
        for message_id in changed_ids:
            Message.mark_as_seen(message_id)
        try:
            from app.websocket import _emit_to_username
            _emit_to_username(username_or_message, 'message_seen', {
                'message_ids': changed_ids,
                'reader_username': current_user,
                'sender_username': username_or_message,
                'conversation_with': current_user,
                'status': 'seen',
            })
        except Exception as e:
            print(f'Error emitting conversation message_seen socket event: {e}')
    return jsonify({'success': True, 'message': 'Conversation marked as read'}), 200

@messaging_bp.route('/online-status', methods=['GET'])
@jwt_required()
def get_online_users():
    """Get list of currently online users"""
    online_users = User.get_online_users()
    return jsonify({'success': True, 'online_users': online_users}), 200


@messaging_bp.route('/groups', methods=['GET'])
@jwt_required()
def get_groups():
    current_user = get_jwt_identity()
    groups = GroupChat.list_groups_for_user(current_user)
    users = User.get_all_users()

    enriched = []
    for group in groups:
        members = []
        for username in group.get('members', []):
            member_data = users.get(username, {})
            members.append({
                'username': username,
                'display_name': f"{member_data.get('first_name', '')} {member_data.get('last_name', '')}".strip() or username,
                'profile_image': member_data.get('profile_image'),
                'is_online': User.is_online(username),
            })

        item = {
            **group,
            'members_data': members,
            'unread_count': GroupChat.unread_count_for_group(group['id'], current_user),
        }
        enriched.append(item)

    enriched.sort(key=lambda g: g.get('last_message_time', ''), reverse=True)
    return jsonify({'success': True, 'groups': enriched}), 200


@messaging_bp.route('/groups', methods=['POST'])
@jwt_required()
@rate_limit(limit=10, window_seconds=60, scope='create_group')
def create_group():
    current_user = get_jwt_identity()
    data, error_response = require_json_body()
    if error_response:
        return error_response
    name = (data.get('name') or '').strip()
    members = data.get('members') or []
    avatar = data.get('avatar')

    if name:
        valid_name, name_or_message = validate_name(name, 'Group name')
        if not valid_name:
            return jsonify({'success': False, 'message': name_or_message}), 400
        name = name_or_message

    if isinstance(members, str):
        members = [item.strip() for item in members.split(',') if item.strip()]
    elif not isinstance(members, list):
        return jsonify({'success': False, 'message': 'Members must be a list of usernames'}), 400

    normalized_members = []
    for item in members:
        if isinstance(item, dict):
            value = str(item.get('username') or item.get('id') or '').strip()
        else:
            value = str(item).strip()
        valid_member, member_or_message = validate_username(value)
        if not valid_member:
            return jsonify({'success': False, 'message': member_or_message}), 400
        value = member_or_message
        if value and value not in normalized_members and value != current_user:
            normalized_members.append(value)

    if len(normalized_members) < 1:
        return jsonify({
            'success': False,
            'message': 'Select at least 1 other member to create a group'
        }), 400

    users = User.get_all_users()
    missing = [username for username in normalized_members if username not in users]
    if missing:
        return jsonify({
            'success': False,
            'message': f'Invalid members: {", ".join(missing)}'
        }), 400

    success, result = GroupChat.create_group(
        name=name,
        creator=current_user,
        member_usernames=normalized_members,
        avatar=avatar,
    )
    if not success:
        return jsonify({'success': False, 'message': result}), 400
    return jsonify({'success': True, 'group': result}), 201


@messaging_bp.route('/groups/<group_id>/messages', methods=['GET'])
@jwt_required()
def get_group_messages(group_id):
    current_user = get_jwt_identity()
    success, result = GroupChat.get_group_messages(group_id, current_user)
    if not success:
        return jsonify({'success': False, 'message': result}), 403
    GroupChat.mark_group_seen(group_id, current_user)
    return jsonify({'success': True, 'messages': result}), 200


@messaging_bp.route('/groups/<group_id>/messages', methods=['POST'])
@jwt_required()
@rate_limit(limit=30, window_seconds=60, scope='send_group_message')
def send_group_message(group_id):
    current_user = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    text = ''
    message_type = 'text'
    media_base64 = None
    media_bytes = None
    timestamp = None

    if 'media' in request.files:
        text = request.form.get('text', '').strip()
        message_type = request.form.get('message_type', 'video')
        timestamp = request.form.get('timestamp')
        uploaded_file = request.files.get('media')
        if uploaded_file:
            media_bytes = uploaded_file.read()
    else:
        text = data.get('text', '')
        message_type = data.get('message_type', 'text')
        media_base64 = data.get('media_base64')
        timestamp = data.get('timestamp')

    message_type = str(message_type or 'text').strip().lower()
    if message_type not in ['text', 'image', 'video', 'call']:
        return jsonify({'success': False, 'message': 'Invalid message type'}), 400

    if message_type == 'text':
        valid_text, text_or_message = validate_message_text(text)
        if not valid_text:
            return jsonify({'success': False, 'message': text_or_message}), 400
        text = text_or_message

    if message_type in ['image', 'video'] and (not media_base64 or not isinstance(media_base64, str)):
        return jsonify({'success': False, 'message': f'{message_type} data is required'}), 400

    success, result = GroupChat.send_group_message(
        group_id,
        current_user,
        text,
        message_type,
        media_base64=media_base64,
        media_bytes=media_bytes,
        timestamp=timestamp,
    )
    if not success:
        return jsonify({'success': False, 'message': result}), 400

    group = GroupChat.get_group(group_id)
    if group:
        try:
            from app import websocket as ws
            for member in group.get('members', []):
                if member == current_user:
                    continue
                ws._emit_to_username(member, 'group_message_received', result)
        except Exception as e:
            print(f'Error emitting group message socket event: {e}')
    return jsonify({'success': True, 'data': result}), 201


@messaging_bp.route('/groups/<group_id>/members', methods=['POST'])
@jwt_required()
@rate_limit(limit=20, window_seconds=60, scope='group_add_member')
def add_group_member(group_id):
    current_user = get_jwt_identity()
    data, error_response = require_json_body()
    if error_response:
        return error_response
    member_username = data.get('member_username', '')
    valid_member, member_or_message = validate_username(member_username)
    if not valid_member:
        return jsonify({'success': False, 'message': member_or_message}), 400
    success, result = GroupChat.add_member(group_id, current_user, member_or_message)
    if not success:
        return jsonify({'success': False, 'message': result}), 400
    return jsonify({'success': True, 'group': result}), 200


@messaging_bp.route('/groups/<group_id>/members/<member_username>', methods=['DELETE'])
@jwt_required()
@rate_limit(limit=20, window_seconds=60, scope='group_remove_member')
def remove_group_member(group_id, member_username):
    current_user = get_jwt_identity()
    valid_member, member_or_message = validate_username(member_username)
    if not valid_member:
        return jsonify({'success': False, 'message': member_or_message}), 400
    success, result = GroupChat.remove_member(group_id, current_user, member_or_message)
    if not success:
        return jsonify({'success': False, 'message': result}), 400
    return jsonify({'success': True, 'group': result}), 200


@messaging_bp.route('/groups/<group_id>/admins', methods=['PUT'])
@jwt_required()
@rate_limit(limit=20, window_seconds=60, scope='group_set_admin')
def update_group_admin(group_id):
    current_user = get_jwt_identity()
    data, error_response = require_json_body()
    if error_response:
        return error_response
    member_username = data.get('member_username', '')
    is_admin = bool(data.get('is_admin', False))
    valid_member, member_or_message = validate_username(member_username)
    if not valid_member:
        return jsonify({'success': False, 'message': member_or_message}), 400
    success, result = GroupChat.set_admin(group_id, current_user, member_or_message, is_admin)
    if not success:
        return jsonify({'success': False, 'message': result}), 400
    return jsonify({'success': True, 'group': result}), 200


@messaging_bp.route('/react/<message_id>', methods=['POST'])
@jwt_required()
@rate_limit(limit=60, window_seconds=60, scope='react_to_message')
def react_to_message(message_id):
    """Add/toggle an emoji reaction on a message"""
    reactor = get_jwt_identity()
    data, error_response = require_json_body()
    if error_response:
        return error_response
    emoji = data.get('emoji', '')

    if not emoji:
        return jsonify({'success': False, 'message': 'emoji is required'}), 400

    success, reactions = Message.react_to_message(message_id, reactor, emoji)
    if not success:
        return jsonify({'success': False, 'message': 'Message not found'}), 404

    # Fetch message to find receiver
    from app.models.message import get_messages
    messages = get_messages()
    msg = messages.get(message_id)
    if msg:
        receiver = msg.get('receiver') if msg.get('sender') == reactor else msg.get('sender')
        from app.websocket import active_connections
        from app import socketio
        receiver_socket_id = active_connections.get(receiver)
        if receiver_socket_id:
            socketio.emit('message_reaction', {
                'message_id': message_id,
                'reactions': reactions,
                'conversation_with': reactor
            }, to=receiver_socket_id)

    return jsonify({'success': True, 'reactions': reactions}), 200

@messaging_bp.route('/message/<message_id>', methods=['DELETE'])
@jwt_required()
def delete_message(message_id):
    """Unsend/Delete a message for everyone"""
    current_user = get_jwt_identity()
    
    success, result = Message.delete_message(message_id, current_user)
    if not success:
        return jsonify({'success': False, 'message': result}), 400

    # Also notify the receiver via WebSockets
    from app.websocket import active_connections
    from app import socketio
    receiver = result.get('receiver')
    receiver_socket_id = active_connections.get(receiver)
    if receiver_socket_id:
        socketio.emit('message_deleted', {'message_id': message_id, 'conversation_with': current_user}, to=receiver_socket_id)

    return jsonify({'success': True, 'message_id': message_id}), 200
