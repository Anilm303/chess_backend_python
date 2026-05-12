import json
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Simple in-memory user storage (replace with database in production)
USERS_FILE = 'users.json'
ONLINE_USERS = {}  # Track online users and their socket IDs

def get_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

class User:
    """User model with profile support"""
    def __init__(self, username, email, first_name, last_name, password_hash, profile_image=None, bio=None):
        self.username = username
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.password_hash = password_hash
        self.profile_image = profile_image  # Base64 or file path
        self.bio = bio or ""
        self.fcm_token = None
        self.created_at = datetime.utcnow().isoformat()
        self.last_seen = datetime.utcnow().isoformat()
    
    def to_dict(self, include_password=False):
        """Convert user to dictionary"""
        data = {
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'profile_image': self.profile_image,
            'bio': self.bio,
            'fcm_token': getattr(self, 'fcm_token', None),
            'created_at': self.created_at,
            'last_seen': self.last_seen,
            'is_online': ONLINE_USERS.get(self.username) is not None,
        }
        if include_password:
            data['password_hash'] = self.password_hash
        return data
    
    @staticmethod
    def register(username, email, first_name, last_name, password):
        """Register a new user"""
        users = get_users()
        
        # Check if user exists
        if username in users:
            return False, 'Username already exists'
        
        if any(user['email'] == email for user in users.values()):
            return False, 'Email already registered'
        
        # Create new user
        password_hash = generate_password_hash(password)
        user = User(username, email, first_name, last_name, password_hash)
        users[username] = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'password_hash': user.password_hash,
            'profile_image': user.profile_image,
            'bio': user.bio,
            'created_at': user.created_at,
            'last_seen': user.last_seen,
        }
        
        save_users(users)
        return True, user
    
    @staticmethod
    def login(username, password):
        """Authenticate user"""
        users = get_users()
        
        if username not in users:
            return False, 'Invalid credentials'
        
        user_data = users[username]
        if not check_password_hash(user_data['password_hash'], password):
            return False, 'Invalid credentials'
        
        return True, User(
            user_data['username'],
            user_data['email'],
            user_data['first_name'],
            user_data['last_name'],
            user_data['password_hash'],
            user_data.get('profile_image'),
            user_data.get('bio')
        )
    
    @staticmethod
    def get_by_username(username):
        """Get user by username"""
        users = get_users()
        
        if username not in users:
            return None
        
        user_data = users[username]
        return User(
            user_data['username'],
            user_data['email'],
            user_data['first_name'],
            user_data['last_name'],
            user_data['password_hash'],
            user_data.get('profile_image'),
            user_data.get('bio')
        )
    
    @staticmethod
    def get_all_users():
        """Get all registered users with online status"""
        users = get_users()
        return users
    
    @staticmethod
    def update_profile(username, first_name=None, last_name=None, bio=None, profile_image=None):
        """Update user profile information"""
        users = get_users()
        
        if username not in users:
            return False, 'User not found'
        
        user_data = users[username]
        
        if first_name is not None:
            user_data['first_name'] = first_name
        if last_name is not None:
            user_data['last_name'] = last_name
        if bio is not None:
            user_data['bio'] = bio
        if profile_image is not None:
            user_data['profile_image'] = profile_image
        
        save_users(users)
        return True, 'Profile updated'
    
    @staticmethod
    def set_fcm_token(username, token):
        """Update user's FCM token"""
        users = get_users()
        if username in users:
            users[username]['fcm_token'] = token
            save_users(users)
            return True
        return False

    @staticmethod
    def get_fcm_token(username):
        """Get user's FCM token"""
        users = get_users()
        if username in users:
            return users[username].get('fcm_token')
        return None

    @staticmethod
    def set_online(username, socket_id=None):
        """Mark user as online"""
        ONLINE_USERS[username] = socket_id or True
        users = get_users()
        if username in users:
            users[username]['last_seen'] = datetime.utcnow().isoformat()
            save_users(users)
    
    @staticmethod
    def set_offline(username):
        """Mark user as offline"""
        if username in ONLINE_USERS:
            del ONLINE_USERS[username]
        users = get_users()
        if username in users:
            users[username]['last_seen'] = datetime.utcnow().isoformat()
            save_users(users)
    
    @staticmethod
    def is_online(username):
        """Check if user is online"""
        return ONLINE_USERS.get(username) is not None
    
    @staticmethod
    def get_online_users():
        """Get list of online users"""
        return list(ONLINE_USERS.keys())
