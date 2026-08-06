"""
Sprint 3: Intellectual Property Predictor
Assesses patent landscape, novelty, and freedom to operate
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_intellectual_property(design_params):
    """
    Predict intellectual property metrics
    """
    
    material = design_params.get("Material", "Lipid NP")
    size = design_params.get("Size", 100)
    peg_density = design_params.get("PEG_Density", 50)
    charge = design_params.get("Charge", -5)
    ligand = design_params.get("Ligand", "None")
    encapsulation = design_params.get("Encapsulation", "Passive Loading")
    target_disease = design_params.get("TargetDisease", "Cancer")
    
    # Material patent landscapes
    patent_landscapes = {
        "Lipid NP": {
            "active_patents": 450,
            "expired_patents": 85,
            "freedom_to_operate": 65,
            "key_patent_holders": ["Moderna", "BioNTech", "Arcturus", "Genentech"],
            "patent_clusters": ["mRNA delivery", "Immunotherapy", "Gene therapy"],
            "threat_level": "High"
        },
        "PLGA": {
            "active_patents": 380,
            "expired_patents": 120,
            "freedom_to_operate": 55,
            "key_patent_holders": ["Evonik", "Alkermes", "TOLMAR", "Intrinsic Therapeutics"],
            "patent_clusters": ["Microspheres", "Long-acting injectables", "Controlled release"],
            "threat_level": "High"
        },
        "Liposome": {
            "active_patents": 520,
            "expired_patents": 180,
            "freedom_to_operate": 50,
            "key_patent_holders": ["Merck", "Gilead", "Celgene", "Liposolutions"],
            "patent_clusters": ["Cancer therapy", "Amphipathic molecules", "Transition metals"],
            "threat_level": "Very High"
        },
        "Gold NP": {
            "active_patents": 280,
            "expired_patents": 50,
            "freedom_to_operate": 80,
            "key_patent_holders": ["Selecta Biosciences", "Luna Innovations"],
            "patent_clusters": ["Plasmonic properties", "Photothermal therapy"],
            "threat_level": "Low-Moderate"
        },
        "Albumin NP": {
            "active_patents": 180,
            "expired_patents": 60,
            "freedom_to_operate": 85,
            "key_patent_holders": ["Abraxis BioScience", "Intrexon"],
            "patent_clusters": ["Protein binding", "Albumin surfactant systems"],
            "threat_level": "Low"
        },
        "Silica NP": {
            "active_patents": 210,
            "expired_patents": 95,
            "freedom_to_operate": 75,
            "key_patent_holders": ["Evonik", "Nissan Chemical", "W.R. Grace"],
            "patent_clusters": ["Mesoporous silica", "Biomedical applications"],
            "threat_level": "Low-Moderate"
        },
        "DNA Origami": {
            "active_patents": 120,
            "expired_patents": 15,
            "freedom_to_operate": 60,
            "key_patent_holders": ["Harvard University", "University of Munich", "Caltech"],
            "patent_clusters": ["DNA nanotechnology", "Self-assembly"],
            "threat_level": "Moderate"
        },
        "Polymeric NP": {
            "active_patents": 320,
            "expired_patents": 110,
            "freedom_to_operate": 70,
            "key_patent_holders": ["BASF", "Dow Chemical", "Nova Chemicals"],
            "patent_clusters": ["Polymer synthesis", "Morphology control"],
            "threat_level": "Moderate"
        },
        "Exosomes": {
            "active_patents": 150,
            "expired_patents": 20,
            "freedom_to_operate": 55,
            "key_patent_holders": ["Codiak Biosciences", "Neara Therapeutics", "Guard Therapeutics"],
            "patent_clusters": ["Extracellular vesicles", "Bioengineered exosomes"],
            "threat_level": "Moderate"
        }
    }
    
    landscape = patent_landscapes.get(material, patent_landscapes["Lipid NP"])
    
    # Assess novelty of specific design combinations
    novelty_elements = []
    novelty_score = landscape["freedom_to_operate"]
    
    # Size novelty
    if size < 30 or size > 200:
        novelty_elements.append("Unusual nanoparticle size +10pt")
        novelty_score += 10
    
    # Charge-PEG combination novelty
    if peg_density > 70 and abs(charge) > 20:
        novelty_elements.append("Unique PEGylation + charge profile +15pt")
        novelty_score += 15
    elif peg_density > 60:
        novelty_elements.append("High PEGylation +8pt")
        novelty_score += 8
    
    # Ligand-targeting combination
    if ligand and ligand != "None":
        novelty_elements.append(f"Targeting ligand ({ligand}) +12pt")
        novelty_score += 12
    
    # Disease-specific patents
    disease_patent_activity = {
        "Cancer": 850,
        "Cardiac": 320,
        "Neurodegenerative": 280,
        "Infectious Disease": 450,
        "Inflammatory": 360,
        "Metabolic": 220,
        "Genetic": 420
    }
    
    disease_patents = disease_patent_activity.get(target_disease, 500)
    
    novelty_score = min(100, novelty_score)
    
    # Patentability assessment
    if novelty_score >= 80:
        patentability = "🟢 Highly Patentable"
        patent_likelihood = 85
    elif novelty_score >= 60:
        patentability = "🟡 Moderately Patentable"
        patent_likelihood = 65
    elif novelty_score >= 40:
        patentability = "🟠 Challenging to Patent"
        patent_likelihood = 40
    else:
        patentability = "🔴 Likely Not Patentable"
        patent_likelihood = 15
    
    # Patent filing cost estimation (USD)
    patent_filing_costs = {
        "US Provisional Patent": 2000,
        "PCT International Patent": 8000,
        "European Patent": 5000,
        "Japanese Patent": 4500,
        "Chinese Patent": 3500,
        "Continuation Patents (5 total)": 15000
    }
    
    total_patent_costs = sum(patent_filing_costs.values())
    
    # Patent protection timeline
    protection_timeline = {
        "Filing to Publication": 18,  # months
        "Publication to Grant (US)": 36,  # months
        "Full International Protection": 48  # months
    }
    
    return {
        "novelty_score": novelty_score,
        "novelty_elements": novelty_elements,
        "patentability": patentability,
        "patent_likelihood_percent": patent_likelihood,
        "freedom_to_operate": landscape["freedom_to_operate"],
        "threat_level": landscape["threat_level"],
        "active_patents_in_field": landscape["active_patents"],
        "expired_patents_in_field": landscape["expired_patents"],
        "key_patent_holders": landscape["key_patent_holders"],
        "patent_clusters": landscape["patent_clusters"],
        "disease_patents": disease_patents,
        "patent_filing_costs": patent_filing_costs,
        "total_patent_costs": total_patent_costs,
        "protection_timeline": protection_timeline,
        "recommended_patents": [
            "Composition of matter",
            "Method of preparation",
            "Therapeutic use",
            "Dosage form/formulation"
        ]
    }


def display_intellectual_property_widget(design_params):
    """Display intellectual property visualization"""
    
    result = predict_intellectual_property(design_params)
    
    # Main IP metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Novelty Score", f"{result['novelty_score']:.0f}/100")
    with col2:
        st.metric("Freedom to Operate", f"{result['freedom_to_operate']}/100")
    with col3:
        st.metric("Patentability Likelihood", f"{result['patent_likelihood_percent']}%")
    with col4:
        st.metric("Threat Level", result["threat_level"])
    
    st.divider()
    
    # Patentability assessment
    st.markdown("### Patentability Assessment")
    st.info(result["patentability"])
    
    # Novelty elements
    if result["novelty_elements"]:
        st.markdown("### Novelty Elements Identified")
        for element in result["novelty_elements"]:
            st.write(f"✓ {element}")
    else:
        st.write("Standard design without significant novel features")
    
    st.divider()
    
    # Patent landscape overview
    col_landscape, col_threat = st.columns(2)
    
    with col_landscape:
        st.markdown("### Patent Landscape")
        
        landscape_data = {
            "Category": ["Active Patents", "Expired Patents", "Freedom to Operate"],
            "Count/Score": [
                result["active_patents_in_field"],
                result["expired_patents_in_field"],
                result["freedom_to_operate"]
            ]
        }
        
        landscape_df = pd.DataFrame(landscape_data)
        st.table(landscape_df)
    
    with col_threat:
        st.markdown("### Patent Holders in Field")
        for holder in result["key_patent_holders"]:
            st.write(f"• {holder}")
    
    st.divider()
    
    # Patent clusters
    st.markdown("### Patent Clusters in This Technology")
    
    col_clusters = st.columns(len(result["patent_clusters"]))
    for i, cluster in enumerate(result["patent_clusters"]):
        with col_clusters[i]:
            st.markdown(f"**{cluster}**")
    
    st.divider()
    
    # Patent filing costs and timeline
    col_costs, col_timeline = st.columns(2)
    
    with col_costs:
        st.markdown("### Patent Filing Cost Breakdown")
        
        cost_df = pd.DataFrame([
            {"Patent Type": name, "Cost ($)": cost}
            for name, cost in result["patent_filing_costs"].items()
        ]).sort_values("Cost ($)", ascending=True)
        
        fig_costs = go.Figure(data=[go.Bar(
            x=cost_df["Cost ($)"],
            y=cost_df["Patent Type"],
            orientation="h",
            marker_color="lightcoral"
        )])
        st.plotly_chart(fig_costs, use_container_width=True, height=350)
        
        st.metric("Total Patent Investment", f"${result['total_patent_costs']:,}")
    
    with col_timeline:
        st.markdown("### Patent Protection Timeline")
        
        timeline_df = pd.DataFrame([
            {"Phase": name, "Months": months}
            for name, months in result["protection_timeline"].items()
        ])
        
        fig_timeline = go.Figure(data=[go.Bar(
            x=timeline_df["Phase"],
            y=timeline_df["Months"],
            marker_color="mediumpurple"
        )])
        st.plotly_chart(fig_timeline, use_container_width=True, height=350)
    
    st.divider()
    
    # Recommended patent types
    st.markdown("### Recommended Patent Applications")
    
    for i, patent_type in enumerate(result["recommended_patents"], 1):
        st.write(f"{i}. {patent_type}")
    
    st.info(f"**Disease-Specific Patents in Field:** {result['disease_patents']} active")
