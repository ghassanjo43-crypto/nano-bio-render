"""
🔐 Initialize Admin User on App Startup
This module ensures the admin user exists on Streamlit Cloud (or any fresh deployment)
"""

import os
import sqlite3
import bcrypt
from pathlib import Path

def _require_admin_password():
    """The administrator password from the environment, or None.

    Returns None rather than inventing a default: a default password is one
    every installation shares until somebody remembers to change it, and the
    remembering is the step that gets skipped.
    """
    import os

    value = os.environ.get("NANOBIO_ADMIN_PASSWORD", "")
    return value if value.strip() else None

def ensure_admin_user_exists():
    """
    Ensure admin user exists in database.
    Creates admin/admin if they don't exist.
    Called automatically on app startup.
    """
    try:
        # Get current directory
        db_path = Path("users.db").resolve()
        
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Check if users table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not c.fetchone():
            # Create users table if it doesn't exist
            c.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT,
                    password_hash BLOB NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            """)
            print("✅ Created users table")
        
        # Check if admin user exists
        c.execute("SELECT username FROM users WHERE username = 'admin'")
        admin_exists = c.fetchone()
        
        if not admin_exists:
            # Supplied by the environment. Previously a one-word literal, which
            # meant every database this script ever created shared the same
            # trivially guessable administrator password.
            admin_password = _require_admin_password()
            if admin_password is None:
                print(
                    "SKIPPED: no admin user created. Set "
                    "NANOBIO_ADMIN_PASSWORD to a generated value first:\n"
                    "    python -c \"import secrets; "
                    "print(secrets.token_urlsafe(24))\""
                )
                conn.close()
                return False
            password_hash = bcrypt.hashpw(
                admin_password.encode('utf-8'), bcrypt.gensalt())
            
            # Insert admin user
            c.execute("""
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", "admin@nanobio.local", password_hash, "admin", 1))
            
            conn.commit()
            print("✅ Admin user created: admin "
                  "(password taken from NANOBIO_ADMIN_PASSWORD)")
        else:
            print("✅ Admin user already exists")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"⚠️ Warning: Could not ensure admin user exists: {str(e)}")
        return False

def ensure_admin_in_biotech_lab():
    """
    Ensure admin user exists in biotech-lab-main database too
    """
    try:
        db_path = Path("biotech-lab-main/users.db").resolve()
        
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Check if users table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not c.fetchone():
            # Create users table if it doesn't exist
            c.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT,
                    password_hash BLOB NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            """)
            print("✅ Created biotech-lab-main users table")
        
        # Check if admin user exists
        c.execute("SELECT username FROM users WHERE username = 'admin'")
        admin_exists = c.fetchone()
        
        if not admin_exists:
            # Supplied by the environment. Previously a one-word literal, which
            # meant every database this script ever created shared the same
            # trivially guessable administrator password.
            admin_password = _require_admin_password()
            if admin_password is None:
                print(
                    "SKIPPED: no admin user created. Set "
                    "NANOBIO_ADMIN_PASSWORD to a generated value first:\n"
                    "    python -c \"import secrets; "
                    "print(secrets.token_urlsafe(24))\""
                )
                conn.close()
                return False
            password_hash = bcrypt.hashpw(
                admin_password.encode('utf-8'), bcrypt.gensalt())
            
            # Insert admin user
            c.execute("""
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", "admin@nanobio.local", password_hash, "admin", 1))
            
            conn.commit()
            print("✅ Admin user created in biotech-lab-main: admin / admin")
        else:
            print("✅ Admin user already exists in biotech-lab-main")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"⚠️ Warning: Could not ensure admin user in biotech-lab-main: {str(e)}")
        return False

if __name__ == "__main__":
    ensure_admin_user_exists()
    ensure_admin_in_biotech_lab()
    print("\n✅ Database initialization complete")
