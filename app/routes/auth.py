from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models.user import User
from app.security import (
    rate_limit,
    require_json_body,
    validate_email,
    validate_name,
    validate_password,
    validate_username,
)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
@rate_limit(limit=5, window_seconds=60, scope='auth_register')
def register():
    """Register a new user"""
    data, error_response = require_json_body()
    if error_response:
        return error_response

    required_fields = ['username', 'email', 'first_name', 'last_name', 'password']
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return jsonify({'success': False, 'message': f"Missing required fields: {', '.join(missing_fields)}"}), 400

    valid_username, username_or_message = validate_username(data.get('username'))
    if not valid_username:
        return jsonify({'success': False, 'message': username_or_message}), 400

    valid_email, email_or_message = validate_email(data.get('email'))
    if not valid_email:
        return jsonify({'success': False, 'message': email_or_message}), 400

    valid_first_name, first_name_or_message = validate_name(data.get('first_name'), 'First name')
    if not valid_first_name:
        return jsonify({'success': False, 'message': first_name_or_message}), 400

    valid_last_name, last_name_or_message = validate_name(data.get('last_name'), 'Last name')
    if not valid_last_name:
        return jsonify({'success': False, 'message': last_name_or_message}), 400

    valid_password, password_or_message = validate_password(data.get('password'))
    if not valid_password:
        return jsonify({'success': False, 'message': password_or_message}), 400
    
    # Register user
    success, result = User.register(username_or_message, email_or_message, first_name_or_message, last_name_or_message, password_or_message)
    
    if not success:
        return jsonify({'success': False, 'message': result}), 400
    
    # Create access token
    access_token = create_access_token(identity=username)
    
    return jsonify({
        'success': True,
        'message': 'User registered successfully',
        'access_token': access_token,
        'user': result.to_dict()
    }), 201

@auth_bp.route('/login', methods=['POST'])
@rate_limit(limit=8, window_seconds=60, scope='auth_login')
def login():
    """Login user"""
    data, error_response = require_json_body()
    if error_response:
        return error_response

    username = data.get('username', '')
    password = data.get('password', '')

    valid_username, username_or_message = validate_username(username)
    if not valid_username:
        return jsonify({'success': False, 'message': username_or_message}), 400

    valid_password, password_or_message = validate_password(password)
    if not valid_password:
        return jsonify({'success': False, 'message': password_or_message}), 400
    
    # Authenticate user
    success, result = User.login(username_or_message, password_or_message)
    
    if not success:
        return jsonify({'success': False, 'message': result}), 401
    
    # Mark user as online
    User.set_online(username)
    
    # Create access token
    access_token = create_access_token(identity=username)
    
    return jsonify({
        'success': True,
        'message': 'Login successful',
        'access_token': access_token,
        'user': result.to_dict()
    }), 200

@auth_bp.route('/validate-token', methods=['GET'])
@jwt_required()
def validate_token():
    """Validate JWT token and return user info"""
    username = get_jwt_identity()
    user = User.get_by_username(username)
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    return jsonify({
        'success': True,
        'user': user.to_dict()
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user and mark as offline"""
    username = get_jwt_identity()
    User.set_offline(username)
    
    return jsonify({
        'success': True,
        'message': 'Logout successful'
    }), 200

@auth_bp.route('/update-fcm-token', methods=['POST'])
@jwt_required()
@rate_limit(limit=20, window_seconds=60, scope='auth_update_fcm_token')
def update_fcm_token():
    """Update user's FCM token"""
    username = get_jwt_identity()
    data, error_response = require_json_body()
    if error_response:
        return error_response

    token = data.get('fcm_token')
    if not token or not str(token).strip():
        return jsonify({'success': False, 'message': 'FCM token required'}), 400
        
    success = User.set_fcm_token(username, token)
    if success:
        return jsonify({'success': True, 'message': 'FCM token updated'}), 200
    else:
        return jsonify({'success': False, 'message': 'Failed to update FCM token'}), 500

@auth_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'chess-auth-api'}), 200
