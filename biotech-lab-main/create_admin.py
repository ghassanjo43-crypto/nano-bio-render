#!/usr/bin/env python
"""Create admin user with proper bcrypt hashing"""

import os
import sqlite3
import bcrypt
from datetime import datetime

DB_PATH = "users.db"

# Connect to database
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# Create users table if it doesn't exist
cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'student',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        last_activity TIMESTAMP,
        session_start TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )
''')

# Read the password from the environment; never hard-code one.
password = os.environ.get("NANOBIO_ADMIN_PASSWORD", "")
if not password.strip():
    raise SystemExit(
        "ERROR: NANOBIO_ADMIN_PASSWORD is not set.\n"
        "This script creates a real administrator account and no longer has a\n"
        "built-in password. Generate one and re-run:\n"
        '    python -c "import secrets; print(secrets.token_urlsafe(24))"'
    )
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# Check if admin already exists
cur.execute("SELECT username FROM users WHERE username = ?", ("admin",))
if cur.fetchone():
    # Update existing admin
    cur.execute(
        "UPDATE users SET password_hash = ?, is_active = 1 WHERE username = ?",
        (hashed, "admin")
    )
    print("✅ Admin password updated")
else:
    # Create new admin
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        """INSERT INTO users 
           (username, email, password_hash, role, created_at, is_active) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("admin", "admin@example.com", hashed, "admin", now, 1)
    )
    print("✅ Admin user created")

conn.commit()
conn.close()

print("\n" + "="*60)
print("ADMIN CREDENTIALS")
print("="*60)
print(f"Username: admin")
print("Password: (as supplied in NANOBIO_ADMIN_PASSWORD)")
print("="*60)
