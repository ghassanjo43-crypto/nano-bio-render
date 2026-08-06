import sqlite3
import os
from datetime import datetime

db_path = "ml_module.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all records ordered by creation time
cursor.execute("""
    SELECT id, task_name, created_at, model_type, train_score, validation_score 
    FROM trained_models 
    ORDER BY created_at DESC
""")
records = cursor.fetchall()

print(f"📊 Total Training Records: {len(records)}\n")
print("=" * 80)

for i, record in enumerate(records):
    print(f"Model {i+1}:")
    print(f"  ID: {record[0]}")
    print(f"  Task: {record[1]}")
    print(f"  Created: {record[2]}")
    print(f"  Model: {record[3]}")
    print(f"  Train R²: {record[4]}")
    print(f"  Valid R²: {record[5]}")
    print("-" * 50)

conn.close()
