import sqlite3
import os

db_path = 'biotech-lab-main/ml_module.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get trained models with correct column names
    cursor.execute('SELECT COUNT(*) FROM trained_models')
    count = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(n_training_samples), SUM(n_features) FROM trained_models')
    samples_sum, features_sum = cursor.fetchone()
    
    cursor.execute('SELECT task_name, model_type, n_training_samples, n_features FROM trained_models')
    records = cursor.fetchall()
    
    print('=== Training Dataset Volume ===\n')
    print(f'Total trained models: {count}')
    if count > 0:
        print(f'Total training samples used: {int(samples_sum) if samples_sum else 0}')
        print(f'Total feature dimensions: {int(features_sum) if features_sum else 0}')
        print(f'Average samples per model: {int(samples_sum/count) if samples_sum else 0}')
        print(f'\nDetailed breakdown:')
        for task, mtype, samp, feat in records:
            print(f'  - {task} ({mtype}): {samp} samples × {feat} features')
    
    conn.close()
else:
    print(f'Database not found at {db_path}')
