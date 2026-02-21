import sqlite3
import datetime
import os

DB_NAME = "automation.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            whatsapp_no TEXT,
            facebook_id TEXT,
            name_prefix TEXT,
            delay INTEGER,
            cookie_mode TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()

def save_config(data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        INSERT INTO config
        (chat_id, whatsapp_no, facebook_id, name_prefix, delay, cookie_mode, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data["chat_id"],
        data["whatsapp_no"],
        data["facebook_id"],
        data["name_prefix"],
        data["delay"],
        data["cookie_mode"],
        datetime.datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

def log_event(message):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        INSERT INTO logs (message, timestamp)
        VALUES (?, ?)
    """, (message, datetime.datetime.now().isoformat()))

    conn.commit()
    conn.close()

def get_logs(limit=30):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT message FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()

    conn.close()
    return [row[0] for row in rows]
