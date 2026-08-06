"""
Sprint 3: Cost Analysis Predictor
Assesses manufacturing costs, development costs, and market pricing
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_cost_analysis(design_params):
    """
    Predict cost metrics for the nanoparticle design
    """
    
    material = design_params.get("Material", "Lipid NP")
    size = design_params.get("Size", 100)
    peg_density = design_params.get("PEG_Density", 50)
    charge = design_params.get("Charge", -5)
    ligand = design_params.get("Ligand", "None")
    encapsulation = design_params.get("Encapsulation", "Passive Loading")
    
    # Base material costs ($/gram of nanoparticles)
    material_costs = {
        "Lipid NP": 150,
        "PLGA": 120,
        "Liposome": 140,
        "Gold NP": 800,
        "Albumin NP": 100,
        "Silica NP": 80,
        "DNA Origami": 1200,
        "Polymeric NP": 200,
        "Exosomes": 500
    }
    
    base_material_cost = material_costs.get(material, 150)
    
    # Manufacturing complexity multipliers
    encapsulation_multiplier = {
        "Passive Loading": 1.0,
        "Active Loading": 1.3,
        "Electroporation": 1.5,
        "Hydrodynamic Injection": 1.8,
        "Microfluidic": 2.2,
        "Emulsification": 1.2
    }
    
    enc_mult = encapsulation_multiplier.get(encapsulation, 1.0)
    
    # PEG and ligand additions
    peg_cost = (peg_density / 100) * 50  # $0-50 per gram
    ligand_cost = 100 if (ligand and ligand != "None") else 0
    
    # Total material cost per gram of final NP
    material_cost_per_gram = base_material_cost + peg_cost + ligand_cost
    
    # Labor and equipment costs
    labor_hours_per_batch = 16 + (encapsulation == "Microfluidic") * 8  # hours
    labor_rate = 35  # $/hour
    labor_cost = labor_hours_per_batch * labor_rate
    
    # Equipment amortization per batch (assuming batch is 10g)
    equipment_per_batch = 200 + (encapsulation == "Microfluidic") * 300
    
    # QC/Testing costs
    qc_cost = 400 + (ligand != "None") * 200 + (material == "DNA Origami") * 300
    
    # Packaging and delivery
    packaging_cost = 150
    
    # Calculate costs for 10g batch
    batch_size_g = 10
    batch_material_cost = material_cost_per_gram * batch_size_g * enc_mult
    batch_total_cost = (
        batch_material_cost +
        labor_cost +
        equipment_per_batch +
        qc_cost +
        packaging_cost
    )
    
    cost_per_dose_10mg = (batch_total_cost / batch_size_g) * 0.01  # per 10mg dose
    cost_per_dose_100mg = cost_per_dose_10mg * 10
    
    # Development costs
    development_phases = {
        "Synthesis Optimization": 15000,
        "Characterization": 12000,
        "Stability Testing": 10000,
        "Safety Assessment": 18000,
        "Scale-up Studies": 25000,
        "Regulatory Documentation": 20000
    }
    
    total_dev_cost = sum(development_phases.values())
    
    # Timeline to commercialization (months)
    timeline_months = {
        "Research & Development": 6,
        "Scale-up & Process Transfer": 4,
        "Regulatory Preparation": 4,
        "Regulatory Review": 6
    }
    total_timeline = sum(timeline_months.values())
    
    # Market pricing strategy
    cogs = cost_per_dose_10mg
    markup_research = 15  # 15x markup for research use
    markup_clinical = 25  # 25x markup for clinical use
    
    research_price = cogs * markup_research
    clinical_price = cogs * markup_clinical
    
    # Cost breakdown for visualization
    cost_breakdown = {
        "Raw Materials": batch_material_cost,
        "Labor": labor_cost,
        "Equipment": equipment_per_batch,
        "QC & Testing": qc_cost,
        "Packaging & Delivery": packaging_cost
    }
    
    # Return analysis (assuming 5-year product life)
    annual_production_units = 1_000_000  # 10mg doses per year
    annual_revenue_research = annual_production_units * research_price * 0.6  # 60% research market
    annual_revenue_clinical = annual_production_units * clinical_price * 0.4  # 40% clinical
    annual_revenue = annual_revenue_research + annual_revenue_clinical
    annual_cogs = annual_production_units * cogs
    annual_gross_profit = annual_revenue - annual_cogs
    gross_margin = (annual_gross_profit / annual_revenue) * 100
    
    # Payback period (months)
    monthly_profit = annual_gross_profit / 12
    payback_months = total_dev_cost / monthly_profit if monthly_profit > 0 else 999
    
    return {
        "cost_per_dose_10mg_usd": cost_per_dose_10mg,
        "cost_per_dose_100mg_usd": cost_per_dose_100mg,
        "batch_cost_10g": batch_total_cost,
        "development_cost_total": total_dev_cost,
        "development_phases": development_phases,
        "timeline_months": timeline_months,
        "total_timeline_months": total_timeline,
        "research_price_per_dose": research_price,
        "clinical_price_per_dose": clinical_price,
        "cost_breakdown": cost_breakdown,
        "annual_revenue_usd": annual_revenue,
        "annual_cogs": annual_cogs,
        "gross_margin_percent": gross_margin,
        "payback_period_months": payback_months,
        "material_cost_percent": (batch_material_cost / batch_total_cost) * 100
    }


def display_cost_analysis_widget(design_params):
    """Display cost analysis visualization"""
    
    result = predict_cost_analysis(design_params)
    
    # Cost per dose metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("COGS (10mg)", f"${result['cost_per_dose_10mg_usd']:.2f}")
    with col2:
        st.metric("Research Price (10mg)", f"${result['research_price_per_dose']:.2f}")
    with col3:
        st.metric("Clinical Price (10mg)", f"${result['clinical_price_per_dose']:.2f}")
    with col4:
        st.metric("Batch Cost (10g)", f"${result['batch_cost_10g']:.0f}")
    
    st.divider()
    
    # Cost breakdown pie chart
    col_break, col_dev = st.columns(2)
    
    with col_break:
        st.markdown("### Manufacturing Cost Breakdown (10g batch)")
        
        breakdown_df = pd.DataFrame([
            {"Component": name, "Cost ($)": cost}
            for name, cost in result["cost_breakdown"].items()
        ]).sort_values("Cost ($)", ascending=True)
        
        fig_break = go.Figure(data=[go.Pie(
            labels=breakdown_df["Component"],
            values=breakdown_df["Cost ($)"],
            textposition="inside",
            textinfo="label+percent"
        )])
        st.plotly_chart(fig_break, use_container_width=True, height=350)
    
    with col_dev:
        st.markdown("### Development Cost Breakdown")
        
        dev_df = pd.DataFrame([
            {"Phase": name, "Cost ($)": cost}
            for name, cost in result["development_phases"].items()
        ]).sort_values("Cost ($)", ascending=True)
        
        fig_dev = go.Figure(data=[go.Bar(
            x=dev_df["Cost ($)"],
            y=dev_df["Phase"],
            orientation="h",
            marker_color="lightcoral"
        )])
        st.plotly_chart(fig_dev, use_container_width=True, height=350)
    
    st.divider()
    
    # Development timeline
    st.markdown("### Development Timeline to Commercialization")
    
    timeline_df = pd.DataFrame([
        {"Phase": name, "Months": months}
        for name, months in result["timeline_months"].items()
    ])
    
    fig_timeline = go.Figure(data=[go.Bar(
        x=timeline_df["Phase"],
        y=timeline_df["Months"],
        marker_color="mediumpurple"
    )])
    st.plotly_chart(fig_timeline, use_container_width=True, height=300)
    
    st.write(f"**Total Timeline:** {result['total_timeline_months']} months (~{result['total_timeline_months']/12:.1f} years)")
    
    st.divider()
    
    # Financial projections
    col_fin1, col_fin2 = st.columns(2)
    
    with col_fin1:
        st.markdown("### 5-Year Financial Projection")
        st.metric("Annual Revenue (Year 5)", f"${result['annual_revenue_usd']:,.0f}")
        st.metric("Gross Margin", f"{result['gross_margin_percent']:.1f}%")
        st.metric("Material Cost % of COGS", f"{result['material_cost_percent']:.1f}%")
    
    with col_fin2:
        st.markdown("### Investment Analysis")
        st.metric("Development Cost", f"${result['development_cost_total']:,.0f}")
        if result['payback_period_months'] < 999:
            years = result['payback_period_months'] / 12
            st.metric("Payback Period", f"{years:.1f} years")
        else:
            st.metric("Payback Period", "Not profitable")
    
    st.divider()
    
    # Pricing comparison
    st.markdown("### Market Pricing Strategy")
    
    pricing_data = {
        "Market Segment": ["Research Grade (60%)", "Clinical Use (40%)"],
        "Price per 10mg ($)": [result["research_price_per_dose"], result["clinical_price_per_dose"]],
        "Markup Factor": [15, 25]
    }
    
    pricing_df = pd.DataFrame(pricing_data)
    st.table(pricing_df)
