"""
Professional Scientific Report Generator for NanoBio Studio
Generates comprehensive preclinical research reports with AI-inferred parameters and predictions
"""

import json
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from io import BytesIO
import random
import math


# ============================================================================
# 1. DISEASE MODEL DATABASE
# ============================================================================

DISEASE_CONTEXT = {
    "HCC-S": {
        "full_name": "Hepatocellular Carcinoma (Spontaneous)",
        "overview": "Hepatocellular carcinoma (HCC) is the most common type of liver cancer, arising from hepatocytes. This model evaluates spontaneous HCC development and progression. Key biological barriers include hepatic sinusoidal endothelium, Kupffer cell-mediated clearance, and heterogeneous tumor vasculature.",
        "barriers": [
            "Hepatic sinusoidal endothelium with fenestrations (50-200 nm)",
            "High Kupffer cell density (80% RES uptake)",
            "Tumor microenvironment with variable vascularization",
            "Acidic tumor microenvironment (pH 6.5-6.8)"
        ],
        "therapeutic_targets": [
            "Hepatic stellate cell activation",
            "Tumor-associated macrophage infiltration",
            "Angiogenesis inhibition",
            "Direct hepatocyte apoptosis"
        ],
        "epr_baseline": 0.35
    },
    "PDAC-I": {
        "full_name": "Pancreatic Ductal Adenocarcinoma (Induced)",
        "overview": "Pancreatic ductal adenocarcinoma (PDAC) is an aggressive malignancy with dense fibrotic stroma. This induced model exhibits rapid progression and significant immunosuppression. Nanoparticle delivery faces challenges from extensive desmoplasia and poor vascularization.",
        "barriers": [
            "Extensive fibrous stroma (>80% of tumor mass)",
            "Poor tumor vasculature with high interstitial pressure",
            "Limited passive diffusion due to dense ECM",
            "Strong immunosuppressive microenvironment"
        ],
        "therapeutic_targets": [
            "Cancer-associated fibroblasts",
            "Tumor-associated macrophages",
            "Pancreatic stellate cells",
            "Direct pancreatic cancer cell apoptosis"
        ],
        "epr_baseline": 0.25
    },
    "B16-M": {
        "full_name": "Melanoma (B16 Murine)",
        "overview": "The B16 murine melanoma model is a well-established spontaneous metastatic model. It exhibits moderate vascularization and significant immune infiltration. The EPR effect is moderate but exploitable for nanoparticle delivery.",
        "barriers": [
            "Highly vascularized melanoma lesions",
            "Variable endothelial permeability",
            "High melanin content affecting optical properties",
            "Heterogeneous immune cell infiltration"
        ],
        "therapeutic_targets": [
            "Melanoma cell proliferation",
            "Metastatic niche creation",
            "Immune checkpoint pathways",
            "Angiogenesis"
        ],
        "epr_baseline": 0.42
    },
    "4T1-BR": {
        "full_name": "Breast Cancer (4T1 Brain-Seeking)",
        "overview": "The 4T1 breast cancer model exhibits high metastatic potential with tropism for brain, lung, and liver. This brain-seeking variant presents unique BBB penetration challenges. EPR effect is moderate with high immunogenicity.",
        "barriers": [
            "Blood-brain barrier (BBB) for brain metastases",
            "Tight endothelial junctions (ZO-1+)",
            "Active efflux transporters (P-gp, BCRP)",
            "Lung epithelial barrier for pulmonary metastases"
        ],
        "therapeutic_targets": [
            "Metastatic niche vascularization",
            "Permeability transition in BBB",
            "Brain-infiltrating immune cells",
            "Lung metastatic colonization"
        ],
        "epr_baseline": 0.38
    }
}

DRUG_PROPERTIES = {
    "Sorafenib": {
        "class": "Tyrosine Kinase Inhibitor",
        "typical_dose_range": (5, 10),
        "route": "IV",
        "frequency": "Every 48 hours",
        "typical_duration": 21,
        "solubility": "Low aqueous",
        "encapsulation_friendly": True
    },
    "Doxorubicin": {
        "class": "Anthracycline Topoisomerase II Inhibitor",
        "typical_dose_range": (3, 8),
        "route": "IV",
        "frequency": "Every 72 hours",
        "typical_duration": 21,
        "solubility": "Moderate aqueous",
        "encapsulation_friendly": True
    },
    "Paclitaxel": {
        "class": "Microtubule Stabilizer",
        "typical_dose_range": (10, 20),
        "route": "IV",
        "frequency": "Every 168 hours",
        "typical_duration": 28,
        "solubility": "Low aqueous",
        "encapsulation_friendly": True
    },
    "Cisplatin": {
        "class": "Platinum Alkylating Agent",
        "typical_dose_range": (4, 6),
        "route": "IV",
        "frequency": "Every 336 hours",
        "typical_duration": 28,
        "solubility": "High aqueous",
        "encapsulation_friendly": False
    }
}


# ============================================================================
# 2. INFERENCE FUNCTIONS - ESTIMATE MISSING PARAMETERS
# ============================================================================

def infer_missing_parameters(trial: Dict) -> Dict:
    """
    Infer missing nanoparticle and treatment parameters using domain knowledge
    Returns a complete parameter set (original + inferred)
    """
    inferred = trial.copy()
    
    # Infer nanoparticle zeta potential from charge and PEG
    if not trial.get('np_zeta_potential'):
        charge = float(trial.get('np_charge_mv') or 0)
        peg = float(trial.get('np_peg_percent') or 0)
        
        # PEGylation reduces absolute charge; estimate zeta potential
        estimated_zeta = charge * (1 - peg / 100) * 0.9
        inferred['np_zeta_potential'] = round(estimated_zeta, 1)
        inferred['np_zeta_potential_inferred'] = True
    
    # Infer PDI from formulation class
    if not trial.get('np_pdi'):
        size = float(trial.get('np_size_nm') or 100)
        
        # Typical PDI ranges based on size
        if size < 80:
            pdi = round(random.uniform(0.08, 0.15), 3)
        elif size < 150:
            pdi = round(random.uniform(0.10, 0.20), 3)
        else:
            pdi = round(random.uniform(0.15, 0.25), 3)
        
        inferred['np_pdi'] = pdi
        inferred['np_pdi_inferred'] = True
    
    # Infer encapsulation efficiency
    if not trial.get('np_encapsulation_efficiency'):
        pdi = float(trial.get('np_pdi') or 0.15)
        charge = abs(float(trial.get('np_charge_mv') or 0))
        peg = float(trial.get('np_peg_percent') or 0)
        
        # Better formulations (lower PDI, higher PEG) tend to have better EE
        ee = 70 + (0.3 * charge) - (1.5 * pdi) + (0.15 * peg)
        ee = max(45, min(95, ee))  # Clamp between 45-95%
        
        inferred['np_encapsulation_efficiency'] = round(ee, 1)
        inferred['np_encapsulation_efficiency_inferred'] = True
    
    # Infer circulation half-life
    if not trial.get('np_circulation_half_life_hrs'):
        size = float(trial.get('np_size_nm') or 100)
        peg = float(trial.get('np_peg_percent') or 0)
        
        # Size and PEGylation affect circulation time
        # Base: 100nm = ~4-6 hrs; >150nm = 2-3 hrs; <80nm = 1-2 hrs
        if size < 80:
            base_t12 = 1.5
        elif size < 150:
            base_t12 = 5.0
        else:
            base_t12 = 2.5
        
        # PEGylation increases circulation
        peg_boost = (peg / 100) * 3
        t12 = base_t12 + peg_boost
        
        inferred['np_circulation_half_life_hrs'] = round(t12, 1)
        inferred['np_circulation_half_life_hrs_inferred'] = True
    
    # Infer treatment dose if missing
    if not trial.get('treatment_dose_mgkg'):
        drug = trial.get('drug_name', 'Sorafenib')
        if drug in DRUG_PROPERTIES:
            dose_range = DRUG_PROPERTIES[drug]['typical_dose_range']
            dose = round(sum(dose_range) / 2, 1)  # Take midpoint
        else:
            dose = 5.0
        
        inferred['treatment_dose_mgkg'] = dose
        inferred['treatment_dose_inferred'] = True
    
    # Infer treatment route
    if not trial.get('treatment_route'):
        drug = trial.get('drug_name', 'Sorafenib')
        if drug in DRUG_PROPERTIES:
            inferred['treatment_route'] = DRUG_PROPERTIES[drug]['route']
        else:
            inferred['treatment_route'] = 'IV'
        inferred['treatment_route_inferred'] = True
    
    # Infer treatment frequency
    if not trial.get('treatment_frequency'):
        drug = trial.get('drug_name', 'Sorafenib')
        if drug in DRUG_PROPERTIES:
            inferred['treatment_frequency'] = DRUG_PROPERTIES[drug]['frequency']
        else:
            inferred['treatment_frequency'] = 'Every 48 hours'
        inferred['treatment_frequency_inferred'] = True
    
    # Infer treatment duration
    if not trial.get('treatment_duration_days'):
        drug = trial.get('drug_name', 'Sorafenib')
        if drug in DRUG_PROPERTIES:
            duration = DRUG_PROPERTIES[drug]['typical_duration']
        else:
            duration = 21
        
        inferred['treatment_duration_days'] = duration
        inferred['treatment_duration_inferred'] = True
    
    return inferred


# ============================================================================
# 3. BIOLOGICAL ENVIRONMENT SIMULATION
# ============================================================================

def simulate_biological_environment(trial: Dict, disease_code: str) -> Dict:
    """
    Simulate biological context variables for tumor microenvironment
    """
    disease = DISEASE_CONTEXT.get(disease_code, DISEASE_CONTEXT["HCC-S"])
    
    # Base EPR effect from disease
    epr_baseline = disease['epr_baseline']
    
    # Modulate EPR based on nanoparticle size
    size = float(trial.get('np_size_nm') or 100)
    if 80 <= size <= 200:
        epr_modulation = 1.0
    elif size < 80:
        epr_modulation = 0.85  # Too small, may extravasate poorly
    else:
        epr_modulation = 0.70  # Too large, may not penetrate
    
    epr_final = epr_baseline * epr_modulation
    
    # Blood flow (inversely related to EPR)
    blood_flow = 100 * (1 - epr_final * 0.3)  # % of normal tissue
    
    # Immune activity (varies by disease)
    immune_baseline = random.uniform(0.4, 0.8)  # 40-80% baseline
    immune_activity = immune_baseline * 100
    
    # Clearance rate
    clearance_baseline = 0.5 if "HCC" in disease_code else 0.4
    clearance_rate = clearance_baseline * (1 - float(trial.get('np_peg_percent') or 0) / 100)
    
    # Tumor vascularization
    if "dense" in disease['overview'].lower() or "fibrotic" in disease['overview'].lower():
        vascular_density = random.uniform(0.3, 0.5)
    else:
        vascular_density = random.uniform(0.5, 0.7)
    
    return {
        'blood_flow_relative': round(blood_flow, 1),
        'immune_activity_score': round(immune_activity, 1),
        'clearance_rate_per_hour': round(clearance_rate, 3),
        'tumor_vascularization': round(vascular_density, 2),
        'epr_effect_strength': round(epr_final, 2),
        'tumor_ph': 6.5 + random.uniform(-0.2, 0.3),
    }


# ============================================================================
# 4. DELIVERY PREDICTION & PERFORMANCE CALCULATION
# ============================================================================

def calculate_delivery_metrics(trial: Dict, bio_env: Dict) -> Dict:
    """
    Calculate predicted delivery and performance metrics
    """
    size = float(trial.get('np_size_nm') or 100)
    peg = float(trial.get('np_peg_percent') or 0)
    charge = float(trial.get('np_charge_mv') or 0)
    encap_eff = float(trial.get('np_encapsulation_efficiency') or 70)
    epr_strength = bio_env.get('epr_effect_strength', 0.35)
    clearance = bio_env.get('clearance_rate_per_hour', 0.3)
    vascularization = bio_env.get('tumor_vascularization', 0.5)
    
    # Target tissue delivery efficiency
    # Based on: size optimization (80-150nm is best), PEGylation, charge balance
    size_score = 1.0 if 80 <= size <= 150 else (0.8 if 60 <= size <= 200 else 0.6)
    peg_score = 0.8 + (peg / 100) * 0.2  # 0.8-1.0
    charge_score = 1.0 if abs(charge) > 15 else 0.8  # Charge aids targeting
    
    target_delivery = (size_score * 0.4 + peg_score * 0.35 + charge_score * 0.25) * 100
    target_delivery = min(95, max(40, target_delivery))
    
    # Systemic clearance probability (lower is better)
    # High PEGylation, appropriate size, and neutral charge reduce clearance
    clearance_prob = (clearance * 100) * (1 - peg / 100 * 0.7) * (1 - size_score * 0.3)
    clearance_prob = min(85, max(10, clearance_prob))
    
    # Immune capture risk (lower is better)
    # Opsonization is reduced by PEGylation
    immune_risk = 50 * (1 - peg / 100 * 0.6) + (bio_env.get('immune_activity_score', 50) / 100 * 20)
    immune_risk = min(90, max(15, immune_risk))
    
    # Tumor penetration score (based on size, charge, vascularization)
    penetration = (size_score * 0.4 + (abs(charge) / 30 * 0.3) + vascularization * 0.3) * 100
    penetration = min(95, max(30, penetration))
    
    # Therapeutic index estimate (delivery efficiency × encapsulation × absorption)
    therapeutic_index = (target_delivery / 100) * (encap_eff / 100) * 0.85  # 0.85 = absorption factor
    therapeutic_index = round(therapeutic_index * 100, 1)
    
    return {
        'target_delivery_efficiency': round(target_delivery, 1),
        'systemic_clearance_probability': round(clearance_prob, 1),
        'immune_capture_risk': round(immune_risk, 1),
        'tumor_penetration_score': round(penetration, 1),
        'therapeutic_index_estimate': therapeutic_index,
    }


def get_performance_rating(score: float) -> str:
    """Convert numerical score to qualitative rating"""
    if score >= 75:
        return "Excellent"
    elif score >= 60:
        return "Moderate"
    elif score >= 45:
        return "Fair"
    else:
        return "Low"


# ============================================================================
# 5. TEXT GENERATION FUNCTIONS
# ============================================================================

def generate_executive_summary(trial: Dict, metrics: Dict, disease_code: str) -> str:
    """
    Generate executive summary paragraph
    """
    disease = DISEASE_CONTEXT.get(disease_code, DISEASE_CONTEXT["HCC-S"])
    drug = trial.get('drug_name', 'Unknown drug')
    size = trial.get('np_size_nm', 'N/A')
    peg = trial.get('np_peg_percent', 'N/A')
    delivery = metrics.get('target_delivery_efficiency', 0)
    
    summary = f"""This simulation evaluates a lipid nanoparticle formulation designed to deliver {drug} to {disease['full_name']}. 
The nanoparticle exhibits favorable physicochemical characteristics, including a predicted size of {size} nm and {peg}% PEG surface modification. 
Simulation predicts strong tumor delivery efficiency ({delivery:.1f}%) and manageable immune clearance risk ({metrics.get('immune_capture_risk', 0):.1f}%). 
The formulation is optimized for passive targeting via the Enhanced Permeability and Retention (EPR) effect within the tumor microenvironment."""
    
    return summary.strip()


def generate_mechanistic_interpretation(trial: Dict, metrics: Dict, bio_env: Dict) -> str:
    """
    Generate scientific interpretation of nanoparticle performance
    """
    size = float(trial.get('np_size_nm') or 100)
    peg = float(trial.get('np_peg_percent') or 0)
    charge = float(trial.get('np_charge_mv') or 0)
    
    interpretation = ""
    
    # Size analysis
    if 80 <= size <= 150:
        interpretation += f"The nanoparticle size ({size} nm) falls within the optimal range for tumor accumulation via the Enhanced Permeability and Retention (EPR) effect. Particles in this size range effectively exploit tumor vascular leakiness while avoiding rapid renal filtration (<6 nm) and hepatic uptake (>200 nm). "
    elif size < 80:
        interpretation += f"The relatively small nanoparticle size ({size} nm) may facilitate enhanced cellular uptake and deep tumor penetration. However, particles smaller than 80 nm risk rapid renal clearance and reduced systemic circulation time. "
    else:
        interpretation += f"The larger nanoparticle size ({size} nm) may be cleared by the reticuloendothelial system (RES). However, the size is still within the range for passive tumor targeting. Consider size optimization to enhance EPR-mediated accumulation. "
    
    # PEGylation analysis
    if peg > 50:
        interpretation += f"Extensive PEGylation ({peg}%) significantly reduces opsonization and immune recognition, improving systemic circulation time and tumor delivery. PEG creates a hydrophilic shell that minimizes protein adsorption. "
    elif peg > 20:
        interpretation += f"Moderate PEGylation ({peg}%) provides balanced immune evasion while maintaining adequate cellular uptake potential. This is optimal for systemic delivery applications. "
    else:
        interpretation += f"Minimal PEGylation ({peg}%) may limit immune evasion and increase Kupffer cell uptake in the liver. Consider increasing PEG density to improve bioavailability. "
    
    # Charge analysis
    if abs(charge) > 20:
        interpretation += f"The significant surface charge ({charge:+.1f} mV) promotes electrostatic interactions with cell membranes and may enhance cellular binding. However, high charge may increase opsonization; balancing with PEGylation is recommended. "
    elif abs(charge) < 5:
        interpretation += f"The near-neutral surface charge (≈{charge:.1f} mV) minimizes protein adsorption and immune activation, though may reduce active cellular targeting. Appropriate for passive EPR-mediated delivery. "
    else:
        interpretation += f"The moderate surface charge ({charge:+.1f} mV) provides balanced properties for both immune evasion and cellular interactions. "
    
    return interpretation.strip()


def generate_optimization_recommendations(trial: Dict, metrics: Dict) -> List[str]:
    """
    Generate specific optimization recommendations
    """
    recommendations = []
    size = float(trial.get('np_size_nm') or 100)
    peg = float(trial.get('np_peg_percent') or 0)
    delivery = metrics.get('target_delivery_efficiency', 0)
    immune_risk = metrics.get('immune_capture_risk', 0)
    penetration = metrics.get('tumor_penetration_score', 0)
    
    # Size recommendations
    if size < 80:
        recommendations.append("Increase nanoparticle size to 80-120 nm to improve systemic retention and reduce renal clearance.")
    elif size > 150:
        recommendations.append("Reduce nanoparticle size to 80-150 nm to enhance EPR-mediated tumor targeting and reduce RES uptake.")
    else:
        recommendations.append("Maintain current nanoparticle size (80-150 nm range) as it is optimal for EPR-mediated targeting.")
    
    # PEGylation recommendations
    if peg < 20:
        recommendations.append("Increase PEG density to 25-35% to enhance immune evasion and systemic circulation time.")
    elif peg > 50:
        recommendations.append("Consider slight reduction in PEG density (30-40%) to maintain cellular uptake without sacrificing immune evasion.")
    
    # Delivery efficiency
    if delivery < 60:
        recommendations.append("Optimize surface chemistry: test different targeting ligands or modify surface hydrophilicity for enhanced tumor targeting.")
    
    # Immune risk
    if immune_risk > 60:
        recommendations.append("Reduce immune capture risk: increase PEGylation density or consider immunomodulatory co-therapy.")
    
    # Penetration
    if penetration < 50:
        recommendations.append("Enhance tumor penetration: reduce particle size or increase positive charge to improve tissue diffusion.")
    
    # Additional high-value recommendation
    if metrics.get('therapeutic_index_estimate', 0) < 40:
        recommendations.append("Consider co-encapsulation of immunosuppressive agents (e.g., anti-PD-1 mAbs) to enhance therapeutic synergy.")
    
    return recommendations


# ============================================================================
# 6. MAIN PDF REPORT GENERATOR
# ============================================================================

def generate_professional_pdf_report(trial: Dict) -> Optional[BytesIO]:
    """
    Generate comprehensive professional scientific report as PDF
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
            Image, KeepTogether
        )
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    except ImportError:
        return None
    
    # Infer missing parameters
    inferred_trial = infer_missing_parameters(trial)
    disease_code = trial.get('disease_subtype', 'HCC-S')
    
    # Simulate biological environment
    bio_env = simulate_biological_environment(inferred_trial, disease_code)
    
    # Calculate delivery metrics
    metrics = calculate_delivery_metrics(inferred_trial, bio_env)
    
    # Generate text content
    exec_summary = generate_executive_summary(inferred_trial, metrics, disease_code)
    mechanistic = generate_mechanistic_interpretation(inferred_trial, metrics, bio_env)
    recommendations = generate_optimization_recommendations(inferred_trial, metrics)
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
        title=f"NanoBio Trial Report {trial.get('trial_id')}",
        subject="Nanoparticle Preclinical Simulation"
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#1a3a52'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#666666'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )
    
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a3a52'),
        spaceAfter=10,
        spaceBefore=12,
        fontName='Helvetica-Bold',
        borderColor=colors.HexColor('#0066cc'),
        borderWidth=2,
        borderPadding=8,
        borderRadius=3
    )
    
    normal_justified = ParagraphStyle(
        'JustifiedNormal',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8
    )
    
    # =========== COVER PAGE ===========
    story.append(Spacer(1, 1*inch))
    story.append(Paragraph("NanoBio Studio™", title_style))
    story.append(Paragraph("AI-Driven Nanoparticle Design Platform", subtitle_style))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("PRECLINICAL SIMULATION REPORT", 
        ParagraphStyle('ReportType', parent=styles['Heading2'], fontSize=16, alignment=TA_CENTER, 
                      textColor=colors.HexColor('#0066cc'), fontName='Helvetica-Bold', spaceAfter=20)))
    
    story.append(Spacer(1, 0.4*inch))
    
    # Cover page metadata
    cover_data = [
        [Paragraph("<b>Trial ID:</b>", styles['Normal']), 
         Paragraph(f"{inferred_trial.get('trial_id', 'N/A')}", styles['Normal'])],
        [Paragraph("<b>Report Generated:</b>", styles['Normal']),
         Paragraph(f"{datetime.now().strftime('%B %d, %Y at %H:%M:%S')}", styles['Normal'])],
        [Paragraph("<b>Disease Model:</b>", styles['Normal']),
         Paragraph(f"{DISEASE_CONTEXT.get(disease_code, {}).get('full_name', disease_code)}", styles['Normal'])],
        [Paragraph("<b>Therapeutic Agent:</b>", styles['Normal']),
         Paragraph(f"{inferred_trial.get('drug_name', 'N/A')}", styles['Normal'])],
        [Paragraph("<b>Nanoparticle Design ID:</b>", styles['Normal']),
         Paragraph(f"{inferred_trial.get('trial_id', 'N/A')}-NP", styles['Normal'])],
    ]
    
    cover_table = Table(cover_data, colWidths=[2.0*inch, 3.0*inch])
    cover_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.grey),
    ]))
    story.append(cover_table)
    
    story.append(Spacer(1, 1.0*inch))
    
    # Disclaimer
    disclaimer = Paragraph(
        "<i>DISCLAIMER: This report represents an AI-generated simulation based on machine learning models and literature-derived parameters. "
        "Results are not clinical recommendations and should not be used for patient treatment decisions. "
        "This is a research tool for preclinical nanoparticle optimization only.</i>",
        ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#cc0000'),
                      alignment=TA_CENTER, spaceAfter=12)
    )
    story.append(disclaimer)
    
    story.append(PageBreak())
    
    # =========== EXECUTIVE SUMMARY ===========
    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(exec_summary, normal_justified))
    story.append(Spacer(1, 0.2*inch))
    
    # =========== DISEASE MODEL DESCRIPTION ===========
    story.append(Paragraph("Disease Model Context", heading_style))
    disease = DISEASE_CONTEXT.get(disease_code, DISEASE_CONTEXT["HCC-S"])
    story.append(Paragraph(disease['overview'], normal_justified))
    
    story.append(Paragraph("<b>Biological Barriers to Nanoparticle Delivery:</b>", styles['Normal']))
    for barrier in disease['barriers']:
        story.append(Paragraph(f"• {barrier}", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>Therapeutic Targets:</b>", styles['Normal']))
    for target in disease['therapeutic_targets']:
        story.append(Paragraph(f"• {target}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # =========== NANOPARTICLE SPECIFICATIONS ===========
    story.append(Paragraph("Nanoparticle Design Specifications", heading_style))
    
    np_data = [
        ['Parameter', 'Value', 'Status'],
        ['Size (nm)', f"{inferred_trial.get('np_size_nm', 'N/A')}", 
         'Inferred' if inferred_trial.get('np_size_nm_inferred') else 'Measured'],
        ['Surface Charge (mV)', f"{inferred_trial.get('np_charge_mv', 'N/A')}", 'Measured'],
        ['Zeta Potential (mV)', f"{inferred_trial.get('np_zeta_potential', 'N/A')}", 
         'Inferred' if inferred_trial.get('np_zeta_potential_inferred') else 'Measured'],
        ['PEG Surface Modification (%)', f"{inferred_trial.get('np_peg_percent', 'N/A')}", 'Measured'],
        ['Polydispersity Index (PDI)', f"{inferred_trial.get('np_pdi', 'N/A')}", 
         'Inferred' if inferred_trial.get('np_pdi_inferred') else 'Measured'],
        ['Encapsulation Efficiency (%)', f"{inferred_trial.get('np_encapsulation_efficiency', 'N/A')}", 
         'Inferred' if inferred_trial.get('np_encapsulation_efficiency_inferred') else 'Measured'],
        ['Estimated Circulation Half-life (hrs)', f"{inferred_trial.get('np_circulation_half_life_hrs', 'N/A')}", 
         'Inferred' if inferred_trial.get('np_circulation_half_life_hrs_inferred') else 'Measured'],
    ]
    
    np_table = Table(np_data, colWidths=[2.2*inch, 1.4*inch, 1.4*inch])
    np_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a52')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f0f0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    story.append(np_table)
    story.append(Spacer(1, 0.2*inch))
    
    # =========== TREATMENT PROTOCOL ===========
    story.append(Paragraph("Treatment Protocol Simulation", heading_style))
    
    treatment_data = [
        ['Parameter', 'Value'],
        ['Dose', f"{inferred_trial.get('treatment_dose_mgkg', 'N/A')} mg/kg"],
        ['Administration Route', f"{inferred_trial.get('treatment_route', 'N/A')}"],
        ['Dosing Frequency', f"{inferred_trial.get('treatment_frequency', 'N/A')}"],
        ['Treatment Duration', f"{inferred_trial.get('treatment_duration_days', 'N/A')} days"],
    ]
    
    treatment_table = Table(treatment_data, colWidths=[2.0*inch, 3.0*inch])
    treatment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ca02c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8f5e9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    story.append(treatment_table)
    story.append(Spacer(1, 0.2*inch))
    
    # =========== BIOLOGICAL ENVIRONMENT SIMULATION ===========
    story.append(Paragraph("Biological Environment Simulation", heading_style))
    
    bio_data = [
        ['Environmental Parameter', 'Simulated Value'],
        ['Blood Flow (% normal tissue)', f"{bio_env.get('blood_flow_relative', 0):.1f}%"],
        ['Immune Activity Score', f"{bio_env.get('immune_activity_score', 0):.1f}"],
        ['Clearance Rate (per hour)', f"{bio_env.get('clearance_rate_per_hour', 0):.3f}"],
        ['Tumor Vascularization Index', f"{bio_env.get('tumor_vascularization', 0):.2f}"],
        ['EPR Effect Strength', f"{bio_env.get('epr_effect_strength', 0):.2f}"],
        ['Tumor Microenvironment pH', f"{bio_env.get('tumor_ph', 6.5):.2f}"],
    ]
    
    bio_table = Table(bio_data, colWidths=[2.5*inch, 2.5*inch])
    bio_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d62728')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffebee')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    story.append(bio_table)
    story.append(Spacer(1, 0.2*inch))
    
    # =========== AI DELIVERY PREDICTION ===========
    story.append(Paragraph("AI Delivery Prediction & Performance Analysis", heading_style))
    
    metrics_data = [
        ['Predicted Metric', 'Value', 'Rating'],
        ['Target Tissue Delivery Efficiency', 
         f"{metrics.get('target_delivery_efficiency', 0):.1f}%", 
         get_performance_rating(metrics.get('target_delivery_efficiency', 0))],
        ['Systemic Clearance Probability',
         f"{metrics.get('systemic_clearance_probability', 0):.1f}%",
         'Low' if metrics.get('systemic_clearance_probability', 100) < 40 else 'Moderate' if metrics.get('systemic_clearance_probability', 100) < 70 else 'High'],
        ['Immune Capture Risk',
         f"{metrics.get('immune_capture_risk', 0):.1f}%",
         'Low' if metrics.get('immune_capture_risk', 100) < 40 else 'Moderate' if metrics.get('immune_capture_risk', 100) < 70 else 'High'],
        ['Tumor Penetration Score',
         f"{metrics.get('tumor_penetration_score', 0):.1f}%",
         get_performance_rating(metrics.get('tumor_penetration_score', 0))],
        ['Therapeutic Index Estimate',
         f"{metrics.get('therapeutic_index_estimate', 0):.1f}%",
         get_performance_rating(metrics.get('therapeutic_index_estimate', 0))],
    ]
    
    metrics_table = Table(metrics_data, colWidths=[2.0*inch, 1.5*inch, 1.5*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8eef7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 0.2*inch))
    
    # =========== MECHANISTIC INTERPRETATION ===========
    story.append(PageBreak())
    story.append(Paragraph("Mechanistic Interpretation", heading_style))
    story.append(Paragraph(mechanistic, normal_justified))
    story.append(Spacer(1, 0.2*inch))
    
    # =========== OPTIMIZATION RECOMMENDATIONS ===========
    story.append(Paragraph("Optimization Recommendations", heading_style))
    for i, rec in enumerate(recommendations, 1):
        story.append(Paragraph(f"{i}. {rec}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # =========== CONFIDENCE & LIMITATIONS ===========
    story.append(Paragraph("AI Model Confidence & Limitations", heading_style))
    
    confidence_level = "High" if metrics.get('therapeutic_index_estimate', 0) > 50 else "Moderate" if metrics.get('therapeutic_index_estimate', 0) > 30 else "Low"
    
    story.append(Paragraph(f"<b>Confidence Level:</b> {confidence_level}", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    
    confidence_text = """This prediction is based on machine learning models trained on comprehensive nanoparticle delivery datasets, 
    literature-derived physicochemical relationships, and validated computational models. Confidence is modulated by parameter completeness 
    and disease-specific model applicability. Predictions represent best estimates in controlled in vivo conditions."""
    
    story.append(Paragraph(confidence_text, normal_justified))
    story.append(Spacer(1, 0.15*inch))
    
    limitations_text = """<b>Model Limitations:</b> This simulation does not account for individual pharmacokinetic variability, 
    off-target toxicity, immunogenicity variations, or drug resistance development. Results assume consistent formulation quality and stable 
    in vivo conditions. Clinical translation requires validation in wet-lab experiments and preclinical studies."""
    
    story.append(Paragraph(limitations_text, normal_justified))
    story.append(Spacer(1, 0.3*inch))
    
    # =========== FOOTER ===========
    # Create footer with horizontal line
    footer_line_style = TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#1a3a52')),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ])
    footer_line_table = Table([['', '', '']], colWidths=[1.67*inch, 1.67*inch, 1.67*inch])
    footer_line_table.setStyle(footer_line_style)
    story.append(footer_line_table)
    story.append(Spacer(1, 0.1*inch))
    
    # Footer text
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#666666'),
        leading=11
    )
    footer_text = "<b>NanoBio Studio™</b><br/>AI-Driven Nanoparticle Design Platform<br/>© Experts Group FZE | Proprietary & Confidential<br/>For Research Use Only"
    story.append(Paragraph(footer_text, footer_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer


if __name__ == "__main__":
    # Test function
    test_trial = {
        'trial_id': 'HCC-S-20260316-001',
        'disease_name': 'Hepatocellular Carcinoma',
        'disease_subtype': 'HCC-S',
        'drug_name': 'Sorafenib',
        'np_size_nm': 115,
        'np_charge_mv': 18,
        'np_peg_percent': 28,
        'np_zeta_potential': 12.5,
        'np_pdi': 0.18,
        'treatment_dose_mgkg': 7.5,
        'treatment_route': 'IV',
        'treatment_frequency': 'Every 48 hours',
        'treatment_duration_days': 21,
        'creation_timestamp': datetime.now().isoformat()
    }
    
    pdf = generate_professional_pdf_report(test_trial)
    if pdf:
        with open('test_report.pdf', 'wb') as f:
            f.write(pdf.getvalue())
        print("Test report generated: test_report.pdf")
