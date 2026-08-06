"""
Test database connection and schema
Verifies that UNIQUE constraint has been removed
"""

import sqlite3
import os

def test_database():
    """Test database connection and schema"""
    
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
    
    # Check if we can insert multiple records with same task_name
    print("🧪 Testing UNIQUE constraint on task_name...\n")
    
    # First, clear test data
    cursor.execute("DELETE FROM trained_models WHERE task_name LIKE 'test_%'")
    conn.commit()
    
    # Insert first record
    cursor.execute("""
        INSERT INTO trained_models 
        (id, task_name, model_type, task_type, target_variable, created_at, model_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ('test1', 'test_task', 'linear', 'regression', 'target', '2024-01-01', '/path'))
    conn.commit()
    print("✅ Inserted first record (id: test1, task: test_task)")
    
    # Insert second record with same task_name
    try:
        cursor.execute("""
            INSERT INTO trained_models 
            (id, task_name, model_type, task_type, target_variable, created_at, model_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('test2', 'test_task', 'random_forest', 'regression', 'target', '2024-01-02', '/path'))
        conn.commit()
        print("✅ Inserted second record (id: test2, task: test_task)")
        print("\n✨ SUCCESS! Can insert multiple records with same task_name - UNIQUE constraint is FIXED!\n")
    except sqlite3.IntegrityError as e:
        print(f"❌ FAILED: UNIQUE constraint error: {e}")
        print("   Run 'python fix_database_schema.py' to fix the schema\n")
    finally:
        # Clean up
        cursor.execute("DELETE FROM trained_models WHERE task_name LIKE 'test_%'")
        conn.commit()
        
        # Show summary
        cursor.execute("SELECT COUNT(*) FROM trained_models")
        count = cursor.fetchone()[0]
        print(f"📊 Database Summary:")
        print(f"   Total trained models: {count}")
        
        conn.close()

if __name__ == "__main__":
    test_database()
