"""
Instructor Notes Page - Password Protected
"""

import streamlit as st

def show():
    """Display instructor notes (password protected)"""
    st.title("🧑‍🏫 Instructor Notes")
    st.markdown("**Password-protected teaching resources, model answers, and grading rubrics**")
    
    st.markdown("---")
    
    # Password protection
    if 'instructor_authenticated' not in st.session_state:
        st.session_state.instructor_authenticated = False
    
    if not st.session_state.instructor_authenticated:
        st.warning("⚠️ This section is password-protected for instructors only")
        
        password = st.text_input("Enter Instructor Password", type="password", key="instructor_pw")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("🔓 Unlock", type="primary", use_container_width=True):
                # Default password: "instructor2024" (change this in production)
                if password == "instructor2024":
                    st.session_state.instructor_authenticated = True
                    st.success("✅ Access granted!")
                    st.rerun()
                else:
                    st.error("❌ Incorrect password")
        
        st.markdown("---")
        st.info("**Note for Instructors**: Default password is `instructor2024`. You can customize this in the source code.")
        
        return
    
    # If authenticated, show instructor content
    st.success("✅ Authenticated as Instructor")
    
    if st.button("🔒 Lock (Logout)"):
        st.session_state.instructor_authenticated = False
        st.rerun()
    
    st.markdown("---")
    
    # Instructor content tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 Model Answers",
        "📊 Grading Rubrics",
        "💡 Teaching Tips",
        "📚 Additional Resources"
    ])
    
    with tab1:
        show_model_answers()
    
    with tab2:
        show_grading_rubrics()
    
    with tab3:
        show_teaching_tips()
    
    with tab4:
        show_additional_resources()

def show_model_answers():
    """Model answers for exercises"""
    st.subheader("📝 Model Answers for Tutorial Exercises")
    
    exercise = st.selectbox(
        "Select Exercise",
        [
            "Exercise 1: Cancer Nanotherapy",
            "Exercise 2: Blood-Brain Barrier",
            "Exercise 3: Cost-Benefit Analysis",
            "Exercise 4: Safety Assessment"
        ]
    )
    
    st.markdown("---")
    
    if exercise == "Exercise 1: Cancer Nanotherapy":
        st.markdown("""
        ## Exercise 1 Model Answers
        
        ### Design Parameters
        
        **Optimal Design:**
        - Size: 100 nm (±10 nm acceptable)
        - Charge: -8 to -12 mV
        - Ligand: PEG2000
        - Payload: siRNA
        - Loading: 35-40%
        - Dose: 2-3 mg/kg
        
        ### Expected Results
        
        **PK/PD Simulation:**
        - T_max plasma: ~1-2 hours
        - T_max tissue: ~6-8 hours
        - Tissue accumulation ratio: 2.5-4.0
        - Plasma half-life: 8-12 hours
        
        **Safety Assessment:**
        - Overall safety score: 3.5-4.5 (Moderate)
        - Size risk: Low (2-3)
        - Charge risk: Low (2-3)
        - Ligand risk: Very Low (1-2)
        - Payload risk: Low (3)
        
        **Cost Estimation:**
        - Material cost: ~$200-400 per batch (1g)
        - Cost per patient (70 kg, 3 mg/kg): ~$800-1200
        
        ### Discussion Question Answers
        
        **1. Why is 100 nm optimal for tumor targeting?**
        
        **Model Answer:**
        - Tumors have fenestrations of 100-600 nm due to leaky vasculature
        - 100 nm particles can extravasate through these pores (EPR effect)
        - Particles <10 nm are rapidly cleared by kidneys
        - Particles >200 nm are captured by splenic filtration
        - 100 nm balances EPR penetration with extended circulation time
        
        **2. How does PEGylation affect biodistribution?**
        
        **Model Answer:**
        - Creates a hydrophilic "cloud" around nanoparticle
        - Reduces opsonization (protein binding)
        - Decreases recognition by macrophages in liver and spleen (RES)
        - Increases circulation half-life from minutes to hours
        - Reduces non-specific tissue accumulation
        - Allows time for EPR-mediated tumor accumulation
        - Trade-off: "PEG dilemma" - may reduce cellular uptake
        
        **3. Effect of increasing size to 300 nm?**
        
        **Model Answer:**
        - Rapid clearance by splenic filtration (>200 nm)
        - Reduced EPR effect (cannot penetrate tumor fenestrations efficiently)
        - Higher accumulation in liver and spleen
        - Lower tumor accumulation ratio
        - Potential for capillary embolism at high doses
        - Shorter circulation time
        - Result: Poor tumor targeting, increased off-target effects
        
        **4. Why siRNA instead of small molecules?**
        
        **Model Answer:**
        - Specificity: siRNA targets specific mRNA sequences
        - Duration: Gene silencing lasts days to weeks
        - Druggability: Can target "undruggable" proteins
        - Mechanism: Prevents protein production vs inhibiting existing protein
        - Off-targets: Potential, but more specific than many small molecules
        - Delivery challenge: siRNA is large, charged, and rapidly degraded → needs nanoparticle protection
        - Recent success: FDA-approved siRNA therapeutics (Onpattro, Givlaari)
        
        ### Common Student Errors
        
        ❌ **Error 1**: Size too small (<50 nm)
        - Result: Rapid kidney clearance, poor tumor accumulation
        
        ❌ **Error 2**: Positive charge (>+5 mV)
        - Result: High toxicity, hemolysis, rapid clearance
        
        ❌ **Error 3**: No PEGylation
        - Result: Very short circulation time (<30 min), RES clearance
        
        ❌ **Error 4**: Very high payload loading (>60%)
        - Result: Instability, high PDI, potential aggregation
        
        ### Assessment Criteria
        
        **Excellent (90-100%):**
        - All parameters within optimal range
        - Thoughtful discussion of trade-offs
        - Correct interpretation of simulation results
        - Recognition of EPR effect importance
        
        **Good (80-89%):**
        - Most parameters reasonable
        - Basic understanding demonstrated
        - Minor errors in interpretation
        
        **Satisfactory (70-79%):**
        - Some parameter optimization needed
        - Conceptual understanding present but incomplete
        
        **Needs Improvement (<70%):**
        - Major parameter errors
        - Limited understanding of concepts
        """)
    
    elif exercise == "Exercise 2: Blood-Brain Barrier":
        st.markdown("""
        ## Exercise 2 Model Answers
        
        ### Design Comparison
        
        **Design A: Ultra-Small Gold NP**
        - Size: 5-8 nm
        - Pros: Can pass through BBB via paracellular route
        - Cons: Rapid kidney clearance, low drug loading capacity, non-biodegradable
        - Expected brain accumulation: 0.1-0.5% injected dose
        
        **Design B: Receptor-Targeted Liposomes**
        - Size: 60-80 nm
        - Pros: Higher payload capacity, receptor-mediated transcytosis
        - Cons: More complex, expensive ligand, still limited penetration
        - Expected brain accumulation: 0.5-2% injected dose (with targeting)
        
        ### Model Answers to Discussion Questions
        
        **1. Why is small size critical for BBB?**
        
        - BBB endothelial cells have tight junctions (occludin, claudin)
        - Paracellular pores are extremely limited (~1 nm)
        - Transcellular pathways are selective and limited
        - Only very small (<10 nm) and lipophilic molecules can passively diffuse
        - Larger particles require active transport mechanisms
        - Even with targeting, BBB penetration remains <5% for most nanoparticles
        
        **2. Risks of cationic nanoparticles in CNS?**
        
        - Neurotoxicity: Disruption of neuronal membranes
        - Inflammation: Microglial activation, cytokine release
        - BBB disruption: Increased permeability (double-edged sword)
        - Seizure risk: Neuronal hyperexcitability
        - Oxidative stress: ROS generation in neurons
        - Mitochondrial dysfunction
        - Recommendation: Keep charge neutral or slightly negative for brain applications
        
        **3. How does transferrin receptor enable BBB crossing?**
        
        - Transferrin receptor (TfR) is highly expressed on BBB endothelium
        - Physiological role: Iron transport into brain
        - Receptor-mediated transcytosis pathway
        - Transferrin-conjugated nanoparticles bind to TfR
        - Endocytosis occurs
        - Vesicle trafficking across endothelial cell
        - Release on brain side
        - Efficiency: Still limited, but 5-10× better than non-targeted
        
        **4. Additional BBB challenges?**
        
        - Blood-CSF barrier at choroid plexus
        - Efflux transporters (P-gp, BCRP, MRP1)
        - Enzymatic degradation in brain parenchyma
        - Glial cell barriers (astrocyte end-feet)
        - Limited interstitial penetration in brain tissue
        - Immune privilege: Inflammatory responses
        
        ### Reality Check for Students
        
        **Important Truth**: BBB penetration is one of the HARDEST challenges in nanomedicine.
        
        - Most nanoparticles achieve <1% brain accumulation
        - Even "successful" targeted systems reach only 2-5%
        - Many CNS diseases remain untreatable due to delivery barriers
        - Alternative strategies: Direct injection, intranasal delivery, focused ultrasound BBB disruption
        
        **This is why:**
        - Glioblastoma has such poor prognosis
        - Alzheimer's and Parkinson's are so difficult to treat
        - Many psychiatric drugs have side effects (need high doses)
        
        ### Assessment Criteria
        
        Students should demonstrate:
        ✅ Understanding that BBB is a major challenge
        ✅ Recognition of size limitations
        ✅ Knowledge of targeting strategies
        ✅ Realistic expectations (not claiming 50% brain accumulation!)
        ✅ Awareness of alternative delivery routes
        """)
    
    elif exercise == "Exercise 3: Cost-Benefit Analysis":
        st.markdown("""
        ## Exercise 3 Model Answers
        
        ### Comparison Table
        
        | Parameter | Basic PLGA | PEGylated PLGA | mAb-Gold NP |
        |-----------|-----------|---------------|-------------|
        | Material Cost/g | $80 | $80 | $500 |
        | Ligand Cost/g | $0 | $100 | $5,000 |
        | Total Cost/Patient | $300 | $500 | $3,500 |
        | Safety Score | 4.5 | 3.5 | 5.5 |
        | Tissue Accum. Ratio | 1.5 | 2.8 | 4.5 |
        | Manufacturing Complexity | Low | Medium | High |
        | Scale-up Ease | Easy | Easy | Difficult |
        
        ### Model Answers
        
        **1. Cost vs. Performance**
        
        - Most expensive ≠ most effective per dollar
        - mAb-Gold NP: 3× accumulation but 11× cost vs. Basic PLGA
        - PEGylated PLGA: 2× accumulation at 1.7× cost → best value
        - Cost per unit efficacy:
          - Basic PLGA: $300 / 1.5 = $200 per unit
          - PEG-PLGA: $500 / 2.8 = $179 per unit ← **winner**
          - mAb-Gold: $3500 / 4.5 = $778 per unit
        
        **2. Scalability Analysis**
        
        **Basic PLGA:**
        ✅ Well-established manufacturing
        ✅ Emulsion techniques scale linearly
        ✅ FDA-approved excipients
        ✅ Low cost at scale
        
        **PEG-PLGA:**
        ✅ Adds one conjugation step
        ✅ PEG is commodity reagent
        ✅ Still relatively easy to scale
        ⚠️ Need to control PEG density consistently
        
        **mAb-Gold NP:**
        ❌ Antibody production expensive (CHO cells, purification)
        ❌ Conjugation chemistry variable
        ❌ Gold synthesis requires strict control
        ❌ Characterization complex
        ❌ Batch-to-batch variability high
        
        **3. Market Considerations**
        
        **Oncology Market:**
        - Patients often willing/able to pay high costs
        - Insurance coverage variable
        - Competition from standard chemotherapy
        - Value: Reduced side effects, improved QOL
        - Price ceiling: ~$10,000-50,000 per treatment course
        
        **Rare Diseases:**
        - Orphan drug pricing: Can exceed $300,000/year
        - Small patient population
        - High development costs amortized over few patients
        - Example: Onpattro (siRNA-LNP) ~$450,000/year
        
        **Vaccines:**
        - Must be affordable for mass deployment
        - Price target: <$50 per dose
        - Manufacturing must scale to millions/billions of doses
        - mRNA-LNP COVID vaccines: $20-40 per dose (government contracts)
        
        **4. Value Proposition**
        
        **What justifies high cost?**
        - 🎯 Better efficacy (e.g., higher cure rate)
        - 🎯 Fewer side effects (improved QOL)
        - 🎯 Reduced hospitalization
        - 🎯 Longer survival
        - 🎯 No alternative treatments available
        
        **Cost-effectiveness metrics:**
        - Quality-Adjusted Life Years (QALY)
        - Incremental Cost-Effectiveness Ratio (ICER)
        - Threshold: ~$100,000-150,000 per QALY in US
        
        ### Case Study: Doxil
        
        **Doxil (liposomal doxorubicin):**
        - Cost: ~$5,000 per treatment vs. $50 for free doxorubicin
        - Benefit: Reduced cardiotoxicity, longer circulation
        - Market: Successfully commercialized since 1995
        - Lesson: Significant cost increase justified by safety improvement
        
        ### Teaching Points
        
        For students to understand:
        1. ✅ Most expensive ≠ always best choice
        2. ✅ Consider cost-per-unit-efficacy, not just absolute cost
        3. ✅ Scalability is critical for commercialization
        4. ✅ Market and disease indication affect acceptable cost
        5. ✅ Regulatory pathway affects development cost
        6. ✅ Manufacturing complexity = higher cost + higher risk
        """)

def show_grading_rubrics():
    """Grading rubrics"""
    st.subheader("📊 Grading Rubrics")
    
    st.markdown("""
    ## General Grading Rubric for NanoBio Studio Exercises
    
    ### Design Quality (30%)
    
    **Excellent (27-30 points):**
    - All parameters within optimal range for target application
    - Demonstrates understanding of property-behavior relationships
    - Thoughtful consideration of trade-offs
    - PDI <0.2, appropriate size and charge for target
    
    **Good (24-26 points):**
    - Most parameters reasonable
    - Minor optimization possible
    - Basic understanding of relationships demonstrated
    
    **Satisfactory (21-23 points):**
    - Functional design but not optimized
    - Some parameters outside ideal range
    - Conceptual gaps present
    
    **Needs Improvement (<21 points):**
    - Major design flaws
    - Parameters contradict stated goals
    - Limited understanding demonstrated
    
    ### Analysis & Interpretation (30%)
    
    **Excellent (27-30 points):**
    - Correct interpretation of all simulation results
    - Insightful analysis of PK/PD profiles
    - Proper use of technical terminology
    - Connections made between parameters and outcomes
    - Identifies limitations of the model
    
    **Good (24-26 points):**
    - Mostly correct interpretations
    - Minor errors in analysis
    - Good use of terminology
    
    **Satisfactory (21-23 points):**
    - Basic interpretation present
    - Some errors or misconceptions
    - Limited depth of analysis
    
    **Needs Improvement (<21 points):**
    - Significant misinterpretations
    - Inability to explain results
    - Incorrect technical terminology
    
    ### Critical Thinking (25%)
    
    **Excellent (23-25 points):**
    - Thoughtful responses to discussion questions
    - Considers multiple perspectives
    - Makes connections to real-world applications
    - Identifies trade-offs and limitations
    - Proposes reasonable improvements
    
    **Good (20-22 points):**
    - Reasonable responses to questions
    - Some critical analysis
    - Basic real-world connections
    
    **Satisfactory (18-19 points):**
    - Surface-level responses
    - Limited critical analysis
    - Few connections to broader context
    
    **Needs Improvement (<18 points):**
    - Superficial or incorrect responses
    - No demonstration of critical thinking
    
    ### Technical Communication (15%)
    
    **Excellent (14-15 points):**
    - Clear, professional presentation
    - Appropriate figures and tables
    - Well-organized
    - Proper citations and references
    - Data properly formatted
    
    **Good (12-13 points):**
    - Generally clear communication
    - Adequate figures and organization
    - Minor formatting issues
    
    **Satisfactory (11 points):**
    - Understandable but not polished
    - Organizational issues
    - Incomplete documentation
    
    **Needs Improvement (<11 points):**
    - Unclear or disorganized
    - Missing key elements
    - Poor presentation
    
    ---
    
    ## Exercise-Specific Rubrics
    
    ### Exercise 1: Cancer Nanotherapy
    
    **Key Assessment Points:**
    - ✅ Size 80-120 nm (5 points)
    - ✅ Negative charge -5 to -15 mV (5 points)
    - ✅ Includes PEGylation (5 points)
    - ✅ Tissue accumulation >2x (5 points)
    - ✅ Safety score <5 (5 points)
    - ✅ Correct EPR discussion (5 points)
    - ✅ Understanding of siRNA delivery (5 points)
    
    ### Exercise 2: BBB Penetration
    
    **Key Assessment Points:**
    - ✅ Recognizes BBB difficulty (10 points)
    - ✅ Appropriate size consideration (<20 nm or targeted) (10 points)
    - ✅ Realistic accumulation expectations (<2%) (10 points)
    - ✅ Understanding of transcytosis (10 points)
    - ✅ Awareness of alternative strategies (10 points)
    
    ### Exercise 3: Cost-Benefit Analysis
    
    **Key Assessment Points:**
    - ✅ Accurate cost calculations (10 points)
    - ✅ Cost-per-efficacy analysis (10 points)
    - ✅ Scalability considerations (10 points)
    - ✅ Market awareness (10 points)
    - ✅ Value proposition assessment (10 points)
    
    ### Exercise 4: Safety Assessment
    
    **Key Assessment Points:**
    - ✅ Correct risk factor identification (10 points)
    - ✅ Appropriate mitigation strategies (10 points)
    - ✅ Understanding of toxicity mechanisms (10 points)
    - ✅ Regulatory awareness (10 points)
    - ✅ Before/after comparison (10 points)
    
    ---
    
    ## Common Student Issues to Watch For
    
    ### Misconceptions:
    ❌ "Smaller is always better" → No, depends on application
    ❌ "Positive charge is good for cellular uptake" → Yes, but toxicity trade-off
    ❌ "More targeting ligand = better" → Saturation, cost, complexity
    ❌ "100% payload loading" → Physically impossible, destabilizes particles
    ❌ "Nanoparticles can easily cross BBB" → One of the hardest challenges
    
    ### Calculation Errors:
    ❌ Wrong dose calculations (mg/kg conversions)
    ❌ Misinterpreting AUC ratios
    ❌ Confusing t_max with t_half
    ❌ Not accounting for waste factor in cost
    
    ### Analysis Errors:
    ❌ Not recognizing parameter interactions
    ❌ Ignoring trade-offs
    ❌ Overgeneralizing from single simulation
    ❌ Not questioning model limitations
    
    """)

def show_teaching_tips():
    """Teaching tips and strategies"""
    st.subheader("💡 Teaching Tips and Strategies")
    
    st.markdown("""
    ## Effective Use of NanoBio Studio in Teaching
    
    ### Course Integration
    
    #### For Undergraduate Courses:
    - **Nanotechnology Survey Course**: Use as hands-on lab component
    - **Biochemistry**: Illustrate drug delivery and targeting
    - **Biomedical Engineering**: Design project for medical applications
    - **Chemistry**: Connect synthesis to biological function
    
    #### For Graduate Courses:
    - **Advanced Drug Delivery**: Detailed parameter optimization
    - **Nanomedicine**: Integration of concepts across modules
    - **Pharmacokinetics**: Real-world PK/PD modeling
    - **Pharmaceutical Sciences**: Formulation development
    
    ### Lesson Plans
    
    #### 50-Minute Lecture + Lab Session
    
    **Minutes 0-15: Introduction**
    - Brief lecture on nanomedicine principles
    - Show real-world examples (Doxil, mRNA vaccines)
    - Introduce NanoBio Studio interface
    
    **Minutes 15-40: Guided Exercise**
    - Students work through Exercise 1
    - Instructor circulates, answers questions
    - Common stopping points:
      - After design (check parameters)
      - After simulation (interpret results)
      - After safety assessment
    
    **Minutes 40-50: Discussion**
    - Share interesting results
    - Discuss parameter choices
    - Connect to broader concepts
    
    #### Multi-Week Project
    
    **Week 1**: Introduction and basic design
    **Week 2**: Simulation and PK/PD interpretation
    **Week 3**: Safety and cost analysis
    **Week 4**: Advanced optimization
    **Week 5**: Final presentation and report
    
    ### Active Learning Strategies
    
    #### Think-Pair-Share:
    1. Students design individually (5 min)
    2. Pair up and compare designs (5 min)
    3. Share best designs with class (5 min)
    4. Discuss: Why different? What worked best?
    
    #### Jigsaw Method:
    1. Divide class into groups
    2. Each group becomes "expert" on one module:
       - Group A: Design optimization
       - Group B: PK/PD simulation
       - Group C: Safety assessment
       - Group D: Cost analysis
    3. Regroup with one expert from each area
    4. Solve comprehensive problem together
    
    #### Peer Review:
    1. Students export their designs
    2. Exchange with partner
    3. Review and provide feedback
    4. Revise based on feedback
    5. Compare before/after improvements
    
    ### Discussion Prompts
    
    **To stimulate critical thinking:**
    
    1. "What would happen if...?"
       - Size was doubled?
       - Charge flipped from negative to positive?
       - PEG was removed?
    
    2. "Why do you think...?"
       - Cancer drugs use the EPR effect?
       - Brain delivery is so difficult?
       - mRNA vaccines cost more than traditional vaccines?
    
    3. "How would you...?"
       - Improve tissue targeting?
       - Reduce toxicity?
       - Make it more cost-effective?
    
    4. "Compare and contrast..."
       - Lipid vs. polymer nanoparticles
       - Passive vs. active targeting
       - In vitro vs. in vivo results
    
    ### Common Student Questions (and Good Answers)
    
    **Q: "Why can't we just make everything very small?"**
    A: Great question! Very small particles (<10 nm) are rapidly cleared by kidneys. We need particles large enough to avoid renal clearance but small enough to penetrate target tissues. It's all about finding the optimal size window.
    
    **Q: "Why don't we always use antibodies for targeting?"**
    A: Antibodies are expensive (~$5,000 per gram), difficult to manufacture, can trigger immune responses, and add significant complexity. They're saved for applications where passive targeting isn't sufficient and the benefit justifies the cost and risk.
    
    **Q: "Is this model realistic?"**
    A: Good critical thinking! This is a simplified model. Real biology is messier - immune responses, protein corona, metabolism, etc. But the model captures key principles and helps us understand trade-offs before expensive lab work.
    
    **Q: "Why study this if we'll do experiments anyway?"**
    A: Virtual design saves time and money. If we can eliminate poor designs computationally, we only synthesize and test promising candidates. In pharma, this "fail fast, fail cheap" approach is standard.
    
    ### Troubleshooting Common Issues
    
    **Issue: Students design randomly without thinking**
    → Require them to justify each parameter choice in writing
    
    **Issue: Students don't understand PK/PD curves**
    → Have them sketch predicted curves before running simulation
    → Compare prediction to actual result and discuss differences
    
    **Issue: Students skip safety assessment**
    → Make it required component of grade
    → Emphasize that real drugs need safety data for FDA approval
    
    **Issue: Students claim unrealistic results**
    → Ask them to cite literature supporting their claims
    → Discuss typical accumulation values (2-5% for tumors, <1% for brain)
    
    ### Extensions and Variations
    
    **For Advanced Students:**
    - Design for specific diseases (glioblastoma, metastatic breast cancer)
    - Compare multiple formulations systematically
    - Write mock regulatory submission
    - Present to class as if to investors/FDA
    
    **For Interdisciplinary Classes:**
    - Biology students: Focus on targeting mechanisms
    - Chemistry students: Focus on synthesis and characterization
    - Engineering students: Focus on optimization and modeling
    - Business students: Focus on cost and commercialization
    
    **Group Projects:**
    - Startup competition: Design, pitch, and "fund" best nanomedicine
    - Peer review: Review other groups' designs as mock study section
    - Regulatory panel: Present to class acting as FDA reviewers
    
    ### Assessment Beyond Rubrics
    
    **Portfolio Assessment:**
    - Collect all designs from semester
    - Student writes reflection on learning progression
    - Demonstrate improvement over time
    
    **Concept Mapping:**
    - Students create concept map linking parameters to outcomes
    - Visualizes understanding of interconnections
    
    **Video Explanation:**
    - Students record 3-5 min video explaining their design choices
    - Assesses communication skills
    
    ### Accessibility Considerations
    
    ✅ Ensure all students have computer/internet access
    ✅ Provide alternative text-based data if simulations don't run
    ✅ Allow extra time for students with accommodations
    ✅ Provide screen reader compatible materials
    ✅ Offer one-on-one support as needed
    
    ### Connection to Careers
    
    Help students see relevance:
    - **Pharma R&D**: Formulation scientists do similar work
    - **Regulatory Affairs**: FDA review requires this analysis
    - **Clinical Trials**: PK/PD modeling used in dose selection
    - **Consulting**: Cost-benefit analysis for biotech investments
    - **Academia**: Experimental design and optimization
    
    ### Further Resources for Instructors
    
    **Recommended Textbooks:**
    - "Nanomedicine: Design and Applications of Magnetic Nanomaterials..." by Vallabani & Singh
    - "Drug Delivery: Fundamentals and Applications" by Hillery et al.
    - "Pharmacokinetics and Pharmacodynamics" by Gabrielsson & Weiner
    
    **Online Resources:**
    - FDA Nanotechnology Guidance Documents
    - Nature Nanotechnology (journal)
    - NIH Common Fund - Nanomedicine Initiative
    
    **Professional Development:**
    - Controlled Release Society (CRS) conferences
    - American Association of Pharmaceutical Scientists (AAPS)
    - Society for Biomaterials
    """)

def show_additional_resources():
    """Additional teaching resources"""
    st.subheader("📚 Additional Resources")
    
    st.markdown("""
    ## Additional Teaching Resources
    
    ### Lecture Slides (Suggested Topics)
    
    #### Module 1: Introduction to Nanomedicine (Week 1)
    - History of nanomedicine
    - Size scale and properties
    - Current FDA-approved nanomedicines
    - NanoBio Studio overview
    
    #### Module 2: Nanoparticle Design Principles (Week 2-3)
    - Material types and properties
    - Surface modifications
    - Payload encapsulation
    - Characterization techniques
    
    #### Module 3: Biological Interactions (Week 4-5)
    - Protein corona
    - EPR effect
    - RES clearance
    - Biological barriers
    
    #### Module 4: Pharmacokinetics (Week 6-7)
    - Compartment models
    - Absorption, distribution, metabolism, excretion
    - PK/PD relationships
    
    #### Module 5: Toxicology (Week 8-9)
    - Nanotoxicology mechanisms
    - In vitro and in vivo testing
    - Regulatory requirements
    
    #### Module 6: Clinical Translation (Week 10-11)
    - Cost considerations
    - Scalability
    - GMP manufacturing
    - Clinical trials
    
    ### Exam Questions (Examples)
    
    #### Multiple Choice:
    
    **1. Which nanoparticle size is optimal for tumor targeting via EPR effect?**
    a) 5 nm
    b) 50 nm
    c) 100 nm ✓
    d) 500 nm
    
    *Explanation: 100 nm particles accumulate in tumors through leaky vasculature while avoiding rapid renal clearance*
    
    **2. PEGylation primarily:**
    a) Increases cellular uptake
    b) Increases circulation time ✓
    c) Increases payload loading
    d) Decreases stability
    
    **3. The blood-brain barrier is particularly restrictive because:**
    a) It has tight junctions ✓
    b) It has large pores
    c) It lacks blood flow
    d) It is not vascularized
    
    #### Short Answer:
    
    **1. Explain why highly cationic nanoparticles show enhanced cellular uptake but increased toxicity. (10 points)**
    
    *Expected answer: Cationic nanoparticles interact electrostatically with negatively charged cell membranes, promoting endocytosis. However, this same charge interaction can disrupt membrane integrity, cause hemolysis, activate platelets, and trigger complement activation, leading to toxicity.*
    
    **2. Compare passive vs. active targeting strategies. Give one advantage and disadvantage of each. (10 points)**
    
    *Expected answer:*
    - *Passive (EPR): Advantage - simpler, cheaper; Disadvantage - not tissue-specific*
    - *Active (targeting ligands): Advantage - specific recognition; Disadvantage - expensive, complex, may trigger immune response*
    
    #### Problem-Solving:
    
    **1. You design a nanoparticle with the following properties:**
    - Size: 250 nm
    - Charge: +35 mV
    - No PEG
    - Dose: 20 mg/kg
    
    **Identify three major problems with this design and propose solutions. (15 points)**
    
    *Expected answer:*
    1. *Size too large → rapid splenic clearance. Solution: Reduce to 80-120 nm*
    2. *Highly cationic → toxicity. Solution: Reduce charge to -10 to +5 mV*
    3. *No PEG → rapid RES clearance. Solution: Add PEG2000 coating*
    
    ### Laboratory Exercises
    
    If you have access to a nanomedicine lab, these complement virtual exercises:
    
    #### Lab 1: Nanoparticle Synthesis
    - Synthesize PLGA nanoparticles by emulsion method
    - Compare to designed specifications from NanoBio Studio
    
    #### Lab 2: Characterization
    - DLS: Size and PDI measurement
    - Zeta potential analysis
    - TEM imaging
    - Compare actual vs. predicted properties
    
    #### Lab 3: In Vitro Testing
    - Cell viability assay
    - Cellular uptake by flow cytometry
    - Relate to design parameters
    
    #### Lab 4: Formulation Optimization
    - Design 3 formulations virtually
    - Synthesize most promising
    - Test and iterate
    
    ### Guest Speakers
    
    Invite professionals to speak about:
    - **Formulation Scientist** (pharma): Real-world drug development
    - **FDA Reviewer**: Regulatory perspective on nanomedicines
    - **Clinical Researcher**: Translation from bench to bedside
    - **Startup Founder**: Commercialization challenges
    - **Patent Attorney**: IP considerations in nanotechnology
    
    ### Field Trips (Virtual or In-Person)
    
    - **Pharmaceutical company**: See GMP manufacturing
    - **CRO (Contract Research Organization)**: Preclinical testing
    - **Academic nanomedicine lab**: Research environment
    - **FDA office**: Regulatory review process
    
    ### Recommended Videos and Media
    
    **YouTube Channels:**
    - Kurzgesagt: Immune system and nanotechnology
    - MIT OpenCourseWare: Drug delivery lectures
    - Nature Video: Nanomedicine breakthroughs
    
    **Documentaries:**
    - "Nano" (PBS documentary)
    - "The Code" (cancer immunotherapy, includes nanomedicine)
    
    **TED Talks:**
    - Sangeeta Bhatia: "Tiny robots that could transform medicine"
    - Jennifer Kahn: "Gene editing with CRISPR" (delivered via nanoparticles)
    
    ### Reading List
    
    #### Required Reading:
    1. Shi J. et al. (2017) "Cancer nanomedicine: progress, challenges and opportunities" *Nature Reviews Cancer*
    2. FDA Guidance: "Drug Products, Including Biological Products, that Contain Nanomaterials"
    3. Pardi N. et al. (2018) "mRNA vaccines" *Nature Reviews Drug Discovery*
    
    #### Supplementary Reading:
    1. "Challenges and strategies for drug delivery to the brain" - *Advanced Drug Delivery Reviews*
    2. "The EPR effect: Unique features of tumor blood vessels" - *Advanced Drug Delivery Reviews*
    3. "Nanotoxicology: An emerging discipline" - *Angew. Chem. Int. Ed.*
    
    ### Online Tools and Databases
    
    **Complement NanoBio Studio with:**
    - PubChem: Chemical structures and properties
    - Protein Data Bank: 3D protein structures for targeting
    - ClinicalTrials.gov: Search for nanoparticle clinical trials
    - Nanoparticle Information Library (NIL): Characterization data
    
    ### Assessment Rubric Templates
    
    **Downloadable rubrics available for:**
    - Individual design project
    - Group presentation
    - Written report
    - Laboratory notebook
    - Final exam
    
    ### Student Feedback Forms
    
    Collect feedback on:
    - ✅ Software usability
    - ✅ Learning objectives met
    - ✅ Difficulty level
    - ✅ Most/least valuable exercises
    - ✅ Suggestions for improvement
    
    ### Continuing Education for Instructors
    
    **Stay current with:**
    - Nature Nanotechnology (monthly journal)
    - ACS Nano (weekly journal)
    - Journal of Controlled Release (twice monthly)
    - Advanced Drug Delivery Reviews (review articles)
    
    **Conferences:**
    - Controlled Release Society Annual Meeting
    - AAPS PharmSci 360
    - Society for Biomaterials Annual Meeting
    
    ### Collaboration Opportunities
    
    **Connect with other instructors:**
    - Share custom exercises
    - Compare assessment strategies
    - Develop new teaching materials
    - Co-author educational publications
    
    **Contact us:** info@expertsgroup.me for instructor community access
    
    """)
