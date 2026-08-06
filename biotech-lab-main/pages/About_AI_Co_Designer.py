import streamlit as st

# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
st.set_page_config(
    page_title="About AI Co-Designer",
    layout="wide"
)

st.title("🤖 About AI Co-Designer")

st.markdown("""
### A simple explanation for everyone

**AI Co-Designer** is a smart assistant inside **NanoBio Studio**.  
Its purpose is to help you **decide which nanoparticle designs are worth testing**, before spending time and money in the lab.
""")

st.divider()

st.header("🔬 What problem does it solve?")

st.markdown("""
Designing nanoparticles involves many choices:
- How big the particle should be  
- How charged it is  
- What it is made of  
- What drug it carries  
- How much of it is used  

There are **hundreds or thousands of possible combinations**.

Testing all of them in real experiments would be:
- Expensive  
- Time-consuming  
- Often unnecessary  

**AI Co-Designer helps you narrow this down to the best few options.**
""")

st.divider()

st.header("🆚 How is this different from the old NanoBio Studio?")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Before (Old Version)")
    st.markdown("""
- You tested **one design at a time**
- You manually compared results
- You relied heavily on experience and guesswork
- Good designs could be missed
    """)

with col2:
    st.subheader("Now (With AI Co-Designer)")
    st.markdown("""
- The system tests **many designs automatically**
- It compares them intelligently
- It filters out weak or risky options
- It recommends the **best candidates**
    """)

st.divider()

st.header("🧠 What does AI Co-Designer actually do?")

st.markdown("""
Behind the scenes, AI Co-Designer:

1. Tries many nanoparticle designs on the computer  
2. Checks for each design:
   - How well it might work  
   - How risky it might be  
   - How difficult or costly it might be to make  
3. Compares all results  
4. Shows you **a ranked list of the most promising designs**

You stay in control — the system only **assists your decision**.
""")

st.divider()

st.header("📊 What results will you see?")

st.markdown("""
AI Co-Designer shows you:
- A short list of **top recommended designs**
- Simple charts showing trade-offs (performance vs safety vs cost)
- A confidence level for each recommendation
- Clear explanations of potential risks (for example: high dose or extreme charge)
""")

st.divider()

st.header("🧭 How do users typically use it?")

st.markdown("""
1. Define reasonable ranges (size, charge, materials, dose)  
2. Choose what matters most (performance, safety, or cost)  
3. Click **Run Optimization**  
4. Review the recommended designs  
5. Select a few designs for real laboratory testing  

This helps focus experiments on the **most promising options first**.
""")

st.divider()

st.header("❗ What AI Co-Designer does NOT do")

st.markdown("""
To avoid misunderstanding:

- ❌ It does **not** replace laboratory experiments  
- ❌ It does **not** treat patients  
- ❌ It does **not** make medical or clinical decisions  

✔ It is a **decision-support tool**, designed to guide research planning.
""")

st.divider()

st.header("🎯 Why this matters")

st.markdown("""
AI Co-Designer helps:
- Save research time  
- Reduce experimental cost  
- Lower risk of failed experiments  
- Improve decision-making  
- Use labs and funding more efficiently  

**In short:**  
The old NanoBio Studio showed results.  
**AI Co-Designer helps you decide what to do next.**
""")

st.success("You are still the decision maker. AI Co-Designer is here to assist you.")
