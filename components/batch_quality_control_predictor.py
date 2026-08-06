"""
Sprint 3: Batch Quality Control Predictor
Assesses QC parameters, release criteria, and batch variability
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_batch_quality_control(design_params):
    """
    Predict batch quality control metrics
    """
    
    material = design_params.get("Material", "Lipid NP")
    size = design_params.get("Size", 100)
    peg_density = design_params.get("PEG_Density", 50)
    charge = design_params.get("Charge", -5)
    ligand = design_params.get("Ligand", "None")
    
    # QC parameters difficulty by material
    qc_difficulty = {
        "Lipid NP": 0.7,
        "PLGA": 0.8,
        "Liposome": 0.75,
        "Gold NP": 0.6,
        "Albumin NP": 0.65,
        "Silica NP": 0.5,
        "DNA Origami": 0.95,
        "Polymeric NP": 0.85,
        "Exosomes": 0.90
    }
    
    difficulty = qc_difficulty.get(material, 0.75)
    
    # Define QC parameters (each 0-100%)
    qc_parameters = {
        "Particle Size Distribution": {
            "target": 100 - (difficulty * 20),
            "units": "PDI < 0.2",
            "method": "DLS"
        },
        "Encapsulation Efficiency": {
            "target": 90 - (difficulty * 15),
            "units": "%",
            "method": "HPLC/UPLC"
        },
        "Purity": {
            "target": 95 - (difficulty * 10),
            "units": "%",
            "method": "SEC/Mass Spec"
        },
        "Endotoxin Level": {
            "target": 85,
            "units": "< 0.1 EU/mg",
            "method": "LAL Test"
        },
        "Sterility": {
            "target": 100,
            "units": "Neg",
            "method": "Sterile Filter Test"
        },
        "Surface Charge": {
            "target": 100 - (abs(charge) / 50 * 10),
            "units": "Ζ potential",
            "method": "Zetametry"
        },
        "Moisture Content": {
            "target": 90,
            "units": "< 5%",
            "method": "Karl Fischer"
        },
        "Protein Content": {
            "target": 85,
            "units": "mg/mL",
            "method": "BCA/Bradford"
        },
        "Lipid Peroxide": {
            "target": 80,
            "units": "< 2 mEq/kg",
            "method": "TBARS"
        },
        "Bacterial Contamination": {
            "target": 100,
            "units": "Negative",
            "method": "Culture"
        }
    }
    
    # Adjust based on ligand complexity
    if ligand and ligand != "None":
        qc_parameters["Ligand Density"] = {
            "target": 75 - (difficulty * 15),
            "units": "%",
            "method": "HPLC/Densitometry"
        }
        qc_parameters["Ligand Activity"] = {
            "target": 80 - (difficulty * 20),
            "units": "%",
            "method": "Flow Cytometry"
        }
    
    # Calculate release criteria pass rate
    release_criteria = {
        "Potency": {"specification": "90-110%", "pass_rate": 92},
        "Purity": {"specification": "> 95%", "pass_rate": 88},
        "Sterility": {"specification": "Negative", "pass_rate": 100},
        "Endotoxin": {"specification": "< 0.1 EU/mg", "pass_rate": 95},
        "Particle Size": {"specification": "PDI < 0.2", "pass_rate": 85},
        "Moisture": {"specification": "< 5%", "pass_rate": 90}
    }
    
    total_release_rate = np.mean([rc["pass_rate"] for rc in release_criteria.values()])
    
    # Batch variability coefficient
    batch_variability = 15 + (difficulty * 20)  # %
    batch_consistency_score = 100 - batch_variability
    
    # Lot disposition (typical batch success rate)
    lot_disposition = {
        "Pass": 85 + (difficulty * -10),
        "Hold": 10,
        "Reject": 5 + (difficulty * 10)
    }
    
    # Testing timeline (days)
    qc_testing_duration = {
        "Immediate Tests": 1,
        "Potency Assays": 3,
        "Stability Assays": 7,
        "Full Lot Release": 14
    }
    
    total_qc_score = np.mean([v["target"] for v in qc_parameters.values() if isinstance(v, dict) and "target" in v])
    
    return {
        "qc_parameters": qc_parameters,
        "release_criteria": release_criteria,
        "total_release_rate": total_release_rate,
        "batch_variability_percent": batch_variability,
        "batch_consistency_score": batch_consistency_score,
        "lot_disposition": lot_disposition,
        "qc_testing_duration": qc_testing_duration,
        "total_qc_score": total_qc_score,
        "critical_parameters": ["Particle Size Distribution", "Encapsulation Efficiency", "Sterility"],
        "gmp_compliance_level": 85 if difficulty < 0.7 else (75 if difficulty < 0.85 else 65)
    }


def display_batch_quality_control_widget(design_params):
    """Display batch quality control visualization"""
    
    result = predict_batch_quality_control(design_params)
    
    # Overall QC metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("QC Score", f"{result['total_qc_score']:.0f}/100")
    with col2:
        st.metric("Release Rate", f"{result['total_release_rate']:.0f}%")
    with col3:
        st.metric("Batch Consistency", f"{result['batch_consistency_score']:.1f}%")
    with col4:
        st.metric("GMP Compliance", f"{result['gmp_compliance_level']:.0f}%")
    
    st.divider()
    
    # QC Parameters performance
    st.markdown("### QC Parameters Assessment")
    
    qc_df = pd.DataFrame([
        {
            "Parameter": name,
            "Target (%)": param["target"] if "target" in param else 0,
            "Method": param.get("method", ""),
            "Spec": param.get("units", "")
        }
        for name, param in result["qc_parameters"].items()
        if isinstance(param, dict) and "target" in param
    ]).sort_values("Target (%)", ascending=True)
    
    fig_qc = go.Figure(data=[go.Bar(
        x=qc_df["Target (%)"],
        y=qc_df["Parameter"],
        orientation="h",
        marker_color="lightgreen"
    )])
    st.plotly_chart(fig_qc, use_container_width=True, height=350)
    
    st.divider()
    
    # Release Criteria and Batch Disposition
    col_rel, col_lot = st.columns(2)
    
    with col_rel:
        st.markdown("### Release Criteria Pass Rate")
        rel_df = pd.DataFrame([
            {
                "Criterion": name,
                "Pass Rate (%)": rc["pass_rate"],
                "Spec": rc["specification"]
            }
            for name, rc in result["release_criteria"].items()
        ]).sort_values("Pass Rate (%)", ascending=False)
        
        fig_rel = go.Figure(data=[go.Bar(
            x=rel_df["Pass Rate (%)"],
            y=rel_df["Criterion"],
            orientation="h",
            marker_color="lightblue"
        )])
        st.plotly_chart(fig_rel, use_container_width=True, height=300)
    
    with col_lot:
        st.markdown("### Lot Disposition")
        lots = list(result["lot_disposition"].keys())
        values = list(result["lot_disposition"].values())
        colors = ['green', 'yellow', 'red']
        
        fig_lot = go.Figure(data=[go.Pie(
            labels=lots,
            values=values,
            marker_color=colors,
            textposition="inside",
            textinfo="label+percent"
        )])
        st.plotly_chart(fig_lot, use_container_width=True, height=300)
    
    st.divider()
    
    # Testing timeline
    st.markdown("### QC Testing Timeline")
    timeline_df = pd.DataFrame([
        {"Stage": name, "Days": duration}
        for name, duration in result["qc_testing_duration"].items()
    ])
    
    fig_timeline = go.Figure(data=[go.Bar(
        x=timeline_df["Stage"],
        y=timeline_df["Days"],
        marker_color="mediumpurple"
    )])
    st.plotly_chart(fig_timeline, use_container_width=True, height=280)
    
    st.divider()
    
    # Critical parameters and batch variability
    col_crit, col_var = st.columns(2)
    
    with col_crit:
        st.markdown("### Critical QC Parameters")
        for param in result["critical_parameters"]:
            st.write(f"🔴 {param}")
    
    with col_var:
        st.markdown("### Batch Variability Analysis")
        st.metric("Coefficient of Variation", f"{result['batch_variability_percent']:.1f}%")
        st.write(f"*Target: < 10% for release*")
