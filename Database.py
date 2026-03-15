#!/usr/bin/env python3
"""
Database Initialization Script for E2EE Messenger
Run this first to create all tables
"""

import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta

def init_database():
    """Initialize database with all required tables"""
    
    # Create database directory if not exists
    os.makedirs('../database', exist_ok=True)
    
    # Database path
    db_path = '../database/e2ee_messenger.db'
    
    # Remove existing database if exists
    if os.path.exists(db_path):
        os.remove(db_path)
        print("✓ Removed existing database")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute('PRAGMA foreign_keys = ON')
    
    print("\n📦 Creating E2EE Database Tables...")
    
    # ============================================
    # USERS TABLE
    # ============================================
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            public_key TEXT,
            private_key_encrypted TEXT,
            fb_uid TEXT,
            fb_cookie_encrypted TEXT,
            avatar TEXT,
            bio TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
            last_login TIMESTAMP,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("  ✓ users table created")
    
    # ============================================
    # SESSIONS TABLE
    # ============================================
    cursor.execute('''
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            cookie_token TEXT UNIQUE NOT NULL,
            cookie_data TEXT,
            user_agent TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    print("  ✓ sessions table created")
    
    # ============================================
    # MESSAGES TABLE
    # ============================================
    cursor.execute('''
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            encrypted_content TEXT NOT NULL,
            encrypted_file TEXT,
            file_name TEXT,
            file_size INTEGER,
            mime_type TEXT,
            signature TEXT,
            key_id TEXT,
            is_delivered BOOLEAN DEFAULT 0,
            is_read BOOLEAN DEFAULT 0,
            is_offline BOOLEAN DEFAULT 0,
            delivery_attempts INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered_at TIMESTAMP,
            read_at TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    print("  ✓ messages table created")
    
    # ============================================
    # OFFLINE QUEUE TABLE
    # ============================================
    cursor.execute('''
        CREATE TABLE offline_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 5,
            next_retry TIMESTAMP,
            is_processed BOOLEAN DEFAULT 0,
            error_message TEXT,
            queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            last_attempt TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    print("  ✓ offline_queue table created")
    
    # ============================================
    # LOGIN ATTEMPTS TABLE
    # ============================================
    cursor.execute('''
        CREATE TABLE login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            ip_address TEXT,
            user_agent TEXT,
            success BOOLEAN DEFAULT 0,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("  ✓ login_attempts table created")
    
    # ============================================
    # USER KEYS TABLE
    # ============================================
    cursor.execute('''
        CREATE TABLE user_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_type TEXT,
            public_key TEXT NOT NULL,
            encrypted_private_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    print("  ✓ user_keys table created")
    
    # ============================================
    # CHATS TABLE
    # ============================================
    cursor.execute('''
        CREATE TABLE chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE NOT NULL,
            name TEXT,
            type TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    print("  ✓ chats table created")
    
    # ============================================
    # CHAT PARTICIPANTS TABLE
    # ============================================
    cursor.execute('''
        CREATE TABLE chat_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_read TIMESTAMP,
            is_admin BOOLEAN DEFAULT 0,
            FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(chat_id, user_id)
        )
    ''')
    print("  ✓ chat_participants table created")
    
    # ============================================
    # CREATE INDEXES
    # ============================================
    print("\n📊 Creating Indexes...")
    
    cursor.execute('CREATE INDEX idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX idx_users_uid ON users(uid)')
    cursor.execute('CREATE INDEX idx_users_last_seen ON users(last_seen)')
    
    cursor.execute('CREATE INDEX idx_sessions_token ON sessions(cookie_token)')
    cursor.execute('CREATE INDEX idx_sessions_expiry ON sessions(expires_at)')
    
    cursor.execute('CREATE INDEX idx_messages_chat ON messages(chat_id)')
    cursor.execute('CREATE INDEX idx_messages_receiver ON messages(receiver_id, is_delivered)')
    
    cursor.execute('CREATE INDEX idx_queue_retry ON offline_queue(next_retry) WHERE is_processed=0')
    
    print("  ✓ All indexes created")
    
    # Commit changes
    conn.commit()
    
    # ============================================
    # VERIFY TABLES
    # ============================================
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("\n" + "="*60)
    print("✅ E2EE DATABASE INITIALIZED SUCCESSFULLY")
    print("="*60)
    print(f"📍 Database Location: {os.path.abspath(db_path)}")
    print(f"📋 Tables Created: {len(tables)}")
    
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"   • {table[0]}: {count} records")
    
    print("="*60)
    
    # Close connection
    conn.close()
    
    return True

def create_test_user():
    """Create a test user for development"""
    conn = sqlite3.connect('../database/e2ee_messenger.db')
    cursor = conn.cursor()
    
    # Test user data
    test_email = "test@example.com"
    test_password = "Test@1234"
    test_username = "Test User"
    
    # Check if test user exists
    cursor.execute("SELECT * FROM users WHERE email = ?", (test_email,))
    if cursor.fetchone():
        print("\n⚠️  Test user already exists")
        conn.close()
        return
    
    # Generate secure values
    uid = "VR" + str(int(datetime.utcnow().timestamp())) + secrets.token_hex(8).upper()
    salt = secrets.token_hex(16)
    
    # Create password hash (simplified for demo)
    peppered = test_password + "E2EE_VIRAT_RAJPUT_2026"
    password_hash = hashlib.sha256((peppered + salt).encode()).hexdigest()
    
    # Insert test user
    cursor.execute('''
        INSERT INTO users (
            uid, username, email, password_hash, salt,
            public_key, private_key_encrypted,
            last_login, last_seen, created_at, is_verified
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        uid, test_username, test_email, password_hash, salt,
        "test_public_key", "test_private_key",
        datetime.utcnow(), datetime.utcnow(), datetime.utcnow(), 1
    ))
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*60)
    print("🎉 TEST USER CREATED SUCCESSFULLY")
    print("="*60)
    print("📧 Email:    test@example.com")
    print("🔑 Password: Test@1234")
    print("🆔 UID:      " + uid)
    print("="*60)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔐 E2EE MESSENGER - DATABASE SETUP v3.0")
    print("="*60)
    print("👤 Created by: Virat Rajput")
    print("📅 Year: 2026")
    print("="*60)
    
    # Initialize database
    if init_database():
        print("\n✨ Database setup complete!")
        
        # Ask for test user
        response = input("\n❓ Create test user? (y/n): ")
        if response.lower() == 'y':
            create_test_user()
        
        print("\n🚀 You can now start the server:")
        print("   cd backend")
        print("   python app.py")
        print("\n🌐 Access at: http://localhost:5000")
    else:
        print("\n❌ Database setup failed!")
