"""
Trial Registry Module - Manages unique trial IDs and tracking
Generates non-repeating trial IDs and maintains trial history
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / "trial_registry.db"

# ============================================================================
# TRIAL ID GENERATOR
# ============================================================================

class TrialIDGenerator:
    """Generate unique, human-readable trial IDs"""
    
    @staticmethod
    def generate_trial_id(disease_subtype: str, np_size_nm: int) -> str:
        """
        Generate unique trial ID
        Format: TRIAL-{DISEASE}-NP{SIZE}-{YYYYMMDD}-{SEQUENCE}
        Example: TRIAL-HCC-L-NP65-20260316-00147
        """
        timestamp = datetime.now().strftime("%Y%m%d")
        
        # Map disease subtype to code
        disease_map = {
            "hcc_s": "HCC-S",
            "hcc_ms": "HCC-MS",
            "hcc_l": "HCC-L"
        }
        disease_code = disease_map.get(disease_subtype, "UNKNOWN")
        
        # Get next sequence number for this date
        sequence = _get_next_sequence(disease_code, timestamp)
        
        trial_id = f"TRIAL-{disease_code}-NP{np_size_nm}-{timestamp}-{sequence:05d}"
        return trial_id

# ============================================================================
# TRIAL HISTORY DATABASE
# ============================================================================

def _init_db():
    """Initialize trial registry database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            trial_id TEXT PRIMARY KEY,
            disease_subtype TEXT,
            disease_name TEXT,
            drug_name TEXT,
            np_size_nm INTEGER,
            np_charge_mv INTEGER,
            np_peg_percent REAL,
            np_zeta_potential REAL,
            np_pdi REAL,
            treatment_dose_mgkg REAL,
            treatment_route TEXT,
            treatment_frequency TEXT,
            treatment_duration_days INTEGER,
            trial_outcomes TEXT,
            trial_notes TEXT,
            creation_timestamp TEXT,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            export_path TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trial_sequences (
            date TEXT,
            disease_code TEXT,
            next_sequence INTEGER DEFAULT 1,
            PRIMARY KEY (date, disease_code)
        )
    """)
    
    conn.commit()
    
    # Add missing columns if they don't exist (for backward compatibility)
    try:
        cursor.execute("ALTER TABLE trials ADD COLUMN np_zeta_potential REAL")
        cursor.execute("ALTER TABLE trials ADD COLUMN np_pdi REAL")
        cursor.execute("ALTER TABLE trials ADD COLUMN treatment_dose_mgkg REAL")
        cursor.execute("ALTER TABLE trials ADD COLUMN treatment_route TEXT")
        cursor.execute("ALTER TABLE trials ADD COLUMN treatment_frequency TEXT")
        cursor.execute("ALTER TABLE trials ADD COLUMN treatment_duration_days INTEGER")
        cursor.execute("ALTER TABLE trials ADD COLUMN trial_outcomes TEXT")
        cursor.execute("ALTER TABLE trials ADD COLUMN trial_notes TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        # Columns already exist, no action needed
        pass
    
    conn.close()

def _get_next_sequence(disease_code: str, date: str) -> int:
    """Get next sequence number for trial ID"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT next_sequence FROM trial_sequences WHERE date = ? AND disease_code = ?",
        (date, disease_code)
    )
    result = cursor.fetchone()
    
    if result:
        sequence = result[0]
        cursor.execute(
            "UPDATE trial_sequences SET next_sequence = ? WHERE date = ? AND disease_code = ?",
            (sequence + 1, date, disease_code)
        )
    else:
        sequence = 1
        cursor.execute(
            "INSERT INTO trial_sequences (date, disease_code, next_sequence) VALUES (?, ?, ?)",
            (date, disease_code, 2)
        )
    
    conn.commit()
    conn.close()
    return sequence

# ============================================================================
# TRIAL REGISTRY
# ============================================================================

def create_trial_entry(
    trial_id: str,
    disease_subtype: str,
    disease_name: str,
    drug_name: str,
    np_size_nm: int,
    np_charge_mv: int,
    np_peg_percent: float,
    np_zeta_potential: Optional[float] = None,
    np_pdi: Optional[float] = None,
    treatment_dose_mgkg: Optional[float] = None,
    treatment_route: Optional[str] = None,
    treatment_frequency: Optional[str] = None,
    treatment_duration_days: Optional[int] = None,
    trial_outcomes: Optional[str] = None,
    notes: str = ""
) -> bool:
    """Create new trial entry in registry"""
    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO trials 
            (trial_id, disease_subtype, disease_name, drug_name, np_size_nm, 
             np_charge_mv, np_peg_percent, np_zeta_potential, np_pdi,
             treatment_dose_mgkg, treatment_route, treatment_frequency, treatment_duration_days,
             trial_outcomes, creation_timestamp, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trial_id, disease_subtype, disease_name, drug_name, np_size_nm,
            np_charge_mv, np_peg_percent, np_zeta_potential, np_pdi,
            treatment_dose_mgkg, treatment_route, treatment_frequency, treatment_duration_days,
            trial_outcomes, timestamp, 'Active', notes
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Trial created: {trial_id}")
        return True
    except Exception as e:
        logger.error(f"Error creating trial: {e}")
        return False

def get_trial_by_id(trial_id: str) -> Optional[Dict]:
    """Retrieve trial by ID"""
    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trials WHERE trial_id = ?", (trial_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error retrieving trial: {e}")
        return None

def get_all_trials() -> List[Dict]:
    """Get all trials"""
    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trials 
            ORDER BY creation_timestamp DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving trials: {e}")
        return []

def update_trial_parameters(
    trial_id: str,
    np_zeta_potential: Optional[float] = None,
    np_pdi: Optional[float] = None,
    treatment_dose_mgkg: Optional[float] = None,
    treatment_route: Optional[str] = None,
    treatment_frequency: Optional[str] = None,
    treatment_duration_days: Optional[int] = None,
    trial_outcomes: Optional[str] = None
) -> bool:
    """Update trial with treatment and nanoparticle parameters"""
    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trials 
            SET np_zeta_potential = COALESCE(?, np_zeta_potential),
                np_pdi = COALESCE(?, np_pdi),
                treatment_dose_mgkg = COALESCE(?, treatment_dose_mgkg),
                treatment_route = COALESCE(?, treatment_route),
                treatment_frequency = COALESCE(?, treatment_frequency),
                treatment_duration_days = COALESCE(?, treatment_duration_days),
                trial_outcomes = COALESCE(?, trial_outcomes)
            WHERE trial_id = ?
        """, (
            np_zeta_potential, np_pdi, treatment_dose_mgkg,
            treatment_route, treatment_frequency, treatment_duration_days,
            trial_outcomes, trial_id
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Trial parameters updated: {trial_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating trial parameters: {e}")
        return False

def get_recent_trials(limit: int = 10) -> List[Dict]:
    """Get recent trials"""
    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trials 
            ORDER BY creation_timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving recent trials: {e}")
        return []

def export_trial_to_json(trial_id: str, export_path: Optional[str] = None) -> Optional[str]:
    """Export trial configuration to JSON"""
    trial = get_trial_by_id(trial_id)
    if not trial:
        logger.error(f"Trial not found: {trial_id}")
        return None
    
    if not export_path:
        export_path = f"trial_export_{trial_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        # Convert to JSON-serializable format
        trial_data = {
            'trial_id': trial['trial_id'],
            'disease_subtype': trial['disease_subtype'],
            'disease_name': trial['disease_name'],
            'drug_name': trial['drug_name'],
            'np_parameters': {
                'size_nm': trial['np_size_nm'],
                'charge_mv': trial['np_charge_mv'],
                'peg_percent': trial['np_peg_percent'],
                'zeta_potential': trial.get('np_zeta_potential'),
                'pdi': trial.get('np_pdi')
            },
            'treatment_parameters': {
                'dose_mgkg': trial.get('treatment_dose_mgkg'),
                'route': trial.get('treatment_route'),
                'frequency': trial.get('treatment_frequency'),
                'duration_days': trial.get('treatment_duration_days')
            },
            'trial_outcomes': trial.get('trial_outcomes'),
            'creation_timestamp': trial['creation_timestamp'],
            'status': trial['status'],
            'notes': trial['notes']
        }
        
        with open(export_path, 'w') as f:
            json.dump(trial_data, f, indent=2)
        
        logger.info(f"Trial exported: {export_path}")
        return export_path
    except Exception as e:
        logger.error(f"Error exporting trial: {e}")
        return None

def get_trial_completeness(trial_id: str) -> Dict[str, bool]:
    """
    Check which parameters are present in a trial
    Returns dict with parameter names and whether they're populated
    """
    trial = get_trial_by_id(trial_id)
    if not trial:
        return {}
    
    return {
        'np_size': trial.get('np_size_nm') is not None,
        'np_charge': trial.get('np_charge_mv') is not None,
        'np_peg': trial.get('np_peg_percent') is not None,
        'np_zeta_potential': trial.get('np_zeta_potential') is not None,
        'np_pdi': trial.get('np_pdi') is not None,
        'treatment_dose': trial.get('treatment_dose_mgkg') is not None,
        'treatment_route': trial.get('treatment_route') is not None,
        'treatment_frequency': trial.get('treatment_frequency') is not None,
        'treatment_duration': trial.get('treatment_duration_days') is not None,
        'trial_outcomes': trial.get('trial_outcomes') is not None
    }

def get_missing_parameters(trial_id: str) -> List[str]:
    """Get list of missing/empty parameters for a trial"""
    completeness = get_trial_completeness(trial_id)
    missing = []
    
    param_names = {
        'np_size': 'NP Size (nm)',
        'np_charge': 'NP Charge (mV)',
        'np_peg': 'NP PEG (%)',
        'np_zeta_potential': 'NP Zeta Potential',
        'np_pdi': 'NP PDI',
        'treatment_dose': 'Treatment Dose (mg/kg)',
        'treatment_route': 'Treatment Route',
        'treatment_frequency': 'Treatment Frequency',
        'treatment_duration': 'Treatment Duration (days)',
        'trial_outcomes': 'Trial Outcomes'
    }
    
    for param, is_complete in completeness.items():
        if not is_complete:
            missing.append(param_names.get(param, param))
    
    return missing


def update_trial_status(trial_id: str, status: str, notes: str = "") -> bool:
    """
    Update trial status and notes
    
    Args:
        trial_id: Trial ID to update
        status: New status (e.g., 'Active', 'Calibrated', 'Completed')
        notes: Optional notes about the status change
        
    Returns:
        True if successful, False otherwise
    """
    _init_db()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if trial exists
        cursor.execute("SELECT trial_id FROM trials WHERE trial_id = ?", (trial_id,))
        if not cursor.fetchone():
            logger.warning(f"Trial {trial_id} not found")
            conn.close()
            return False
        
        # Update status and notes
        cursor.execute("""
            UPDATE trials 
            SET status = ?, notes = ?, trial_notes = ?
            WHERE trial_id = ?
        """, (status, notes, notes, trial_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated trial {trial_id} status to '{status}'")
        return True
        
    except Exception as e:
        logger.error(f"Error updating trial status: {e}")
        return False
