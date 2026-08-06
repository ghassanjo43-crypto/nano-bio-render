"""
ML Disease Connector - Links disease-specific parameters with ML model
Enables disease-tagged training data, similarity searches, and recommendations
"""

import sqlite3
import json
from typing import List, Dict, Optional, Tuple
import pandas as pd
from datetime import datetime
import os

# ============================================================
# DATABASE SCHEMA & INITIALIZATION
# ============================================================

DB_PATH = "nanoparticles_disease_tagged.db"

def init_disease_db():
    """Initialize disease-tagged nanoparticle database"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    
    # Create disease-tagged designs table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS disease_tagged_designs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            design_name TEXT NOT NULL,
            cancer_type TEXT NOT NULL,
            hcc_subtype TEXT,  -- "hcc_s", "hcc_ms", "hcc_l", etc.
            drug_names TEXT,  -- JSON list
            
            -- Nanoparticle parameters
            size_nm REAL,
            surface_charge INTEGER,
            peg_coating_percent REAL,
            targeting_ligand TEXT,
            drug_loading_percent REAL,
            
            -- Performance metrics
            predicted_efficacy REAL,  -- ML-predicted efficacy (0-100)
            cytotoxicity_risk REAL,  -- ML-predicted toxicity (0-100)
            bioavailability_estimate REAL,  -- Theoretical bioavailability
            
            -- Design metadata
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            design_source TEXT,  -- "clinical_trial", "literature", "student_design", "ai_generated"
            clinical_trial_id TEXT,  -- Link to clinical trial if applicable
            reference_paper TEXT,  -- Link to research paper
            notes TEXT,
            
            -- User info
            created_by TEXT,  -- "system", "student", "researcher"
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Create disease-specific recommendations table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS disease_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hcc_subtype TEXT UNIQUE NOT NULL,
            recommended_size_nm_min INTEGER,
            recommended_size_nm_max INTEGER,
            recommended_size_optimal INTEGER,
            recommended_charge INTEGER,
            recommended_peg_percent REAL,
            recommended_drug_loading_min INTEGER,
            recommended_drug_loading_max INTEGER,
            recommended_ligands TEXT,  -- JSON list
            design_difficulty_level INTEGER,  -- 1-5
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# ============================================================
# DATA INSERTION FUNCTIONS
# ============================================================

def add_design_to_database(
    design_name: str,
    cancer_type: str,
    hcc_subtype: str,
    drug_names: List[str],
    size_nm: float,
    surface_charge: int,
    peg_coating_percent: float,
    targeting_ligand: str,
    drug_loading_percent: float,
    predicted_efficacy: float,
    cytotoxicity_risk: float,
    design_source: str = "student_design",
    clinical_trial_id: Optional[str] = None,
    created_by: str = "student",
    notes: str = ""
) -> int:
    """Add a new design to the disease-tagged database"""
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    
    try:
        cur.execute('''
            INSERT INTO disease_tagged_designs (
                design_name, cancer_type, hcc_subtype, drug_names,
                size_nm, surface_charge, peg_coating_percent, targeting_ligand,
                drug_loading_percent, predicted_efficacy, cytotoxicity_risk,
                design_source, clinical_trial_id, created_by, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            design_name, cancer_type, hcc_subtype, json.dumps(drug_names),
            size_nm, surface_charge, peg_coating_percent, targeting_ligand,
            drug_loading_percent, predicted_efficacy, cytotoxicity_risk,
            design_source, clinical_trial_id, created_by, notes
        ))
        
        conn.commit()
        design_id = cur.lastrowid
        return design_id
    
    finally:
        conn.close()

def add_recommendation_to_database(
    hcc_subtype: str,
    size_nm_min: int,
    size_nm_max: int,
    size_optimal: int,
    charge: int,
    peg_percent: float,
    drug_loading_min: int,
    drug_loading_max: int,
    ligands: List[str],
    difficulty_level: int
) -> bool:
    """Add disease-specific design recommendations"""
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    
    try:
        cur.execute('''
            INSERT OR REPLACE INTO disease_recommendations (
                hcc_subtype, recommended_size_nm_min, recommended_size_nm_max,
                recommended_size_optimal, recommended_charge, recommended_peg_percent,
                recommended_drug_loading_min, recommended_drug_loading_max,
                recommended_ligands, design_difficulty_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            hcc_subtype, size_nm_min, size_nm_max, size_optimal,
            charge, peg_percent, drug_loading_min, drug_loading_max,
            json.dumps(ligands), difficulty_level
        ))
        
        conn.commit()
        return True
    
    finally:
        conn.close()

# ============================================================
# QUERY FUNCTIONS
# ============================================================

def get_similar_designs_for_disease(
    hcc_subtype: str,
    size_nm: float,
    surface_charge: int,
    tolerance_percent: float = 10
) -> pd.DataFrame:
    """
    Find similar historical designs for a given HCC subtype
    Returns designs within tolerance_percent of target parameters
    """
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    
    size_tolerance = (size_nm / 100) * tolerance_percent
    
    query = '''
        SELECT 
            design_name, cancer_type, hcc_subtype, drug_names,
            size_nm, surface_charge, peg_coating_percent, targeting_ligand,
            drug_loading_percent, predicted_efficacy, cytotoxicity_risk,
            design_source, created_date, notes
        FROM disease_tagged_designs
        WHERE hcc_subtype = ?
            AND size_nm BETWEEN ? AND ?
            AND surface_charge BETWEEN ? AND ?
            AND is_active = 1
        ORDER BY predicted_efficacy DESC
        LIMIT 10
    '''
    
    try:
        df = pd.read_sql_query(query, conn, params=(
            hcc_subtype,
            size_nm - size_tolerance,
            size_nm + size_tolerance,
            surface_charge - 2,
            surface_charge + 2
        ))
        
        # Parse drug_names from JSON
        if len(df) > 0:
            df['drug_names'] = df['drug_names'].apply(json.loads)
        
        return df
    
    finally:
        conn.close()

def get_all_designs_for_hcc_subtype(hcc_subtype: str) -> pd.DataFrame:
    """Get all designs for a specific HCC subtype"""
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    
    query = '''
        SELECT 
            design_name, cancer_type, hcc_subtype, drug_names,
            size_nm, surface_charge, peg_coating_percent, targeting_ligand,
            drug_loading_percent, predicted_efficacy, cytotoxicity_risk,
            design_source, created_date
        FROM disease_tagged_designs
        WHERE hcc_subtype = ? AND is_active = 1
        ORDER BY predicted_efficacy DESC
    '''
    
    try:
        df = pd.read_sql_query(query, conn, params=(hcc_subtype,))
        
        if len(df) > 0:
            df['drug_names'] = df['drug_names'].apply(json.loads)
        
        return df
    
    finally:
        conn.close()

def get_top_performers_by_disease(
    hcc_subtype: str,
    metric: str = "predicted_efficacy",
    top_n: int = 5
) -> pd.DataFrame:
    """Get top performing designs for a specific HCC subtype"""
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    
    # Validate metric to prevent SQL injection
    valid_metrics = ["predicted_efficacy", "cytotoxicity_risk"]
    if metric not in valid_metrics:
        metric = "predicted_efficacy"
    
    order_by = f"ORDER BY {metric} DESC" if metric == "predicted_efficacy" else f"ORDER BY {metric} ASC"
    
    query = f'''
        SELECT 
            design_name, cancer_type, hcc_subtype, drug_names,
            size_nm, surface_charge, peg_coating_percent, targeting_ligand,
            drug_loading_percent, predicted_efficacy, cytotoxicity_risk,
            design_source, created_date, notes
        FROM disease_tagged_designs
        WHERE hcc_subtype = ? AND is_active = 1
        {order_by}
        LIMIT ?
    '''
    
    try:
        df = pd.read_sql_query(query, conn, params=(hcc_subtype, top_n))
        
        if len(df) > 0:
            df['drug_names'] = df['drug_names'].apply(json.loads)
        
        return df
    
    finally:
        conn.close()

def get_disease_statistics(hcc_subtype: str) -> Dict:
    """Get statistics for designs of a specific HCC subtype"""
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT 
                COUNT(*) as total_designs,
                AVG(size_nm) as avg_size,
                MIN(size_nm) as min_size,
                MAX(size_nm) as max_size,
                AVG(predicted_efficacy) as avg_efficacy,
                AVG(cytotoxicity_risk) as avg_toxicity,
                COUNT(DISTINCT design_source) as design_sources
            FROM disease_tagged_designs
            WHERE hcc_subtype = ? AND is_active = 1
        ''', (hcc_subtype,))
        
        row = cur.fetchone()
        
        if row:
            return {
                "total_designs": row[0],
                "avg_size_nm": round(row[1], 2) if row[1] else 0,
                "min_size_nm": round(row[2], 2) if row[2] else 0,
                "max_size_nm": round(row[3], 2) if row[3] else 0,
                "avg_predicted_efficacy": round(row[4], 2) if row[4] else 0,
                "avg_toxicity_risk": round(row[5], 2) if row[5] else 0,
                "design_sources": row[6] or 0
            }
        else:
            return {
                "total_designs": 0,
                "avg_size_nm": 0,
                "min_size_nm": 0,
                "max_size_nm": 0,
                "avg_predicted_efficacy": 0,
                "avg_toxicity_risk": 0,
                "design_sources": 0
            }
    
    finally:
        conn.close()

def get_recommendation_for_subtype(hcc_subtype: str) -> Optional[Dict]:
    """Get design recommendations for a specific HCC subtype"""
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT 
                hcc_subtype, recommended_size_nm_min, recommended_size_nm_max,
                recommended_size_optimal, recommended_charge, recommended_peg_percent,
                recommended_drug_loading_min, recommended_drug_loading_max,
                recommended_ligands, design_difficulty_level
            FROM disease_recommendations
            WHERE hcc_subtype = ?
        ''', (hcc_subtype,))
        
        row = cur.fetchone()
        
        if row:
            return {
                "hcc_subtype": row[0],
                "size_nm_min": row[1],
                "size_nm_max": row[2],
                "size_optimal": row[3],
                "charge": row[4],
                "peg_percent": row[5],
                "drug_loading_min": row[6],
                "drug_loading_max": row[7],
                "ligands": json.loads(row[8]),
                "difficulty_level": row[9]
            }
        else:
            return None
    
    finally:
        conn.close()

# ============================================================
# ML MODEL INTEGRATION
# ============================================================

def score_design_for_disease(
    hcc_subtype: str,
    size_nm: float,
    surface_charge: int,
    peg_percent: float,
    drug_loading: float,
    targeting_ligand: str
) -> Tuple[float, str]:
    """
    Score a design against disease-specific recommendations
    Returns (score, feedback)
    """
    
    recommendation = get_recommendation_for_subtype(hcc_subtype)
    
    if not recommendation:
        return 50.0, "No recommendations available for this subtype"
    
    score = 100.0
    feedback = []
    
    # Size scoring
    if recommendation["size_nm_min"] <= size_nm <= recommendation["size_nm_max"]:
        feedback.append(f"✅ Size {size_nm}nm is within optimal range")
    else:
        score -= 20
        feedback.append(f"⚠️ Size {size_nm}nm is outside optimal range ({recommendation['size_nm_min']}-{recommendation['size_nm_max']}nm)")
    
    # Charge scoring
    if surface_charge == recommendation["charge"]:
        feedback.append(f"✅ Surface charge {surface_charge} matches recommendation")
    else:
        score -= 10
        feedback.append(f"⚠️ Charge {surface_charge} differs from recommended {recommendation['charge']}")
    
    # PEG scoring
    if abs(peg_percent - recommendation["peg_percent"]) <= 2:
        feedback.append(f"✅ PEG coating {peg_percent}% is within acceptable range")
    else:
        score -= 10
        feedback.append(f"⚠️ PEG {peg_percent}% differs from recommended {recommendation['peg_percent']}%")
    
    # Drug loading scoring
    if recommendation["drug_loading_min"] <= drug_loading <= recommendation["drug_loading_max"]:
        feedback.append(f"✅ Drug loading {drug_loading}% is within optimal range")
    else:
        score -= 15
        feedback.append(f"⚠️ Drug loading {drug_loading}% is outside optimal range ({recommendation['drug_loading_min']}-{recommendation['drug_loading_max']}%)")
    
    # Ensure score doesn't go below 0
    score = max(0.0, score)
    
    return score, "\n".join(feedback)

# ============================================================
# DATABASE MAINTENANCE
# ============================================================

def populate_initial_recommendations():
    """Populate the database with initial recommendations from disease_database"""
    from modules.disease_database import (
        get_disease_design_parameters,
        get_liver_cancer_subtypes,
        get_design_rationale
    )
    
    difficulty_map = {"hcc_s": 1, "hcc_ms": 3, "hcc_l": 5}
    
    for subtype in get_liver_cancer_subtypes():
        params = get_disease_design_parameters(subtype)
        if params:
            difficulty_level = difficulty_map.get(subtype, 3)
            add_recommendation_to_database(
                hcc_subtype=subtype,
                size_nm_min=params.size_nm_min,
                size_nm_max=params.size_nm_max,
                size_optimal=params.size_nm_optimal,
                charge=params.charge_value,
                peg_percent=params.peg_coating_percent,
                drug_loading_min=params.drug_loading_percent_min,
                drug_loading_max=params.drug_loading_percent_max,
                ligands=[params.targeting_ligand.value],
                difficulty_level=difficulty_level
            )

# ============================================================
# DEMO DATA
# ============================================================

def add_sample_designs():
    """Add sample designs to demonstrate the system"""
    
    # HCC-L aggressive case with high efficacy
    add_design_to_database(
        design_name="HCC-L Optimized v1",
        cancer_type="liver",
        hcc_subtype="hcc_l",
        drug_names=["Atezolizumab", "Bevacizumab"],
        size_nm=65,
        surface_charge=-10,
        peg_coating_percent=10.0,
        targeting_ligand="asgpr_peptide",
        drug_loading_percent=35,
        predicted_efficacy=87.5,
        cytotoxicity_risk=12.3,
        design_source="clinical_trial",
        clinical_trial_id="IMBRAVE150",
        created_by="system",
        notes="Based on IMbrave150 trial data for advanced HCC-L"
    )
    
    # HCC-MS intermediate case
    add_design_to_database(
        design_name="HCC-MS Balanced Design",
        cancer_type="liver",
        hcc_subtype="hcc_ms",
        drug_names=["Lenvatinib"],
        size_nm=100,
        surface_charge=-5,
        peg_coating_percent=7.0,
        targeting_ligand="asialoglycoprotein",
        drug_loading_percent=28,
        predicted_efficacy=76.3,
        cytotoxicity_risk=18.5,
        design_source="literature",
        created_by="system",
        notes="Intermediate HCC design balancing efficacy and safety"
    )
    
    # HCC-S slower case
    add_design_to_database(
        design_name="HCC-S Well-Differentiated",
        cancer_type="liver",
        hcc_subtype="hcc_s",
        drug_names=["Sorafenib"],
        size_nm=120,
        surface_charge=0,
        peg_coating_percent=5.0,
        targeting_ligand="asialoglycoprotein",
        drug_loading_percent=24,
        predicted_efficacy=72.1,
        cytotoxicity_risk=8.7,
        design_source="literature",
        created_by="system",
        notes="Well-differentiated HCC design with low toxicity profile"
    )

# Initialize database when module is first imported
if not os.path.exists(DB_PATH):
    init_disease_db()
    populate_initial_recommendations()
    add_sample_designs()
