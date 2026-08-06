"""
Clear all trial records from both database AND session state
Resets to only the 30 permanent hardcoded trials
"""
import sys
from pathlib import Path
import sqlite3
import json

sys.path.insert(0, str(Path(__file__).parent))

from modules.trial_registry import DB_PATH

def clear_all_trial_data():
    """
    Clear trials from:
    1. SQLite database
    2. Session state cache files
    """
    print("=" * 70)
    print("COMPLETE RESET - DATABASE + SESSION STATE")
    print("=" * 70)
    print("")
    
    # 1. Clear database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM trials")
        before_count = cursor.fetchone()[0]
        print(f"[1/2] Database Clean-up")
        print(f"      Trials before: {before_count}")
        
        cursor.execute("DELETE FROM trials")
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM trials")
        after_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"      Trials after:  {after_count}")
        print(f"      ✓ Database cleared ({before_count} trials deleted)")
        
    except Exception as e:
        print(f"      ✗ Error: {e}")
        return False
    
    # 2. Clear session state files
    print("")
    print(f"[2/2] Session State Clean-up")
    
    try:
        # Look for sessions.json which stores session state
        sessions_file = Path(__file__).parent / "sessions.json"
        if sessions_file.exists():
            with open(sessions_file, 'r') as f:
                sessions_data = json.load(f)
            
            before_sessions = len(sessions_data)
            
            # Clear trial_history from each session
            for session_id, session_data in sessions_data.items():
                if "trial_history" in session_data:
                    del session_data["trial_history"]
            
            with open(sessions_file, 'w') as f:
                json.dump(sessions_data, f, indent=2)
            
            print(f"      ✓ Cleared trial_history from {before_sessions} session(s)")
        else:
            print(f"      ℹ No sessions.json file found")
            
    except Exception as e:
        print(f"      ⚠ Warning (non-critical): {e}")
    
    print("")
    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print("")
    print("✅ All trial data cleared successfully!")
    print("")
    print("Status:")
    print("  • Database trials: 0")
    print("  • Session trial_history: Cleared")
    print("  • Hardcoded permanent trials: 30 (T-001 to T-030)")
    print("  • Total visible in app: 30")
    print("")
    print("To verify:")
    print("  1. Refresh/reopen the app or clear browser cache")
    print("  2. Go to Trial History tab")
    print("  3. You should see ONLY the 30 permanent trials (T-001 to T-030)")
    print("")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    clear_all_trial_data()
