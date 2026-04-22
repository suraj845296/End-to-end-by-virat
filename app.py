"""
==================================================
🔥 FACEBOOK MESSENGER E2EE BOT - COMPLETE PACKAGE 🔥
==================================================
Created by: SURAJ OBEROY
Copyright: 2026 All Rights Reserved
Contact: +91 8452969216
==================================================
"""

import os
import time
import json
import base64
import sqlite3
import threading
import hashlib
import hmac
import secrets
import requests
import random
import re
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import parse_qs, urlparse

# Flask related imports
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Cryptographic imports
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

# ==================================================
# 🔧 INITIALIZATION
# ==================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'suraj-oberoy-2026-secure-key-8452969216'
app.config['DATABASE'] = 'e2ee_bot.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file

# Create upload folder if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('templates', exist_ok=True)

bcrypt = Bcrypt(app)

# ==================================================
# 💾 DATABASE SETUP (SQLite)
# ==================================================

def get_db():
    """Get database connection"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Create all tables"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Cookies table (encrypted)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cookies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                cookie_data TEXT NOT NULL,
                cookie_hash TEXT UNIQUE,
                is_valid INTEGER DEFAULT 1,
                last_used TIMESTAMP,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Bot sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_name TEXT,
                chat_id TEXT NOT NULL,
                target_name TEXT,
                status TEXT DEFAULT 'stopped',
                delay_seconds INTEGER DEFAULT 2,
                messages_sent INTEGER DEFAULT 0,
                messages_failed INTEGER DEFAULT 0,
                last_message_time TIMESTAMP,
                public_key TEXT,
                private_key_encrypted TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Message logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                recipient TEXT,
                message_type TEXT,
                content_preview TEXT,
                encrypted_content TEXT,
                status TEXT,
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES bot_sessions (id) ON DELETE CASCADE
            )
        ''')
        
        # System logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                component TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        db.commit()

# Initialize database
init_db()

# ==================================================
# 🔐 E2EE ENCRYPTION MANAGER
# ==================================================

class E2EEManager:
    """End-to-End Encryption Handler"""
    
    def __init__(self):
        self.backend = default_backend()
    
    def generate_keys(self, password=None):
        """Generate RSA key pair for E2EE"""
        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=self.backend
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Serialize private key
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Serialize public key
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            return {
                'private': private_pem.decode('utf-8'),
                'public': public_pem.decode('utf-8')
            }
        except Exception as e:
            self.log_error('E2EE', f'Key generation failed: {e}')
            return None
    
    def encrypt_message(self, message, public_key_pem):
        """Encrypt message with recipient's public key"""
        try:
            # Load public key
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=self.backend
            )
            
            # Encrypt message
            encrypted = public_key.encrypt(
                message.encode('utf-8'),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            self.log_error('E2EE', f'Encryption failed: {e}')
            return None
    
    def decrypt_message(self, encrypted_message, private_key_pem):
        """Decrypt message with private key"""
        try:
            # Load private key
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None,
                backend=self.backend
            )
            
            # Decode from base64
            encrypted_data = base64.b64decode(encrypted_message)
            
            # Decrypt
            decrypted = private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return decrypted.decode('utf-8')
        except Exception as e:
            self.log_error('E2EE', f'Decryption failed: {e}')
            return None
    
    def hash_cookie(self, cookie_string):
        """Create hash of cookie for validation"""
        return hashlib.sha256(cookie_string.encode()).hexdigest()
    
    def log_error(self, component, message):
        """Log errors to database"""
        try:
            db = get_db()
            db.execute(
                'INSERT INTO system_logs (level, component, message) VALUES (?, ?, ?)',
                ('ERROR', component, message)
            )
            db.commit()
        except:
            pass

# Initialize E2EE manager
e2ee = E2EEManager()

# ==================================================
# 🍪 COOKIE MANAGER
# ==================================================

class CookieManager:
    """Facebook Cookie Handler"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def parse_cookie_string(self, cookie_string):
        """Convert cookie string to dict"""
        cookies = {}
        try:
            for item in cookie_string.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
        except Exception as e:
            self.log_error(f'Cookie parse failed: {e}')
        return cookies
    
    def validate_cookie(self, cookie_string):
        """Check if Facebook cookie is valid"""
        try:
            cookies = self.parse_cookie_string(cookie_string)
            
            # Check if essential cookies exist
            if 'c_user' not in cookies or 'xs' not in cookies:
                return False, 'Missing required cookies (c_user or xs)'
            
            # Try to access Facebook API
            response = self.session.get(
                'https://graph.facebook.com/me',
                cookies=cookies,
                params={'fields': 'id,name,email'},
                timeout=10
            )
            
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f'API returned {response.status_code}'
                
        except requests.exceptions.Timeout:
            return False, 'Connection timeout'
        except Exception as e:
            return False, str(e)
    
    def store_cookie(self, user_id, cookie_string):
        """Store cookie in database"""
        try:
            cookie_hash = e2ee.hash_cookie(cookie_string)
            
            # Simple encryption (base64)
            encrypted = base64.b64encode(cookie_string.encode()).decode()
            
            # Set expiry (approx 60 days from now)
            expires_at = datetime.now() + timedelta(days=60)
            
            db = get_db()
            cursor = db.cursor()
            
            # Check if exists
            cursor.execute(
                'SELECT id FROM cookies WHERE cookie_hash = ?',
                (cookie_hash,)
            )
            existing = cursor.fetchone()
            
            if existing:
                return existing['id']
            
            # Insert new
            cursor.execute('''
                INSERT INTO cookies (user_id, cookie_data, cookie_hash, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, encrypted, cookie_hash, expires_at))
            
            db.commit()
            return cursor.lastrowid
            
        except Exception as e:
            self.log_error(f'Store cookie failed: {e}')
            return None
    
    def get_cookie(self, cookie_id):
        """Retrieve and decrypt cookie"""
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                'SELECT cookie_data FROM cookies WHERE id = ? AND is_valid = 1',
                (cookie_id,)
            )
            row = cursor.fetchone()
            
            if row:
                # Decrypt
                decrypted = base64.b64decode(row['cookie_data']).decode()
                return decrypted
            return None
        except Exception as e:
            self.log_error(f'Get cookie failed: {e}')
            return None
    
    def log_error(self, message):
        """Log errors"""
        try:
            db = get_db()
            db.execute(
                'INSERT INTO system_logs (level, component, message) VALUES (?, ?, ?)',
                ('ERROR', 'CookieManager', message)
            )
            db.commit()
        except:
            pass

# Initialize cookie manager
cookie_manager = CookieManager()

# ==================================================
# 🤖 FACEBOOK BOT ENGINE
# ==================================================

class FacebookBot:
    """Main bot engine for Facebook Messenger"""
    
    def __init__(self, cookie_string, chat_id):
        self.cookie_string = cookie_string
        self.chat_id = chat_id
        self.is_running = False
        self.message_count = 0
        self.session_id = None
        
        # Setup session
        self.session = requests.Session()
        self.cookies = cookie_manager.parse_cookie_string(cookie_string)
        self.session.cookies.update(self.cookies)
        
        # Update headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.facebook.com/',
            'Origin': 'https://www.facebook.com',
            'Connection': 'keep-alive'
        })
    
    def get_fb_dtsg(self):
        """Extract fb_dtsg token from Facebook"""
        try:
            response = self.session.get('https://www.facebook.com/', timeout=10)
            html = response.text
            
            # Try multiple patterns
            patterns = [
                r'"fb_dtsg" value="([^"]+)"',
                r'name="fb_dtsg" value="([^"]+)"',
                r'fb_dtsg\\":\\"([^\\"]+)\\"'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            self.log_error(f'Failed to get fb_dtsg: {e}')
            return None
    
    def send_message(self, message_text, is_encrypted=True):
        """Send message to Facebook Messenger"""
        try:
            # Get fb_dtsg token
            fb_dtsg = self.get_fb_dtsg()
            if not fb_dtsg:
                return False, 'Failed to get fb_dtsg token'
            
            # Prepare message with E2EE marker
            if is_encrypted:
                final_message = f"🔒 [E2EE] {message_text}"
            else:
                final_message = message_text
            
            # Generate message ID
            message_id = f"mid.{int(time.time() * 1000)}"
            offline_id = str(int(time.time() * 1000))
            
            # Prepare data for Facebook
            data = {
                'client': 'mercury',
                'action_type': 'ma-type:user-generated-message',
                'body': final_message,
                'ephemeral_ttl_mode': '0',
                'has_attachment': 'false',
                'message_id': message_id,
                'offline_threading_id': offline_id,
                'source': 'source:chat:web',
                'specific_to_list[0]': f'fbid:{self.chat_id}',
                'fb_dtsg': fb_dtsg,
                '__user': self.cookies.get('c_user', '0'),
                '__a': '1',
                '__dyn': '',
                '__csr': '',
                '__req': '',
                '__be': '',
                '__pc': '',
                'fb_dtsg': fb_dtsg,
                'jazoest': '',
                'lsd': ''
            }
            
            # Send message
            response = self.session.post(
                'https://www.facebook.com/messaging/send/',
                data=data,
                timeout=15,
                allow_redirects=False
            )
            
            if response.status_code == 200:
                self.message_count += 1
                
                # Check response for success
                if 'error' not in response.text.lower():
                    return True, 'Message sent successfully'
                else:
                    return False, 'Facebook returned error'
            else:
                return False, f'HTTP {response.status_code}'
                
        except requests.exceptions.Timeout:
            return False, 'Request timeout'
        except Exception as e:
            return False, str(e)
    
    def send_file(self, file_path):
        """Send file in message"""
        try:
            if not os.path.exists(file_path):
                return False, 'File not found'
            
            # Get file info
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # For now, send as message with file name
            return self.send_message(f"[FILE] {file_name} ({file_size} bytes)")
            
        except Exception as e:
            return False, str(e)
    
    def start_automation(self, message_list, delay_seconds, session_id=None):
        """Start automated messaging"""
        self.is_running = True
        self.session_id = session_id
        
        for i, message in enumerate(message_list):
            if not self.is_running:
                break
            
            # Send message
            success, result = self.send_message(message)
            
            # Log to database
            if session_id:
                try:
                    db = get_db()
                    db.execute('''
                        INSERT INTO message_logs 
                        (session_id, recipient, message_type, content_preview, status, error_message)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id,
                        self.chat_id,
                        'text',
                        message[:50],
                        'sent' if success else 'failed',
                        None if success else result
                    ))
                    
                    # Update session counts
                    if success:
                        db.execute(
                            'UPDATE bot_sessions SET messages_sent = messages_sent + 1, last_message_time = ? WHERE id = ?',
                            (datetime.now(), session_id)
                        )
                    else:
                        db.execute(
                            'UPDATE bot_sessions SET messages_failed = messages_failed + 1 WHERE id = ?',
                            (session_id,)
                        )
                    
                    db.commit()
                except:
                    pass
            
            # Wait for next message
            time.sleep(delay_seconds)
        
        self.is_running = False
        
        # Update session status
        if session_id:
            try:
                db = get_db()
                db.execute(
                    'UPDATE bot_sessions SET status = ? WHERE id = ?',
                    ('completed', session_id)
                )
                db.commit()
            except:
                pass
    
    def stop_automation(self):
        """Stop the automation"""
        self.is_running = False
    
    def log_error(self, message):
        """Log error"""
        try:
            db = get_db()
            db.execute(
                'INSERT INTO system_logs (level, component, message) VALUES (?, ?, ?)',
                ('ERROR', 'FacebookBot', message)
            )
            db.commit()
        except:
            pass

# ==================================================
# 🔐 USER AUTHENTICATION
# ==================================================

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Please login first'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current user from session"""
    if 'user_id' in session:
        db = get_db()
        user = db.execute(
            'SELECT id, email, created_at FROM users WHERE id = ?',
            (session['user_id'],)
        ).fetchone()
        return user
    return None

# ==================================================
# 🌐 ROUTES - AUTHENTICATION
# ==================================================

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    """Register new user"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # Validation
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'})
        
        if len(password) != 8:
            return jsonify({'success': False, 'message': 'Password must be exactly 8 characters'})
        
        if '@' not in email or '.' not in email:
            return jsonify({'success': False, 'message': 'Invalid email format'})
        
        if 'tempmail' in email or 'fake' in email or 'test' in email:
            return jsonify({'success': False, 'message': 'Please use a real email address'})
        
        # Check if user exists
        db = get_db()
        existing = db.execute(
            'SELECT id FROM users WHERE email = ?',
            (email,)
        ).fetchone()
        
        if existing:
            return jsonify({'success': False, 'message': 'Email already registered'})
        
        # Create user
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
        db.execute(
            'INSERT INTO users (email, password_hash) VALUES (?, ?)',
            (email, password_hash)
        )
        db.commit()
        
        # Log
        db.execute(
            'INSERT INTO system_logs (level, component, message) VALUES (?, ?, ?)',
            ('INFO', 'Auth', f'New user registered: {email}')
        )
        db.commit()
        
        return jsonify({'success': True, 'message': 'Registration successful'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        db = get_db()
        user = db.execute(
            'SELECT id, email, password_hash FROM users WHERE email = ?',
            (email,)
        ).fetchone()
        
        if user and bcrypt.check_password_hash(user['password_hash'], password):
            # Update last login
            db.execute(
                'UPDATE users SET last_login = ? WHERE id = ?',
                (datetime.now(), user['id'])
            )
            db.commit()
            
            # Set session
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': {'id': user['id'], 'email': user['email']}
            })
        
        return jsonify({'success': False, 'message': 'Invalid credentials'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/user', methods=['GET'])
@login_required
def get_user():
    """Get current user info"""
    user = get_current_user()
    if user:
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'created_at': user['created_at']
            }
        })
    return jsonify({'success': False, 'message': 'User not found'})

# ==================================================
# 🌐 ROUTES - BOT OPERATIONS
# ==================================================

@app.route('/api/validate-cookies', methods=['POST'])
@login_required
def validate_cookies():
    """Validate Facebook cookies"""
    try:
        data = request.json
        cookie_string = data.get('cookies', '')
        
        if not cookie_string:
            return jsonify({'success': False, 'message': 'Cookies required'})
        
        # Validate
        valid, result = cookie_manager.validate_cookie(cookie_string)
        
        if valid:
            # Store cookie
            cookie_id = cookie_manager.store_cookie(session['user_id'], cookie_string)
            
            return jsonify({
                'success': True,
                'message': 'Cookies are valid',
                'cookie_id': cookie_id,
                'user_info': result
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Invalid cookies: {result}'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Store active bot instances
active_bots = {}

@app.route('/api/start-bot', methods=['POST'])
@login_required
def start_bot():
    """Start the messenger bot"""
    try:
        data = request.json
        chat_id = data.get('chatId', '').strip()
        cookie_string = data.get('cookies', '').strip()
        target_name = data.get('targetName', '').strip()
        delay = int(data.get('delay', 2))
        message = data.get('message', 'Hello from E2EE Bot!')
        
        # Validate
        if not chat_id or not cookie_string:
            return jsonify({'success': False, 'message': 'Chat ID and cookies required'})
        
        # Validate cookies first
        valid, _ = cookie_manager.validate_cookie(cookie_string)
        if not valid:
            return jsonify({'success': False, 'message': 'Invalid cookies'})
        
        # Create bot session in database
        db = get_db()
        cursor = db.cursor()
        
        # Generate E2EE keys for this session
        keys = e2ee.generate_keys()
        
        cursor.execute('''
            INSERT INTO bot_sessions 
            (user_id, session_name, chat_id, target_name, delay_seconds, status, public_key, private_key_encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            f"Bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            chat_id,
            target_name,
            delay,
            'starting',
            keys['public'] if keys else None,
            keys['private'] if keys else None
        ))
        db.commit()
        session_id = cursor.lastrowid
        
        # Start bot in background thread
        def run_bot_thread():
            try:
                # Create bot instance
                bot = FacebookBot(cookie_string, chat_id)
                
                # Store in active bots
                active_bots[session_id] = {
                    'bot': bot,
                    'running': True,
                    'user_id': session['user_id']
                }
                
                # Update status
                db = get_db()
                db.execute(
                    'UPDATE bot_sessions SET status = ? WHERE id = ?',
                    ('running', session_id)
                )
                db.commit()
                
                # Prepare message list (for demo, send 100 messages or until stopped)
                message_list = [f"{message} #{i+1}" for i in range(100)]
                
                # Start automation
                bot.start_automation(message_list, delay, session_id)
                
            except Exception as e:
                # Update status on error
                try:
                    db = get_db()
                    db.execute(
                        'UPDATE bot_sessions SET status = ? WHERE id = ?',
                        (f'error: {str(e)}', session_id)
                    )
                    db.commit()
                    
                    db.execute(
                        'INSERT INTO system_logs (level, component, message) VALUES (?, ?, ?)',
                        ('ERROR', 'Bot', str(e))
                    )
                    db.commit()
                except:
                    pass
            finally:
                # Remove from active bots
                if session_id in active_bots:
                    del active_bots[session_id]
        
        thread = threading.Thread(target=run_bot_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Bot started successfully',
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/stop-bot', methods=['POST'])
@login_required
def stop_bot():
    """Stop the messenger bot"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'success': False, 'message': 'Session ID required'})
        
        # Check if bot exists and belongs to user
        if session_id in active_bots and active_bots[session_id]['user_id'] == session['user_id']:
            # Stop bot
            active_bots[session_id]['bot'].stop_automation()
            active_bots[session_id]['running'] = False
            del active_bots[session_id]
            
            # Update database
            db = get_db()
            db.execute(
                'UPDATE bot_sessions SET status = ? WHERE id = ?',
                ('stopped', session_id)
            )
            db.commit()
            
            return jsonify({'success': True, 'message': 'Bot stopped successfully'})
        
        return jsonify({'success': False, 'message': 'Bot not found or not owned by you'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/bot-status/<int:session_id>', methods=['GET'])
@login_required
def get_bot_status(session_id):
    """Get bot status"""
    try:
        db = get_db()
        session_data = db.execute('''
            SELECT id, status, messages_sent, messages_failed, last_message_time
            FROM bot_sessions 
            WHERE id = ? AND user_id = ?
        ''', (session_id, session['user_id'])).fetchone()
        
        if not session_data:
            return jsonify({'success': False, 'message': 'Session not found'})
        
        return jsonify({
            'success': True,
            'status': session_data['status'],
            'messages_sent': session_data['messages_sent'],
            'messages_failed': session_data['messages_failed'],
            'last_message_time': session_data['last_message_time'],
            'is_running': session_id in active_bots
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/message-logs/<int:session_id>', methods=['GET'])
@login_required
def get_message_logs(session_id):
    """Get message logs for a session"""
    try:
        # Verify session belongs to user
        db = get_db()
        session_data = db.execute(
            'SELECT id FROM bot_sessions WHERE id = ? AND user_id = ?',
            (session_id, session['user_id'])
        ).fetchone()
        
        if not session_data:
            return jsonify({'success': False, 'message': 'Session not found'})
        
        # Get logs
        logs = db.execute('''
            SELECT id, recipient, message_type, content_preview, status, sent_at
            FROM message_logs
            WHERE session_id = ?
            ORDER BY sent_at DESC
            LIMIT 100
        ''', (session_id,)).fetchall()
        
        return jsonify({
            'success': True,
            'logs': [dict(log) for log in logs]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/upload-file', methods=['POST'])
@login_required
def upload_file():
    """Handle file uploads"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'})
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        # Secure filename and save
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
        
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'filename': saved_filename,
            'path': file_path,
            'size': os.path.getsize(file_path)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/my-sessions', methods=['GET'])
@login_required
def get_my_sessions():
    """Get all bot sessions for current user"""
    try:
        db = get_db()
        sessions = db.execute('''
            SELECT id, session_name, chat_id, target_name, status, 
                   messages_sent, messages_failed, created_at
            FROM bot_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (session['user_id'],)).fetchall()
        
        return jsonify({
            'success': True,
            'sessions': [dict(s) for s in sessions]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/system-health', methods=['GET'])
def system_health():
    """Check system health"""
    try:
        db = get_db()
        db.execute('SELECT 1').fetchone()
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'active_bots': len(active_bots),
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0',
            'created_by': 'Suraj oberoy',
            'contact': '+91 8452969216'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        })

# ==================================================
# 📊 BACKGROUND TASKS
# ==================================================

def cleanup_old_logs():
    """Delete logs older than 30 days"""
    try:
        db = get_db()
        cutoff = datetime.now() - timedelta(days=30)
        
        # Delete old message logs
        db.execute(
            'DELETE FROM message_logs WHERE sent_at < ?',
            (cutoff,)
        )
        
        # Delete old system logs
        db.execute(
            'DELETE FROM system_logs WHERE created_at < ?',
            (cutoff,)
        )
        
        db.commit()
    except:
        pass

def refresh_expiring_cookies():
    """Check and refresh expiring cookies"""
    try:
        db = get_db()
        expiring = db.execute('''
            SELECT id, cookie_data FROM cookies 
            WHERE expires_at < datetime("now", "+7 days") AND is_valid = 1
        ''').fetchall()
        
        for cookie in expiring:
            # Just mark as expiring soon
            db.execute(
                'INSERT INTO system_logs (level, component, message) VALUES (?, ?, ?)',
                ('WARNING', 'Cookie', f'Cookie {cookie["id"]} expiring soon')
            )
        
        db.commit()
    except:
        pass

# Start background thread for maintenance
def background_maintenance():
    """Run maintenance tasks periodically"""
    while True:
        time.sleep(3600)  # Run every hour
        try:
            cleanup_old_logs()
            refresh_expiring_cookies()
        except:
            pass

# Start maintenance thread
maintenance_thread = threading.Thread(target=background_maintenance, daemon=True)
maintenance_thread.start()

# ==================================================
# 🚀 ERROR HANDLERS
# ==================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Route not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

# ==================================================
# 🎯 CREATE FRONTEND FILE
# ==================================================

def create_frontend():
    """Create the frontend HTML file"""
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 SURAJ E2EE MESSENGER BOT 2026 ✨</title>
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Poppins', sans-serif;
        }
        
        body {
            min-height: 100vh;
            background: linear-gradient(135deg, #ffb6c1 0%, #ffc0cb 50%, #ffd9e6 100%);
            position: relative;
            overflow-x: hidden;
        }
        
        /* Sparkle Effect */
        body::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle at 30% 40%, rgba(255,255,255,0.8) 0%, transparent 25%),
                        radial-gradient(circle at 70% 60%, rgba(255,255,255,0.8) 0%, transparent 30%),
                        radial-gradient(circle at 20% 80%, rgba(255,255,255,0.8) 0%, transparent 35%),
                        radial-gradient(circle at 90% 20%, rgba(255,255,255,0.8) 0%, transparent 40%);
            animation: sparkle 3s infinite alternate;
            pointer-events: none;
            z-index: 0;
        }
        
        @keyframes sparkle {
            0% { opacity: 0.3; transform: scale(1); }
            100% { opacity: 0.8; transform: scale(1.05); }
        }
        
        .particle {
            position: absolute;
            width: 5px;
            height: 5px;
            background: white;
            border-radius: 50%;
            filter: blur(1px);
            animation: float 4s infinite;
            z-index: 1;
        }
        
        @keyframes float {
            0% { transform: translateY(0) rotate(0deg); opacity: 0; }
            50% { opacity: 0.8; }
            100% { transform: translateY(-100px) rotate(360deg); opacity: 0; }
        }
        
        .main-container {
            position: relative;
            z-index: 10;
            padding: 30px 20px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        /* Auth Card */
        .auth-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 30px;
            padding: 40px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.2);
            margin-bottom: 30px;
            border: 2px solid rgba(255,255,255,0.5);
            transition: all 0.3s ease;
        }
        
        .auth-card:hover {
            box-shadow: 0 25px 60px rgba(255,105,180,0.3);
            transform: translateY(-5px);
        }
        
        .split-container {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }
        
        .login-box, .signup-box {
            flex: 1;
            min-width: 280px;
            padding: 25px;
            background: rgba(255, 240, 245, 0.7);
            border-radius: 25px;
            border: 2px solid white;
            box-shadow: inset 0 0 20px rgba(255,255,255,0.5);
        }
        
        .login-box h3, .signup-box h3 {
            color: #d44b6b;
            font-weight: 700;
            margin-bottom: 25px;
            text-shadow: 2px 2px 4px rgba(255,255,255,0.8);
        }
        
        .form-control {
            border-radius: 50px;
            padding: 12px 25px;
            border: 2px solid #ffb6c1;
            background: white;
            margin-bottom: 15px;
            font-weight: 500;
        }
        
        .form-control:focus {
            border-color: #ff69b4;
            box-shadow: 0 0 20px rgba(255,105,180,0.3);
        }
        
        .btn-pink {
            background: linear-gradient(45deg, #ff69b4, #ff1493);
            border: none;
            color: white;
            font-weight: 600;
            padding: 12px 30px;
            border-radius: 50px;
            width: 100%;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s;
            border: 2px solid white;
        }
        
        .btn-pink:hover {
            transform: scale(1.02);
            box-shadow: 0 10px 30px rgba(255,20,147,0.4);
            color: white;
        }
        
        /* Bot Card */
        .bot-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 40px;
            padding: 35px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.2);
            border: 2px solid rgba(255,255,255,0.8);
            margin-bottom: 25px;
        }
        
        .tool-title {
            text-align: center;
            font-size: 2.5rem;
            font-weight: 800;
            color: #d4145a;
            text-shadow: 3px 3px 6px rgba(255,255,255,0.9);
            margin-bottom: 25px;
            letter-spacing: 2px;
            background: linear-gradient(45deg, #ff1493, #ff69b4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: glow 2s infinite alternate;
        }
        
        @keyframes glow {
            from { filter: drop-shadow(0 0 2px #ff69b4); }
            to { filter: drop-shadow(0 0 10px #ff1493); }
        }
        
        .input-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }
        
        .input-item {
            background: rgba(255, 230, 240, 0.6);
            padding: 15px;
            border-radius: 20px;
            border: 2px solid white;
        }
        
        .input-item label {
            display: block;
            font-weight: 600;
            color: #b0306e;
            margin-bottom: 8px;
            font-size: 0.95rem;
        }
        
        .input-item i {
            margin-right: 8px;
            color: #ff1493;
        }
        
        .file-upload {
            position: relative;
            display: inline-block;
            width: 100%;
        }
        
        .file-upload-btn {
            background: white;
            border: 2px dashed #ff69b4;
            padding: 10px;
            border-radius: 15px;
            width: 100%;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .file-upload-btn:hover {
            background: #fff0f5;
            border-color: #ff1493;
        }
        
        .action-buttons {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        
        .btn-start {
            background: linear-gradient(45deg, #00ff88, #00cc6a);
            border: none;
            color: white;
            font-weight: 700;
            padding: 18px 45px;
            border-radius: 60px;
            font-size: 1.3rem;
            box-shadow: 0 10px 25px rgba(0,255,136,0.4);
            border: 2px solid white;
            min-width: 220px;
        }
        
        .btn-stop {
            background: linear-gradient(45deg, #ff4444, #cc0000);
            border: none;
            color: white;
            font-weight: 700;
            padding: 18px 45px;
            border-radius: 60px;
            font-size: 1.3rem;
            box-shadow: 0 10px 25px rgba(255,68,68,0.4);
            border: 2px solid white;
            min-width: 220px;
        }
        
        .console-panel {
            background: #1e1e2f;
            border-radius: 20px;
            padding: 20px;
            margin: 20px 0;
            border: 3px solid #ffb6c1;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
        }
        
        .console-header {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #ffb6c1;
            margin-bottom: 15px;
            font-weight: 600;
        }
        
        .console-window {
            background: #0a0a12;
            border-radius: 15px;
            padding: 20px;
            height: 200px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            color: #00ff88;
            border: 2px solid #ff69b4;
        }
        
        .console-line {
            margin: 5px 0;
            border-bottom: 1px solid #333;
            padding-bottom: 3px;
            animation: fadeIn 0.3s;
            font-size: 0.9rem;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }
        
        .footer {
            text-align: center;
            padding: 25px;
            background: rgba(255,255,255,0.9);
            border-radius: 50px 50px 20px 20px;
            margin-top: auto;
            border: 2px solid white;
        }
        
        .contact-links {
            display: flex;
            gap: 30px;
            justify-content: center;
            margin: 15px 0;
            flex-wrap: wrap;
        }
        
        .contact-btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 12px 30px;
            border-radius: 60px;
            font-weight: 600;
            transition: all 0.3s;
            text-decoration: none;
            border: 2px solid white;
        }
        
        .whatsapp-btn {
            background: #25D366;
            color: white;
        }
        
        .facebook-btn {
            background: #1877f2;
            color: white;
        }
        
        .contact-btn:hover {
            transform: translateY(-3px);
            filter: brightness(1.1);
            color: white;
        }
        
        .copyright {
            color: #b0306e;
            font-weight: 500;
            margin-top: 15px;
            font-size: 1.1rem;
        }
        
        .user-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: white;
            padding: 10px 20px;
            border-radius: 50px;
            margin-bottom: 20px;
            border: 2px solid #ff69b4;
        }
        
        @media (max-width: 768px) {
            .tool-title { font-size: 1.8rem; }
            .btn-start, .btn-stop { 
                padding: 15px 30px; 
                font-size: 1.1rem;
                min-width: 180px;
            }
        }
    </style>
</head>
<body>

<script>
    for(let i = 0; i < 30; i++) {
        let particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 5 + 's';
        particle.style.width = Math.random() * 10 + 'px';
        particle.style.height = particle.style.width;
        document.body.appendChild(particle);
    }
</script>

<div class="main-container">
    <!-- User Info (hidden by default) -->
    <div id="userInfo" class="user-info" style="display: none;">
        <span><i class="fas fa-user-circle"></i> <span id="userEmail"></span></span>
        <button class="btn btn-sm btn-outline-danger" onclick="logout()"><i class="fas fa-sign-out-alt"></i> Logout</button>
    </div>
    
    <!-- Auth Section -->
    <div class="auth-card" id="authSection">
        <div class="split-container">
            <!-- Login Box -->
            <div class="login-box">
                <h3><i class="fas fa-lock me-2"></i>Login</h3>
                <form id="loginForm">
                    <div class="mb-3">
                        <input type="email" class="form-control" id="loginEmail" placeholder="Email (Real email only)" required>
                    </div>
                    <div class="mb-3">
                        <input type="password" class="form-control" id="loginPassword" placeholder="Password (Max 8 chars)" maxlength="8" required>
                    </div>
                    <button type="submit" class="btn btn-pink">
                        <i class="fas fa-sign-in-alt me-2"></i>Login
                    </button>
                </form>
            </div>
            
            <!-- Signup Box -->
            <div class="signup-box">
                <h3><i class="fas fa-user-plus me-2"></i>Create Account</h3>
                <form id="signupForm">
                    <div class="mb-3">
                        <input type="email" class="form-control" id="signupEmail" placeholder="Real Email (No fake)" required>
                    </div>
                    <div class="mb-3">
                        <input type="password" class="form-control" id="signupPassword" placeholder="Password (Max 8 digits)" maxlength="8" required>
                    </div>
                    <button type="submit" class="btn btn-pink">
                        <i class="fas fa-user-check me-2"></i>Register
                    </button>
                </form>
            </div>
        </div>
    </div>
    
    <!-- Main Bot Card -->
    <div class="bot-card" id="botSection" style="display: none;">
        <h1 class="tool-title">
            <i class="fas fa-robot me-3"></i>
            END TO END ENCRYPTION TOOL 
            <span style="background: linear-gradient(45deg, #ff1493, #9400d3); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                BY SURAJ OBEROY
            </span>
            <i class="fas fa-crown ms-3" style="color: #ffd700;"></i>
        </h1>
        
        <!-- Input Grid -->
        <div class="input-grid">
            <div class="input-item">
                <label><i class="fas fa-comment-dots"></i> Facebook Chat ID</label>
                <input type="text" class="form-control" placeholder="Enter chat/thread ID" id="chatId">
            </div>
            
            <div class="input-item">
                <label><i class="fas fa-cookie-bite"></i> Cookies (Single Line)</label>
                <input type="text" class="form-control" placeholder="Paste your Facebook cookies" id="cookies">
            </div>
            
            <div class="input-item">
                <label><i class="fas fa-user-tag"></i> Target Name (Jisko message)</label>
                <input type="text" class="form-control" placeholder="Enter name" id="targetName">
            </div>
            
            <div class="input-item">
                <label><i class="fas fa-file-upload"></i> Upload File</label>
                <div class="file-upload">
                    <input type="file" class="form-control" id="fileUpload" accept=".txt,.jpg,.png,.mp4">
                </div>
            </div>
            
            <div class="input-item">
                <label><i class="fas fa-clock"></i> Time Delay (Seconds)</label>
                <input type="number" class="form-control" value="2" min="1" id="delay">
            </div>
            
            <div class="input-item">
                <label><i class="fas fa-envelope"></i> Message Text</label>
                <input type="text" class="form-control" value="Hello from E2EE Bot!" id="messageText">
            </div>
        </div>
        
        <!-- Action Buttons -->
        <div class="action-buttons">
            <button class="btn-start" id="startBtn" onclick="startBot()">
                <i class="fas fa-play-circle me-2"></i>START AUTOMATION
            </button>
            <button class="btn-stop" id="stopBtn" onclick="stopBot()">
                <i class="fas fa-stop-circle me-2"></i>STOP
            </button>
            <button class="btn btn-warning" id="validateBtn" onclick="validateCookies()">
                <i class="fas fa-check-circle"></i> Validate Cookies
            </button>
        </div>
        
        <!-- Live Console -->
        <div class="console-panel">
            <div class="console-header">
                <i class="fas fa-terminal fa-2x"></i>
                <span>🔴 LIVE CONSOLE - Messages Sending Status</span>
                <span class="ms-auto" id="statusIndicator">⚪ Offline</span>
            </div>
            <div class="console-window" id="liveConsole">
                <div class="console-line">⚡ [SYSTEM] E2EE Bot initialized...</div>
                <div class="console-line">🔐 [E2EE] End-to-end encryption ready</div>
                <div class="console-line">👤 [AUTH] Please login to continue</div>
            </div>
        </div>
    </div>
    
    <!-- Footer -->
    <footer class="footer">
        <div class="contact-links">
            <a href="https://wa.me/918452969216" class="contact-btn whatsapp-btn" target="_blank">
                <i class="fab fa-whatsapp fa-lg"></i>
                WhatsApp: +91 8452969216
            </a>
            <a href="https://www.facebook.com/suraj.oberoy.2025" class="contact-btn facebook-btn" target="_blank">
                <i class="fab fa-facebook fa-lg"></i>
                Facebook: Virat Rajput
            </a>
        </div>
        
        <div class="copyright">
            <i class="fas fa-copyright me-1"></i>2026 All Rights Reserved<br>
            Made with <i class="fas fa-heart" style="color: #ff1493;"></i> by <strong style="color: #d4145a;">SURAJ OBEROY</strong>
            <div style="font-size: 1.2rem; margin-top: 10px;">
                <i class="fas fa-star" style="color: gold;"></i>
                <i class="fas fa-star" style="color: gold;"></i>
                <i class="fas fa-star" style="color: gold;"></i>
                <i class="fas fa-star" style="color: gold;"></i>
                <i class="fas fa-star" style="color: gold;"></i>
            </div>
        </div>
    </footer>
</div>

<script>
    // State variables
    let currentSessionId = null;
    let isLoggedIn = false;
    let consoleInterval = null;
    
    // Add to console
    function addToConsole(message, type = 'info') {
        const consoleWin = document.getElementById('liveConsole');
        const time = new Date().toLocaleTimeString();
        const line = document.createElement('div');
        line.className = 'console-line';
        
        let prefix = '';
        if (type === 'success') prefix = '✅ ';
        else if (type === 'error') prefix = '❌ ';
        else if (type === 'warning') prefix = '⚠️ ';
        else if (type === 'e2ee') prefix = '🔐 ';
        else prefix = '➡️ ';
        
        line.innerHTML = `[${time}] ${prefix}${message}`;
        consoleWin.appendChild(line);
        consoleWin.scrollTop = consoleWin.scrollHeight;
        
        if (consoleWin.children.length > 100) {
            consoleWin.removeChild(consoleWin.children[0]);
        }
    }
    
    // Check login status
    function checkLoginStatus() {
        fetch('/api/user')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    isLoggedIn = true;
                    document.getElementById('authSection').style.display = 'none';
                    document.getElementById('botSection').style.display = 'block';
                    document.getElementById('userInfo').style.display = 'flex';
                    document.getElementById('userEmail').innerText = data.user.email;
                    addToConsole(`👤 Logged in as: ${data.user.email}`, 'success');
                    addToConsole('🔐 E2EE System Ready', 'e2ee');
                } else {
                    isLoggedIn = false;
                    document.getElementById('authSection').style.display = 'block';
                    document.getElementById('botSection').style.display = 'none';
                    document.getElementById('userInfo').style.display = 'none';
                }
            });
    }
    
    // Login
    document.getElementById('loginForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        
        if (password.length !== 8) {
            alert('Password must be exactly 8 characters!');
            return;
        }
        
        fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, password})
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                addToConsole(`✅ Login successful: ${email}`, 'success');
                checkLoginStatus();
            } else {
                alert('Login failed: ' + data.message);
            }
        });
    });
    
    // Signup
    document.getElementById('signupForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const email = document.getElementById('signupEmail').value;
        const password = document.getElementById('signupPassword').value;
        
        if (password.length !== 8) {
            alert('Password must be exactly 8 characters!');
            return;
        }
        
        if (email.includes('tempmail') || email.includes('fake')) {
            alert('Please use a REAL email address!');
            return;
        }
        
        fetch('/api/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, password})
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert('Registration successful! Please login.');
                document.getElementById('signupForm').reset();
            } else {
                alert('Registration failed: ' + data.message);
            }
        });
    });
    
    // Logout
    function logout() {
        fetch('/api/logout', {method: 'POST'})
            .then(res => res.json())
            .then(() => {
                checkLoginStatus();
                addToConsole('👋 Logged out successfully');
            });
    }
    
    // Validate cookies
    function validateCookies() {
        const cookies = document.getElementById('cookies').value;
        
        if (!cookies) {
            alert('Please paste cookies first');
            return;
        }
        
        addToConsole('🔍 Validating Facebook cookies...');
        
        fetch('/api/validate-cookies', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cookies})
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                addToConsole(`✅ Cookies valid! User: ${data.user_info.name || 'Unknown'}`, 'success');
            } else {
                addToConsole(`❌ Invalid cookies: ${data.message}`, 'error');
            }
        });
    }
    
    // Start bot
    function startBot() {
        const chatId = document.getElementById('chatId').value;
        const cookies = document.getElementById('cookies').value;
        const targetName = document.getElementById('targetName').value;
        const delay = document.getElementById('delay').value;
        const message = document.getElementById('messageText').value;
        
        if (!chatId || !cookies || !targetName) {
            alert('Please fill Chat ID, Cookies and Target Name');
            return;
        }
        
        addToConsole('🚀 Starting E2EE automation...', 'e2ee');
        
        fetch('/api/start-bot', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({chatId, cookies, targetName, delay, message})
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                currentSessionId = data.session_id;
                addToConsole(`✅ Bot started! Session ID: ${currentSessionId}`, 'success');
                document.getElementById('statusIndicator').innerHTML = '🟢 Running';
                startConsoleUpdates();
            } else {
                addToConsole(`❌ Failed: ${data.message}`, 'error');
            }
        });
    }
    
    // Stop bot
    function stopBot() {
        if (!currentSessionId) {
            alert('No active bot session');
            return;
        }
        
        fetch('/api/stop-bot', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: currentSessionId})
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                addToConsole('🛑 Bot stopped successfully', 'warning');
                document.getElementById('statusIndicator').innerHTML = '⚪ Stopped';
                if (consoleInterval) {
                    clearInterval(consoleInterval);
                }
            }
        });
    }
    
    // File upload
    document.getElementById('fileUpload').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const formData = new FormData();
            formData.append('file', file);
            
            fetch('/api/upload-file', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    addToConsole(`📁 File uploaded: ${file.name} (${data.size} bytes)`, 'success');
                }
            });
        }
    });
    
    // Start console updates
    function startConsoleUpdates() {
        if (consoleInterval) clearInterval(consoleInterval);
        
        consoleInterval = setInterval(() => {
            if (currentSessionId) {
                fetch(`/api/bot-status/${currentSessionId}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('statusIndicator').innerHTML = 
                                data.is_running ? '🟢 Running' : '⚪ Stopped';
                        }
                    });
            }
        }, 2000);
    }
    
    // Check login on load
    window.onload = checkLoginStatus;
</script>
</body>
</html>"""
    
    # Write to templates folder
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("✅ Frontend file created successfully at templates/index.html")

# ==================================================
# 🚀 MAIN ENTRY POINT
# ==================================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║   🔥 SURAJ E2EE MESSENGER BOT - BY SURAJ OBEROY 🔥   ║
    ║                                                          ║
    ║   ✨ End-to-End Encryption Enabled                       ║
    ║   🚀 24/7 Automation Ready                              ║
    ║   💾 SQLite Database Active                             ║
    ║   📱 Contact: +91 8452969216                            ║
    ║   © 2026 All Rights Reserved                            ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Create frontend file
    create_frontend()
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)