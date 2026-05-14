from gevent import monkey
monkey.patch_all()

import os
from app import create_app, socketio

if __name__ == '__main__':
    app = create_app()
    
    # Prefer PORT for container platforms (Hugging Face Spaces, Render, etc.)
    # and fall back to FLASK_PORT for local development.
    port = int(os.getenv('PORT', os.getenv('FLASK_PORT', 7860)))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"Starting Chess Authentication API on port {port}...")
    print("Make sure to change SECRET_KEY and JWT_SECRET_KEY in app/__init__.py for production!")
    
    # Run Flask + Socket.IO server
    socketio.run(app, debug=debug_mode, host='0.0.0.0', port=port)
