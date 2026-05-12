import os
from datetime import timedelta

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

# Initialize SocketIO globally
socketio = SocketIO(cors_allowed_origins="*")

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
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', str(100 * 1024 * 1024)))
    
    # Enable CORS for Flutter frontend (including uploads)
    CORS(app, resources={
        r"/api/*": {"origins": "*"},
        r"/uploads/*": {"origins": "*"},
    })
    
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
    
    # Initialize Socket.IO with the app
    socketio.init_app(app)

    @app.after_request
    def apply_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
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
            'message': 'Chess backend is live on Hugging Face Spaces',
            'health_check': '/api/auth/health',
        }
    
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        uploads_dir = os.path.join(os.getcwd(), 'uploads')
        return send_from_directory(uploads_dir, filename)
    
    # Start background cleanup task
    from app.cleanup import start_cleanup_thread
    start_cleanup_thread()

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
