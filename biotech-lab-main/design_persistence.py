"""
Design Database Persistence Module
Handles saving and loading designs from SQLite database with user association
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
import streamlit as st
from typing import List, Dict, Optional


# Database path
DB_PATH = Path(__file__).parent / "nano_bio.db"


def init_design_db():
    """Initialize the design database tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create designs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_designs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        design_name TEXT NOT NULL,
        design_data TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_favorite INTEGER DEFAULT 0,
        tags TEXT,
        FOREIGN KEY (username) REFERENCES users(username),
        UNIQUE(username, design_name)
    )
    """)
    
    # Create design versions table (for history/versioning)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS design_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        design_id INTEGER NOT NULL,
        version_number INTEGER NOT NULL,
        design_data TEXT NOT NULL,
        version_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (design_id) REFERENCES user_designs(id) ON DELETE CASCADE,
        UNIQUE(design_id, version_number)
    )
    """)
    
    # Create indexes for performance
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_designs_username 
    ON user_designs(username)
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_designs_created 
    ON user_designs(created_at)
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_versions_design_id 
    ON design_versions(design_id)
    """)
    
    conn.commit()
    conn.close()


def save_design_to_db(username: str, design_name: str, design_data: dict, 
                      description: str = "", tags: str = "") -> bool:
    """
    Save a design to the database.
    
    Args:
        username: Username of the designer
        design_name: Name of the design
        design_data: Dictionary containing all design parameters
        description: Optional description of the design
        tags: Optional comma-separated tags
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Convert design_data to JSON
        design_json = json.dumps(design_data)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if design already exists
        cursor.execute(
            "SELECT id FROM user_designs WHERE username = ? AND design_name = ?",
            (username, design_name)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update existing design
            design_id = existing[0]
            cursor.execute("""
                UPDATE user_designs 
                SET design_data = ?, description = ?, updated_at = ?, tags = ?
                WHERE id = ?
            """, (design_json, description, timestamp, tags, design_id))
            
            # Create version entry
            cursor.execute(
                "SELECT COUNT(*) FROM design_versions WHERE design_id = ?",
                (design_id,)
            )
            version_num = cursor.fetchone()[0] + 1
            
            cursor.execute("""
                INSERT INTO design_versions 
                (design_id, version_number, design_data, version_notes)
                VALUES (?, ?, ?, ?)
            """, (design_id, version_num, design_json, "Auto-saved update"))
            
        else:
            # Insert new design
            cursor.execute("""
                INSERT INTO user_designs 
                (username, design_name, design_data, description, tags)
                VALUES (?, ?, ?, ?, ?)
            """, (username, design_name, design_json, description, tags))
            
            design_id = cursor.lastrowid
            
            # Create initial version
            cursor.execute("""
                INSERT INTO design_versions 
                (design_id, version_number, design_data, version_notes)
                VALUES (?, ?, ?, ?)
            """, (design_id, 1, design_json, "Initial version"))
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error saving design: {str(e)}")
        return False


def load_design_from_db(username: str, design_name: str) -> Optional[dict]:
    """
    Load a design from the database.
    
    Args:
        username: Username of the designer
        design_name: Name of the design to load
    
    Returns:
        Design dictionary or None if not found
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT design_data FROM user_designs 
            WHERE username = ? AND design_name = ?
        """, (username, design_name))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return json.loads(result[0])
        return None
    
    except Exception as e:
        print(f"Error loading design: {str(e)}")
        return None


def get_user_designs(username: str) -> List[Dict]:
    """
    Get all designs for a user.
    
    Args:
        username: Username
    
    Returns:
        List of design dictionaries with metadata
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, design_name, description, created_at, updated_at, 
                   is_favorite, tags
            FROM user_designs 
            WHERE username = ?
            ORDER BY updated_at DESC
        """, (username,))
        
        results = cursor.fetchall()
        conn.close()
        
        designs = []
        for row in results:
            designs.append({
                "id": row["id"],
                "design_name": row["design_name"],
                "description": row["description"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "is_favorite": bool(row["is_favorite"]),
                "tags": row["tags"]
            })
        
        return designs
    
    except Exception as e:
        print(f"Error getting designs: {str(e)}")
        return []


def delete_design_from_db(username: str, design_name: str) -> bool:
    """
    Delete a design from the database.
    
    Args:
        username: Username
        design_name: Design to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get design_id first
        cursor.execute(
            "SELECT id FROM user_designs WHERE username = ? AND design_name = ?",
            (username, design_name)
        )
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False
        
        design_id = result[0]
        
        # Delete design (versions will cascade delete)
        cursor.execute(
            "DELETE FROM user_designs WHERE id = ?",
            (design_id,)
        )
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error deleting design: {str(e)}")
        return False


def toggle_favorite(username: str, design_name: str) -> bool:
    """
    Toggle favorite status of a design.
    
    Args:
        username: Username
        design_name: Design name
    
    Returns:
        New favorite status
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute(
            "SELECT is_favorite FROM user_designs WHERE username = ? AND design_name = ?",
            (username, design_name)
        )
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False
        
        new_status = 1 - result[0]  # Toggle 0 -> 1 or 1 -> 0
        
        # Update
        cursor.execute("""
            UPDATE user_designs 
            SET is_favorite = ?
            WHERE username = ? AND design_name = ?
        """, (new_status, username, design_name))
        
        conn.commit()
        conn.close()
        return bool(new_status)
    
    except Exception as e:
        print(f"Error toggling favorite: {str(e)}")
        return False


def get_design_versions(username: str, design_name: str) -> List[Dict]:
    """
    Get all versions of a design.
    
    Args:
        username: Username
        design_name: Design name
    
    Returns:
        List of design versions
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT v.version_number, v.design_data, v.version_notes, v.created_at
            FROM design_versions v
            JOIN user_designs d ON v.design_id = d.id
            WHERE d.username = ? AND d.design_name = ?
            ORDER BY v.version_number DESC
        """, (username, design_name))
        
        results = cursor.fetchall()
        conn.close()
        
        versions = []
        for row in results:
            versions.append({
                "version_number": row["version_number"],
                "design_data": json.loads(row["design_data"]),
                "version_notes": row["version_notes"],
                "created_at": row["created_at"]
            })
        
        return versions
    
    except Exception as e:
        print(f"Error getting versions: {str(e)}")
        return []


def restore_design_version(username: str, design_name: str, version_number: int) -> bool:
    """
    Restore a previous version of a design.
    
    Args:
        username: Username
        design_name: Design name
        version_number: Version to restore
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get the version data
        cursor.execute("""
            SELECT v.design_data
            FROM design_versions v
            JOIN user_designs d ON v.design_id = d.id
            WHERE d.username = ? AND d.design_name = ? AND v.version_number = ?
        """, (username, design_name, version_number))
        
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False
        
        design_data = result[0]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update the main design
        cursor.execute("""
            UPDATE user_designs 
            SET design_data = ?, updated_at = ?
            WHERE username = ? AND design_name = ?
        """, (design_data, timestamp, username, design_name))
        
        # Get design_id and create new version
        cursor.execute(
            "SELECT id FROM user_designs WHERE username = ? AND design_name = ?",
            (username, design_name)
        )
        design_id = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT MAX(version_number) FROM design_versions WHERE design_id = ?",
            (design_id,)
        )
        max_version = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            INSERT INTO design_versions 
            (design_id, version_number, design_data, version_notes)
            VALUES (?, ?, ?, ?)
        """, (design_id, max_version + 1, design_data, f"Restored from version {version_number}"))
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error restoring version: {str(e)}")
        return False


def get_design_stats(username: str) -> Dict:
    """
    Get statistics about user's designs.
    
    Args:
        username: Username
    
    Returns:
        Dictionary with design statistics
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total designs
        cursor.execute(
            "SELECT COUNT(*) FROM user_designs WHERE username = ?",
            (username,)
        )
        total_designs = cursor.fetchone()[0]
        
        # Favorite designs
        cursor.execute(
            "SELECT COUNT(*) FROM user_designs WHERE username = ? AND is_favorite = 1",
            (username,)
        )
        favorite_designs = cursor.fetchone()[0]
        
        # Total versions
        cursor.execute("""
            SELECT COUNT(*) FROM design_versions 
            WHERE design_id IN (SELECT id FROM user_designs WHERE username = ?)
        """, (username,))
        total_versions = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_designs": total_designs,
            "favorite_designs": favorite_designs,
            "total_versions": total_versions
        }
    
    except Exception as e:
        print(f"Error getting stats: {str(e)}")
        return {"total_designs": 0, "favorite_designs": 0, "total_versions": 0}


def render_design_selector_db(username: str):
    """
    Render a Streamlit UI for selecting and loading designs from database.
    
    Args:
        username: Current username
    """
    designs = get_user_designs(username)
    
    if not designs:
        st.info("📭 No designs saved yet. Create and save a design to get started!")
        return
    
    st.markdown("### 📂 Your Designs")
    
    # Display design list
    for design in designs:
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            st.write(f"**{design['design_name']}**")
            if design['description']:
                st.caption(design['description'])
            st.caption(f"Updated: {design['updated_at']}")
        
        with col2:
            if st.button("📂 Load", key=f"load_{design['id']}", use_container_width=True):
                loaded = load_design_from_db(username, design['design_name'])
                if loaded:
                    st.session_state.design = loaded
                    st.success(f"Loaded: {design['design_name']}")
                    st.rerun()
        
        with col3:
            fav_label = "⭐" if design['is_favorite'] else "☆"
            if st.button(fav_label, key=f"fav_{design['id']}", use_container_width=True):
                toggle_favorite(username, design['design_name'])
                st.rerun()
        
        with col4:
            if st.button("🗑️", key=f"delete_{design['id']}", use_container_width=True):
                delete_design_from_db(username, design['design_name'])
                st.success(f"Deleted: {design['design_name']}")
                st.rerun()


def render_save_design_form_db(username: str):
    """
    Render a form to save current design to database.
    
    Args:
        username: Current username
    """
    design_name = st.text_input(
        "Design Name",
        value=st.session_state.get("current_design_name", "My Design"),
        help="Unique name for this design"
    )
    
    description = st.text_area(
        "Description (optional)",
        value="",
        height=60,
        help="Add notes about this design"
    )
    
    tags = st.text_input(
        "Tags (comma-separated, optional)",
        value="",
        help="e.g., prototype, optimized, tested"
    )
    
    if st.button("💾 Save to Database", type="primary", use_container_width=True):
        if design_name.strip():
            success = save_design_to_db(
                username,
                design_name,
                st.session_state.design,
                description,
                tags
            )
            
            if success:
                st.session_state.current_design_name = design_name
                st.success(f"✅ Saved: {design_name}")
                st.rerun()
            else:
                st.error("❌ Failed to save design")
        else:
            st.warning("⚠️ Please enter a design name")


# Initialize database on module load
init_design_db()
