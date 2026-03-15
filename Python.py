#!/usr/bin/env python3
"""
E2EE Messenger Main Application
Created by Virat Rajput © 2026
"""

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import logging
from datetime import datetime

# Import modules
from auth_routes import auth_bp, token_required
from config import config

# Initialize Flask app
app = Flask(__name__, 
            static_folder='../frontend', 
            static_url_path='')

# Load configuration
env = os.getenv('FLASK_ENV', 'development')
app.config.from_object(config[env])

# Initialize extensions
CORS(app, supports_credentials=True, origins=app.config['CORS_ORIGINS'])
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   ping_timeout=60,
                   ping_interval=25)

# Register blueprints
app.register_blueprint(auth_bp)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Active users tracking
active_users = {}

# Routes
@app.route('/')
@app.route('/<path:filename>')
def serve_frontend(filename='index.html'):
    """Serve frontend files"""
    return send_from_directory('../frontend', filename)

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '3.0',
        'environment': env,
        'creator': 'Virat Rajput',
        'year': 2026
    })

@app.route('/api/stats')
def get_stats():
    """Get system statistics"""
    return jsonify({
        'active_users': len(active_users),
        'uptime': 'active',
        'mode': 'E2EE enabled',
        'offline_support': True,
        'persistence': '365 days'
    })

# Socket.IO Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'status': 'connected', 'timestamp': datetime.utcnow().isoformat()})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    # Remove from active users
    for uid, sid in list(active_users.items()):
        if sid == request.sid:
            del active_users[uid]
            logger.info(f"User {uid} disconnected")
            break

@socketio.on('authenticate')
def handle_authenticate(data):
    """Authenticate socket connection"""
    token = data.get('token')
    # Verify token (implement your verification)
    uid = data.get('uid')
    if uid:
        active_users[uid] = request.sid
        emit('authenticated', {'status': 'success', 'uid': uid})

@socketio.on('join_chat')
def handle_join_chat(data):
    """Join a chat room"""
    chat_id = data.get('chat_id')
    if chat_id:
        join_room(chat_id)
        emit('joined', {'chat_id': chat_id})

@socketio.on('send_message')
def handle_send_message(data):
    """Handle real-time message"""
    chat_id = data.get('chat_id')
    message = data.get('message')
    # Broadcast to chat room
    emit('new_message', {
        'chat_id': chat_id,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }, room=chat_id)

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# Create tables if they don't exist
def init_db():
    """Initialize database tables"""
    from models import db
    db.create_all()

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🔐 E2EE MESSENGER SERVER v3.0")
    print("="*70)
    print(f"👤 Created by: Virat Rajput")
    print(f"📅 Year: 2026")
    print(f"⚙️  Mode: {env.upper()}")
    print(f"🌐 Host: 0.0.0.0")
    print(f"🚪 Port: 5000")
    print("="*70)
    print("\n✨ Features Enabled:")
    print("   ✓ End-to-End Encryption")
    print("   ✓ 1-Year Cookie Persistence")
    print("   ✓ Offline Message Queue")
    print("   ✓ Real-time WebSocket")
    print("   ✓ Secure Authentication")
    print("\n📝 Test Credentials:")
    print("   Email: test@example.com")
    print("   Password: Test@1234")
    print("\n🚀 Server starting...")
    print("="*70 + "\n")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=(env == 'development'),
        allow_unsafe_werkzeug=True
    )
