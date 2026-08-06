import sqlite3
import bcrypt
from getpass import getpass

username = "admin"
new_pw = getpass("New password for admin: ")

conn = sqlite3.connect("users.db")
cur = conn.cursor()
pw_hash = bcrypt.hashpw(new_pw.encode("utf-8"), bcrypt.gensalt())
cur.execute("UPDATE users SET password_hash=? WHERE username=?", (pw_hash, username))
conn.commit()
conn.close()

print("Admin password updated.")
