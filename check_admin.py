#!/usr/bin/env python
"""Check admin user in database"""
import sqlite3

conn = sqlite3.connect('biotech-lab-main/users.db')
cursor = conn.cursor()

cursor.execute('SELECT username, email, role, is_active FROM users WHERE username=?', ('admin',))
result = cursor.fetchone()

if result:
    print('✅ Admin user found:')
    print(f'   Username: {result[0]}')
    print(f'   Email: {result[1]}')
    print(f'   Role: {result[2]}')
    print(f'   Active: {result[3]}')
else:
    print('❌ Admin user NOT found')
    print('\n📋 All users in database:')
    cursor.execute('SELECT username, role, is_active FROM users')
    users = cursor.fetchall()
    if users:
        for user in users:
            print(f'   - {user[0]} ({user[1]}) - Active: {user[2]}')
    else:
        print('   No users found')

conn.close()
