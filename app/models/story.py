import json
import os
from datetime import datetime, timedelta
import uuid
import base64

from app.storage import create_media_filename, store_media_bytes

STORIES_FILE = 'stories.json'
UPLOADS_FOLDER = 'uploads/stories'

os.makedirs(UPLOADS_FOLDER, exist_ok=True)


class Story:
    """Model for user stories (status updates)"""

    @staticmethod
    def _load_stories():
        if not os.path.exists(STORIES_FILE):
            return []
        try:
            with open(STORIES_FILE, 'r') as f:
                return json.load(f)
        except:
            return []

    @staticmethod
    def _save_stories(stories):
        with open(STORIES_FILE, 'w') as f:
            json.dump(stories, f, indent=2)

    @staticmethod
    def upload_story(username, media_base64, media_type):
        stories = Story._load_stories()

        extension = 'mp4' if media_type == 'video' else 'jpg'
        filename = create_media_filename(extension)

        try:
            media_bytes = base64.b64decode(media_base64)
        except Exception as exception:
            print(f"Error saving file: {exception}")
            return None

        try:
            media_url = store_media_bytes(
                'stories',
                filename,
                media_bytes,
                content_type='video/mp4' if media_type == 'video' else 'image/jpeg',
            )
        except Exception as exception:
            print(f"Error storing story media: {exception}")
            return None

        story_id = str(uuid.uuid4())
        thumbnail_url = None

        if media_type == 'video':
            try:
                from app.utils import generate_video_thumbnail

                thumb_filename = f"{filename.split('.')[0]}_thumb.jpg"
                thumb_filepath = os.path.join(UPLOADS_FOLDER, thumb_filename)
                media_filepath = os.path.join(UPLOADS_FOLDER, filename)
                if generate_video_thumbnail(media_filepath, thumb_filepath):
                    with open(thumb_filepath, 'rb') as thumb_file:
                        thumbnail_url = store_media_bytes(
                            'stories',
                            thumb_filename,
                            thumb_file.read(),
                            content_type='image/jpeg',
                        )
            except Exception as exception:
                print(f"⚠️ Thumbnail generation error (non-blocking): {exception}")

        story = {
            'id': story_id,
            'username': username,
            'media_url': media_url,
            'thumbnail_url': thumbnail_url,
            'media_type': media_type,
            'timestamp': datetime.now().isoformat(),
            'viewers': [],
            'reactions': {},
            'reaction_details': {},
        }

        stories.append(story)
        Story._save_stories(stories)
        return story

    @staticmethod
    def upload_story_bytes(username, media_bytes, media_type):
        """Upload raw bytes (used by multipart form uploads)."""
        stories = Story._load_stories()

        extension = 'mp4' if media_type == 'video' else 'jpg'
        filename = create_media_filename(extension)

        try:
            media_url = store_media_bytes(
                'stories',
                filename,
                media_bytes,
                content_type='video/mp4' if media_type == 'video' else 'image/jpeg',
            )
        except Exception as exception:
            print(f"❌ Error storing file bytes: {exception}")
            return None

        story_id = str(uuid.uuid4())
        thumbnail_url = None

        if media_type == 'video':
            try:
                from app.utils import generate_video_thumbnail

                thumb_filename = f"{filename.split('.')[0]}_thumb.jpg"
                thumb_filepath = os.path.join(UPLOADS_FOLDER, thumb_filename)
                media_filepath = os.path.join(UPLOADS_FOLDER, filename)
                print(f"🎬 Attempting thumbnail generation: {thumb_filepath}")
                if generate_video_thumbnail(media_filepath, thumb_filepath):
                    with open(thumb_filepath, 'rb') as thumb_file:
                        thumbnail_url = store_media_bytes(
                            'stories',
                            thumb_filename,
                            thumb_file.read(),
                            content_type='image/jpeg',
                        )
                    print("✅ Thumbnail generated successfully")
                else:
                    print("⚠️ Thumbnail generation returned False, continuing without thumbnail")
            except Exception as exception:
                print(f"⚠️ Thumbnail generation error (non-blocking): {exception}")

        story = {
            'id': story_id,
            'username': username,
            'media_url': media_url,
            'thumbnail_url': thumbnail_url,
            'media_type': media_type,
            'timestamp': datetime.now().isoformat(),
            'viewers': [],
            'reactions': {},
            'reaction_details': {},
        }

        try:
            stories.append(story)
            Story._save_stories(stories)
            print(f"✅ Story saved to stories.json: {story_id}")
            return story
        except Exception as exception:
            print(f"❌ Error saving story to file: {exception}")
            return None

    @staticmethod
    def get_active_stories():
        stories = Story._load_stories()
        active = []
        now = datetime.now()

        for story in stories:
            try:
                story_time = datetime.fromisoformat(story['timestamp'])
                age = now - story_time
                if age < timedelta(hours=24):
                    # Migrate old format to new format
                    if 'viewed_by' in story and 'viewers' not in story:
                        story['viewers'] = [{'username': u, 'timestamp': story['timestamp']} for u in story['viewed_by']]
                        del story['viewed_by']
                    
                    # Ensure all required fields exist
                    if 'viewers' not in story:
                        story['viewers'] = []
                    if 'reactions' not in story:
                        story['reactions'] = {}
                    if 'reaction_details' not in story:
                        story['reaction_details'] = {}
                    
                    active.append(story)
            except:
                pass

        return active

    @staticmethod
    def get_user_stories(username):
        all_stories = Story.get_active_stories()
        return [s for s in all_stories if s['username'] == username]

    @staticmethod
    def mark_story_viewed(story_id, viewer_username):
        stories = Story._load_stories()

        for story in stories:
            if story['id'] == story_id:
                # Ensure viewers list exists and is updated format
                if 'viewers' not in story:
                    story['viewers'] = []
                if 'viewed_by' in story:
                    del story['viewed_by']  # Remove old format
                
                # Check if viewer already exists
                viewer_exists = any(v.get('username') == viewer_username for v in story['viewers'])
                if not viewer_exists:
                    story['viewers'].append({
                        'username': viewer_username,
                        'timestamp': datetime.now().isoformat(),
                    })
                Story._save_stories(stories)
                return True

        return False

    @staticmethod
    def react_to_story(story_id, reactor_username, emoji):
        """Add or remove a reaction emoji on a story. Toggling same emoji removes it."""
        stories = Story._load_stories()

        for story in stories:
            if story['id'] == story_id:
                if 'reactions' not in story:
                    story['reactions'] = {}
                if 'reaction_details' not in story:
                    story['reaction_details'] = {}
                
                if story['reactions'].get(reactor_username) == emoji:
                    # Toggle off
                    del story['reactions'][reactor_username]
                    if reactor_username in story['reaction_details']:
                        del story['reaction_details'][reactor_username]
                else:
                    story['reactions'][reactor_username] = emoji
                    story['reaction_details'][reactor_username] = {
                        'emoji': emoji,
                        'timestamp': datetime.now().isoformat(),
                    }
                Story._save_stories(stories)
                return True, story['reactions'], story['reaction_details'], story['username']

        return False, {}, {}, None

    @staticmethod
    def get_story_reactions(story_id):
        """Get all reactions for a story as {username: emoji}"""
        stories = Story._load_stories()
        for story in stories:
            if story['id'] == story_id:
                return story.get('reactions', {})
        return {}

    @staticmethod
    def get_story_viewers(story_id):
        """Get list of viewers for a story with timestamps"""
        stories = Story._load_stories()
        for story in stories:
            if story['id'] == story_id:
                return story.get('viewers', [])
        return []

    @staticmethod
    def get_story_reaction_details(story_id):
        """Get detailed reaction info {username: {emoji: str, timestamp: str}}"""
        stories = Story._load_stories()
        for story in stories:
            if story['id'] == story_id:
                return story.get('reaction_details', {})
        return {}

    @staticmethod
    def cleanup_expired_stories():
        stories = Story._load_stories()
        now = datetime.now()
        active_stories = []

        for story in stories:
            try:
                story_time = datetime.fromisoformat(story['timestamp'])
                age = now - story_time
                if age < timedelta(hours=24):
                    active_stories.append(story)
            except:
                pass

        Story._save_stories(active_stories)
