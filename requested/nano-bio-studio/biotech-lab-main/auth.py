# ============================================================
# Authentication & Authorization Module
# Supports role-based access control with user registration
# ============================================================

import sqlite3
import bcrypt
from typing import Tuple, Optional, List, Dict
from datetime import datetime, timedelta
import re
import uuid
import secrets

DB_PATH = "users.db"

# Password requirements
MIN_PASSWORD_LENGTH = 6
PASSWORD_REGEX = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{' + str(MIN_PASSWORD_LENGTH) + ',}$'

# Session settings
SESSION_TIMEOUT_MINUTES = 30  # 30 minute timeout for inactive sessions
ACTIVITY_LOG_ENABLED = True  # Enable activity logging


# ============================================================
# Database Initialization
# ============================================================

def init_db():
    """Initialize database with users and activity_log tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    
    # Create users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            last_activity TIMESTAMP,
            session_start TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Add missing columns if they don't exist (for existing databases)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN last_activity TIMESTAMP")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute("ALTER TABLE users ADD COLUMN session_start TIMESTAMP")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create activity log table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')
    
    # Create indexes for faster queries
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_activity_username 
        ON activity_log(username)
    ''')
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_activity_timestamp 
        ON activity_log(timestamp)
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on import
init_db()


# ============================================================
# Authentication
# ============================================================

def authenticate(username: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    Authenticate user and return success status and role.
    
    Returns:
        Tuple[bool, Optional[str]]: (success, role)
    """
    username = (username or "").strip()
    if not username or not password:
        return False, None

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(
        "SELECT password_hash, role, is_active FROM users WHERE username = ?", 
        (username,)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return False, None

    pw_hash, role, is_active = row
    
    # Check if account is active
    if not is_active:
        return False, None
    
    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), pw_hash)
    except Exception:
        ok = False

    # Only update session timestamps if password is correct
    if ok:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE users SET last_login = ?, session_start = ?, last_activity = ? WHERE username = ?",
                (now, now, now, username)
            )
            conn.commit()
        except Exception as e:
            pass
        finally:
            conn.close()
        
        # Log successful login
        log_activity(username, "LOGIN", "User logged in successfully")

    return (ok, role if ok else None)


# ============================================================
# Activity Logging & Session Tracking
# ============================================================

# Auto-reset admin session on startup (for development/testing)
def _reset_admin_session():
    """Reset admin session timestamps on startup. Remove in production."""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET session_start = ?, last_activity = ? WHERE username = 'admin'",
            (now, now)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

_reset_admin_session()

def log_activity(username: str, action: str, details: str = None, ip_address: str = None) -> bool:
    """
    Log user activity for security audit trail.
    
    Args:
        username: User who performed the action
        action: Type of action (LOGIN, LOGOUT, PASSWORD_CHANGE, etc.)
        details: Additional details about the action
        ip_address: IP address of the user (optional)
    
    Returns:
        bool: Success status
    """
    if not ACTIVITY_LOG_ENABLED:
        return True
    
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO activity_log (username, action, details, ip_address) VALUES (?, ?, ?, ?)",
            (username, action, details, ip_address)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error logging activity: {e}")
        return False


def update_last_activity(username: str) -> bool:
    """
    Update the last activity timestamp for a user (for session timeout tracking).
    
    Args:
        username: Username to update
    
    Returns:
        bool: Success status
    """
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET last_activity = ? WHERE username = ?",
            (now, username)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_session_info(username: str) -> Optional[Dict]:
    """
    Get session information for a user.
    
    Args:
        username: Username to check
    
    Returns:
        Dict with session info or None if user not found
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            "SELECT session_start, last_activity, last_login FROM users WHERE username = ?",
            (username,)
        )
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "session_start": row[0],
            "last_activity": row[1],
            "last_login": row[2]
        }
    except Exception:
        return None


def is_session_expired(username: str, timeout_minutes: int = None) -> Tuple[bool, str]:
    """
    Check if a user's session has expired due to inactivity.
    
    Args:
        username: Username to check
        timeout_minutes: Timeout duration in minutes (default: SESSION_TIMEOUT_MINUTES)
    
    Returns:
        Tuple[bool, str]: (is_expired, time_remaining_str)
    """
    if timeout_minutes is None:
        timeout_minutes = SESSION_TIMEOUT_MINUTES
    
    session_info = get_session_info(username)
    if not session_info or not session_info["last_activity"]:
        return False, "No active session"
    
    try:
        # Parse SQLite timestamp format (YYYY-MM-DD HH:MM:SS)
        last_activity_str = session_info["last_activity"]
        if isinstance(last_activity_str, str):
            last_activity = datetime.strptime(last_activity_str, "%Y-%m-%d %H:%M:%S")
        else:
            last_activity = last_activity_str
        
        now = datetime.now()
        inactive_duration = now - last_activity
        timeout_duration = timedelta(minutes=timeout_minutes)
        
        if inactive_duration > timeout_duration:
            return True, "Session expired"
        
        remaining = timeout_duration - inactive_duration
        remaining_minutes = int(remaining.total_seconds() / 60)
        remaining_seconds = int(remaining.total_seconds() % 60)
        
        return False, f"{remaining_minutes}m {remaining_seconds}s"
    except Exception as e:
        return False, "Unable to determine session status"


def get_activity_log(username: str = None, limit: int = 100) -> List[Dict]:
    """
    Get activity log entries.
    
    Args:
        username: Filter by username (optional)
        limit: Maximum number of entries to return
    
    Returns:
        List of activity log entries
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        if username:
            cur.execute(
                "SELECT username, action, details, timestamp FROM activity_log WHERE username = ? ORDER BY timestamp DESC LIMIT ?",
                (username, limit)
            )
        else:
            cur.execute(
                "SELECT username, action, details, timestamp FROM activity_log ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        
        rows = cur.fetchall()
        conn.close()
        
        return [
            {
                "username": row[0],
                "action": row[1],
                "details": row[2],
                "timestamp": row[3]
            }
            for row in rows
        ]
    except Exception:
        return []


def get_activity_log_by_date(start_date: str = None, end_date: str = None, limit: int = 100) -> List[Dict]:
    """
    Get activity log entries filtered by date range.
    
    Args:
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        limit: Maximum number of entries to return
    
    Returns:
        List of activity log entries
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        if start_date and end_date:
            cur.execute(
                """SELECT username, action, details, timestamp FROM activity_log 
                   WHERE timestamp BETWEEN ? AND ? 
                   ORDER BY timestamp DESC LIMIT ?""",
                (f"{start_date} 00:00:00", f"{end_date} 23:59:59", limit)
            )
        else:
            cur.execute(
                "SELECT username, action, details, timestamp FROM activity_log ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        
        rows = cur.fetchall()
        conn.close()
        
        return [
            {
                "username": row[0],
                "action": row[1],
                "details": row[2],
                "timestamp": row[3]
            }
            for row in rows
        ]
    except Exception:
        return []


def get_activity_stats(days: int = 7) -> Dict:
    """
    Get activity statistics for the past N days.
    
    Args:
        days: Number of days to look back
    
    Returns:
        Dict with activity statistics
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        # Get stats for past N days
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
        
        # Total activities
        cur.execute(
            "SELECT COUNT(*) FROM activity_log WHERE timestamp > ?",
            (start_date,)
        )
        total_activities = cur.fetchone()[0]
        
        # Activities by action type
        cur.execute(
            """SELECT action, COUNT(*) as count FROM activity_log 
               WHERE timestamp > ? 
               GROUP BY action ORDER BY count DESC""",
            (start_date,)
        )
        activities_by_action = {row[0]: row[1] for row in cur.fetchall()}
        
        # Unique users
        cur.execute(
            "SELECT COUNT(DISTINCT username) FROM activity_log WHERE timestamp > ?",
            (start_date,)
        )
        unique_users = cur.fetchone()[0]
        
        # Failed login attempts
        cur.execute(
            "SELECT COUNT(*) FROM activity_log WHERE action LIKE 'LOGIN_FAILED%' AND timestamp > ?",
            (start_date,)
        )
        failed_logins = cur.fetchone()[0]
        
        # Password changes
        cur.execute(
            "SELECT COUNT(*) FROM activity_log WHERE action = 'PASSWORD_CHANGED' AND timestamp > ?",
            (start_date,)
        )
        password_changes = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "total_activities": total_activities,
            "activities_by_action": activities_by_action,
            "unique_users": unique_users,
            "failed_logins": failed_logins,
            "password_changes": password_changes,
            "period_days": days
        }
    except Exception as e:
        return {}


def audit_log_search(query: str, search_fields: List[str] = None) -> List[Dict]:
    """
    Search audit logs by action, details, or username.
    
    Args:
        query: Search query string
        search_fields: Fields to search in ['username', 'action', 'details']
    
    Returns:
        List of matching audit log entries
    """
    if search_fields is None:
        search_fields = ['action', 'details', 'username']
    
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        # Build WHERE clause
        where_conditions = []
        for field in search_fields:
            if field in ['username', 'action', 'details']:
                where_conditions.append(f"{field} LIKE ?")
        
        where_clause = " OR ".join(where_conditions)
        search_param = f"%{query}%"
        params = [search_param] * len(where_conditions)
        
        cur.execute(
            f"""SELECT username, action, details, timestamp FROM activity_log 
               WHERE {where_clause} 
               ORDER BY timestamp DESC LIMIT 500""",
            params
        )
        
        rows = cur.fetchall()
        conn.close()
        
        return [
            {
                "username": row[0],
                "action": row[1],
                "details": row[2],
                "timestamp": row[3]
            }
            for row in rows
        ]
    except Exception:
        return []


def get_user_audit_trail(username: str) -> List[Dict]:
    """
    Get complete audit trail for a specific user.
    
    Args:
        username: Username to get audit trail for
    
    Returns:
        List of all actions performed by the user (newest first)
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        cur.execute(
            """SELECT action, details, timestamp FROM activity_log 
               WHERE username = ? 
               ORDER BY timestamp DESC""",
            (username,)
        )
        
        rows = cur.fetchall()
        conn.close()
        
        return [
            {
                "action": row[0],
                "details": row[1],
                "timestamp": row[2]
            }
            for row in rows
        ]
    except Exception:
        return []


def export_audit_log(start_date: str = None, end_date: str = None, action_filter: str = None) -> List[Dict]:
    """
    Export audit log entries for compliance and reporting.
    
    Args:
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        action_filter: Filter by specific action type
    
    Returns:
        List of audit log entries matching criteria
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        query = "SELECT username, action, details, ip_address, timestamp FROM activity_log WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(f"{start_date} 00:00:00")
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(f"{end_date} 23:59:59")
        
        if action_filter:
            query += " AND action = ?"
            params.append(action_filter)
        
        query += " ORDER BY timestamp DESC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        
        return [
            {
                "username": row[0],
                "action": row[1],
                "details": row[2],
                "ip_address": row[3],
                "timestamp": row[4]
            }
            for row in rows
        ]
    except Exception:
        return []


# ============================================================
# Application-Level Audit Logging (for design/optimization actions)
# ============================================================

def log_design_action(username: str, action: str, design_id: str, design_name: str, details: str = None) -> bool:
    """
    Log design-related actions (create, save, load, delete, optimize).
    
    Args:
        username: User performing the action
        action: Action type (CREATE, SAVE, LOAD, DELETE, OPTIMIZE)
        design_id: Design identifier
        design_name: Design name/title
        details: Additional details
    
    Returns:
        bool: Success status
    """
    full_details = f"Design '{design_name}' (ID: {design_id})"
    if details:
        full_details += f" - {details}"
    
    return log_activity(username, f"DESIGN_{action}", full_details)


def log_optimization_action(username: str, design_id: str, n_trials: int, best_score: float, details: str = None) -> bool:
    """
    Log optimization runs.
    
    Args:
        username: User performing optimization
        design_id: Design identifier
        n_trials: Number of trials run
        best_score: Best score achieved
        details: Additional details
    
    Returns:
        bool: Success status
    """
    opt_details = f"Design ID: {design_id}, Trials: {n_trials}, Best Score: {best_score:.4f}"
    if details:
        opt_details += f" - {details}"
    
    return log_activity(username, "OPTIMIZATION_RUN", opt_details)


def log_admin_action(admin_username: str, action: str, target_user: str = None, details: str = None) -> bool:
    """
    Log administrative actions (user management, permission changes, etc).
    
    Args:
        admin_username: Admin performing the action
        action: Action type (USER_CREATED, USER_DISABLED, ROLE_CHANGED, etc)
        target_user: User being acted upon (if applicable)
        details: Additional details
    
    Returns:
        bool: Success status
    """
    admin_details = f"Target: {target_user}" if target_user else ""
    if details:
        admin_details += f" - {details}" if admin_details else details
    
    return log_activity(admin_username, f"ADMIN_{action}", admin_details or "No details")


# ============================================================
# Audit Report Generation
# ============================================================

def generate_audit_report(report_type: str = "summary", days: int = 7) -> Dict:
    """
    Generate audit reports for security and compliance.
    
    Args:
        report_type: 'summary', 'security', 'activity', or 'user_access'
        days: Number of days to include in report
    
    Returns:
        Dict with report data
    """
    if report_type == "summary":
        return get_activity_stats(days)
    
    elif report_type == "security":
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cur = conn.cursor()
            
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
            
            # Failed login attempts
            cur.execute(
                """SELECT username, COUNT(*) as attempts FROM activity_log 
                   WHERE action = 'LOGIN_FAILED' AND timestamp > ? 
                   GROUP BY username ORDER BY attempts DESC""",
                (start_date,)
            )
            failed_attempts = [{"username": row[0], "attempts": row[1]} for row in cur.fetchall()]
            
            # Password changes
            cur.execute(
                """SELECT username, COUNT(*) as changes FROM activity_log 
                   WHERE action = 'PASSWORD_CHANGED' AND timestamp > ? 
                   GROUP BY username""",
                (start_date,)
            )
            password_changes = [{"username": row[0], "changes": row[1]} for row in cur.fetchall()]
            
            conn.close()
            
            return {
                "report_type": "security",
                "period_days": days,
                "failed_login_attempts": failed_attempts,
                "password_changes": password_changes
            }
        except Exception:
            return {}
    
    elif report_type == "user_access":
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cur = conn.cursor()
            
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
            
            # User access patterns
            cur.execute(
                """SELECT username, COUNT(*) as total_actions, 
                   MAX(timestamp) as last_activity 
                   FROM activity_log 
                   WHERE timestamp > ? 
                   GROUP BY username 
                   ORDER BY total_actions DESC""",
                (start_date,)
            )
            
            user_activity = [
                {"username": row[0], "total_actions": row[1], "last_activity": row[2]} 
                for row in cur.fetchall()
            ]
            
            conn.close()
            
            return {
                "report_type": "user_access",
                "period_days": days,
                "user_activity": user_activity
            }
        except Exception:
            return {}
    
    return {}
# ============================================================

def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username format and availability"""
    username = (username or "").strip()
    
    if not username:
        return False, "Username cannot be empty"
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if len(username) > 30:
        return False, "Username must be less than 30 characters"
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscore, and hyphen"
    
    if user_exists(username):
        return False, "Username already exists"
    
    return True, "Valid"


def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password strength"""
    if not password:
        return False, "Password cannot be empty"
    
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)"
    
    # Check for at least one letter and one number
    if not re.match(PASSWORD_REGEX, password):
        return False, f"Password must contain at least one letter and one number"
    
    return True, "Valid"


def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format"""
    email = (email or "").strip()
    
    if not email:
        return True, "Valid"  # Email is optional
    
    if len(email) > 100:
        return False, "Email is too long"
    
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return False, "Invalid email format"
    
    # Check if email already used
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE email = ?", (email,))
    exists = cur.fetchone() is not None
    conn.close()
    
    if exists:
        return False, "Email already registered"
    
    return True, "Valid"


def register_user(username: str, password: str, email: str = "", role: str = "student") -> Tuple[bool, str]:
    """
    Register a new user.
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Validate inputs
    valid, msg = validate_username(username)
    if not valid:
        return False, msg
    
    valid, msg = validate_password(password)
    if not valid:
        return False, msg
    
    valid, msg = validate_email(email)
    if not valid:
        return False, msg
    
    # Validate role
    valid_roles = ["admin", "research", "educator", "student", "viewer"]
    if role not in valid_roles:
        return False, f"Invalid role. Must be one of: {', '.join(valid_roles)}"
    
    try:
        # Hash password
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        
        # Insert user
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email or None, password_hash, role)
        )
        conn.commit()
        conn.close()
        
        return True, f"User '{username}' registered successfully with role '{role}'"
    
    except sqlite3.IntegrityError:
        return False, "Username or email already exists"
    except Exception as e:
        return False, f"Registration error: {str(e)}"


# ============================================================
# Admin Functions for Role Management
# ============================================================

def get_all_users() -> List[Tuple[str, str]]:
    """Get all users and their roles"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT username, role FROM users ORDER BY username")
    users = cur.fetchall()
    conn.close()
    return users


def update_user_role(username: str, new_role: str) -> bool:
    """Update a user's role. Returns True if successful."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (new_role, username)
        )
        conn.commit()
        success = cur.rowcount > 0
    except Exception:
        success = False
    finally:
        conn.close()
    return success


def get_user_role(username: str) -> Optional[str]:
    """Get a specific user's role"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def count_users_by_role() -> dict:
    """Count users in each role"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
    results = cur.fetchall()
    conn.close()
    return {role: count for role, count in results}


def user_exists(username: str) -> bool:
    """Check if a user exists"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def delete_user(username: str) -> bool:
    """Delete a user. Returns True if successful."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        success = cur.rowcount > 0
    except Exception:
        success = False
    finally:
        conn.close()
    return success


# ============================================================
# Audit Logging (optional)
# ============================================================

def log_auth_event(username: str, event_type: str, success: bool, details: str = "") -> None:
    """Log authentication events for audit trail"""
    # This could be extended to log to a separate audit table
    # For now, we'll just pass - implement if needed
    pass


# ============================================================
# User Account Management
# ============================================================

def change_password(username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """Change user's password after verifying old password"""
    # Verify old password
    ok, _ = authenticate(username, old_password)
    if not ok:
        log_activity(username, "PASSWORD_CHANGE_FAILED", "Invalid current password")
        return False, "Current password is incorrect"
    
    # Validate new password
    valid, msg = validate_password(new_password)
    if not valid:
        return False, msg
    
    # Check that new password is different
    if old_password == new_password:
        log_activity(username, "PASSWORD_CHANGE_FAILED", "Attempted to reuse same password")
        return False, "New password must be different from current password"
    
    try:
        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, username)
        )
        conn.commit()
        conn.close()
        log_activity(username, "PASSWORD_CHANGED", "User changed password")
        return True, "Password changed successfully"
    except Exception as e:
        log_activity(username, "PASSWORD_CHANGE_ERROR", str(e))
        return False, f"Error changing password: {str(e)}"


def reset_password(username: str, new_password: str) -> Tuple[bool, str]:
    """Reset user's password (admin function)"""
    # Validate new password
    valid, msg = validate_password(new_password)
    if not valid:
        return False, msg
    
    # Check user exists
    if not user_exists(username):
        return False, f"User '{username}' does not exist"
    
    try:
        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, username)
        )
        conn.commit()
        conn.close()
        log_activity(username, "PASSWORD_RESET", "Admin reset password")
        return True, f"Password reset for user '{username}' successfully"
    except Exception as e:
        log_activity(username, "PASSWORD_RESET_ERROR", str(e))
        return False, f"Error resetting password: {str(e)}"


def get_user_info(username: str) -> Optional[dict]:
    """Get user information"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(
        "SELECT username, email, role, created_at, last_login, is_active FROM users WHERE username = ?",
        (username,)
    )
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "username": row[0],
        "email": row[1],
        "role": row[2],
        "created_at": row[3],
        "last_login": row[4],
        "is_active": bool(row[5])
    }


def deactivate_user(username: str) -> Tuple[bool, str]:
    """Deactivate a user account (prevents login)"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_active = 0 WHERE username = ?", (username,))
        conn.commit()
        success = cur.rowcount > 0
        conn.close()
        
        if success:
            return True, f"User '{username}' deactivated"
        else:
            return False, f"User '{username}' not found"
    except Exception as e:
        return False, f"Error deactivating user: {str(e)}"


def activate_user(username: str) -> Tuple[bool, str]:
    """Activate a user account"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_active = 1 WHERE username = ?", (username,))
        conn.commit()
        success = cur.rowcount > 0
        conn.close()
        
        if success:
            return True, f"User '{username}' activated"
        else:
            return False, f"User '{username}' not found"
    except Exception as e:
        return False, f"Error activating user: {str(e)}"


def list_users_detailed() -> List[dict]:
    """Get detailed information about all users"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(
        "SELECT username, email, role, created_at, last_login, is_active FROM users ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    
    return [
        {
            "username": row[0],
            "email": row[1] or "N/A",
            "role": row[2],
            "created_at": row[3],
            "last_login": row[4] or "Never",
            "status": "Active" if row[5] else "Inactive"
        }
        for row in rows
    ]


def setup_admin_account(username: str, password: str, email: str = "") -> Tuple[bool, str]:
    """
    Setup initial admin account. Only works if no admin exists.
    Returns: (success, message)
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    
    # Check if any admin exists
    cur.execute("SELECT 1 FROM users WHERE role = 'admin'")
    admin_exists = cur.fetchone() is not None
    
    conn.close()
    
    if admin_exists:
        return False, "An admin account already exists"
    
    # Register as admin
    return register_user(username, password, email, role="admin")


def count_admin_users() -> int:
    """Count number of admin users"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    count = cur.fetchone()[0]
    conn.close()
    return count


# ============================================================
# AuthManager Class - Wrapper for object-oriented interface
# ============================================================

import uuid
import secrets

# Session storage (in-memory for simplicity, can be extended to database)
_sessions = {}  # {session_token: {'username': str, 'created_at': datetime, 'last_activity': datetime}}


class AuthManager:
    """
    Authentication Manager class for object-oriented interface.
    Provides session management and user operations.
    """
    
    def __init__(self):
        """Initialize the auth manager"""
        init_db()
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        Authenticate a user and return user info dict.
        
        Returns:
            dict with user info or None if authentication fails
        """
        username = (username or "").strip()
        if not username or not password:
            return None

        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            "SELECT password_hash, role, is_active, email FROM users WHERE username = ?", 
            (username,)
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        pw_hash, role, is_active, email = row
        
        if not is_active:
            return None
        
        try:
            ok = bcrypt.checkpw(password.encode("utf-8"), pw_hash)
        except Exception:
            ok = False

        if ok:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE users SET last_login = ?, session_start = ?, last_activity = ? WHERE username = ?",
                    (now, now, now, username)
                )
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()
            
            log_activity(username, "LOGIN", "User logged in successfully")
            
            return {
                'username': username,
                'role': role,
                'email': email,
                'full_name': username.title(),  # Default to title-cased username
                'is_active': True
            }
        
        return None
    
    def create_session(self, username: str) -> str:
        """
        Create a session token for a user.
        
        Returns:
            session token string
        """
        session_token = secrets.token_urlsafe(32)
        _sessions[session_token] = {
            'username': username,
            'created_at': datetime.now(),
            'last_activity': datetime.now()
        }
        return session_token
    
    def validate_session(self, session_token: str) -> Optional[Dict]:
        """
        Validate a session token and return user info.
        
        Returns:
            dict with user info or None if session invalid/expired
        """
        if session_token not in _sessions:
            return None
        
        session_info = _sessions[session_token]
        username = session_info['username']
        
        # Check if session expired (30 minutes by default)
        session_age = (datetime.now() - session_info['created_at']).total_seconds()
        if session_age > SESSION_TIMEOUT_MINUTES * 60:
            del _sessions[session_token]
            return None
        
        # Update last activity
        _sessions[session_token]['last_activity'] = datetime.now()
        
        # Get fresh user info
        user_info = get_user_info(username)
        if user_info:
            user_info['full_name'] = user_info.get('full_name', username.title())
        return user_info
    
    def delete_session(self, session_token: str) -> bool:
        """Delete a session token"""
        if session_token in _sessions:
            del _sessions[session_token]
            return True
        return False
    
    def register_user(self, username: str, password: str, email: str = "", role: str = "student") -> Tuple[bool, str]:
        """Register a new user"""
        return register_user(username, password, email, role)
    
    def change_password(self, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change user password"""
        return change_password(username, old_password, new_password)
    
    def admin_reset_password(self, username: str, new_password: str) -> Tuple[bool, str]:
        """Reset user password (admin only)"""
        return reset_password(username, new_password)
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information"""
        info = get_user_info(username)
        if info:
            info['full_name'] = info.get('full_name', username.title())
        return info
    
    def get_user_details(self, username: str) -> Optional[Dict]:
        """Get detailed user information"""
        return self.get_user_info(username)
    
    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        users = get_all_users()
        return users
    
    def update_user_role(self, username: str, new_role: str) -> Tuple[bool, str]:
        """Update user role"""
        success = update_user_role(username, new_role)
        return (success, "Role updated successfully" if success else "Failed to update role")
    
    def update_username(self, old_username: str, new_username: str) -> Tuple[bool, str]:
        """Update/rename user account"""
        if not new_username or not old_username:
            return False, "Invalid username"
        
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        try:
            cur.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, old_username))
            conn.commit()
            conn.close()
            return True, "Username updated successfully"
        except sqlite3.IntegrityError:
            conn.close()
            return False, "Username already exists"
        except Exception as e:
            conn.close()
            return False, f"Error updating username: {str(e)}"
    
    def update_user_info(self, username: str, email: str = None, full_name: str = None) -> Tuple[bool, str]:
        """Update user email and full name"""
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        try:
            if email:
                cur.execute("UPDATE users SET email = ? WHERE username = ?", (email, username))
            if full_name:
                # Store full_name in a separate column if it exists, or in a notes column
                cur.execute("UPDATE users SET email = ? WHERE username = ?", (email or "", username))
            
            conn.commit()
            conn.close()
            return True, "User info updated successfully"
        except Exception as e:
            conn.close()
            return False, f"Error updating user info: {str(e)}"
    
    def delete_user(self, username: str) -> Tuple[bool, str]:
        """Delete a user account"""
        success = delete_user(username)
        return (success, "User deleted successfully" if success else "Failed to delete user")
    
    def deactivate_user(self, username: str) -> Tuple[bool, str]:
        """Deactivate a user"""
        return deactivate_user(username)
    
    def activate_user(self, username: str) -> Tuple[bool, str]:
        """Activate a user"""
        return activate_user(username)
    
    def log_activity(self, username: str, action: str, details: str = None) -> bool:
        """Log user activity"""
        return log_activity(username, action, details)


# ============================================================
# Session Recovery - Get most recent active session
# ============================================================

def get_most_recent_active_session() -> Optional[Dict]:
    """
    Get the most recently active user session from the database.
    Used for session recovery on app refresh.
    
    Returns:
        Dict with username and role, or None if no active sessions
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        # Get the most recently active user
        cur.execute(
            "SELECT username, role, last_activity FROM users WHERE is_active = 1 ORDER BY last_activity DESC LIMIT 1"
        )
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        username, role, last_activity = row
        
        # Check if this session is still within the timeout window
        if last_activity:
            try:
                last_activity_time = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                inactive_duration = now - last_activity_time
                timeout_duration = timedelta(minutes=SESSION_TIMEOUT_MINUTES)
                
                # If session is not expired, return it
                if inactive_duration <= timeout_duration:
                    return {
                        "username": username,
                        "role": role,
                        "last_activity": last_activity
                    }
            except Exception:
                pass
        
        return None
    except Exception:
        return None


# Initialize database on module import
init_db()
