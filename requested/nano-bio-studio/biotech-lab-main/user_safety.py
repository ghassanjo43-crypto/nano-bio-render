#!/usr/bin/env python
"""
User Data Backup and Safety Feature
Ensures users are never accidentally lost when making updates
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = "users.db"
BACKUP_DIR = Path("user_backups")

def create_backup_directory():
    """Create backup directory if it doesn't exist"""
    BACKUP_DIR.mkdir(exist_ok=True)

def backup_user_database():
    """Create a timestamped backup of the users database"""
    create_backup_directory()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"users_backup_{timestamp}.db"
    
    if Path(DB_PATH).exists():
        shutil.copy2(DB_PATH, backup_file)
        return True, str(backup_file)
    return False, "Database file not found"

def list_backups():
    """List all available backups"""
    create_backup_directory()
    backups = sorted(BACKUP_DIR.glob("users_backup_*.db"), reverse=True)
    return backups

def restore_from_backup(backup_file):
    """Restore database from a backup file"""
    backup_path = Path(backup_file)
    
    if not backup_path.exists():
        return False, "Backup file not found"
    
    try:
        # Create a backup of current database first
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup = BACKUP_DIR / f"users_backup_before_restore_{timestamp}.db"
        if Path(DB_PATH).exists():
            shutil.copy2(DB_PATH, current_backup)
        
        # Restore from backup
        shutil.copy2(backup_path, DB_PATH)
        return True, f"Database restored from {backup_path.name}"
    except Exception as e:
        return False, f"Error restoring backup: {str(e)}"

def get_user_count():
    """Get total number of users in database"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

def verify_user_persistence(username: str) -> bool:
    """Verify that a user was successfully saved to database"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        result = cur.fetchone()
        conn.close()
        return result is not None
    except:
        return False

if __name__ == "__main__":
    print("User Data Safety Features")
    print("=" * 50)
    
    # Test backup
    success, msg = backup_user_database()
    print(f"Backup: {'✅' if success else '❌'} {msg}")
    
    # Show user count
    count = get_user_count()
    print(f"Users in database: {count}")
    
    # List backups
    backups = list_backups()
    print(f"Total backups: {len(backups)}")
    if backups:
        print("Recent backups:")
        for backup in backups[:5]:
            print(f"  - {backup.name}")
