import json
import base64
import os
import uuid
from datetime import datetime

GROUPS_FILE = 'groups.json'
GROUP_MESSAGES_FILE = 'group_messages.json'
CALL_HISTORY_FILE = 'group_call_history.json'
UPLOADS_FOLDER = os.path.join('uploads', 'messages')

os.makedirs(UPLOADS_FOLDER, exist_ok=True)


def _load_json(path, default):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    return default


def _save_json(path, data):
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2)


def _normalize_timestamp(value=None):
    if not value:
        return datetime.utcnow().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return datetime.utcnow().isoformat()
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).isoformat()
    except Exception:
        return text


class GroupChat:
    @staticmethod
    def create_group(name, creator, member_usernames, avatar=None):
        unique_members = sorted(set([creator, *member_usernames]))
        if len(unique_members) < 2:
            return False, 'A group must include at least 2 members'

        group_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        groups = _load_json(GROUPS_FILE, {})
        groups[group_id] = {
            'id': group_id,
            'name': name.strip() or 'Untitled Group',
            'avatar': avatar,
            'created_by': creator,
            'admins': [creator],
            'members': unique_members,
            'created_at': now,
            'updated_at': now,
            'last_message': '',
            'last_message_time': now,
        }
        _save_json(GROUPS_FILE, groups)
        return True, groups[group_id]

    @staticmethod
    def list_groups_for_user(username):
        groups = _load_json(GROUPS_FILE, {})
        return [group for group in groups.values() if username in group.get('members', [])]

    @staticmethod
    def get_group(group_id):
        groups = _load_json(GROUPS_FILE, {})
        return groups.get(group_id)

    @staticmethod
    def add_member(group_id, requester, member_username):
        groups = _load_json(GROUPS_FILE, {})
        group = groups.get(group_id)
        if not group:
            return False, 'Group not found'
        if requester not in group.get('admins', []):
            return False, 'Only group admins can add members'
        if member_username in group['members']:
            return False, 'User already in group'
        group['members'].append(member_username)
        group['updated_at'] = datetime.utcnow().isoformat()
        _save_json(GROUPS_FILE, groups)
        return True, group

    @staticmethod
    def remove_member(group_id, requester, member_username):
        groups = _load_json(GROUPS_FILE, {})
        group = groups.get(group_id)
        if not group:
            return False, 'Group not found'
        if requester not in group.get('admins', []):
            return False, 'Only group admins can remove members'
        if member_username not in group['members']:
            return False, 'User is not a member'
        if member_username == group.get('created_by'):
            return False, 'Group creator cannot be removed'
        group['members'] = [m for m in group['members'] if m != member_username]
        group['admins'] = [a for a in group.get('admins', []) if a != member_username]
        group['updated_at'] = datetime.utcnow().isoformat()
        _save_json(GROUPS_FILE, groups)
        return True, group

    @staticmethod
    def set_admin(group_id, requester, member_username, is_admin):
        groups = _load_json(GROUPS_FILE, {})
        group = groups.get(group_id)
        if not group:
            return False, 'Group not found'
        if requester not in group.get('admins', []):
            return False, 'Only group admins can update admin role'
        if member_username not in group.get('members', []):
            return False, 'User is not a member'

        admins = set(group.get('admins', []))
        if is_admin:
            admins.add(member_username)
        else:
            if member_username == group.get('created_by'):
                return False, 'Group creator must remain admin'
            admins.discard(member_username)
        group['admins'] = sorted(admins)
        group['updated_at'] = datetime.utcnow().isoformat()
        _save_json(GROUPS_FILE, groups)
        return True, group

    @staticmethod
    def send_group_message(group_id, sender, text, message_type='text', media_base64=None, media_bytes=None, timestamp=None):
        groups = _load_json(GROUPS_FILE, {})
        group = groups.get(group_id)
        if not group:
            return False, 'Group not found'
        if sender not in group.get('members', []):
            return False, 'Not a group member'
        if message_type == 'text' and not text.strip():
            return False, 'Message cannot be empty'

        media_url = None
        thumbnail_url = None
        if message_type in ['image', 'video']:
            extension = 'mp4' if message_type == 'video' else 'jpg'
            filename = f"{uuid.uuid4()}.{extension}"
            filepath = os.path.join(UPLOADS_FOLDER, filename)

            try:
                if media_bytes is not None:
                    with open(filepath, 'wb') as file_handle:
                        file_handle.write(media_bytes)
                elif media_base64:
                    with open(filepath, 'wb') as file_handle:
                        file_handle.write(base64.b64decode(media_base64))
                else:
                    return False, f'{message_type} data required'

                media_url = f'/uploads/messages/{filename}'

                if message_type == 'video':
                    try:
                        from app.utils import generate_video_thumbnail

                        thumb_filename = f"{filename.split('.')[0]}_thumb.jpg"
                        thumb_filepath = os.path.join(UPLOADS_FOLDER, thumb_filename)
                        if generate_video_thumbnail(filepath, thumb_filepath):
                            thumbnail_url = f'/uploads/messages/{thumb_filename}'
                    except Exception:
                        thumbnail_url = None
            except Exception as exc:
                print(f'Error saving group media: {exc}')
                return False, 'Failed to save media file'

        messages = _load_json(GROUP_MESSAGES_FILE, {})
        message_id = str(uuid.uuid4())
        now = _normalize_timestamp(timestamp)
        message = {
            'id': message_id,
            'group_id': group_id,
            'sender': sender,
            'text': text.strip(),
            'message_type': message_type,
            'media_url': media_url,
            'thumbnail_url': thumbnail_url,
            'timestamp': now,
            'seen_by': [sender],
        }
        messages[message_id] = message
        _save_json(GROUP_MESSAGES_FILE, messages)

        group['last_message'] = message['text'] if message['text'] else message_type.capitalize()
        group['last_message_time'] = now
        group['updated_at'] = now
        groups[group_id] = group
        _save_json(GROUPS_FILE, groups)

        return True, message

    @staticmethod
    def get_group_messages(group_id, requester):
        group = GroupChat.get_group(group_id)
        if not group:
            return False, 'Group not found'
        if requester not in group.get('members', []):
            return False, 'Not a group member'

        messages = _load_json(GROUP_MESSAGES_FILE, {})
        result = [m for m in messages.values() if m.get('group_id') == group_id]
        result.sort(key=lambda item: item.get('timestamp', ''))
        return True, result

    @staticmethod
    def mark_group_seen(group_id, username):
        messages = _load_json(GROUP_MESSAGES_FILE, {})
        changed = False
        for message in messages.values():
            if message.get('group_id') != group_id:
                continue
            seen_by = set(message.get('seen_by', []))
            if username not in seen_by:
                seen_by.add(username)
                message['seen_by'] = sorted(seen_by)
                changed = True
        if changed:
            _save_json(GROUP_MESSAGES_FILE, messages)
        return changed

    @staticmethod
    def unread_count_for_group(group_id, username):
        messages = _load_json(GROUP_MESSAGES_FILE, {})
        count = 0
        for message in messages.values():
            if message.get('group_id') != group_id:
                continue
            if message.get('sender') == username:
                continue
            if username not in message.get('seen_by', []):
                count += 1
        return count

    @staticmethod
    def log_call(group_id, started_by, call_type, participants, status='completed'):
        history = _load_json(CALL_HISTORY_FILE, {})
        call_id = str(uuid.uuid4())
        history[call_id] = {
            'id': call_id,
            'group_id': group_id,
            'started_by': started_by,
            'call_type': call_type,
            'participants': participants,
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
        }
        _save_json(CALL_HISTORY_FILE, history)
        return history[call_id]
