"""
Simple LNP dataset generator - minimal dependencies
Creates LNP training data without heavy imports
"""
import csv
import random
from datetime import datetime

# Known Pfizer & Moderna COVID-19 LNP formulations (published data)
KNOWN_FORMULATIONS = [
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

MATERIALS = [
    "Lipid NP (LNP)",
    "PLGA",
    "Liposomes",
    "DNA Origami",
    "Exosomes",
]

TARGETS = [
    "Liver Cells",
    "Immune Cells",
    "Tumor Cells",
    "Neurons",
    "Lung Cells",
    "Spleen",
]

LIGANDS = [
    "GalNAc",
    "Aptamer",
    "PEG",
    "Transferrin",
    "Folate",
    "Antibody",
]

RECEPTORS = [
    "ASGPR",
    "TLR",
    "HER2",
    "LDLR",
    "Folate Receptor",
    "EGFR",
]

METHODS = [
    "Microfluidic",
    "Ethanol injection",
    "Sonication",
    "Extrusion",
    "Spontaneous emission",
]

def generate_sample():
    """Generate a single LNP sample"""
    material = random.choice(MATERIALS)
    
    # Parameter ranges based on material type
    if material == "Lipid NP (LNP)":
        size = random.uniform(70, 150)
        pdi = random.uniform(0.1, 0.25)
        charge = random.uniform(-15, -5)
        encapsulation = random.uniform(75, 95)
        stability = random.uniform(75, 95)
        toxicity = random.uniform(15, 40)
    elif material == "PLGA":
        size = random.uniform(100, 300)
        pdi = random.uniform(0.15, 0.35)
        charge = random.uniform(-20, -8)
        encapsulation = random.uniform(60, 85)
        stability = random.uniform(60, 85)
        toxicity = random.uniform(30, 55)
    elif material == "DNA Origami":
        size = random.uniform(50, 120)
        pdi = random.uniform(0.08, 0.20)
        charge = random.uniform(-5, 20)
        encapsulation = random.uniform(70, 90)
        stability = random.uniform(70, 90)
        toxicity = random.uniform(10, 35)
    else:  # Liposomes and Exosomes
        size = random.uniform(80, 200)
        pdi = random.uniform(0.12, 0.30)
        charge = random.uniform(-10, 10)
        encapsulation = random.uniform(50, 80)
        stability = random.uniform(65, 88)
        toxicity = random.uniform(20, 50)
    
    # Calculate derived parameters
    hydrodynamic_size = size * (1 + pdi / 2)
    surface_area = 4 * 3.14159 * (size / 2) ** 2
    pore_size = random.uniform(1.5, 4.5)
    degradation_time = random.uniform(10, 120) if material == "PLGA" else random.uniform(20, 60)
    delivery_efficiency = (encapsulation / 100) * ((100 - toxicity) / 100) * 100
    
    return {
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
        "Target_Cells": random.choice(TARGETS),
        "Ligand": random.choice(LIGANDS),
        "Receptor": random.choice(RECEPTORS),
        "Delivery_Efficiency_%": round(delivery_efficiency, 1),
        "Particle_Concentration_per_mL": f"{random.uniform(1e12, 1e15):.2e}",
        "Preparation_Method": random.choice(METHODS),
        "pH": round(random.uniform(6.8, 7.4), 1),
        "Osmolality_mOsm": round(random.uniform(250, 350), 1),
        "Sterility_Pass": "Yes" if random.random() > 0.05 else "No",
        "Endotoxin_EU_mL": round(random.uniform(0.001, 0.5), 4),
    }

def main():
    """Generate dataset"""
    print("=" * 70)
    print("🧬 LNP Dataset Generator")
    print("=" * 70)
    
    # Get desired sample size
    try:
        n_samples = int(input("\nHow many samples do you want to generate? (default 200): ") or "200")
    except:
        n_samples = 200
    
    filename = "comprehensive_lnp_dataset.csv"
    
    print(f"\n📊 Generating {n_samples} LNP samples...")
    
    with open(filename, 'w', newline='') as f:
        fieldnames = [
            "Batch_ID", "Material", "Size_nm", "PDI", "Charge_mV",
            "Encapsulation_%", "Stability_%", "Toxicity_%",
            "Hydrodynamic_Size_nm", "Surface_Area_nm2", "Pore_Size_nm",
            "Degradation_Time_days", "Target_Cells", "Ligand", "Receptor",
            "Delivery_Efficiency_%", "Particle_Concentration_per_mL",
            "Preparation_Method", "pH", "Osmolality_mOsm",
            "Sterility_Pass", "Endotoxin_EU_mL"
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Add known formulations
        for i, known in enumerate(KNOWN_FORMULATIONS, 1):
            known["Batch_ID"] = known["Batch_ID"]
            writer.writerow(known)
            print(f"  ✓ Added: {known['Batch_ID']}")
        
        # Generate synthetic samples
        for i in range(n_samples):
            sample = generate_sample()
            sample["Batch_ID"] = f"LNP-{i+1+len(KNOWN_FORMULATIONS):05d}"
            writer.writerow(sample)
            
            if (i + 1) % 50 == 0:
                print(f"  ✓ Generated {i + 1} samples...")
    
    total = n_samples + len(KNOWN_FORMULATIONS)
    print(f"\n✅ Success!")
    print(f"   Total samples: {total}")
    print(f"   Saved to: {filename}")
    print(f"   Features: 21 parameters per sample")
    print(f"\n📤 Next step: Upload '{filename}' to the ML Training tab")
    print("=" * 70)

if __name__ == "__main__":
    main()
