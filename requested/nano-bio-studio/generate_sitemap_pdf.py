#!/usr/bin/env python3
"""
Generate NanoBio Studio Sitemap as PDF
Updated with latest improvements (March 19, 2026)
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from datetime import datetime

# Create PDF
pdf_path = "SITEMAP_LATEST.pdf"
doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.7*inch, bottomMargin=0.7*inch,
                       leftMargin=0.6*inch, rightMargin=0.6*inch)

# Container for PDF elements
story = []
styles = getSampleStyleSheet()

# Custom styles
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=24,
    textColor=colors.HexColor('#1a237e'),
    spaceAfter=12,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

subtitle_style = ParagraphStyle(
    'CustomSubtitle',
    parent=styles['Normal'],
    fontSize=11,
    textColor=colors.HexColor('#667eea'),
    spaceAfter=10,
    alignment=TA_CENTER,
    fontName='Helvetica-Oblique'
)

section_style = ParagraphStyle(
    'SectionHead',
    parent=styles['Heading2'],
    fontSize=13,
    textColor=colors.HexColor('#1a237e'),
    spaceAfter=10,
    spaceBefore=8,
    fontName='Helvetica-Bold',
    borderColor=colors.HexColor('#667eea'),
    borderPadding=5
)

subsection_style = ParagraphStyle(
    'SubsectionHead',
    parent=styles['Heading3'],
    fontSize=11,
    textColor=colors.HexColor('#667eea'),
    spaceAfter=6,
    spaceBefore=6,
    fontName='Helvetica-Bold'
)

normal_style = ParagraphStyle(
    'Normal',
    parent=styles['Normal'],
    fontSize=9,
    spaceAfter=4,
    alignment=TA_LEFT
)

code_style = ParagraphStyle(
    'Code',
    parent=styles['Normal'],
    fontSize=8,
    fontName='Courier',
    textColor=colors.HexColor('#444444'),
    spaceAfter=2,
    leftIndent=20
)

# ============================================================================
# TITLE PAGE
# ============================================================================

story.append(Spacer(1, 0.5*inch))
story.append(Paragraph("🏗️ NanoBio Studio", title_style))
story.append(Paragraph("Application Site Map & Architecture", subtitle_style))
story.append(Spacer(1, 0.3*inch))
story.append(Paragraph(f"<i>Generated: {datetime.now().strftime('%B %d, %Y')}</i>", 
                      ParagraphStyle('date', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)))
story.append(Spacer(1, 0.2*inch))

info_table_data = [
    [Paragraph("<b>App Type:</b>", normal_style), Paragraph("Streamlit Multi-Page Application", normal_style)],
    [Paragraph("<b>Status:</b>", normal_style), Paragraph("Production Ready", normal_style)],
    [Paragraph("<b>Last Update:</b>", normal_style), Paragraph("March 19, 2026", normal_style)],
    [Paragraph("<b>Database:</b>", normal_style), Paragraph("SQLite (trial_registry.db, nanobio_studio.db)", normal_style)],
]

info_table = Table(info_table_data, colWidths=[1.5*inch, 4*inch])
info_table.setStyle(TableStyle([
    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f0f0f0'), colors.white]),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ('PADDING', (0, 0), (-1, -1), 6),
]))
story.append(info_table)

story.append(PageBreak())

# ============================================================================
# TABLE OF CONTENTS
# ============================================================================

story.append(Paragraph("📑 Table of Contents", section_style))
story.append(Spacer(1, 0.1*inch))

toc_items = [
    "1. Authentication & Session Management",
    "2. Main Workflow Pages",
    "3. AI Co-Designer Services",
    "4. Education & Training",
    "5. Administration & Data Management",
    "6. User Roles & Access Control",
    "7. Database Architecture",
    "8. Recent Improvements (March 2026)",
    "9. Key Features & Capabilities",
]

for item in toc_items:
    story.append(Paragraph(item, normal_style))
    story.append(Spacer(1, 0.05*inch))

story.append(PageBreak())

# ============================================================================
# 1. AUTHENTICATION & SESSION MANAGEMENT
# ============================================================================

story.append(Paragraph("1️⃣  Authentication & Session Management", section_style))

auth_text = """
<b>Entry Point:</b> Login.py<br/>
<b>Technology:</b> Streamlit Auth with Persistent Session Storage<br/>
<b>Status:</b> ✅ fully implemented with 15-minute idle timeout
"""
story.append(Paragraph(auth_text, normal_style))
story.append(Spacer(1, 0.05*inch))

story.append(Paragraph("<b>Session Features:</b>", subsection_style))
session_features = [
    "✅ Persistent login (survives page refresh)",
    "✅ 15-minute idle timeout with auto-logout",
    "✅ Session tokens stored in sessions.json",
    "✅ Session data: username, user_id, email, roles, timestamps",
    "✅ Token passing via URL query parameters (?session_token=...)",
    "✅ Auto-restoration of session on page load",
]

for feat in session_features:
    story.append(Paragraph(feat, code_style))

story.append(Spacer(1, 0.1*inch))

# ============================================================================
# 2. MAIN WORKFLOW PAGES
# ============================================================================

story.append(Paragraph("2️⃣  Main Workflow Pages", section_style))

workflow_data = [
    ["Page", "Route", "Purpose", "Features"],
    ["🔐 Login", "Login.py", "Authentication Entry Point", "Persistent session, RBAC check"],
    ["0️⃣ Disease Selection", "pages/0_Disease_Selection.py", "Workflow Step 1", "Disease & pathology selection"],
    ["1️⃣ Design Parameters", "pages/1_Design_Parameters.py", "Workflow Step 2", "NP design parameters"],
    ["2️⃣ Run Simulation", "pages/2_Run_Simulation.py", "Workflow Step 3 (FINAL)", "Runs simulation, saves to DB"],
    ["6️⃣ Trial History", "pages/6_Trial_History.py", "Advanced Feature", "Loads from trial_registry.db"],
    ["7️⃣ AI Co-Designer", "pages/7_AI_Co_Designer.py", "AI Services", "AI-powered suggestions"],
    ["8️⃣ Protocol Generator", "pages/8_Protocol_Generator.py", "Lab Protocols", "Generate synthesis protocols"],
    ["9️⃣ AI Architecture", "pages/9_AI_Architecture.py", "System Design", "Architecture documentation"],
    ["🔟 ML Training", "pages/10_ML_Training.py", "Machine Learning", "Model training interface"],
]

workflow_table = Table(workflow_data, colWidths=[1*inch, 2.2*inch, 1.8*inch, 1.8*inch])
workflow_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 9),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('FONTSIZE', (0, 1), (-1, -1), 8),
    ('GRIDLINE', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ('PADDING', (0, 0), (-1, -1), 5),
]))
story.append(workflow_table)

story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("<b>All Pages Have:</b>", subsection_style))
redirect_features = [
    "✅ Redirect button when not logged in ('Go to Login' with st.switch_page())",
    "✅ Timeout detection with auto-logout after 30 minutes",
    "✅ Clear messaging about session status",
]
for feat in redirect_features:
    story.append(Paragraph(feat, code_style))

story.append(PageBreak())

# ============================================================================
# 3. AI CO-DESIGNER SERVICES
# ============================================================================

story.append(Paragraph("3️⃣  AI Co-Designer Services", section_style))

ai_services = [
    ["Service", "Route", "Purpose"],
    ["AI Co-Designer", "pages/7_AI_Co_Designer.py", "AI-powered design suggestions & optimization"],
    ["Documentation", "pages/About_AI_Co_Designer.py", "AI system documentation & capabilities"],
]

ai_table = Table(ai_services, colWidths=[1.5*inch, 2.5*inch, 2.5*inch])
ai_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ('GRIDLINE', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ('PADDING', (0, 0), (-1, -1), 5),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
]))
story.append(ai_table)

story.append(PageBreak())

# ============================================================================
# 4. EDUCATION & TRAINING
# ============================================================================

story.append(Paragraph("4️⃣  Education & Training", section_style))

training_data = [
    ["Component", "Route", "Purpose"],
    ["Tutorial", "pages/10_Tutorial.py", "Learning resources & guides"],
    ["ML Training (5 pages)", "pages/13_ML Training/", "ML architecture & model training"],
    ["Architecture", "pages/11_AI_Architecture.py", "System architecture documentation"],
]

training_table = Table(training_data, colWidths=[1.5*inch, 2.5*inch, 2.5*inch])
training_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ('GRIDLINE', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ('PADDING', (0, 0), (-1, -1), 5),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
]))
story.append(training_table)

story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("<b>ML Training Pages:</b>", subsection_style))
ml_pages = [
    "1_AI_Architecture.py - AI system design",
    "2_Model_Training_Process.py - Model training workflow",
    "3_Feature_Engineering.py - Feature engineering techniques",
    "4_Validation_Testing.py - Model validation & testing",
    "5_Dataset_Statistics.py - Data analysis & statistics",
]
for page in ml_pages:
    story.append(Paragraph(f"• {page}", code_style))

story.append(PageBreak())

# ============================================================================
# 5. ADMINISTRATION & DATA MANAGEMENT
# ============================================================================

story.append(Paragraph("5️⃣  Administration & Data Management", section_style))

admin_text = """
<b>Admin Dashboard:</b> audit_dashboard.py<br/>
<b>User Management:</b> users.json (admin, designer, viewer roles)<br/>
<b>Database Management:</b> Multiple utility scripts for data maintenance
"""
story.append(Paragraph(admin_text, normal_style))
story.append(Spacer(1, 0.05*inch))

admin_tools = [
    "✅ Audit dashboard for system monitoring",
    "✅ User role management (Admin, Designer, Viewer)",
    "✅ Dataset management & import",
    "✅ Model storage & versioning",
    "✅ Data source integration (ToxCast API, external sources)",
]

for tool in admin_tools:
    story.append(Paragraph(tool, code_style))

story.append(PageBreak())

# ============================================================================
# 6. USER ROLES & ACCESS CONTROL
# ============================================================================

story.append(Paragraph("6️⃣  User Roles & Access Control", section_style))

roles_data = [
    ["Role", "Permissions", "Restrictions"],
    ["👤 Admin", "Full access to all pages, user management, data sources, audit dashboard", "None"],
    ["👨‍💼 Designer", "Workflow pages (0-17), AI Co-Designer, Trial History, Tutorial", "No user mgmt, no audit"],
    ["👁️ Viewer", "Read-only access to Trial History, Analytics, Tutorial", "No design/edit perms"],
]

roles_table = Table(roles_data, colWidths=[1.2*inch, 2.4*inch, 2.4*inch])
roles_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('GRIDLINE', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ('PADDING', (0, 0), (-1, -1), 6),
]))
story.append(roles_table)

story.append(PageBreak())

# ============================================================================
# 7. DATABASE ARCHITECTURE
# ============================================================================

story.append(Paragraph("7️⃣  Database Architecture", section_style))

story.append(Paragraph("<b>Primary Databases:</b>", subsection_style))

db_info = [
    ["Database", "Tables", "Purpose"],
    ["trial_registry.db", "trials, trial_sequences", "Stores all simulation trials & results"],
    ["nanobio_studio.db", "designs, parameters, results", "Design configurations & outputs"],
    ["users.db", "users, roles", "User authentication & RBAC"],
]

db_table = Table(db_info, colWidths=[2*inch, 2*inch, 2.5*inch])
db_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ('GRIDLINE', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ('PADDING', (0, 0), (-1, -1), 5),
]))
story.append(db_table)

story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("<b>Session Storage:</b>", subsection_style))
story.append(Paragraph("• sessions.json - Persistent user sessions with tokens & timestamps", code_style))
story.append(Paragraph("• users.json - User credentials & metadata", code_style))

story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("<b>Key Tables (trial_registry.db):</b>", subsection_style))
trial_schema = [
    "trials: trial_id, disease_subtype, disease_name, drug_name, np_size_nm,",
    "        np_charge_mv, np_peg_percent, np_zeta_potential, np_pdi,",
    "        treatment_dose_mgkg, treatment_route, treatment_frequency,",
    "        treatment_duration_days, trial_outcomes, creation_timestamp, status, notes",
    "",
    "trial_sequences: date, disease_code, next_sequence",
]

for line in trial_schema:
    story.append(Paragraph(line, code_style))

story.append(PageBreak())

# ============================================================================
# 8. RECENT IMPROVEMENTS (MARCH 2026)
# ============================================================================

story.append(Paragraph("8️⃣  Recent Improvements (March 2026)", section_style))

story.append(Paragraph("<b>Session Persistence System (March 18-19):</b>", subsection_style))
improvements = [
    "✅ Implemented persistent login surviving page refresh",
    "✅ Added 15-minute idle timeout with auto-logout",
    "✅ Session tokens stored in sessions.json with timestamps",
    "✅ Session restoration on page load via URL query parameters",
    "✅ Clear messaging on timeout with redirect button",
]

for imp in improvements:
    story.append(Paragraph(imp, code_style))

story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("<b>Redirect Button Implementation:</b>", subsection_style))
redirect_imp = [
    "✅ Added 'Go to Login' button to all protected pages",
    "✅ Button uses st.switch_page() for explicit navigation",
    "✅ Applied to 11+ pages across entire application",
    "✅ Consistent UX: message + centered button + st.stop()",
    "✅ Buttons clear query params before redirect",
]

for imp in redirect_imp:
    story.append(Paragraph(imp, code_style))

story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("<b>Trial History Fix:</b>", subsection_style))
trial_imp = [
    "✅ Trials now saved to persistent trial_registry.db",
    "✅ Run Simulation calls create_trial_entry() for each new trial",
    "✅ Trial History reads from database via get_all_trials()",
    "✅ Trial count no longer stuck at 31 after refresh",
    "✅ New trials persist across sessions & user logins",
]

for imp in trial_imp:
    story.append(Paragraph(imp, code_style))

story.append(PageBreak())

# ============================================================================
# 9. KEY FEATURES & CAPABILITIES
# ============================================================================

story.append(Paragraph("9️⃣  Key Features & Capabilities", section_style))

story.append(Paragraph("<b>Core Features:</b>", subsection_style))
features = [
    "🧪 Nanoparticle Design Optimization - Multi-parameter design tool",
    "📊 Simulation Engine - Kinetics, biodistribution, safety predictions",
    "🤖 AI Co-Designer - AI-powered design suggestions",
    "📈 Trial History - Track & compare all designs",
    "📋 Data Analytics - Performance trends & metrics",
    "🔐 Authentication - Multi-user support with RBAC",
    "⏱️ Session Management - Persistent login with idle timeout",
    "💾 Data Persistence - SQLite databases for trials & configurations",
]

for feat in features:
    story.append(Paragraph(feat, code_style))

story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("<b>Project Structure:</b>", subsection_style))
structure = [
    "/pages/ → Main application pages (0-17 + utilities)",
    "/pages/13_ML Training/ → 5-page ML training module",
    "/ai_engine/ → AI optimization & analysis",
    "/core/ → Scoring, analysis, algorithms",
    "/utils/ → PDF generation, helpers",
    "/modules/ → Trial registry, clinical data",
    "/tabs/ → Internal tab components",
    "/components/ → UI components & utilities",
]

for item in structure:
    story.append(Paragraph(item, code_style))

story.append(PageBreak())

# ============================================================================
# FOOTER
# ============================================================================

story.append(Spacer(1, 1*inch))

footer_data = [
    ["Repository", "NanoBio Studio (Private)", "GitHub"],
    ["Deployment", "Streamlit Cloud", "Automatic via git push"],
    ["Version", "1.0.0", "Production"],
    ["Last Deploy", f"{datetime.now().strftime('%B %d, %Y')}", "Successful"],
]

footer_table = Table(footer_data, colWidths=[1.5*inch, 2.3*inch, 2.2*inch])
footer_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
    ('GRIDLINE', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ('PADDING', (0, 0), (-1, -1), 5),
]))
story.append(footer_table)

story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("📧 <i>For questions or updates, contact the development team</i>", 
                      ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)))

# ============================================================================
# BUILD PDF
# ============================================================================

doc.build(story)
print(f"✅ PDF generated successfully: {pdf_path}")
