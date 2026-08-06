#!/usr/bin/env python3
"""Verify trials in database and session state"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = Path(__file__).parent / "trial_registry.db"

print("=" * 60)
print("TRIAL REGISTRY VERIFICATION")
print("=" * 60)

# Check if database file exists
if not DB_PATH.exists():
    print(f"❌ DATABASE NOT FOUND: {DB_PATH}")
else:
    print(f"✅ Database found at: {DB_PATH}")
    print(f"   File size: {DB_PATH.stat().st_size} bytes")
    print()
    
    # Check database contents
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check table structure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📊 Database Tables: {[table[0] for table in tables]}")
        print()
        
        # Get all trials
        if tables:
            cursor.execute("SELECT * FROM trials ORDER BY creation_timestamp DESC")
            rows = cursor.fetchall()
            print(f"📋 Total Trials in Database: {len(rows)}")
            print()
            
            if rows:
                print("Latest 10 Trials:")
                print("-" * 110)
                for i, row in enumerate(rows[:10], 1):
                    trial_dict = dict(row)
                    trial_id = trial_dict.get('trial_id', 'N/A')
                    timestamp = trial_dict.get('creation_timestamp', 'N/A')[:10]  # Get date part
                    disease = trial_dict.get('disease_name', 'N/A')
                    size = str(trial_dict.get('np_size_nm', 'N/A'))
                    status = trial_dict.get('status', 'N/A')
                    print(f"{i:2d}. {trial_id:10s} | {timestamp} | {disease:30s} | Size: {size:4s}nm | {status}")
                print("-" * 110)
                print()
                
                # Show date range
                cursor.execute("SELECT MIN(creation_timestamp), MAX(creation_timestamp) FROM trials")
                date_range = cursor.fetchone()
                if date_range and date_range[0]:
                    min_date = date_range[0][:10]
                    max_date = date_range[1][:10] if date_range[1] else "N/A"
                    print(f"📅 Date Range: {min_date} to {max_date}")
                print()
            else:
                print("⚠️  No trials found in database (database is empty)")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")

# Check sessions file
print()
print("=" * 60)
print("SESSION STATE VERIFICATION")
print("=" * 60)

sessions_file = Path(__file__).parent / "sessions.json"
if sessions_file.exists():
    try:
        with open(sessions_file, 'r') as f:
            sessions_data = json.load(f)
        print(f"✅ Sessions file found: {len(sessions_data)} active sessions")
        if sessions_data:
            for key, session in list(sessions_data.items())[:2]:
                print(f"   User: {session.get('username', 'Unknown')}")
    except Exception as e:
        print(f"❌ Error reading sessions: {e}")
else:
    print("⚠️  No sessions file found")

print()
print("=" * 60)
print(f"✅ Verification completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)
