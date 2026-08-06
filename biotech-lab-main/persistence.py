# ============================================================
# Design Persistence & Storage Helper
# Streamlit integration for database operations
# ============================================================

import streamlit as st
from models import (
    SessionLocal, DesignRepository, ProjectRepository, 
    OptimizationRepository, Design, Project
)
from datetime import datetime
import pandas as pd

# ============================================================
# Session Management
# ============================================================

def get_current_user_id() -> int:
    """Get current logged-in user ID from session state"""
    if "user_id" not in st.session_state:
        # For now, use username as proxy (should be replaced with actual user_id)
        # This requires auth.py to be updated to set user_id
        return None
    return st.session_state.user_id


def init_persistence_session():
    """Initialize persistence session state"""
    if "current_project_id" not in st.session_state:
        st.session_state.current_project_id = None
    if "design_list_cache" not in st.session_state:
        st.session_state.design_list_cache = None
    if "current_design" not in st.session_state:
        st.session_state.current_design = None


# ============================================================
# Design Operations
# ============================================================

def save_design(name: str, parameters: dict, description: str = None, 
                project_id: int = None, scores: dict = None) -> Design:
    """Save design to database"""
    user_id = get_current_user_id()
    if not user_id:
        st.error("User not authenticated")
        return None
    
    db = SessionLocal()
    try:
        repo = DesignRepository(db)
        design = repo.create_design(
            user_id=user_id,
            name=name,
            parameters=parameters,
            project_id=project_id or st.session_state.current_project_id,
            description=description
        )
        
        # Update scores if provided
        if scores:
            repo.update_design_scores(
                design.id,
                delivery=scores.get('delivery', 0),
                toxicity=scores.get('toxicity', 5),
                cost=scores.get('cost', 100)
            )
        
        # Clear cache
        st.session_state.design_list_cache = None
        st.success(f"✅ Design '{name}' saved successfully!")
        return design
    
    except Exception as e:
        st.error(f"Error saving design: {str(e)}")
        return None
    finally:
        db.close()


def load_design(design_id: int) -> Design:
    """Load design from database"""
    db = SessionLocal()
    try:
        repo = DesignRepository(db)
        design = repo.get_design(design_id)
        if design:
            st.session_state.current_design = design
            return design
        else:
            st.error("Design not found")
            return None
    finally:
        db.close()


def list_user_designs(project_id: int = None) -> list:
    """List all designs for current user"""
    user_id = get_current_user_id()
    if not user_id:
        return []
    
    db = SessionLocal()
    try:
        repo = DesignRepository(db)
        designs = repo.list_user_designs(user_id, project_id)
        return designs
    finally:
        db.close()


def delete_design(design_id: int) -> bool:
    """Delete a design"""
    db = SessionLocal()
    try:
        repo = DesignRepository(db)
        success = repo.delete_design(design_id)
        if success:
            st.session_state.design_list_cache = None
            st.success("Design deleted successfully")
        return success
    except Exception as e:
        st.error(f"Error deleting design: {str(e)}")
        return False
    finally:
        db.close()


def update_design(design_id: int, **kwargs) -> Design:
    """Update a design"""
    db = SessionLocal()
    try:
        repo = DesignRepository(db)
        design = repo.update_design(design_id, **kwargs)
        st.session_state.design_list_cache = None
        return design
    except Exception as e:
        st.error(f"Error updating design: {str(e)}")
        return None
    finally:
        db.close()


def get_design_as_dict(design: Design) -> dict:
    """Convert design object to dictionary"""
    return {
        'id': design.id,
        'name': design.name,
        'description': design.description,
        'parameters': design.parameters,
        'delivery_score': design.delivery_score,
        'toxicity_score': design.toxicity_score,
        'cost_score': design.cost_score,
        'overall_score': design.overall_score,
        'created_at': design.created_at.isoformat() if design.created_at else None,
        'updated_at': design.updated_at.isoformat() if design.updated_at else None,
        'is_favorited': design.is_favorited,
        'version': design.version
    }


def designs_to_dataframe(designs: list) -> pd.DataFrame:
    """Convert list of designs to pandas DataFrame for display"""
    if not designs:
        return pd.DataFrame()
    
    data = []
    for design in designs:
        data.append({
            'ID': design.id,
            'Name': design.name,
            'Material': design.parameters.get('Material', 'N/A'),
            'Size (nm)': design.parameters.get('Size', 'N/A'),
            'Delivery Score': f"{design.delivery_score:.1f}%" if design.delivery_score else "—",
            'Toxicity': f"{design.toxicity_score:.1f}/10" if design.toxicity_score else "—",
            'Cost': f"{design.cost_score:.1f}" if design.cost_score else "—",
            'Overall Score': f"{design.overall_score:.2f}" if design.overall_score else "—",
            'Created': design.created_at.strftime('%Y-%m-%d %H:%M') if design.created_at else "—",
            '★': '⭐' if design.is_favorited else '☆'
        })
    
    return pd.DataFrame(data)


# ============================================================
# Project Operations
# ============================================================

def create_project(name: str, description: str = None) -> Project:
    """Create a new project"""
    user_id = get_current_user_id()
    if not user_id:
        st.error("User not authenticated")
        return None
    
    db = SessionLocal()
    try:
        repo = ProjectRepository(db)
        project = repo.create_project(user_id, name, description)
        st.success(f"✅ Project '{name}' created!")
        return project
    except Exception as e:
        st.error(f"Error creating project: {str(e)}")
        return None
    finally:
        db.close()


def list_user_projects() -> list:
    """List all projects for current user"""
    user_id = get_current_user_id()
    if not user_id:
        return []
    
    db = SessionLocal()
    try:
        repo = ProjectRepository(db)
        return repo.list_user_projects(user_id)
    finally:
        db.close()


def get_project(project_id: int) -> Project:
    """Get a project by ID"""
    db = SessionLocal()
    try:
        repo = ProjectRepository(db)
        return repo.get_project(project_id)
    finally:
        db.close()


# ============================================================
# Optimization Operations
# ============================================================

def save_optimization_run(design_id: int, objective_weights: dict, 
                         pareto_front: list, best_design: dict, 
                         algorithm: str = "optuna", evaluations: int = 0):
    """Save optimization run results"""
    db = SessionLocal()
    try:
        repo = OptimizationRepository(db)
        opt = repo.create_optimization(design_id, objective_weights, algorithm)
        opt = repo.update_optimization(
            opt.id,
            status="completed",
            pareto_front=pareto_front,
            best_design=best_design,
            total_evaluations=evaluations,
            completed_at=datetime.utcnow()
        )
        st.success("✅ Optimization results saved!")
        return opt
    except Exception as e:
        st.error(f"Error saving optimization: {str(e)}")
        return None
    finally:
        db.close()


def get_optimization_history(design_id: int) -> list:
    """Get all optimization runs for a design"""
    db = SessionLocal()
    try:
        repo = OptimizationRepository(db)
        return repo.list_design_optimizations(design_id)
    finally:
        db.close()


# ============================================================
# UI Helpers
# ============================================================

def render_design_selector():
    """Render a UI widget to select a saved design"""
    projects = list_user_projects()
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_project = st.selectbox(
            "Select Project (optional)",
            [None] + projects,
            format_func=lambda x: "All Designs" if x is None else x.name,
            key="design_project_selector"
        )
        if selected_project:
            st.session_state.current_project_id = selected_project.id
        else:
            st.session_state.current_project_id = None
    
    with col2:
        if st.button("🔄 Refresh", width='stretch'):
            st.session_state.design_list_cache = None
            st.rerun()
    
    # Load designs
    designs = list_user_designs(st.session_state.current_project_id)
    
    if designs:
        df = designs_to_dataframe(designs)
        st.dataframe(df, width='stretch', hide_index=True)
        
        # Load design button
        design_ids = {d.name: d.id for d in designs}
        selected_design_name = st.selectbox(
            "Load Design",
            list(design_ids.keys()),
            key="design_loader"
        )
        
        if st.button("📂 Load Selected Design", width='stretch'):
            design = load_design(design_ids[selected_design_name])
            if design:
                st.session_state.design = design.parameters
                st.success(f"Loaded: {design.name}")
                st.rerun()
    else:
        st.info("📭 No designs saved yet. Create your first design to get started!")


def render_save_design_form():
    """Render a form to save current design"""
    st.subheader("💾 Save Design")
    
    col1, col2 = st.columns(2)
    with col1:
        design_name = st.text_input("Design Name", placeholder="e.g., 'Liver-Targeting NP v1'")
    with col2:
        projects = list_user_projects()
        selected_project = st.selectbox(
            "Project",
            [None] + projects,
            format_func=lambda x: "New Project" if x is None else x.name
        )
    
    description = st.text_area("Description (optional)", height=80)
    
    if st.button("💾 Save Design", width='stretch', type="primary"):
        if not design_name:
            st.error("Please enter a design name")
        else:
            project_id = selected_project.id if selected_project else None
            design = save_design(
                name=design_name,
                parameters=st.session_state.design,
                description=description,
                project_id=project_id
            )
            if design:
                st.balloons()
                st.rerun()
