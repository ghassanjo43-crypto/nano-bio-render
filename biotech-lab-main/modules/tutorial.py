"""
Tutorial Page - Educational Guide
"""

import streamlit as st

def show():
    """Display tutorial interface"""
    st.title("📘 Tutorial & Learning Guide")
    st.markdown("Interactive exercises and learning objectives for NanoBio Studio")
    
    st.markdown("---")
    
    # Learning objectives
    st.subheader("🎯 Learning Objectives")
    
    objectives = [
        "Understand the relationship between nanoparticle physicochemical properties and biological behavior",
        "Design nanoparticles optimized for specific biological targets",
        "Interpret pharmacokinetic and pharmacodynamic simulation results",
        "Assess safety risks based on formulation parameters",
        "Estimate manufacturing costs and economic feasibility",
        "Generate comprehensive experimental protocols"
    ]
    
    for i, obj in enumerate(objectives, 1):
        st.markdown(f"{i}. {obj}")
    
    st.markdown("---")
    
    # Tutorial sections
    tutorial_section = st.selectbox(
        "Select Tutorial Section",
        [
            "Introduction to Nanomedicine",
            "Exercise 1: Design a Cancer Nanotherapy",
            "Exercise 2: Optimize for Blood-Brain Barrier",
            "Exercise 3: Cost-Benefit Analysis",
            "Exercise 4: Safety Assessment",
            "Advanced: Multi-Parameter Optimization"
        ]
    )
    
    st.markdown("---")
    
    if tutorial_section == "Introduction to Nanomedicine":
        show_introduction()
    elif tutorial_section == "Exercise 1: Design a Cancer Nanotherapy":
        show_exercise_1()
    elif tutorial_section == "Exercise 2: Optimize for Blood-Brain Barrier":
        show_exercise_2()
    elif tutorial_section == "Exercise 3: Cost-Benefit Analysis":
        show_exercise_3()
    elif tutorial_section == "Exercise 4: Safety Assessment":
        show_exercise_4()
    elif tutorial_section == "Advanced: Multi-Parameter Optimization":
        show_advanced()

def show_introduction():
    """Introduction section"""
    st.markdown("""
    ## Introduction to Nanomedicine
    
    ### What is Nanomedicine?
    
    Nanomedicine is the application of nanotechnology to medicine, particularly for diagnosis, monitoring, control, prevention, and treatment of diseases. Nanoparticles (1-500 nm) can:
    
    - **Enhance drug delivery** to specific tissues
    - **Protect therapeutic cargo** from degradation
    - **Control release kinetics** for sustained effect
    - **Enable combination therapies** in a single platform
    - **Improve biodistribution** and reduce side effects
    
    ### Key Concepts
    
    #### 1. Physicochemical Properties
    
    **Size:**
    - **<10 nm**: Rapid renal clearance
    - **10-100 nm**: Optimal for EPR effect in tumors
    - **>200 nm**: Clearance by spleen and liver
    
    **Surface Charge (Zeta Potential):**
    - **Highly positive (>+30 mV)**: Enhanced cellular uptake but potential toxicity
    - **Neutral (-10 to +10 mV)**: Reduced protein binding, "stealth" behavior
    - **Negative (<-20 mV)**: Good stability, reduced non-specific interactions
    
    **Surface Modification:**
    - **PEGylation**: Increases circulation time, reduces protein binding
    - **Targeting ligands**: Antibodies, peptides, small molecules for specific cell recognition
    
    #### 2. Enhanced Permeability and Retention (EPR) Effect
    
    Tumors have:
    - Leaky blood vessels
    - Poor lymphatic drainage
    
    → Nanoparticles accumulate preferentially in tumor tissue (passive targeting)
    
    #### 3. Biological Barriers
    
    - **Blood-Brain Barrier**: Restricts particles >10 nm
    - **Reticuloendothelial System (RES)**: Liver and spleen capture particles
    - **Kidney filtration**: Clears particles <5.5 nm
    
    ### Why Use NanoBio Studio?
    
    Traditional nanoparticle development is:
    - ❌ Time-consuming (months to years)
    - ❌ Expensive (equipment, materials, labor)
    - ❌ Trial-and-error based
    
    NanoBio Studio enables:
    - ✅ Rapid virtual design and testing
    - ✅ Parameter optimization before synthesis
    - ✅ Cost estimation and feasibility assessment
    - ✅ Educational exploration of nano-bio interactions
    
    ### Next Steps
    
    Select one of the exercises to begin hands-on exploration of nanoparticle design!
    """)

def show_exercise_1():
    """Exercise 1: Cancer Nanotherapy"""
    st.markdown("""
    ## Exercise 1: Design a Cancer Nanotherapy
    
    ### 🎯 Objective
    Design a lipid nanoparticle (LNP) loaded with siRNA to silence an oncogene in solid tumors.
    
    ### 📚 Background
    
    Solid tumors are one of the primary targets for nanomedicine due to the EPR effect. Key considerations:
    
    - **Tumor vasculature**: Leaky, allowing particles 10-200 nm to accumulate
    - **Target size**: 80-120 nm optimal for EPR
    - **Surface charge**: Slightly negative for stability and stealth
    - **PEGylation**: Essential for extended circulation time
    
    ### ✍️ Instructions
    
    1. **Navigate to Design Nanoparticle page**
    
    2. **Set the following parameters:**
       - Name: `siRNA-LNP-Tumor-01`
       - Material: Lipid Nanoparticle (LNP)
       - Size: 100 nm
       - Charge: -10 mV
       - Ligand: PEG2000
       - Payload: siRNA
       - Payload Loading: 30-40%
       - Target: Tumor Tissue (Solid)
       - Dose: 2-5 mg/kg
    
    3. **Run Delivery Simulation**
       - Observe tissue vs plasma concentration
       - Note the time to peak tissue concentration
       - Calculate tissue accumulation ratio
    
    4. **Assess Safety**
       - Run toxicity assessment
       - Review risk factors
       - Note any high-risk parameters
    
    5. **Estimate Costs**
       - Calculate cost per patient
       - Assess economic feasibility
    
    ### 🤔 Discussion Questions
    
    1. **Why is 100 nm optimal for tumor targeting?**
       - Consider EPR effect
       - Think about clearance mechanisms
    
    2. **How does PEGylation affect biodistribution?**
       - Effect on protein binding
       - Impact on circulation time
       - Influence on RES uptake
    
    3. **What would happen if you increased the size to 300 nm?**
       - Consider splenic filtration
       - Think about EPR efficiency
    
    4. **Why use siRNA instead of small molecule drugs?**
       - Specificity of target
       - Gene knockdown vs. protein inhibition
    
    ### 📊 Expected Results
    
    - Tissue accumulation ratio: 2-5 (good tumor targeting)
    - T_max tissue: 4-12 hours
    - Safety score: Low to moderate risk
    - Typical cost: $500-2000 per patient (depending on scale)
    
    ### 🏆 Success Criteria
    
    ✅ Size: 80-120 nm
    ✅ PDI: <0.2
    ✅ Charge: -5 to -15 mV
    ✅ Tissue accumulation: >2x plasma AUC
    ✅ Safety score: <5 (Moderate risk or better)
    
    ### 💡 Extension Activities
    
    1. **Optimize payload loading**: Test 20%, 30%, 40%, 50% - which is optimal?
    2. **Compare ligands**: Try without PEG vs. with PEG
    3. **Dose variation**: Test 1, 2, 5, 10 mg/kg - effects on toxicity?
    """)

def show_exercise_2():
    """Exercise 2: BBB penetration"""
    st.markdown("""
    ## Exercise 2: Optimize for Blood-Brain Barrier Penetration
    
    ### 🎯 Objective
    Design nanoparticles capable of crossing or bypassing the blood-brain barrier (BBB) for neurological applications.
    
    ### 📚 Background
    
    The BBB is one of the most challenging barriers in drug delivery:
    
    - **Tight junctions**: Prevent paracellular transport
    - **Size restriction**: Generally <10 nm for passive diffusion
    - **Efflux pumps**: P-glycoprotein actively removes many drugs
    - **Selective permeability**: Requires specific transporters or receptors
    
    **Strategies for BBB penetration:**
    1. Small size (<20 nm)
    2. Lipophilic surface
    3. Receptor-mediated transcytosis (e.g., transferrin receptor)
    4. Cell-penetrating peptides
    
    ### ✍️ Instructions
    
    #### Design A: Ultra-Small Gold Nanoparticles
    
    1. Material: Gold Nanoparticle (AuNP)
    2. Size: 5-10 nm (very small)
    3. Charge: Near neutral (0 to -5 mV)
    4. Ligand: PEG (for stability)
    5. Payload: Small molecule drug
    6. Target: Brain (Blood-Brain Barrier)
    
    #### Design B: Receptor-Targeted Liposomes
    
    1. Material: Liposome
    2. Size: 50-80 nm
    3. Charge: Slightly positive (+5 to +10 mV)
    4. Ligand: Transferrin (targets transferrin receptor on BBB)
    5. Payload: Protein/Peptide
    6. Target: Brain (Blood-Brain Barrier)
    
    ### 🔬 Analysis Tasks
    
    1. **Compare both designs:**
       - Run simulations for both
       - Compare tissue accumulation
       - Assess safety profiles
       - Compare costs
    
    2. **Evaluate trade-offs:**
       - Size vs. payload capacity
       - Targeting vs. complexity
       - Safety vs. efficacy
    
    ### 🤔 Discussion Questions
    
    1. **Why is small size critical for BBB penetration?**
    2. **What are the risks of cationic nanoparticles in the CNS?**
    3. **How does the transferrin receptor enable BBB crossing?**
    4. **What additional challenges exist beyond the BBB (blood-CSF barrier)?**
    
    ### 📊 Expected Challenges
    
    - Very low accumulation (<0.5% injected dose)
    - Trade-off between size and loading capacity
    - Higher safety concerns with positive charge in brain
    - Expensive targeting ligands (antibodies, transferrin)
    
    ### 💡 Real-World Context
    
    BBB penetration remains one of the greatest challenges in nanomedicine. Most CNS diseases have limited treatment options due to delivery barriers. This exercise illustrates why:
    
    - Brain tumors have poor prognosis
    - Neurodegenerative diseases are difficult to treat
    - CNS infections require high systemic doses
    """)

def show_exercise_3():
    """Exercise 3: Cost-benefit analysis"""
    st.markdown("""
    ## Exercise 3: Cost-Benefit Analysis
    
    ### 🎯 Objective
    Compare the economic feasibility of different nanoparticle formulations for the same therapeutic application.
    
    ### 📚 Background
    
    Nanomedicine development must balance:
    - **Scientific efficacy**: Does it work?
    - **Safety profile**: Is it safe?
    - **Economic feasibility**: Can it be commercialized?
    - **Scalability**: Can it be manufactured at scale?
    
    ### ✍️ Instructions
    
    Design three different formulations for tumor-targeted drug delivery:
    
    #### Formulation 1: Basic PLGA
    - Material: PLGA polymer
    - Ligand: None (passive targeting only)
    - Payload: Small molecule drug
    - Size: 150 nm
    
    #### Formulation 2: PEGylated PLGA
    - Material: PLGA polymer
    - Ligand: PEG (stealth effect)
    - Payload: Small molecule drug
    - Size: 150 nm
    
    #### Formulation 3: Antibody-Targeted Gold NP
    - Material: Gold Nanoparticle
    - Ligand: Monoclonal Antibody (mAb)
    - Payload: Small molecule drug
    - Size: 50 nm
    
    ### 📊 Analysis Table
    
    Create a comparison table:
    
    | Parameter | Formulation 1 | Formulation 2 | Formulation 3 |
    |-----------|--------------|--------------|--------------|
    | Material Cost | $ | $ | $ |
    | Ligand Cost | $ | $ | $ |
    | Total Cost/Patient | $ | $ | $ |
    | Safety Score | / 10 | / 10 | / 10 |
    | Tissue Accumulation | AUC ratio | AUC ratio | AUC ratio |
    | Complexity | Low/Med/High | Low/Med/High | Low/Med/High |
    
    ### 🤔 Discussion Questions
    
    1. **Cost vs. Performance:**
       - Is the most expensive formulation the most effective?
       - What is the cost per unit of efficacy?
    
    2. **Scalability:**
       - Which formulation is easiest to scale up?
       - What are manufacturing challenges for each?
    
    3. **Market Considerations:**
       - For oncology: What price can the market bear?
       - For rare diseases: Different pricing model?
       - For vaccines: Must be affordable at scale
    
    4. **Value Proposition:**
       - What value does each formulation provide over standard treatment?
       - How much improvement justifies the cost?
    
    ### 💰 Real-World Context
    
    **Approved Nanomedicines and Their Costs:**
    
    - Doxil (liposomal doxorubicin): ~$4,000-6,000 per treatment cycle
    - Onpattro (LNP-siRNA): ~$450,000 per year
    - Moderna/Pfizer COVID vaccines (mRNA-LNP): ~$20-40 per dose
    
    **Why such variation?**
    - Disease rarity (orphan drugs command higher prices)
    - Manufacturing complexity
    - Development costs
    - Market competition
    - Healthcare system willingness to pay
    
    ### 🏆 Learning Outcomes
    
    After this exercise, you should understand:
    
    ✅ Trade-offs between cost and performance
    ✅ Impact of material selection on economics
    ✅ Value of targeting ligands vs. their cost
    ✅ Importance of dose and batch size optimization
    ✅ Real-world commercialization considerations
    """)

def show_exercise_4():
    """Exercise 4: Safety assessment"""
    st.markdown("""
    ## Exercise 4: Safety Assessment and Risk Mitigation
    
    ### 🎯 Objective
    Evaluate safety risks of nanoparticle formulations and design strategies to mitigate them.
    
    ### 📚 Background
    
    Nanotoxicology considers multiple risk factors:
    
    **Size-Dependent Toxicity:**
    - Very small (<5 nm): Kidney filtration, potential organ penetration
    - Large (>200 nm): Rapid clearance by RES, potential embolism
    
    **Charge-Dependent Toxicity:**
    - Cationic (+): Hemolysis, platelet activation, membrane disruption
    - Highly anionic (-): Complement activation
    
    **Material-Dependent Toxicity:**
    - Quantum dots: Heavy metal content (Cd, Se)
    - Carbon nanotubes: Biopersistence, asbestos-like effects
    - Non-degradable materials: Long-term accumulation
    
    ### ✍️ Instructions
    
    #### Part A: Identify High-Risk Formulations
    
    Design and assess the following "problematic" formulations:
    
    **Formulation A: Highly Cationic**
    - Size: 100 nm
    - Charge: +40 mV
    - Material: Dendrimer
    - Dose: 10 mg/kg
    
    **Formulation B: Very Small Quantum Dots**
    - Size: 5 nm
    - Charge: -20 mV
    - Material: Quantum Dot
    - Dose: 5 mg/kg
    
    **Formulation C: Large, High-Dose PLGA**
    - Size: 400 nm
    - Charge: +15 mV
    - Material: PLGA
    - Dose: 50 mg/kg
    
    #### Part B: Risk Mitigation
    
    For each problematic formulation, redesign to reduce risk:
    
    1. Identify the primary risk factors
    2. Propose design modifications
    3. Re-assess safety score
    4. Compare before/after risk profiles
    
    ### 🔬 Analysis Tasks
    
    1. **Generate radar charts** for all formulations
    2. **Identify highest-risk parameters**
    3. **Calculate overall safety scores**
    4. **Rank formulations by risk level**
    
    ### 🤔 Discussion Questions
    
    1. **Charge Reduction:**
       - How can you reduce positive charge?
       - What is the role of PEGylation?
       - Trade-off: cellular uptake vs. toxicity
    
    2. **Size Optimization:**
       - What is the "safest" size range?
       - How does size affect different organs?
       - Balance between EPR effect and safety
    
    3. **Material Selection:**
       - Why prefer biodegradable materials?
       - What makes lipids safer than metals?
       - Role of FDA approval history
    
    4. **Dose Considerations:**
       - Relationship between dose and toxicity
       - Therapeutic index
       - Maximum tolerated dose (MTD)
    
    ### ⚕️ Regulatory Perspective
    
    **FDA Considerations for Nanomedicines:**
    
    1. **Physicochemical Characterization:**
       - Size distribution
       - Surface properties
       - Composition
       - Stability
    
    2. **Preclinical Safety:**
       - In vitro cytotoxicity
       - Hemolysis
       - Complement activation
       - Acute toxicity (single dose)
       - Repeat-dose toxicity (28-90 days)
       - Biodistribution
       - Clearance and excretion
    
    3. **Clinical Development:**
       - Phase I: Safety and MTD
       - Phase II: Efficacy signals
       - Phase III: Comparative efficacy
    
    ### 🏆 Learning Outcomes
    
    ✅ Identify safety risk factors
    ✅ Understand toxicity mechanisms
    ✅ Design safer formulations
    ✅ Apply risk mitigation strategies
    ✅ Consider regulatory requirements
    
    ### 📚 Recommended Reading
    
    - FDA Guidance: "Considering Whether an FDA-Regulated Product Involves the Application of Nanotechnology"
    - ISO/TR 13014:2012: Nanotoxicology
    - EMA Reflection Paper on Nanotechnology-Based Medicinal Products
    """)

def show_advanced():
    """Advanced multi-parameter optimization"""
    st.markdown("""
    ## Advanced: Multi-Parameter Optimization
    
    ### 🎯 Objective
    Perform systematic optimization of multiple parameters to achieve optimal balance between efficacy, safety, and cost.
    
    ### 📚 Background
    
    Real nanoparticle development requires optimization across multiple competing objectives:
    
    - **Maximize**: Tissue accumulation, payload loading, stability
    - **Minimize**: Toxicity, cost, polydispersity
    - **Constraints**: Size range, charge limits, dose limits
    
    This is a **multi-objective optimization** problem.
    
    ### ✍️ Instructions
    
    #### Challenge: Design an Optimal mRNA-LNP for Cancer
    
    **Requirements:**
    - Tissue accumulation ratio >3
    - Safety score <4 (Low to Moderate)
    - Cost per patient <$2000
    - PDI <0.15
    - Stable for >30 days at 4°C
    
    **Parameters to Optimize:**
    1. Size (50-150 nm)
    2. Charge (-30 to +10 mV)
    3. Ligand type
    4. Payload loading (20-60%)
    5. Dose (1-10 mg/kg)
    
    ### 🔬 Systematic Approach
    
    #### Step 1: Design of Experiments (DoE)
    
    Create a matrix of designs to test:
    
    | Design | Size | Charge | Ligand | Loading | Dose |
    |--------|------|--------|---------|---------|------|
    | A1 | 80 nm | -10 mV | PEG | 30% | 2 mg/kg |
    | A2 | 80 nm | -10 mV | PEG | 40% | 2 mg/kg |
    | A3 | 80 nm | -5 mV | PEG2000 | 40% | 3 mg/kg |
    | ... | ... | ... | ... | ... | ... |
    
    #### Step 2: Evaluate Each Design
    
    For each design, record:
    - Tissue accumulation ratio
    - Safety score
    - Cost per patient
    - Any constraint violations
    
    #### Step 3: Multi-Criteria Decision Analysis
    
    Create a scoring system:
    
    ```
    Score = w1 × (Efficacy) - w2 × (Safety_Risk) - w3 × (Cost) + w4 × (Stability)
    ```
    
    Where w1, w2, w3, w4 are weights based on priorities.
    
    #### Step 4: Identify Optimal Design
    
    - Highest score wins
    - Check that all constraints are met
    - Verify trade-offs are acceptable
    
    ### 📊 Example Analysis
    
    **Pareto Frontier:**
    
    Plot efficacy vs. safety for all designs. The Pareto frontier represents designs where you cannot improve one objective without worsening another.
    
    Optimal designs lie on this frontier.
    
    ### 🤔 Advanced Discussion Questions
    
    1. **Trade-off Analysis:**
       - What is the cost of improving efficacy by 20%?
       - How much safety risk to accept for better targeting?
    
    2. **Sensitivity Analysis:**
       - Which parameter has the largest effect on efficacy?
       - Which parameter affects safety the most?
       - Are there interactions between parameters?
    
    3. **Robustness:**
       - How sensitive is the design to manufacturing variability?
       - What if size is ±10%? Charge ±5 mV?
       - Design a robust formulation
    
    4. **Scale-Up Considerations:**
       - Will the optimal design work at 100× scale?
       - Manufacturing challenges?
       - Quality control strategy?
    
    ### 🏆 Real-World Application
    
    This exercise mirrors actual pharmaceutical development:
    
    - **Formulation scientists** perform similar optimizations
    - **Statistical DoE** is used in industry
    - **Quality by Design (QbD)** requires understanding parameter relationships
    - **Regulatory agencies** expect optimization justification
    
    ### 💡 Tools for Advanced Optimization
    
    In real development, you might use:
    - Design-Expert software for DoE
    - MODDE or JMP for multivariate analysis
    - Python/R for custom optimization algorithms
    - Machine learning for predictive modeling
    
    ### 📚 Further Learning
    
    - Read about Quality by Design (QbD) in pharmaceuticals
    - Study DoE methodology
    - Explore multi-objective optimization algorithms (NSGA-II, MOPSO)
    - Learn about Bayesian optimization for expensive experiments
    """)
