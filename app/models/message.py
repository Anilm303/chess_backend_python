import json
import os
from datetime import datetime
import uuid
import base64

from app.storage import create_media_filename, store_media_bytes

MESSAGES_FILE = 'messages.json'
UPLOADS_FOLDER = 'uploads/messages'

os.makedirs(UPLOADS_FOLDER, exist_ok=True)


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

def get_messages():
    """Load messages from JSON file"""
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_messages(messages):
    """Save messages to JSON file"""
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(messages, f, indent=2)

class Message:
    """Message model for one-to-one chat"""
    def __init__(self, sender, receiver, text='', message_type='text',
                 media_url=None, thumbnail_url=None, reply_to_id=None,
                 timestamp=None):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.receiver = receiver
        self.text = text
        self.message_type = message_type   # 'text', 'image', 'video'
        self.media_url = media_url
        self.thumbnail_url = thumbnail_url
        self.reply_to_id = reply_to_id     # id of message being replied to
        self.timestamp = _normalize_timestamp(timestamp)
        self.is_read = False
        self.status = 'sent'
        self.reactions = {}                # {username: [emoji, ...]}

    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender,
            'receiver': self.receiver,
            'text': self.text,
            'message_type': self.message_type,
            'media_url': self.media_url,
            'thumbnail_url': self.thumbnail_url,
            'reply_to_id': self.reply_to_id,
            'timestamp': self.timestamp,
            'status': self.status,
            'is_read': self.is_read,
            'reactions': self.reactions,
        }

    @staticmethod
    def send_message(sender, receiver, text='', message_type='text',
                     media_base64=None, reply_to_id=None, timestamp=None):
        """Send a message from sender to receiver"""
        from .user import User

        sender_user = User.get_by_username(sender)
        receiver_user = User.get_by_username(receiver)

        if not sender_user:
            return False, 'Sender not found'
        if not receiver_user:
            return False, 'Receiver not found'

        media_url = None
        thumbnail_url = None
        if message_type == 'text':
            if not text or text.strip() == '':
                return False, 'Message cannot be empty'
        elif message_type == 'call':
            if not text or text.strip() == '':
                text = 'Incoming call'
        elif message_type in ['image', 'video']:
            if not media_base64:
                return False, f'{message_type} data required'
            extension = 'mp4' if message_type == 'video' else 'jpg'
            filename = create_media_filename(extension)
            try:
                media_bytes = base64.b64decode(media_base64)
                media_url = store_media_bytes('messages', filename, media_bytes, content_type='video/mp4' if message_type == 'video' else 'image/jpeg')

                # Generate thumbnail if it's a video
                if message_type == 'video':
                    from app.utils import generate_video_thumbnail
                    thumb_filename = f"{filename.split('.')[0]}_thumb.jpg"
                    thumb_filepath = os.path.join(UPLOADS_FOLDER, thumb_filename)
                    if generate_video_thumbnail(os.path.join(UPLOADS_FOLDER, filename), thumb_filepath):
                        with open(thumb_filepath, 'rb') as thumb_file:
                            thumbnail_url = store_media_bytes('messages', thumb_filename, thumb_file.read(), content_type='image/jpeg')
            except Exception as e:
                print(f"Error saving file: {e}")
                return False, 'Failed to save media file'
        else:
            return False, 'Invalid message type'

        message = Message(sender, receiver, text.strip() if text else '',
                          message_type, media_url, thumbnail_url, reply_to_id,
                          timestamp=timestamp)

        messages = get_messages()
        messages[message.id] = message.to_dict()
        save_messages(messages)

        return True, message

    @staticmethod
    def send_message_bytes(sender, receiver, text='', message_type='text',
                           media_bytes=None, reply_to_id=None, timestamp=None):
        """Send a message using raw file bytes instead of base64."""
        from .user import User

        sender_user = User.get_by_username(sender)
        receiver_user = User.get_by_username(receiver)

        if not sender_user:
            return False, 'Sender not found'
        if not receiver_user:
            return False, 'Receiver not found'

        media_url = None
        thumbnail_url = None
        if message_type == 'text':
            if not text or text.strip() == '':
                return False, 'Message cannot be empty'
        elif message_type == 'call':
            if not text or text.strip() == '':
                text = 'Incoming call'
        elif message_type in ['image', 'video']:
            if not media_bytes:
                return False, f'{message_type} data required'
            extension = 'mp4' if message_type == 'video' else 'jpg'
            filename = create_media_filename(extension)
            try:
                media_url = store_media_bytes('messages', filename, media_bytes, content_type='video/mp4' if message_type == 'video' else 'image/jpeg')

                if message_type == 'video':
                    from app.utils import generate_video_thumbnail
                    thumb_filename = f"{filename.split('.')[0]}_thumb.jpg"
                    thumb_filepath = os.path.join(UPLOADS_FOLDER, thumb_filename)
                    if generate_video_thumbnail(os.path.join(UPLOADS_FOLDER, filename), thumb_filepath):
                        with open(thumb_filepath, 'rb') as thumb_file:
                            thumbnail_url = store_media_bytes('messages', thumb_filename, thumb_file.read(), content_type='image/jpeg')
            except Exception as e:
                print(f"Error saving file: {e}")
                return False, 'Failed to save media file'
        else:
            return False, 'Invalid message type'

        message = Message(sender, receiver, text.strip() if text else '',
                          message_type, media_url, thumbnail_url, reply_to_id,
                          timestamp=timestamp)

        messages = get_messages()
        messages[message.id] = message.to_dict()
        save_messages(messages)

        return True, message

    @staticmethod
    def react_to_message(message_id, reactor, emoji):
        """Toggle an emoji reaction on a message. Returns updated reactions."""
        messages = get_messages()
        if message_id not in messages:
            return False, {}

        msg = messages[message_id]
        if 'reactions' not in msg:
            msg['reactions'] = {}

        user_reactions = msg['reactions'].get(reactor, [])
        if emoji in user_reactions:
            user_reactions.remove(emoji)
        else:
            user_reactions.append(emoji)

        if user_reactions:
            msg['reactions'][reactor] = user_reactions
        else:
            msg['reactions'].pop(reactor, None)

        messages[message_id] = msg
        save_messages(messages)
        return True, msg['reactions']

    @staticmethod
    def delete_message(message_id, requestor_username):
        """Unsend/Delete a message for everyone"""
        messages = get_messages()
        if message_id not in messages:
            return False, 'Message not found'
        
        msg = messages[message_id]
        if msg['sender'] != requestor_username:
            return False, 'Unauthorized'
            
        # Update the message instead of actually remving it so history stays contiguous
        msg['text'] = 'This message was unsent'
        msg['message_type'] = 'deleted'
        msg['media_url'] = None
        msg['thumbnail_url'] = None
        
        messages[message_id] = msg
        save_messages(messages)
        return True, msg

    @staticmethod
    def get_conversation(user1, user2):
        messages = get_messages()
        conversation = []
        for msg_data in messages.values():
            if ((msg_data['sender'] == user1 and msg_data['receiver'] == user2) or
                    (msg_data['sender'] == user2 and msg_data['receiver'] == user1)):
                # Back-fill missing fields for old messages
                if 'reactions' not in msg_data:
                    msg_data['reactions'] = {}
                if 'reply_to_id' not in msg_data:
                    msg_data['reply_to_id'] = None
                if 'status' not in msg_data:
                    msg_data['status'] = 'seen' if msg_data.get('is_read') else 'sent'
                conversation.append(msg_data)
        conversation.sort(key=lambda x: x['timestamp'])
        return conversation

    @staticmethod
    def get_all_conversations(username):
        messages = get_messages()
        users_set = set()
        for msg_data in messages.values():
            if msg_data['sender'] == username:
                users_set.add(msg_data['receiver'])
            elif msg_data['receiver'] == username:
                users_set.add(msg_data['sender'])
        return sorted(list(users_set))

    @staticmethod
    def unread_count_between(user1, user2):
        messages = get_messages()
        count = 0
        for msg_data in messages.values():
            if msg_data['sender'] == user2 and msg_data['receiver'] == user1 and not msg_data.get('is_read', False):
                count += 1
        return count

    @staticmethod
    def mark_conversation_as_read(current_user, other_user):
        messages = get_messages()
        changed_ids = []
        for msg_data in messages.values():
            if msg_data['sender'] == other_user and msg_data['receiver'] == current_user and not msg_data.get('is_read', False):
                msg_data['is_read'] = True
                msg_data['status'] = 'seen'
                changed_ids.append(msg_data['id'])
        if changed_ids:
            save_messages(messages)
        return changed_ids

    @staticmethod
    def get_last_message(user1, user2):
        messages = get_messages()
        relevant = []
        for msg_data in messages.values():
            if ((msg_data['sender'] == user1 and msg_data['receiver'] == user2) or
                    (msg_data['sender'] == user2 and msg_data['receiver'] == user1)):
                relevant.append(msg_data)
        if not relevant:
            return None
        relevant.sort(key=lambda x: x['timestamp'], reverse=True)
        return relevant[0]

    @staticmethod
    def mark_as_read(message_id):
        messages = get_messages()
        if message_id in messages:
            messages[message_id]['is_read'] = True
            messages[message_id]['status'] = 'seen'
            save_messages(messages)
            return messages[message_id]
        return None

    @staticmethod
    def mark_as_delivered(message_id):
        messages = get_messages()
        if message_id in messages:
            messages[message_id]['status'] = 'delivered'
            save_messages(messages)
            return messages[message_id]
        return None

    @staticmethod
    def mark_as_seen(message_id):
        messages = get_messages()
        if message_id in messages:
            messages[message_id]['is_read'] = True
            messages[message_id]['status'] = 'seen'
            save_messages(messages)
            return messages[message_id]
        return None
