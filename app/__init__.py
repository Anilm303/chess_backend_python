import os
from datetime import timedelta

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from app.token_store import is_token_revoked, cleanup_blocklist, clear_blocklist

# Initialize SocketIO globally.
# Use threading mode so the backend runs on Python 3.13 / Windows without eventlet.
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-jwt-secret-key-change-in-production')
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=90)
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', str(100 * 1024 * 1024)))
    
    # Enable CORS for Flutter frontend (including uploads)
    allowed_origins_raw = os.getenv('ALLOWED_ORIGINS', '*')
    allowed_origins = [
        origin.strip()
        for origin in allowed_origins_raw.split(',')
        if origin.strip()
    ] or '*'
    cors_resources = {
        r"/api/*": {"origins": allowed_origins},
        r"/uploads/*": {"origins": allowed_origins},
        r"/socket.io/*": {"origins": allowed_origins},
    }
    CORS(app, resources=cors_resources)
    
    # Initialize JWT Manager
    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def unauthorized_response(message):
        return jsonify({'success': False, 'message': message}), 401

    @jwt.invalid_token_loader
    def invalid_token_response(message):
        return jsonify({'success': False, 'message': message}), 401

    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return jsonify({'success': False, 'message': 'Token has expired'}), 401

    @jwt.revoked_token_loader
    def revoked_token_response(jwt_header, jwt_payload):
        return jsonify({'success': False, 'message': 'Token has been revoked'}), 401

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return is_token_revoked(jwt_payload.get('jti'))
    
    # Initialize Socket.IO with the app
    socketio.init_app(app)

    @app.after_request
    def apply_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Cache-Control'] = 'no-store'
        return response
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.messaging import messaging_bp
    from app.routes.stories import stories_bp
    from app.routes.notes import notes_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(messaging_bp, url_prefix='/api/messages')
    app.register_blueprint(stories_bp, url_prefix='/api/stories')
    app.register_blueprint(notes_bp, url_prefix='/api/notes')

    # Register Socket.IO handlers (messaging + call signaling)
    from app import websocket as ws_handlers  # noqa: F401

    @app.route('/')
    def home():
        return {
            'service': 'chess-backend',
            'status': 'running',
            'message': 'Chess backend is live',
            'health_check': '/api/ping',
        }

    @app.route('/ping')
    def ping():
        return jsonify({'status': 'ok', 'service': 'chess-backend'}), 200
    
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        uploads_dir = os.path.join(os.getcwd(), 'uploads')
        return send_from_directory(uploads_dir, filename)
    
    # Start background cleanup task
    from app.cleanup import start_cleanup_thread
    start_cleanup_thread()
    # Optionally clear auth/token state on startup if requested by the environment.
    # Useful when deploying to a fresh environment and you want to avoid reusing
    # previously persisted token blocklists across deployments (e.g. HF Spaces).
    if os.getenv('RESET_AUTH_DATA', '0') == '1' or os.getenv('CLEAR_TOKEN_BLOCKLIST_ON_STARTUP', '0') == '1':
        try:
            clear_blocklist()
            app.logger.info('Auth token blocklist cleared on startup due to env flag.')
        except Exception:
            app.logger.exception('Failed to clear token blocklist on startup')
    # Always attempt to clean up expired entries in the blocklist (if present)
    try:
        cleanup_blocklist()
    except Exception:
        app.logger.exception('Failed to cleanup token blocklist')

    # Initialize HF sync if configured (download users.json into local DATA_ROOT)
    try:
        from app.models.user import USERS_FILE
        from app import hf_sync  # type: ignore
        hf_sync.initialize(USERS_FILE)
        app.logger.info('HF sync initialization attempted')
    except Exception:
        app.logger.exception('HF sync initialization failed')

    # Warn if JWT secret uses default value (encourage setting env var)
    if os.getenv('JWT_SECRET_KEY') is None:
        app.logger.warning('JWT_SECRET_KEY not explicitly set; using default from config.')

    # Debug endpoint to inspect socket state (development only)
    @app.route('/debug/socket_state')
    def debug_socket_state():
        try:
            # Access active_connections and call_rooms from websocket module
            return {
                'active_connections': getattr(ws_handlers, 'active_connections', {}),
                'call_rooms': getattr(ws_handlers, 'call_rooms', {}),
            }
        except Exception as e:
            return {'error': str(e)}, 500
    
    return app
