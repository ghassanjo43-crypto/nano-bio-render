"""
🔐 Initialize Admin User on App Startup
This module ensures the admin user exists on Streamlit Cloud (or any fresh deployment)
"""

import os
import sqlite3
import bcrypt
from pathlib import Path

def ensure_admin_user_exists():
    """
    Ensure admin user exists in database.
    Creates admin / <redacted> if they don't exist.
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
            # Hash the password
            password = os.environ.get("NANOBIO_ADMIN_PASSWORD")  # set this yourself
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # Insert admin user
            c.execute("""
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", "admin@nanobio.local", password_hash, "admin", 1))
            
            conn.commit()
            print("✅ Admin user created: admin / <redacted>")
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
            # Hash the password
            password = os.environ.get("NANOBIO_ADMIN_PASSWORD")  # set this yourself
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # Insert admin user
            c.execute("""
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", "admin@nanobio.local", password_hash, "admin", 1))
            
            conn.commit()
            print("✅ Admin user created in biotech-lab-main: admin / <redacted>")
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
