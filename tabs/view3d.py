"""
3D Nanoparticle Visualization Module
Interactive 3D renderings of nanoparticle designs with multiple visualization modes
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Tuple, List


def create_3d_nanoparticle(design: Dict) -> go.Figure:
    """
    Create interactive 3D nanoparticle model with core, ligands, and encapsulated drugs
    
    Args:
        design: Design dictionary with particle parameters
    
    Returns:
        Plotly figure with 3D nanoparticle visualization
    """
    
    # Core nanoparticle sphere
    size = design.get('Size', 100) / 50  # Scale for visualization
    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    x = size * np.outer(np.cos(u), np.sin(v))
    y = size * np.outer(np.sin(u), np.sin(v))
    z = size * np.outer(np.ones(np.size(u)), np.cos(v))
    
    # Surface charge representation with color coding
    charge = design.get('Charge', 0)
    if charge > 0:
        charge_color = 'red'
    elif charge < 0:
        charge_color = 'blue'
    else:
        charge_color = 'gray'
    
    charge_intensity = min(1.0, abs(charge) / 30)
    
    # Generate ligand positions on surface
    ligand_positions = []
    num_ligands = max(3, int(design.get('Encapsulation', 70) / 20))
    
    for i in range(num_ligands):
        theta = 2 * np.pi * i / num_ligands
        phi = np.pi / 4
        ligand_x = size * 1.2 * np.sin(phi) * np.cos(theta)
        ligand_y = size * 1.2 * np.sin(phi) * np.sin(theta)
        ligand_z = size * 1.2 * np.cos(phi)
        ligand_positions.append((ligand_x, ligand_y, ligand_z))
    
    # Create figure
    fig = go.Figure()
    
    # Add core nanoparticle
    fig.add_trace(go.Surface(
        x=x, y=y, z=z,
        colorscale=[[0, charge_color], [1, charge_color]],
        opacity=0.8,
        showscale=False,
        name=f"Core ({design.get('Size', 100)}nm)"
    ))
    
    # Add ligands if present
    if ligand_positions:
        lig_x, lig_y, lig_z = zip(*ligand_positions)
        fig.add_trace(go.Scatter3d(
            x=lig_x, y=lig_y, z=lig_z,
            mode='markers+lines',
            marker=dict(
                size=6,
                color='green',
                symbol='circle',
                opacity=0.8
            ),
            line=dict(
                color='darkgreen',
                width=2
            ),
            name=f"Ligands ({design.get('Ligand', 'GalNAc')})"
        ))
        
        # Connect ligands to core
        for lig_x_i, lig_y_i, lig_z_i in ligand_positions:
            fig.add_trace(go.Scatter3d(
                x=[0, lig_x_i],
                y=[0, lig_y_i],
                z=[0, lig_z_i],
                mode='lines',
                line=dict(color='lightgreen', width=1),
                showlegend=False,
                hoverinfo='skip'
            ))
    
    # Add encapsulated drug molecules
    if design.get('Encapsulation', 0) > 0:
        drug_positions = []
        num_drugs = max(5, int(design.get('Encapsulation', 70) / 10))
        np.random.seed(42)  # For reproducibility
        
        for i in range(num_drugs):
            r = np.random.random() * size * 0.7
            theta = np.random.random() * 2 * np.pi
            phi = np.random.random() * np.pi
            drug_x = r * np.sin(phi) * np.cos(theta)
            drug_y = r * np.sin(phi) * np.sin(theta)
            drug_z = r * np.cos(phi)
            drug_positions.append((drug_x, drug_y, drug_z))
        
        if drug_positions:
            drug_x, drug_y, drug_z = zip(*drug_positions)
            fig.add_trace(go.Scatter3d(
                x=drug_x, y=drug_y, z=drug_z,
                mode='markers',
                marker=dict(
                    size=3,
                    color='purple',
                    symbol='diamond',
                    opacity=0.9
                ),
                name=f"Drug Payload ({design.get('Encapsulation', 70)}%)"
            ))
    
    # Add surface coating if specified
    if design.get('SurfaceCoating'):
        # Add a slightly larger transparent sphere to represent coating
        coat_size = size * 1.1
        x_coat = coat_size * np.outer(np.cos(u), np.sin(v))
        y_coat = coat_size * np.outer(np.sin(u), np.sin(v))
        z_coat = coat_size * np.outer(np.ones(np.size(u)), np.cos(v))
        
        fig.add_trace(go.Surface(
            x=x_coat, y=y_coat, z=z_coat,
            colorscale=[[0, 'yellow'], [1, 'yellow']],
            opacity=0.2,
            showscale=False,
            name=f"Coating ({design.get('SurfaceCoating', 'PEG')})"
        ))
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=f"<b>3D Nanoparticle Model: {design.get('Material', 'Lipid NP')}</b><br><sub>Size: {design.get('Size', 100)}nm | Charge: {design.get('Charge', 0)}mV</sub>",
            x=0.5,
            xanchor='center'
        ),
        scene=dict(
            xaxis=dict(title="X (nm)", backgroundcolor="rgb(230, 230,230)", gridcolor="white"),
            yaxis=dict(title="Y (nm)", backgroundcolor="rgb(230, 230,230)", gridcolor="white"),
            zaxis=dict(title="Z (nm)", backgroundcolor="rgb(230, 230,230)", gridcolor="white"),
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.5),
                center=dict(x=0, y=0, z=0)
            )
        ),
        width=900,
        height=700,
        showlegend=True,
        hovermode='closest'
    )
    
    return fig


def create_multi_parameter_radar(design: Dict) -> go.Figure:
    """
    Create radar chart comparing current design against optimal parameters
    
    Args:
        design: Design dictionary with particle parameters
    
    Returns:
        Plotly radar figure
    """
    
    categories = ['Size (100nm)', 'Charge (±10mV)', 'Encapsulation (%)', 
                  'Stability (%)', 'PDI (0.15)', 'Targeting']
    
    # Normalize values for radar chart (0-100 scale)
    size_score = max(0, 100 - abs(design.get('Size', 100) - 100) / 2)
    charge_score = max(0, 100 - abs(design.get('Charge', 0)) * 3)
    encap_score = design.get('Encapsulation', 70)
    stability_score = design.get('Stability', 75)
    pdi_score = max(0, 100 - (design.get('PDI', 0.15) * 200))
    targeting_score = 80  # Based on ligand-receptor match
    
    values = [size_score, charge_score, encap_score, stability_score, pdi_score, targeting_score]
    
    fig = go.Figure()
    
    # Current design trace
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name='Current Design',
        line=dict(color='#1f77b4', width=2),
        fillcolor='rgba(31, 119, 180, 0.3)'
    ))
    
    # Optimal design trace
    optimal_values = [95, 95, 95, 95, 95, 95]
    fig.add_trace(go.Scatterpolar(
        r=optimal_values,
        theta=categories,
        fill='toself',
        name='Optimal Target',
        line=dict(color='#2ca02c', width=2, dash='dash'),
        fillcolor='rgba(44, 160, 44, 0.1)'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10)
            ),
            angularaxis=dict(
                tickfont=dict(size=11)
            )
        ),
        showlegend=True,
        title="<b>Design Parameter Performance</b>",
        font=dict(size=12),
        height=600,
        width=800
    )
    
    return fig


def create_size_distribution(design: Dict) -> go.Figure:
    """
    Create a plot showing particle size distribution around the nominal size
    
    Args:
        design: Design dictionary
    
    Returns:
        Plotly histogram figure
    """
    
    nominal_size = design.get('Size', 100)
    pdi = design.get('PDI', 0.15)
    
    # Generate size distribution based on PDI
    # PDI = Mw/Mn, for lognormal: PDI = sqrt(sigma^2 + 1)
    sigma = np.sqrt(np.log(pdi**2 + 1))
    mu = np.log(nominal_size) - sigma**2 / 2
    
    sizes = np.random.lognormal(mu, sigma, 1000)
    sizes = sizes[(sizes > nominal_size * 0.3) & (sizes < nominal_size * 3)]  # Reasonable range
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=sizes,
        nbinsx=50,
        name='Size Distribution',
        marker=dict(color='rgba(99, 110, 250, 0.7)'),
        hovertemplate='Size: %{x:.1f}nm<br>Count: %{y}<extra></extra>'
    ))
    
    # Add nominal size line
    fig.add_vline(
        x=nominal_size,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Nominal: {nominal_size}nm",
        annotation_position="top right"
    )
    
    fig.update_layout(
        title=f"<b>Particle Size Distribution</b><br><sub>Nominal: {nominal_size}nm | PDI: {pdi:.2f}</sub>",
        xaxis_title="Particle Size (nm)",
        yaxis_title="Frequency",
        height=400,
        width=800,
        hovermode='x unified'
    )
    
    return fig


def create_charge_surface_map(design: Dict) -> go.Figure:
    """
    Create a 3D heatmap showing charge distribution on particle surface
    
    Args:
        design: Design dictionary
    
    Returns:
        Plotly 3D surface figure
    """
    
    size = design.get('Size', 100) / 50
    u = np.linspace(0, 2 * np.pi, 50)
    v = np.linspace(0, np.pi, 50)
    x = size * np.outer(np.cos(u), np.sin(v))
    y = size * np.outer(np.sin(u), np.sin(v))
    z = size * np.outer(np.ones(np.size(u)), np.cos(v))
    
    # Create charge intensity map based on surface position
    u_2d, v_2d = np.meshgrid(u, v)
    charge_intensity = np.sin(u_2d) * np.cos(v_2d) * design.get('Charge', 0)
    
    fig = go.Figure()
    
    fig.add_trace(go.Surface(
        x=x, y=y, z=z,
        surfacecolor=charge_intensity,
        colorscale='RdBu',
        showscale=True,
        colorbar=dict(title="Charge<br>Density (mV)"),
        name="Charge Distribution"
    ))
    
    fig.update_layout(
        title=f"<b>Surface Charge Distribution</b><br><sub>Total Charge: {design.get('Charge', 0)}mV</sub>",
        scene=dict(
            xaxis_title="X (nm)",
            yaxis_title="Y (nm)",
            zaxis_title="Z (nm)",
            bgcolor='white'
        ),
        height=700,
        width=900
    )
    
    return fig


def create_composition_breakdown(design: Dict) -> go.Figure:
    """
    Create a pie chart showing nanoparticle composition breakdown
    
    Args:
        design: Design dictionary
    
    Returns:
        Plotly pie figure
    """
    
    # Component percentages
    encapsulation = design.get('Encapsulation', 70)
    matrix = 100 - encapsulation
    
    # Get material type to determine composition
    material = design.get('Material', 'Lipid NP')
    
    if 'Lipid' in material:
        components = ['Drug Payload', 'Lipid Matrix', 'PEG Coating', 'Targeting Ligands']
        percentages = [encapsulation * 0.7, matrix * 0.8, 5, 5]
    elif 'PLGA' in material:
        components = ['Drug Payload', 'PLGA Matrix', 'Surface Coating', 'Other']
        percentages = [encapsulation * 0.75, matrix * 0.75, 8, 100 - encapsulation * 0.75 - matrix * 0.75 - 8]
    else:
        components = ['Drug Payload', 'Core Material', 'Coating', 'Other']
        percentages = [encapsulation * 0.7, matrix * 0.85, 10, 100 - encapsulation * 0.7 - matrix * 0.85 - 10]
    
    # Ensure percentages sum to 100
    percentages = [max(0, p) for p in percentages]
    total = sum(percentages)
    if total > 0:
        percentages = [p * 100 / total for p in percentages]
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
    
    fig = go.Figure(data=[go.Pie(
        labels=components,
        values=percentages,
        marker=dict(colors=colors),
        textposition='inside',
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>%{value:.1f}%<extra></extra>'
    )])
    
    fig.update_layout(
        title=f"<b>Nanoparticle Composition</b><br><sub>{material}</sub>",
        height=500,
        width=700
    )
    
    return fig


def render_3d_visualization():
    """Main render function for 3D visualization tab"""
    
    st.header("🔬 3D Nanoparticle Visualization")
    st.markdown("### Interactive 3D particle models with multiple visualization modes")
    
    # Check if design exists
    if "design" not in st.session_state:
        st.warning("⚠️ No design loaded. Please create a design in the Design tab first.")
        return
    
    design = st.session_state.design
    
    # Create tabs for different visualizations
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 3D Model",
        "📊 Performance",
        "📈 Size Distribution",
        "🌡️ Charge Map",
        "🥧 Composition"
    ])
    
    with tab1:
        st.subheader("3D Nanoparticle Model")
        st.markdown("""
        **Interactive 3D visualization** of your nanoparticle design:
        - **Red/Blue/Gray sphere**: Core particle (colored by charge)
        - **Green dots & lines**: Targeting ligands on surface
        - **Purple diamonds**: Encapsulated drug molecules
        - **Yellow haze**: Surface coating (if applied)
        """)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            try:
                fig_3d = create_3d_nanoparticle(design)
                st.plotly_chart(fig_3d, use_container_width=True)
            except Exception as e:
                st.error(f"Error rendering 3D model: {str(e)}")
        
        with col2:
            st.markdown("### ⚙️ Settings")
            st.info("""
            **Design Parameters:**
            - Material: {}
            - Size: {}nm
            - Charge: {}mV
            - Encapsulation: {}%
            - Ligand: {}
            """.format(
                design.get('Material', 'N/A'),
                design.get('Size', 'N/A'),
                design.get('Charge', 'N/A'),
                design.get('Encapsulation', 'N/A'),
                design.get('Ligand', 'N/A')
            ))
            
            # Rotation controls
            st.markdown("**Rotation Tip:** Click and drag on the 3D plot to rotate")
            st.markdown("**Zoom Tip:** Scroll to zoom in/out")
    
    with tab2:
        st.subheader("Design Parameter Performance")
        st.markdown("""
        Radar chart comparing your current design against optimal parameters:
        - **Blue area**: Your current design performance
        - **Green dashed**: Target optimal values
        - Larger area = Better overall design
        """)
        
        try:
            fig_radar = create_multi_parameter_radar(design)
            st.plotly_chart(fig_radar, use_container_width=True)
        except Exception as e:
            st.error(f"Error rendering radar chart: {str(e)}")
    
    with tab3:
        st.subheader("Particle Size Distribution")
        st.markdown("""
        Shows the expected size range of particles based on PDI (Polydispersity Index):
        - **Histogram**: Frequency distribution
        - **Red line**: Target nominal size
        - Narrower distribution = More uniform particles
        """)
        
        try:
            fig_dist = create_size_distribution(design)
            st.plotly_chart(fig_dist, use_container_width=True)
        except Exception as e:
            st.error(f"Error rendering size distribution: {str(e)}")
    
    with tab4:
        st.subheader("Surface Charge Distribution Heatmap")
        st.markdown("""
        3D visualization of charge density across the particle surface:
        - **Red areas**: Positive charge
        - **Blue areas**: Negative charge
        - **Gradient intensity**: Charge strength
        """)
        
        try:
            fig_charge = create_charge_surface_map(design)
            st.plotly_chart(fig_charge, use_container_width=True)
        except Exception as e:
            st.error(f"Error rendering charge map: {str(e)}")
    
    with tab5:
        st.subheader("Nanoparticle Composition Breakdown")
        st.markdown("""
        Shows the relative proportions of different components:
        - **Drug Payload**: Encapsulated therapeutic agent
        - **Core Material**: Main nanoparticle matrix
        - **Surface Coating**: Protective/functional layer
        - **Targeting Elements**: Ligands for specific delivery
        """)
        
        try:
            fig_comp = create_composition_breakdown(design)
            st.plotly_chart(fig_comp, use_container_width=True)
        except Exception as e:
            st.error(f"Error rendering composition: {str(e)}")
    
    # Educational information section
    st.markdown("---")
    st.markdown("### 🎓 Understanding Your 3D Model")
    
    info_col1, info_col2, info_col3 = st.columns(3)
    
    with info_col1:
        st.markdown("#### 🎯 Core Structure")
        st.markdown("""
        - **Sphere shape**: Represents the nanoparticle core
        - **Color (red/blue/gray)**: Surface charge
        - **Size**: Proportional to actual dimensions
        - **Opacity**: Material density
        """)
    
    with info_col2:
        st.markdown("#### 🎯 Surface Features")
        st.markdown("""
        - **Green dots**: Targeting ligands
        - **Connecting lines**: Attachment points
        - **Distribution**: Based on encapsulation
        - **Density**: Reflects design specifications
        """)
    
    with info_col3:
        st.markdown("#### 🎯 Internal Content")
        st.markdown("""
        - **Purple diamonds**: Drug molecules
        - **Distribution**: Random/uniform based on type
        - **Quantity**: Proportional to encapsulation
        - **Position**: Inside the core matrix
        """)
