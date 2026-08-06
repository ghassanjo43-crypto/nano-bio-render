"""
3D Nanoparticle Visualization Component
Renders an interactive 3D model of nanoparticles based on design parameters
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from typing import Dict, List, Tuple


# ============================================================
# MATERIAL COLOR SCHEMES
# ============================================================

MATERIAL_COLORS = {
    "Lipid NP": {"core": "rgb(255, 140, 0)", "core_name": "Orange (Lipid)"},
    "PLGA Nanoparticles": {"core": "rgb(144, 238, 144)", "core_name": "Green (PLGA)"},
    "Gold Nanoparticles": {"core": "rgb(255, 215, 0)", "core_name": "Gold"},
    "Silica Nanoparticles": {"core": "rgb(220, 220, 220)", "core_name": "Silver (Silica)"},
    "DNA Origami": {"core": "rgb(100, 150, 255)", "core_name": "Blue (DNA)"},
    "Liposomes": {"core": "rgb(255, 182, 193)", "core_name": "Pink (Lipid)"},
    "Polymeric Nanoparticles": {"core": "rgb(169, 132, 94)", "core_name": "Brown (Polymer)"},
    "Albumin Nanoparticles": {"core": "rgb(245, 245, 245)", "core_name": "White (Albumin)"},
}


# ============================================================
# TARGETING LIGAND STRUCTURES
# ============================================================

LIGAND_STRUCTURES = {
    "RGD Peptide": {"length": 8, "count": 12, "color": "red", "symbol": "sphere"},
    "Folic Acid": {"length": 10, "count": 15, "color": "purple", "symbol": "cone"},
    "Transferrin": {"length": 12, "count": 8, "color": "darkgreen", "symbol": "cube"},
    "Monoclonal Antibodies": {"length": 15, "count": 6, "color": "darkred", "symbol": "sphere"},
    "Aptamers": {"length": 9, "count": 10, "color": "orange", "symbol": "cone"},
    "Hyaluronic Acid": {"length": 11, "count": 14, "color": "brown", "symbol": "sphere"},
    "Peptides": {"length": 7, "count": 16, "color": "teal", "symbol": "cone"},
    "Galactose/Mannose": {"length": 6, "count": 18, "color": "pink", "symbol": "sphere"},
    "None": {"length": 0, "count": 0, "color": "gray", "symbol": "sphere"},
}


# ============================================================
# 3D MODEL GENERATION
# ============================================================

def generate_core_sphere(size_nm: float, center: Tuple[float, float, float] = (0, 0, 0)) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a sphere for the nanoparticle core"""
    u = np.linspace(0, 2 * np.pi, 50)
    v = np.linspace(0, np.pi, 50)
    
    radius = size_nm / 2
    x = radius * np.outer(np.cos(u), np.sin(v)) + center[0]
    y = radius * np.outer(np.sin(u), np.sin(v)) + center[1]
    z = radius * np.outer(np.ones(np.size(u)), np.cos(v)) + center[2]
    
    return x, y, z


def generate_peg_coating_layer(size_nm: float, peg_thickness_nm: float = 5, center: Tuple[float, float, float] = (0, 0, 0)) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a semi-transparent PEG coating layer"""
    u = np.linspace(0, 2 * np.pi, 40)
    v = np.linspace(0, np.pi, 40)
    
    outer_radius = (size_nm + peg_thickness_nm) / 2
    x = outer_radius * np.outer(np.cos(u), np.sin(v)) + center[0]
    y = outer_radius * np.outer(np.sin(u), np.sin(v)) + center[1]
    z = outer_radius * np.outer(np.ones(np.size(u)), np.cos(v)) + center[2]
    
    return x, y, z


def generate_targeting_ligands(size_nm: float, ligand_type: str, charge_mv: float) -> List[Dict]:
    """Generate targeting ligand positions on nanoparticle surface"""
    if ligand_type not in LIGAND_STRUCTURES or ligand_type == "None":
        return []
    
    ligand_info = LIGAND_STRUCTURES[ligand_type]
    ligand_count = ligand_info["count"]
    ligand_length = ligand_info["length"]
    
    # Create uniform distribution on sphere surface (fibonacci sphere algorithm)
    indices = np.arange(0, ligand_count, dtype=float) + 0.5
    
    phi = np.arccos(1 - 2 * indices / ligand_count)
    theta = np.pi * (1 + 5**0.5) * indices
    
    # Surface points
    radius = size_nm / 2
    surface_x = radius * np.cos(theta) * np.sin(phi)
    surface_y = radius * np.sin(theta) * np.sin(phi)
    surface_z = radius * np.cos(phi)
    
    # Extend outward to create ligand tail
    extension_factor = 1.5
    extension_x = surface_x * extension_factor
    extension_y = surface_y * extension_factor
    extension_z = surface_z * extension_factor
    
    ligands = []
    for i in range(ligand_count):
        ligands.append({
            "x": [surface_x[i], extension_x[i]],
            "y": [surface_y[i], extension_y[i]],
            "z": [surface_z[i], extension_z[i]],
            "color": ligand_info["color"],
            "name": f"{ligand_type} #{i+1}",
            "type": ligand_info["symbol"]
        })
    
    return ligands


def render_nanoparticle_3d(design_params: Dict) -> go.Figure:
    """
    Create 3D visualization of nanoparticle
    
    Args:
        design_params: Dictionary containing:
            - Material: Material type
            - Size: Particle size in nm
            - Charge: Zeta potential in mV
            - Surface Functionalization (Ligand): Targeting ligand type
            - PEG_Density: PEG density percentage
            - Coating_Thickness: Coating thickness
    
    Returns:
        Plotly figure object
    """
    
    # Extract parameters with defaults
    material = design_params.get("Material", "Lipid NP")
    size_nm = float(design_params.get("Size", 100))
    charge_mv = float(design_params.get("Charge", -30))
    ligand_type = design_params.get("Surface Functionalization (Ligand)", "None")
    peg_density = float(design_params.get("PEG_Density", 50))
    coating_thickness = float(design_params.get("CoatingThickness") or design_params.get("Coating_Thickness") or 5)
    
    # Get material color
    material_info = MATERIAL_COLORS.get(material, MATERIAL_COLORS["Lipid NP"])
    core_color = material_info["core"]
    
    # Calculate PEG thickness based on density
    peg_thickness = coating_thickness * (peg_density / 100)
    
    # Create figure
    fig = go.Figure()
    
    # ============================================================
    # ADD CORE SPHERE
    # ============================================================
    
    x_core, y_core, z_core = generate_core_sphere(size_nm)
    
    fig.add_trace(go.Surface(
        x=x_core,
        y=y_core,
        z=z_core,
        colorscale=[[0, core_color], [1, core_color]],
        name=f"{material} Core",
        showscale=False,
        hovertemplate=f"<b>{material} Core</b><br>Material: {material}<br>Size: {size_nm} nm<extra></extra>",
        opacity=0.9,
        showlegend=True
    ))
    
    # ============================================================
    # ADD PEG COATING LAYER (if PEG density > 0)
    # ============================================================
    
    if peg_density > 0 and peg_thickness > 0:
        x_peg, y_peg, z_peg = generate_peg_coating_layer(size_nm, peg_thickness)
        
        fig.add_trace(go.Surface(
            x=x_peg,
            y=y_peg,
            z=z_peg,
            colorscale=[[0, "rgba(200, 200, 200, 0.5)"], [1, "rgba(200, 200, 200, 0.5)"]],
            name=f"PEG Coating ({peg_density}%)",
            showscale=False,
            hovertemplate=f"<b>PEG Coating</b><br>Density: {peg_density}%<br>Thickness: {peg_thickness:.1f} nm<extra></extra>",
            opacity=0.3,
            showlegend=True
        ))
    
    # ============================================================
    # ADD TARGETING LIGANDS
    # ============================================================
    
    ligands = generate_targeting_ligands(size_nm, ligand_type, charge_mv)
    
    for ligand in ligands:
        fig.add_trace(go.Scatter3d(
            x=ligand["x"],
            y=ligand["y"],
            z=ligand["z"],
            mode="lines+markers",
            name=ligand_type,
            line=dict(
                color=ligand["color"],
                width=8
            ),
            marker=dict(
                size=[8, 12],
                color=ligand["color"],
                symbol="circle"
            ),
            hovertemplate=f"<b>{ligand['name']}</b><br>Type: {ligand_type}<extra></extra>",
            showlegend=(ligand == ligands[0]) if ligands else False  # Show legend only for first
        ))
    
    # ============================================================
    # LAYOUT AND STYLING
    # ============================================================
    
    fig.update_layout(
        title={
            "text": f"<b>3D Nanoparticle Structure</b><br><sub>{material} • {size_nm} nm • {ligand_type}</sub>",
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 18}
        },
        scene=dict(
            xaxis=dict(
                title="X (nm)",
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                zeroline=True
            ),
            yaxis=dict(
                title="Y (nm)",
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                zeroline=True
            ),
            zaxis=dict(
                title="Z (nm)",
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                zeroline=True
            ),
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.3)
            ),
            aspectmode="data"
        ),
        height=600,
        showlegend=True,
        legend=dict(
            x=0.02,
            y=0.98,
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="gray",
            borderwidth=1
        ),
        hovermode="closest",
        paper_bgcolor="rgba(240, 240, 240, 1)",
        plot_bgcolor="rgba(255, 255, 255, 1)",
        margin=dict(l=0, r=0, b=0, t=100),
    )
    
    return fig


def render_nanoparticle_specifications(design_params: Dict) -> None:
    """Display detailed nanoparticle specifications alongside 3D view"""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Material",
            design_params.get("Material", "N/A"),
            help="Core nanoparticle material"
        )
    
    with col2:
        size = design_params.get("Size", "N/A")
        st.metric(
            "Size",
            f"{size} nm" if size != "N/A" else size,
            help="Diameter of nanoparticle core"
        )
    
    with col3:
        charge = design_params.get("Charge", "N/A")
        st.metric(
            "Charge",
            f"{charge} mV" if charge != "N/A" else charge,
            help="Zeta potential for colloidal stability"
        )
    
    with col4:
        ligand = design_params.get("Surface Functionalization (Ligand)", "None")
        st.metric(
            "Targeting Ligand",
            ligand,
            help="Targeting moiety on surface"
        )
    
    # Additional specifications
    st.divider()
    
    spec_col1, spec_col2, spec_col3 = st.columns(3)
    
    with spec_col1:
        peg_density = design_params.get("PEG_Density", 0)
        peg_chain = design_params.get("PEG_Chain_Length", "N/A")
        st.info(f"""
        **PEGylation Profile**
        - Density: {peg_density}%
        - Chain Length: {peg_chain} units
        - Purpose: Stealth & Circulation Time
        """)
    
    with spec_col2:
        coating = design_params.get("CoatingThickness") or design_params.get("Coating_Thickness") or 0
        st.info(f"""
        **Coating Layer**
        - Thickness: {coating} nm
        - Material: PEG/Polymer
        - Function: Protect & Reduce Immunogenicity
        """)
    
    with spec_col3:
        drug = design_params.get("Drug", "N/A")
        encapsulation = design_params.get("Encapsulation", "N/A")
        st.info(f"""
        **Payload**
        - Drug: {drug}
        - Encapsulation: {encapsulation}%
        - Type: Chemotherapy/Biologic
        """)


def display_3d_nanoparticle_view(design_params: Dict) -> None:
    """
    Main function to display 3D nanoparticle viewer in Streamlit
    
    Usage in Streamlit app:
        from components.nanoparticle_3d_viewer import display_3d_nanoparticle_view
        
        design = st.session_state.get("design", {})
        display_3d_nanoparticle_view(design)
    """
    
    st.subheader("🔬 3D Nanoparticle Structure")
    st.caption("Interactive 3D visualization of your nanoparticle design. Rotate, zoom, and inspect from all angles.")
    
    # Render 3D visualization
    fig = render_nanoparticle_3d(design_params)
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Display specifications
    render_nanoparticle_specifications(design_params)
    
    st.divider()
    
    # Educational context
    with st.expander("📚 Understanding the 3D Structure", expanded=False):
        col_edu1, col_edu2 = st.columns(2)
        
        with col_edu1:
            st.markdown("""
            ### Core Material
            - **Function:** Main carrier structure
            - **Variability:** Color indicates material type (Lipid, PLGA, Gold, etc.)
            - **Determines:** Biodegradability, biocompatibility, manufacturing
            
            ### Coating Layer (Semi-transparent)
            - **Function:** Stealth mechanism to avoid immune system
            - **Composition:** Polyethylene Glycol (PEG) chains
            - **Effect:** Extends circulation time, reduces opsonization
            """)
        
        with col_edu2:
            st.markdown("""
            ### Targeting Ligands (Protruding Structures)
            - **Function:** Attach to disease cells specifically
            - **Examples:** RGD peptides, folic acid, transferrin
            - **Mechanism:** Receptor-mediated endocytosis
            
            ### Size & Charge
            - **Size:** Affects penetration, clearance route, cell uptake
            - **Charge:** Determines colloidal stability and protein binding
            - **Optimal Range:** 50-200 nm for most applications
            """)
    
    # Visualization tips
    with st.expander("💡 How to Use This 3D View", expanded=False):
        st.markdown("""
        **Interactive Controls:**
        - **Rotate:** Click and drag to rotate the particle
        - **Zoom:** Scroll mouse wheel or pinch to zoom
        - **Pan:** Right-click and drag to pan
        - **Hover:** Move mouse over structures to see details
        - **Legend:** Click legend items to show/hide components
        
        **Analysis Workflow:**
        1. Observe the overall structure and size
        2. Examine coating layer thickness and coverage
        3. Count targeting ligands on surface
        4. Verify material color matches your selection
        5. Compare with previous designs in Trial History
        """)
