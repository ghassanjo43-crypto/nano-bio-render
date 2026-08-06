"""
Nanoparticle Design Suitability Scoring System
Evaluates design quality based on parameters, target, and payload
"""

import streamlit as st

class DesignScorer:
    """Calculate suitability score for nanoparticle design"""
    
    def __init__(self):
        # Optimal size ranges for different targets (nm)
        self.target_size_map = {
            "Tumor Tissue (Solid)": (80, 200),  # EPR effect window
            "Liver Hepatocytes": (50, 150),
            "Brain (Blood-Brain Barrier)": (20, 100),  # Smaller preferred
            "Lung Endothelium": (50, 200),
            "Kidney Glomeruli": (5, 50),  # Small for filtration
            "Spleen (RES)": (100, 300),
            "Lymph Nodes": (10, 100),
            "Inflamed Tissue": (50, 200),
            "Cardiovascular Plaques": (30, 150),
            "Bone Marrow": (50, 200),
            "Skin (Dermal)": (50, 300),
            "Ocular Tissue (Eye)": (20, 100)
        }
        
        # Optimal charge for different targets
        self.target_charge_map = {
            "Tumor Tissue (Solid)": (-30, 10),  # Slightly negative to neutral
            "Liver Hepatocytes": (-20, 20),
            "Brain (Blood-Brain Barrier)": (-15, 5),  # Near neutral
            "Lung Endothelium": (-20, 10),
            "Kidney Glomeruli": (-40, -10),  # Negative preferred
            "Spleen (RES)": (-30, 30),
            "Lymph Nodes": (-20, 20),
            "Inflamed Tissue": (-30, 10),
            "Cardiovascular Plaques": (-25, 5),
            "Bone Marrow": (-20, 20),
            "Skin (Dermal)": (-30, 30),
            "Ocular Tissue (Eye)": (-15, 10)
        }
        
        # Material suitability for different payloads (1-10 scale)
        self.material_payload_scores = {
            "Lipid Nanoparticle (LNP)": {
                "mRNA": 10, "siRNA": 9, "DNA (plasmid)": 8, "Small molecule drug": 6,
                "Protein/Peptide": 5, "Antibody": 4, "CRISPR-Cas9 RNP": 9,
                "Imaging agent": 5, "Combination (drug + RNA)": 8, "None": 2
            },
            "Gold Nanoparticle (AuNP)": {
                "mRNA": 4, "siRNA": 5, "DNA (plasmid)": 5, "Small molecule drug": 7,
                "Protein/Peptide": 6, "Antibody": 7, "CRISPR-Cas9 RNP": 4,
                "Imaging agent": 10, "Combination (drug + RNA)": 6, "None": 8
            },
            "Polymeric Nanoparticle (PLGA)": {
                "mRNA": 5, "siRNA": 6, "DNA (plasmid)": 7, "Small molecule drug": 9,
                "Protein/Peptide": 8, "Antibody": 7, "CRISPR-Cas9 RNP": 5,
                "Imaging agent": 7, "Combination (drug + RNA)": 8, "None": 4
            },
            "Silica Nanoparticle (MSN)": {
                "mRNA": 4, "siRNA": 5, "DNA (plasmid)": 5, "Small molecule drug": 9,
                "Protein/Peptide": 7, "Antibody": 6, "CRISPR-Cas9 RNP": 4,
                "Imaging agent": 8, "Combination (drug + RNA)": 7, "None": 6
            },
            "Liposome": {
                "mRNA": 7, "siRNA": 8, "DNA (plasmid)": 7, "Small molecule drug": 8,
                "Protein/Peptide": 7, "Antibody": 6, "CRISPR-Cas9 RNP": 6,
                "Imaging agent": 6, "Combination (drug + RNA)": 8, "None": 3
            },
            "Quantum Dot (QD)": {
                "mRNA": 2, "siRNA": 2, "DNA (plasmid)": 2, "Small molecule drug": 4,
                "Protein/Peptide": 4, "Antibody": 5, "CRISPR-Cas9 RNP": 2,
                "Imaging agent": 10, "Combination (drug + RNA)": 3, "None": 7
            },
            "Carbon Nanotube (CNT)": {
                "mRNA": 5, "siRNA": 6, "DNA (plasmid)": 6, "Small molecule drug": 7,
                "Protein/Peptide": 6, "Antibody": 6, "CRISPR-Cas9 RNP": 5,
                "Imaging agent": 7, "Combination (drug + RNA)": 6, "None": 5
            },
            "Dendrimer": {
                "mRNA": 6, "siRNA": 7, "DNA (plasmid)": 7, "Small molecule drug": 8,
                "Protein/Peptide": 7, "Antibody": 6, "CRISPR-Cas9 RNP": 6,
                "Imaging agent": 6, "Combination (drug + RNA)": 7, "None": 4
            },
            "Metal-Organic Framework (MOF)": {
                "mRNA": 5, "siRNA": 6, "DNA (plasmid)": 6, "Small molecule drug": 9,
                "Protein/Peptide": 8, "Antibody": 7, "CRISPR-Cas9 RNP": 5,
                "Imaging agent": 8, "Combination (drug + RNA)": 7, "None": 5
            },
            "Exosome": {
                "mRNA": 9, "siRNA": 8, "DNA (plasmid)": 7, "Small molecule drug": 7,
                "Protein/Peptide": 9, "Antibody": 8, "CRISPR-Cas9 RNP": 8,
                "Imaging agent": 6, "Combination (drug + RNA)": 8, "None": 3
            }
        }
        
        # Ligand effectiveness for different targets (1-10 scale)
        self.ligand_target_scores = {
            "Tumor Tissue (Solid)": {
                "PEG (Polyethylene Glycol)": 8, "PEG2000": 8, "Cholesterol": 5,
                "Citrate": 4, "Thiol-PEG": 7, "Antibody (mAb)": 10,
                "RGD Peptide": 9, "Folate": 8, "Transferrin": 7,
                "Hyaluronic Acid": 8, "None": 3
            },
            "Liver Hepatocytes": {
                "PEG (Polyethylene Glycol)": 6, "PEG2000": 6, "Cholesterol": 8,
                "Citrate": 5, "Thiol-PEG": 6, "Antibody (mAb)": 8,
                "RGD Peptide": 5, "Folate": 6, "Transferrin": 9,
                "Hyaluronic Acid": 6, "None": 4
            },
            "Brain (Blood-Brain Barrier)": {
                "PEG (Polyethylene Glycol)": 7, "PEG2000": 7, "Cholesterol": 6,
                "Citrate": 4, "Thiol-PEG": 6, "Antibody (mAb)": 9,
                "RGD Peptide": 7, "Folate": 6, "Transferrin": 10,
                "Hyaluronic Acid": 5, "None": 2
            },
            "Lung Endothelium": {
                "PEG (Polyethylene Glycol)": 8, "PEG2000": 8, "Cholesterol": 6,
                "Citrate": 5, "Thiol-PEG": 7, "Antibody (mAb)": 9,
                "RGD Peptide": 8, "Folate": 6, "Transferrin": 7,
                "Hyaluronic Acid": 7, "None": 3
            },
            "Kidney Glomeruli": {
                "PEG (Polyethylene Glycol)": 9, "PEG2000": 9, "Cholesterol": 5,
                "Citrate": 7, "Thiol-PEG": 8, "Antibody (mAb)": 7,
                "RGD Peptide": 6, "Folate": 6, "Transferrin": 6,
                "Hyaluronic Acid": 6, "None": 4
            },
            "Spleen (RES)": {
                "PEG (Polyethylene Glycol)": 5, "PEG2000": 5, "Cholesterol": 7,
                "Citrate": 6, "Thiol-PEG": 5, "Antibody (mAb)": 8,
                "RGD Peptide": 6, "Folate": 6, "Transferrin": 7,
                "Hyaluronic Acid": 6, "None": 8
            },
            "Lymph Nodes": {
                "PEG (Polyethylene Glycol)": 7, "PEG2000": 7, "Cholesterol": 6,
                "Citrate": 6, "Thiol-PEG": 7, "Antibody (mAb)": 9,
                "RGD Peptide": 7, "Folate": 7, "Transferrin": 7,
                "Hyaluronic Acid": 8, "None": 4
            },
            "Inflamed Tissue": {
                "PEG (Polyethylene Glycol)": 7, "PEG2000": 7, "Cholesterol": 6,
                "Citrate": 5, "Thiol-PEG": 7, "Antibody (mAb)": 9,
                "RGD Peptide": 8, "Folate": 7, "Transferrin": 7,
                "Hyaluronic Acid": 9, "None": 4
            },
            "Cardiovascular Plaques": {
                "PEG (Polyethylene Glycol)": 8, "PEG2000": 8, "Cholesterol": 7,
                "Citrate": 5, "Thiol-PEG": 7, "Antibody (mAb)": 9,
                "RGD Peptide": 8, "Folate": 6, "Transferrin": 7,
                "Hyaluronic Acid": 7, "None": 3
            },
            "Bone Marrow": {
                "PEG (Polyethylene Glycol)": 7, "PEG2000": 7, "Cholesterol": 6,
                "Citrate": 5, "Thiol-PEG": 7, "Antibody (mAb)": 9,
                "RGD Peptide": 7, "Folate": 7, "Transferrin": 8,
                "Hyaluronic Acid": 7, "None": 4
            },
            "Skin (Dermal)": {
                "PEG (Polyethylene Glycol)": 6, "PEG2000": 6, "Cholesterol": 7,
                "Citrate": 5, "Thiol-PEG": 6, "Antibody (mAb)": 8,
                "RGD Peptide": 7, "Folate": 6, "Transferrin": 6,
                "Hyaluronic Acid": 9, "None": 5
            },
            "Ocular Tissue (Eye)": {
                "PEG (Polyethylene Glycol)": 8, "PEG2000": 8, "Cholesterol": 6,
                "Citrate": 5, "Thiol-PEG": 7, "Antibody (mAb)": 9,
                "RGD Peptide": 7, "Folate": 6, "Transferrin": 7,
                "Hyaluronic Acid": 8, "None": 3
            }
        }
    
    def score_size(self, size, target):
        """Score size appropriateness for target (0-100)"""
        optimal_range = self.target_size_map.get(target, (50, 200))
        min_size, max_size = optimal_range
        optimal_size = (min_size + max_size) / 2
        
        if min_size <= size <= max_size:
            # Within optimal range - score based on how close to center
            deviation = abs(size - optimal_size) / (max_size - min_size)
            return 100 - (deviation * 20)  # Max 20 point penalty
        else:
            # Outside optimal range
            if size < min_size:
                deviation = (min_size - size) / min_size
            else:
                deviation = (size - max_size) / max_size
            penalty = min(deviation * 100, 80)  # Max 80 point penalty
            return max(20, 100 - penalty)  # Minimum score of 20
    
    def score_charge(self, charge, target):
        """Score charge appropriateness for target (0-100)"""
        optimal_range = self.target_charge_map.get(target, (-20, 10))
        min_charge, max_charge = optimal_range
        
        if min_charge <= charge <= max_charge:
            return 100
        else:
            if charge < min_charge:
                deviation = abs(charge - min_charge) / 50  # Normalize
            else:
                deviation = abs(charge - max_charge) / 50
            penalty = min(deviation * 100, 70)
            return max(30, 100 - penalty)
    
    def score_pdi(self, pdi):
        """Score PDI quality (0-100)"""
        # Lower PDI is better
        if pdi <= 0.1:
            return 100
        elif pdi <= 0.2:
            return 90
        elif pdi <= 0.3:
            return 70
        elif pdi <= 0.4:
            return 50
        else:
            return 30
    
    def score_material_payload(self, material, payload):
        """Score material-payload compatibility (0-100)"""
        # Get base material (remove parentheses content)
        material_key = material.split('(')[0].strip() + ' (' + material.split('(')[1] if '(' in material else material
        score = self.material_payload_scores.get(material_key, {}).get(payload, 5)
        return score * 10  # Convert to 0-100 scale
    
    def score_ligand_target(self, ligand, target):
        """Score ligand-target compatibility (0-100)"""
        # Get base ligand
        ligand_key = ligand.split('(')[0].strip() + ' (' + ligand.split('(')[1] if '(' in ligand else ligand
        score = self.ligand_target_scores.get(target, {}).get(ligand_key, 5)
        return score * 10  # Convert to 0-100 scale
    
    def score_payload_loading(self, payload_amount, payload):
        """Score payload loading appropriateness (0-100)"""
        # Optimal loading ranges vary by payload type
        optimal_ranges = {
            "mRNA": (1, 5), "siRNA": (1, 10), "DNA (plasmid)": (1, 5),
            "Small molecule drug": (5, 30), "Protein/Peptide": (5, 20),
            "Antibody": (5, 15), "CRISPR-Cas9 RNP": (1, 5),
            "Imaging agent": (1, 20), "Combination (drug + RNA)": (5, 20),
            "None": (0, 0)
        }
        
        optimal_range = optimal_ranges.get(payload, (1, 20))
        min_loading, max_loading = optimal_range
        
        if payload == "None":
            return 100 if payload_amount < 1 else 50
        
        if min_loading <= payload_amount <= max_loading:
            return 100
        else:
            if payload_amount < min_loading:
                return max(50, 100 - (min_loading - payload_amount) * 10)
            else:
                return max(50, 100 - (payload_amount - max_loading) * 2)
    
    def calculate_overall_score(self, design):
        """Calculate overall suitability score (0-100)"""
        # Extract parameters
        size = design.get('size', 100)
        charge = design.get('charge', 0)
        pdi = design.get('pdi', 0.15)
        material = design.get('material', 'Lipid Nanoparticle')
        ligand = design.get('ligand', 'PEG')
        payload = design.get('payload', 'mRNA')
        payload_amount = design.get('payload_amount', 50)
        target = design.get('target', 'Tumor Tissue (Solid)')
        
        # Calculate individual scores
        size_score = self.score_size(size, target)
        charge_score = self.score_charge(charge, target)
        pdi_score = self.score_pdi(pdi)
        material_score = self.score_material_payload(material, payload)
        ligand_score = self.score_ligand_target(ligand, target)
        loading_score = self.score_payload_loading(payload_amount, payload)
        
        # Weighted average
        weights = {
            'size': 0.25,
            'charge': 0.15,
            'pdi': 0.10,
            'material': 0.20,
            'ligand': 0.20,
            'loading': 0.10
        }
        
        overall = (
            size_score * weights['size'] +
            charge_score * weights['charge'] +
            pdi_score * weights['pdi'] +
            material_score * weights['material'] +
            ligand_score * weights['ligand'] +
            loading_score * weights['loading']
        )
        
        return {
            'overall': round(overall, 1),
            'size': round(size_score, 1),
            'charge': round(charge_score, 1),
            'pdi': round(pdi_score, 1),
            'material': round(material_score, 1),
            'ligand': round(ligand_score, 1),
            'loading': round(loading_score, 1)
        }
    
    def get_recommendations(self, scores, design):
        """Generate recommendations based on scores"""
        recommendations = []
        
        if scores['size'] < 70:
            recommendations.append(f"⚠️ Size may not be optimal for {design['target']}. Consider adjusting to match target tissue requirements.")
        
        if scores['charge'] < 70:
            recommendations.append(f"⚠️ Surface charge could be better optimized for {design['target']}.")
        
        if scores['pdi'] < 70:
            recommendations.append("⚠️ High polydispersity. Consider improving formulation uniformity.")
        
        if scores['material'] < 70:
            recommendations.append(f"⚠️ {design.get('Material', 'Lipid NP')} may not be ideal for drug delivery.")
        
        if scores['ligand'] < 70:
            recommendations.append(f"⚠️ Consider alternative surface ligands for better {design.get('Target', 'Liver Cells')} targeting.")
        
        if scores['loading'] < 70:
            recommendations.append(f"⚠️ Payload loading may be suboptimal.")
        
        if not recommendations:
            recommendations.append("✅ Excellent design! All parameters are well-optimized.")
        
        return recommendations
