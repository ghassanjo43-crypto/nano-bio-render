import streamlit as st
import pandas as pd

# If you rely on these in this tab, keep them:
from core.state import ensure_state
from core.scoring import compute_impact

def render(plotly_ok: bool = False):
    """
    Materials & Targets tab
    Standard entry point used by app.py: materials.render(...)
    """
    ensure_state()

    st.header("🧱 Materials & Targets Library")
    st.caption("Select nanoparticle materials and targeting ligands, then apply to current design.")

    # ---- Minimal DB (expand later) ----
    materials_db = {
        "Lipid NP": {
            "description": "Lipid-based nanoparticles for mRNA/drug delivery",
            "cost": "Low-Medium",
            "toxicity": "Low",
            "stability": "2-6 months",
            "regulatory": "Well-established",
        },
        "PLGA": {
            "description": "Biodegradable polymer nanoparticles for controlled release",
            "cost": "Medium",
            "toxicity": "Very Low",
            "stability": "6-12 months",
            "regulatory": "FDA approved for several products",
        },
        "Gold NP": {
            "description": "Imaging / photothermal therapy nanoparticles",
            "cost": "High",
            "toxicity": "Medium",
            "stability": "Long-term",
            "regulatory": "Clinical trials ongoing",
        },
        "Silica NP": {
            "description": "Mesoporous silica nanoparticles with tunable pores",
            "cost": "Medium",
            "toxicity": "Low-Medium",
            "stability": "12+ months",
            "regulatory": "Preclinical",
        },
        "DNA Origami": {
            "description": "Programmable DNA nanostructures",
            "cost": "Very High",
            "toxicity": "Low",
            "stability": "Weeks",
            "regulatory": "Early research",
        },
        "MOF-303": {
            "description": "Metal-Organic Framework nanoparticles (high surface area)",
            "cost": "High",
            "toxicity": "Low",
            "stability": "1-3 months",
            "regulatory": "Research phase",
        },
    }

    ligands_db = {
        "GalNAc": {"target": "ASGPR", "cells": "Hepatocytes (Liver cells)"},
        "Folate": {"target": "Folate receptor", "cells": "Cancer cells / Macrophages"},
        "RGD peptide": {"target": "Integrins (αvβ3/αvβ5)", "cells": "Endothelial cells / Tumors"},
        "Transferrin": {"target": "Transferrin receptor", "cells": "Rapidly dividing cells / BBB"},
        "Anti-HER2 antibody": {"target": "HER2", "cells": "HER2+ tumor cells"},
        "Aptamers": {"target": "Programmable", "cells": "Target-specific cells"},
        "None": {"target": "None", "cells": "None"},
    }

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🧪 Select Material")

        current_material = st.session_state.design.get("Material", "Lipid NP")
        mat_names = list(materials_db.keys())
        mat_index = mat_names.index(current_material) if current_material in mat_names else 0

        selected_material = st.selectbox(
            "Core material",
            mat_names,
            index=mat_index,
            key="materials_selected_material",
        )

        mat = materials_db[selected_material]
        st.write(f"**Description:** {mat['description']}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cost", mat["cost"])
        m2.metric("Toxicity", mat["toxicity"])
        m3.metric("Stability", mat["stability"])
        m4.metric("Regulatory", mat["regulatory"])

        st.markdown("### 📊 Compare (quick)")
        compare = st.multiselect(
            "Compare materials",
            mat_names,
            default=[x for x in ["Lipid NP", "PLGA", "Gold NP"] if x in mat_names],
            key="materials_compare_multi",
            max_selections=4,
        )
        if compare:
            rows = []
            for name in compare:
                info = materials_db[name]
                rows.append({
                    "Material": name,
                    "Cost": info["cost"],
                    "Toxicity": info["toxicity"],
                    "Stability": info["stability"],
                    "Regulatory": info["regulatory"],
                })
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    with col2:
        st.subheader("🎯 Targeting")

        current_ligand = st.session_state.design.get("Ligand", "GalNAc")
        lig_names = list(ligands_db.keys())
        lig_index = lig_names.index(current_ligand) if current_ligand in lig_names else 0

        selected_ligand = st.selectbox(
            "Ligand",
            lig_names,
            index=lig_index,
            key="materials_selected_ligand",
        )

        lig = ligands_db[selected_ligand]
        st.write(f"**Target receptor:** {lig['target']}")
        st.write(f"**Target cells:** {lig['cells']}")

        st.markdown("---")
        if st.button("🔄 Apply to Current Design", width='stretch', key="materials_apply_btn"):
            st.session_state.design["Material"] = selected_material
            st.session_state.design["Ligand"] = selected_ligand
            st.session_state.design["Receptor"] = lig["target"]
            st.session_state.design["Target"] = lig["cells"]

            # Optional: recompute & show quick confirmation
            impact = compute_impact(st.session_state.design)
            st.success(
                f"✅ Applied {selected_material} + {selected_ligand}. "
                f"Delivery {impact['Delivery']:.1f}% | Toxicity {impact['Toxicity']:.2f}/10"
            )
            st.rerun()
