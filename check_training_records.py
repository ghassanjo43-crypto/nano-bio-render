"""
Check and export all training records from the database
"""

import sqlite3
import os
import json
from datetime import datetime

def check_database():
    """Check current database records"""
    
    # Find database
    possible_paths = [
        "ml_module.db",
        os.path.join("biotech-lab-main", "ml_module.db"),
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print(f"❌ Database not found")
        return
    
    print(f"✅ Found database at: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all records ordered by creation time
    cursor.execute("""
        SELECT id, task_name, created_at, model_type, train_score, validation_score, metadata_json
        FROM trained_models 
        ORDER BY created_at DESC
    """)
    records = cursor.fetchall()
    
    print("📊 All Training Records in Database:\n")
    print(f"Total records: {len(records)}\n")
    
    for i, record in enumerate(records, 1):
        print(f"Record {i}:")
        print(f"  ID:         {record[0]}")
        print(f"  Task:       {record[1]}")
        print(f"  Created:    {record[2]}")
        print(f"  Model Type: {record[3]}")
        print(f"  Train R²:   {record[4]:.4f}" if record[4] else "  Train R²:   None")
        print(f"  Valid R²:   {record[5]:.4f}" if record[5] else "  Valid R²:   None")
        
        # Parse version info from metadata
        try:
            metadata = json.loads(record[6]) if record[6] and isinstance(record[6], str) else {}
            if 'version' in metadata:
                print(f"  Version:    {metadata['version']}")
        except:
            pass
        
        print("-" * 60)
    
    conn.close()

if __name__ == "__main__":
    check_database()
