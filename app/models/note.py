import base64
import json
import os
import uuid
from datetime import datetime, timedelta

NOTES_FILE = 'notes.json'
UPLOADS_FOLDER = 'uploads/notes'

os.makedirs(UPLOADS_FOLDER, exist_ok=True)


class Note:
    @staticmethod
    def _load_notes():
        if not os.path.exists(NOTES_FILE):
            return []
        try:
            with open(NOTES_FILE, 'r') as file_handle:
                return json.load(file_handle)
        except Exception:
            return []

    @staticmethod
    def _save_notes(notes):
        with open(NOTES_FILE, 'w') as file_handle:
            json.dump(notes, file_handle, indent=2)

    @staticmethod
    def upload_note(username, text_content='', media_base64=None, media_type='text'):
        notes = Note._load_notes()

        if media_type not in ['text', 'image', 'video']:
            return None

        media_url = None
        thumbnail_url = None

        if media_type == 'text':
            if not text_content or not text_content.strip():
                return None
        else:
            if not media_base64:
                return None

            extension = 'mp4' if media_type == 'video' else 'jpg'
            filename = f"{uuid.uuid4()}.{extension}"
            filepath = os.path.join(UPLOADS_FOLDER, filename)

            try:
                with open(filepath, 'wb') as file_handle:
                    file_handle.write(base64.b64decode(media_base64))
                media_url = f"/uploads/notes/{filename}"

                if media_type == 'video':
                    from app.utils import generate_video_thumbnail

                    thumb_filename = f"{filename.split('.')[0]}_thumb.jpg"
                    thumb_filepath = os.path.join(UPLOADS_FOLDER, thumb_filename)
                    if generate_video_thumbnail(filepath, thumb_filepath):
                        thumbnail_url = f"/uploads/notes/{thumb_filename}"
            except Exception as exception:
                print(f"Error saving note media: {exception}")
                return None

        note = {
            'id': str(uuid.uuid4()),
            'username': username,
            'text_content': text_content.strip() if text_content else '',
            'media_url': media_url,
            'thumbnail_url': thumbnail_url,
            'media_type': media_type,
            'timestamp': datetime.now().isoformat(),
            'viewers': [],
        }

        notes.append(note)
        Note._save_notes(notes)
        return note

    @staticmethod
    def get_active_notes():
        notes = Note._load_notes()
        active_notes = []
        now = datetime.now()

        for note in notes:
            try:
                note_time = datetime.fromisoformat(note['timestamp'])
                if now - note_time < timedelta(hours=24):
                    if 'viewers' not in note:
                        note['viewers'] = []
                    active_notes.append(note)
            except Exception:
                pass

        return active_notes

    @staticmethod
    def get_user_notes(username):
        return [note for note in Note.get_active_notes() if note['username'] == username]

    @staticmethod
    def mark_note_viewed(note_id, viewer_username):
        notes = Note._load_notes()

        for note in notes:
            if note['id'] == note_id:
                if 'viewers' not in note:
                    note['viewers'] = []

                if not any(viewer.get('username') == viewer_username for viewer in note['viewers']):
                    note['viewers'].append({
                        'username': viewer_username,
                        'timestamp': datetime.now().isoformat(),
                    })
                Note._save_notes(notes)
                return True

        return False

    @staticmethod
    def cleanup_expired_notes():
        notes = Note._load_notes()
        now = datetime.now()
        active_notes = []

        for note in notes:
            try:
                note_time = datetime.fromisoformat(note['timestamp'])
                if now - note_time < timedelta(hours=24):
                    active_notes.append(note)
            except Exception:
                pass

        Note._save_notes(active_notes)