# 🚀 LAUNCH INSTRUCTIONS

## Quick Start - Choose Your Method

### Method 1: One-Click Start (Easiest) ⚡

**Windows Users:**
```
Double-click: start.bat
```

**Mac/Linux Users:**
```bash
chmod +x start.sh
./start.sh
```

The script will:
1. ✅ Check Python installation
2. ✅ Create virtual environment (if needed)
3. ✅ Install all dependencies
4. ✅ Launch NanoBio Studio
5. ✅ Open browser automatically

---

### Method 2: Manual Start 📝

**Step 1: Open Terminal/Command Prompt**

Windows: Press `Win + R`, type `cmd`, press Enter  
Mac: Press `Cmd + Space`, type `terminal`, press Enter  
Linux: Press `Ctrl + Alt + T`

**Step 2: Navigate to Project**

```bash
cd d:\nano_bio-26_1
```

**Step 3: Install Dependencies**

```bash
pip install -r requirements.txt
```

**Step 4: Run Application**

```bash
streamlit run app.py
```

**Step 5: Open Browser**

Go to: `http://localhost:8501`

---

## What You'll See

When successfully launched, you should see:

```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
  
  For better performance, install these packages:
    pip install watchdog
```

Browser will open showing:

```
🧬 NanoBio Studio
Connecting Nanotech × Biotech

[Navigation Sidebar]
├── 🏠 Home
├── 📚 Materials & Targets
├── 🎨 Design Nanoparticle
├── 📈 Delivery Simulation
├── ⚠️ Toxicity & Safety
├── 💰 Cost Estimator
├── 🤖 AI Protocol Generator
├── 💾 Import / Export
├── 📘 Tutorial
└── 🧑‍🏫 Instructor Notes
```

---

## First Steps Tutorial

### 1. Explore Materials (2 minutes)

1. Click **"📚 Materials & Targets"** in sidebar
2. Browse the 10 nanoparticle types
3. Expand "Lipid Nanoparticle (LNP)" to see details
4. Switch to "Targets" tab
5. Browse the 12 biological targets

### 2. Design Your First Nanoparticle (3 minutes)

1. Click **"🎨 Design Nanoparticle"**
2. Change name to: `My-First-NP`
3. Select material: `Lipid Nanoparticle (LNP)`
4. Adjust size: `100 nm`
5. Adjust charge: `-10 mV`
6. Select ligand: `PEG2000`
7. Select payload: `mRNA`
8. Set loading: `40%`
9. Select target: `Tumor Tissue (Solid)`
10. Set dose: `3 mg/kg`

### 3. Run Simulation (2 minutes)

1. Click **"📈 Delivery Simulation"**
2. Click **"▶️ Run Simulation"**
3. View the two plots:
   - Concentration-time profiles
   - Payload release curve
4. Review key metrics (8 parameters)
5. Click **"💾 Export Results (CSV)"** to save data

### 4. Assess Safety (2 minutes)

1. Click **"⚠️ Toxicity & Safety"**
2. Click **"🔬 Run Safety Assessment"**
3. View radar chart (7 risk factors)
4. Read overall risk level
5. Review safety recommendations

### 5. Calculate Costs (2 minutes)

1. Click **"💰 Cost Estimator"**
2. Review cost breakdown:
   - Material cost
   - Ligand cost
   - Payload cost
3. Check different batch sizes (1g, 10g, 100g)
4. View sensitivity analysis

### 6. Generate Protocol (2 minutes)

1. Click **"🤖 AI Protocol Generator"**
2. Adjust study duration if needed
3. Click **"✨ Generate Protocol"**
4. Review 10-section protocol
5. Click **"📥 Download Protocol (TXT)"**

### 7. Export Your Work (1 minute)

1. Click **"💾 Import / Export"**
2. Go to **"📤 Export Data"** tab
3. Click **"📥 Download Design (JSON)"**
4. Save for later use

---

## Troubleshooting

### Problem: "Python not found"

**Solution:**
1. Install Python from https://www.python.org/downloads/
2. During installation, check ☑️ "Add Python to PATH"
3. Restart terminal/command prompt
4. Try again

### Problem: "streamlit: command not found"

**Solution:**
```bash
pip install streamlit
```

### Problem: Port 8501 already in use

**Solution:**
```bash
# Use a different port
streamlit run app.py --server.port 8502
```

### Problem: Browser doesn't open automatically

**Solution:**
Manually open browser and go to: `http://localhost:8501`

### Problem: "No module named 'pages'"

**Solution:**
Make sure you're in the correct directory:
```bash
cd d:\nano_bio-26_1
pwd  # Should show: d:\nano_bio-26_1
ls   # Should show: app.py, pages/, data/, etc.
```

---

## System Requirements

**Minimum:**
- Python 3.8 or higher
- 4 GB RAM
- Modern web browser

**Recommended:**
- Python 3.10+
- 8 GB RAM
- Chrome or Firefox (latest version)
- 1920×1080 screen resolution

---

## Getting Help

**Check Documentation:**
1. README.md - Main user guide
2. SETUP.md - Detailed installation
3. TESTING.md - Testing procedures
4. Tutorial (in app) - Learning exercises

**Contact:**
- Email: info@expertsgroup.me
- GitHub Issues: [Your repository]

---

## What's Next?

### For Students:
1. Complete Tutorial Exercise 1 (Cancer Nanotherapy)
2. Try different parameter combinations
3. Compare multiple designs
4. Export and analyze results

### For Instructors:
1. Access Instructor Notes (password: `instructor2024`)
2. Review model answers
3. Plan lesson using provided materials
4. Customize exercises for your class

### For Researchers:
1. Design your target formulation
2. Run systematic parameter sweeps
3. Generate protocols for lab work
4. Export data for analysis in R/Python

---

## Features at a Glance

✅ **10 Page Modules** - Complete workflow coverage  
✅ **10 Nanoparticle Types** - LNP, PLGA, Gold, Liposomes, etc.  
✅ **12 Biological Targets** - Tumor, liver, brain, and more  
✅ **Two-Compartment PK Model** - Realistic simulation  
✅ **7-Factor Safety Assessment** - Comprehensive risk analysis  
✅ **Cost Estimation** - Material, ligand, payload breakdown  
✅ **AI Protocol Generator** - 10-section experimental protocols  
✅ **Import/Export** - JSON, CSV, TXT, PNG, Markdown  
✅ **6 Tutorial Exercises** - Guided learning  
✅ **Instructor Resources** - Answers, rubrics, teaching tips  

---

## Advanced Features

### Network Access

Share with others on your network:

```bash
streamlit run app.py --server.address 0.0.0.0
```

Then share the Network URL with colleagues.

### Cloud Deployment

Deploy to Streamlit Cloud (free):
1. Push code to GitHub
2. Go to share.streamlit.io
3. Connect your repository
4. Click Deploy

### Docker Deployment

```bash
docker build -t nanobio-studio .
docker run -p 8501:8501 nanobio-studio
```

---

## Keyboard Shortcuts

**Navigation:**
- `Ctrl + R` - Refresh page
- `Ctrl + Shift + R` - Clear cache and refresh
- `Tab` - Navigate between controls

**Streamlit:**
- `R` - Rerun the app
- `C` - Clear cache
- `A` - Open app in browser

---

## Data Privacy

✅ All data stays on your computer  
✅ No external API calls  
✅ No user tracking  
✅ No cloud storage required  
✅ Complete offline capability  

---

## Performance Tips

1. **Close unused browser tabs** - Reduces memory usage
2. **Use Chrome/Firefox** - Best performance
3. **Reduce simulation duration** - Faster calculations
4. **Clear browser cache** - If app seems slow
5. **Restart app** - After many operations

---

## Updates

Check for updates:

```bash
git pull origin main
pip install --upgrade -r requirements.txt
```

---

## License

MIT License - Free to use, modify, and distribute

---

## Citation

If you use NanoBio Studio in research or teaching:

```
NanoBio Studio: Interactive Platform for Nanoparticle Design
Version 1.0, 2024
https://github.com/expertsgroup/nanobio-studio
```

---

## Ready? Let's Go! 🚀

Choose your start method above and launch NanoBio Studio!

**Have fun exploring nano-bio interactions!**

---

*For detailed documentation, see README.md*  
*For installation help, see SETUP.md*  
*For testing procedures, see TESTING.md*  
*For project overview, see PROJECT_SUMMARY.md*
