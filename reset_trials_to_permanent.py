"""
Reset trial records to only the 30 permanent hardcoded trials
Clears any dynamically added trials from the database
"""
import sys
from pathlib import Path
import sqlite3

sys.path.insert(0, str(Path(__file__).parent))

from modules.trial_registry import DB_PATH

def reset_trials_to_permanent_only():
    """
    Clear the trials table in the database to reset to only the 30 hardcoded trials
    The hardcoded trials are defined in pages/5_Trial_History.py and will be used by default
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current trial count
        cursor.execute("SELECT COUNT(*) FROM trials")
        before_count = cursor.fetchone()[0]
        print(f"Current trials in database: {before_count}")
        
        # Clear all trials
        cursor.execute("DELETE FROM trials")
        conn.commit()
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM trials")
        after_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"Trials deleted: {before_count - after_count}")
        print(f"Remaining trials in database: {after_count}")
        print("")
        print("✅ Database cleared successfully!")
        print("")
        print("Status:")
        print(f"- Database trials: {after_count}")
        print(f"- Hardcoded trials in app: 30 (T-001 to T-030)")
        print(f"- Total trials shown in Trial History: 30")
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting trials: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("RESET TRIAL RECORDS TO PERMANENT TRIALS ONLY")
    print("=" * 60)
    print("")
    
    reset_trials_to_permanent_only()
    
    print("")
    print("=" * 60)
    print("To verify, run the app and check Trial History tab")
    print("You should see exactly 30 trials (T-001 to T-030)")
    print("=" * 60)
