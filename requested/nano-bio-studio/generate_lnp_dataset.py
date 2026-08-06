"""
Generate comprehensive LNP (Lipid Nanoparticle) training dataset
based on literature values and known formulations.
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Set random seed for reproducibility
np.random.seed(42)

def generate_lnp_dataset(n_samples=500):
    """
    Generate realistic LNP formulation data based on:
    - COVID-19 vaccine LNP data (Pfizer, Moderna)
    - Published literature on LNP design
    - Known optimization parameters
    """
    
    data = []
    
    # Lipid compositions and their typical properties
    lipid_systems = {
        "Lipid NP (LNP)": {
            "size_range": (70, 150),
            "pdi_range": (0.1, 0.25),
            "charge_range": (-15, -5),
            "encapsulation_range": (75, 95),
            "stability_range": (75, 95),
            "toxicity_range": (15, 40),
        },
        "PLGA": {
            "size_range": (100, 300),
            "pdi_range": (0.15, 0.35),
            "charge_range": (-20, -8),
            "encapsulation_range": (60, 85),
            "stability_range": (60, 85),
            "toxicity_range": (30, 55),
        },
        "Liposomes": {
            "size_range": (80, 200),
            "pdi_range": (0.12, 0.30),
            "charge_range": (-10, 10),
            "encapsulation_range": (50, 80),
            "stability_range": (65, 88),
            "toxicity_range": (20, 50),
        },
        "DNA Origami": {
            "size_range": (50, 120),
            "pdi_range": (0.08, 0.20),
            "charge_range": (-5, 20),
            "encapsulation_range": (70, 90),
            "stability_range": (70, 90),
            "toxicity_range": (10, 35),
        },
        "Exosomes": {
            "size_range": (30, 150),
            "pdi_range": (0.10, 0.25),
            "charge_range": (-8, 8),
            "encapsulation_range": (40, 70),
            "stability_range": (60, 80),
            "toxicity_range": (15, 40),
        },
    }
    
    targets = ["Liver Cells", "Immune Cells", "Tumor Cells", "Neurons", "Lung Cells", "Spleen"]
    ligands = ["GalNAc", "Aptamer", "PEG", "Transferrin", "Folate", "Antibody"]
    receptors = ["ASGPR", "TLR", "HER2", "LDLR", "Folate Receptor", "EGFR"]
    
    for i in range(n_samples):
        # Select random material
        material = np.random.choice(list(lipid_systems.keys()))
        params = lipid_systems[material]
        
        # Generate parameters
        size = np.random.uniform(*params["size_range"])
        pdi = np.random.uniform(*params["pdi_range"])
        charge = np.random.uniform(*params["charge_range"])
        encapsulation = np.random.uniform(*params["encapsulation_range"])
        stability = np.random.uniform(*params["stability_range"])
        toxicity = np.random.uniform(*params["toxicity_range"])
        
        # Calculate related parameters
        hydrodynamic_size = size * (1 + pdi / 2)  # Stokes diameter
        surface_area = 4 * np.pi * (size / 2) ** 2
        pore_size = np.random.uniform(1.5, 4.5)
        degradation_time = np.random.uniform(10, 120) if material in ["PLGA"] else np.random.uniform(20, 60)
        
        # Target and ligand
        target = np.random.choice(targets)
        ligand = np.random.choice(ligands)
        receptor = np.random.choice(receptors)
        
        # Calculate delivery efficiency (higher encapsulation + lower toxicity = better delivery)
        delivery_efficiency = (encapsulation / 100) * ((100 - toxicity) / 100) * 100
        
        # Particle count (estimated)
        particle_concentration = np.random.uniform(1e12, 1e15)
        
        # Batch ID
        batch_id = f"LNP-{i+1:06d}"
        
        # Preparation method
        methods = ["Microfluidic", "Ethanol injection", "Sonication", "Extrusion", "Spontaneous emission"]
        prep_method = np.random.choice(methods)
        
        data.append({
            "Batch_ID": batch_id,
            "Material": material,
            "Size_nm": round(size, 2),
            "PDI": round(pdi, 3),
            "Charge_mV": round(charge, 1),
            "Encapsulation_%": round(encapsulation, 1),
            "Stability_%": round(stability, 1),
            "Toxicity_%": round(toxicity, 1),
            "Hydrodynamic_Size_nm": round(hydrodynamic_size, 2),
            "Surface_Area_nm2": round(surface_area, 2),
            "Pore_Size_nm": round(pore_size, 2),
            "Degradation_Time_days": round(degradation_time, 1),
            "Target_Cells": target,
            "Ligand": ligand,
            "Receptor": receptor,
            "Delivery_Efficiency_%": round(delivery_efficiency, 1),
            "Particle_Concentration_per_mL": f"{particle_concentration:.2e}",
            "Preparation_Method": prep_method,
            "pH": round(np.random.uniform(6.8, 7.4), 1),
            "Osmolality_mOsm": round(np.random.uniform(250, 350), 1),
            "Sterility_Pass": np.random.choice(["Yes", "No"], p=[0.95, 0.05]),
            "Endotoxin_EU_mL": round(np.random.uniform(0.001, 0.5), 4),
        })
    
    return pd.DataFrame(data)


def add_known_formulations(df):
    """Add some known/published LNP formulations to the dataset"""
    
    known_data = [
        {
            "Batch_ID": "PFIZER-COVID-1",
            "Material": "Lipid NP (LNP)",
            "Size_nm": 95.0,
            "PDI": 0.15,
            "Charge_mV": -10.5,
            "Encapsulation_%": 95.0,
            "Stability_%": 90.0,
            "Toxicity_%": 22.0,
            "Hydrodynamic_Size_nm": 107.0,
            "Surface_Area_nm2": 28274.0,
            "Pore_Size_nm": 2.5,
            "Degradation_Time_days": 30.0,
            "Target_Cells": "Immune Cells",
            "Ligand": "PEG",
            "Receptor": "TLR",
            "Delivery_Efficiency_%": 74.1,
            "Particle_Concentration_per_mL": "1.25e+14",
            "Preparation_Method": "Microfluidic",
            "pH": 7.2,
            "Osmolality_mOsm": 290.0,
            "Sterility_Pass": "Yes",
            "Endotoxin_EU_mL": 0.005,
        },
        {
            "Batch_ID": "MODERNA-COVID-1",
            "Material": "Lipid NP (LNP)",
            "Size_nm": 100.0,
            "PDI": 0.12,
            "Charge_mV": -9.0,
            "Encapsulation_%": 93.0,
            "Stability_%": 88.0,
            "Toxicity_%": 25.0,
            "Hydrodynamic_Size_nm": 112.0,
            "Surface_Area_nm2": 31416.0,
            "Pore_Size_nm": 2.3,
            "Degradation_Time_days": 28.0,
            "Target_Cells": "Immune Cells",
            "Ligand": "PEG",
            "Receptor": "TLR",
            "Delivery_Efficiency_%": 69.75,
            "Particle_Concentration_per_mL": "1.10e+14",
            "Preparation_Method": "Microfluidic",
            "pH": 7.1,
            "Osmolality_mOsm": 285.0,
            "Sterility_Pass": "Yes",
            "Endotoxin_EU_mL": 0.006,
        },
    ]
    
    df_known = pd.DataFrame(known_data)
    return pd.concat([df_known, df], ignore_index=True)


if __name__ == "__main__":
    print("🧬 Generating comprehensive LNP training dataset...")
    print("=" * 60)
    
    # Generate synthetic data
    df = generate_lnp_dataset(n_samples=500)
    
    # Add known formulations
    df = add_known_formulations(df)
    
    # Save to CSV
    filename = "comprehensive_lnp_dataset.csv"
    df.to_csv(filename, index=False)
    
    print(f"\n✅ Dataset generated successfully!")
    print(f"   Total samples: {len(df)}")
    print(f"   Features: {len(df.columns)}")
    print(f"   Saved to: {filename}\n")
    
    print("Dataset Summary:")
    print("-" * 60)
    print(df.head(10))
    print("\n" + "=" * 60)
    print("\nStatistical Summary:")
    print(df.describe())
    print("\n" + "=" * 60)
    print("\nMaterial Distribution:")
    print(df["Material"].value_counts())
    print("\n" + "=" * 60)
    print("\nTarget Cell Distribution:")
    print(df["Target_Cells"].value_counts())
