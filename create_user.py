# create_user.py
import sqlite3
import bcrypt

conn = sqlite3.connect("users.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT
)
""")

def add_user(username, password, role="user"):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    c.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, hashed, role)
    )
    conn.commit()

add_user("admin", "CHANGE_THIS_PASSWORD", "admin")
print("Admin created")

conn.close()
