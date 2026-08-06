"""
Fix database schema to remove UNIQUE constraint from task_name
"""

import sqlite3
import os

def fix_database_schema():
    """Remove UNIQUE constraint from task_name column"""
    
    # Find the database
    possible_paths = [
        "ml_module.db",
        os.path.join("biotech-lab-main", "ml_module.db"),
        os.path.join(os.path.dirname(__file__), "ml_module.db"),
        os.path.join(os.path.dirname(__file__), "biotech-lab-main", "ml_module.db"),
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ Could not find ml_module.db")
        return
    
    print(f"✅ Found database at: {db_path}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("PRAGMA table_info(trained_models)")
    columns = cursor.fetchall()
    print("\n📊 Current schema:")
    for col in columns:
        unique = "UNIQUE" if col[5] == 1 else ""
        print(f"  {col[1]}: {col[2]} {unique}")
    
    # Get the SQL for the current table
    cursor.execute("""
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='trained_models'
    """)
    current_sql = cursor.fetchone()
    if current_sql:
        print(f"\n📄 Current table definition:\n{current_sql[0]}\n")
    
    # Check if task_name has a unique constraint
    has_unique_constraint = False
    if current_sql and 'task_name' in current_sql[0] and 'UNIQUE' in current_sql[0]:
        has_unique_constraint = True
        print("⚠️ Found UNIQUE constraint on task_name in table definition")
    
    if has_unique_constraint:
        print("\n🔄 Recreating table without UNIQUE constraint...\n")
        
        # Backup existing data
        cursor.execute("SELECT * FROM trained_models")
        rows = cursor.fetchall()
        cursor.execute("PRAGMA table_info(trained_models)")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        print(f"📦 Backed up {len(rows)} records")
        
        # Create new table without unique constraint
        cursor.execute("""
            CREATE TABLE trained_models_new (
                id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                model_type TEXT NOT NULL,
                task_type TEXT NOT NULL,
                target_variable TEXT NOT NULL,
                created_at TIMESTAMP,
                n_training_samples INTEGER,
                n_features INTEGER,
                train_score REAL,
                validation_score REAL,
                model_path TEXT NOT NULL,
                preprocessing_path TEXT,
                task_config TEXT,
                evaluation_summary TEXT,
                metadata_json TEXT
            )
        """)
        
        # Copy data to new table
        placeholders = ','.join(['?' for _ in column_names])
        cursor.execute(f"""
            INSERT INTO trained_models_new ({','.join(column_names)})
            SELECT {','.join(column_names)} FROM trained_models
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE trained_models")
        cursor.execute("ALTER TABLE trained_models_new RENAME TO trained_models")
        
        conn.commit()
        print("✅ Table recreated successfully without UNIQUE constraint")
    else:
        print("\n✅ No unique constraint found on task_name")
    
    # Verify the fix
    cursor.execute("PRAGMA table_info(trained_models)")
    columns = cursor.fetchall()
    print("\n📊 New schema:")
    for col in columns:
        unique = "UNIQUE" if col[5] == 1 else ""
        print(f"  {col[1]}: {col[2]} {unique}")
    
    cursor.execute("""
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='trained_models'
    """)
    new_sql = cursor.fetchone()
    if new_sql:
        print(f"\n📄 New table definition:\n{new_sql[0]}\n")
    
    conn.close()
    print("✅ Database schema fix completed!")

if __name__ == "__main__":
    fix_database_schema()
