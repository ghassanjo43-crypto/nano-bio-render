# NanoBio Studio - Application Site Map

## Navigation Structure

```
NanoBio Studio Application
├── 🔐 Authentication
│   └── Login.py (Entry Point)
│       └── Disease Selection (After login)
│
├── Main Workflow Pages (Sequential Flow)
│   ├── 0️⃣  Disease Selection
│   │   └── Disease & Pathology Info
│   │
│   ├── 1️⃣  Features
│   │   └── Feature Definition & Setup
│   │
│   ├── 3️⃣  Design Parameters
│   │   └── Configure Design Parameters
│   │
│   ├── 4️⃣  Run Simulation
│   │   └── Execute Simulations
│   │
│   ├── 5️⃣  Trial History
│   │   └── View & Analyze Results
│   │
│   └── 17️⃣ Data Analytics
│       └── Advanced Analytics Dashboard
│
├── 🤖 AI Co-Designer Services
│   ├── 9️⃣  AI Co-Designer
│   │   └── AI-Powered Design Suggestions
│   │
│   └── About_AI_Co_Designer
│       └── AI Co-Designer Documentation
│
├── 📚 Education & Training
│   └── 🔟 Tutorial
│       └── Learning Resources
│
├── 🔧 Administration & Setup
│   ├── 🔢 Dataset Management
│   │   ├── 14️⃣ Data Sources
│   │   ├── 15️⃣ External Data Sources
│   │   ├── 14️⃣ Model Management
│   │   └── 13️⃣ Database Records
│   │
│   ├── 🤖 ML & Training
│   │   ├── 1️⃣2️⃣  ML Training
│   │   ├── 1️⃣3️⃣  ML Ranking
│   │   └── 13️⃣ Database Records
│   │
│   └── 🎓 Audit & Compliance
│       └── audit_dashboard.py
│
└── 🔐 User Management
    ├── Authentication & RBAC
    ├── User Roles: Admin, Designer, Viewer
    └── Session Management
```

## Application Tabs/Modules

When inside simulation workflow:

```
Internal Tabs (Accessible from main pages):
├── Home Tab (home.py)
│   └── Dashboard & Overview
├── Design Tab (design.py)
│   └── Design Workspace
├── Protocol Tab (protocol.py)
│   └── Protocol Development
├── Materials Tab (materials.py)
│   └── Materials & Composition
├── Toxicity Tab (toxicity.py)
│   └── Toxicity Assessment
├── Cost Tab (cost.py)
│   └── Cost Analysis
├── Delivery Tab (delivery.py)
│   └── Delivery Strategy
├── Optimization Tab (optimize.py)
│   └── Multi-Objective Optimization
├── Quiz Tab (quiz.py)
│   └── Knowledge Assessment
└── 3D View Tab (view3d.py)
    └── 3D Visualization
```

## Data Flow

```
Login.py
   ↓
Authentication Check
   ├─ Success: Load Session
   └─ Failure: Show Error
   ↓
Disease Selection (0_Disease_Selection.py)
   ↓
Sequential Workflow:
   Features → Design Parameters → Run Simulation → Trial History → Analytics
   ↓
Each Page Access: Internal Tabs (home, design, protocol, materials, toxicity, cost, delivery, optimize, quiz, view3d)
   ↓
Data persisted via:
   - nanobio_studio.db (Main database)
   - trial_registry.db (Trial records)
   - users.db (User management)
   - persistence.py (Session persistence)
```

## User Roles & Access

```
👤 Admin
├── Full Access to All Pages
├── Data Sources Management
├── Model Management
├── User Management
└── Audit Dashboard

👨‍💼 Designer
├── Access to Workflow Pages (0-17)
├── AI Co-Designer Features
├── Tutorial & Documentation
└── View Trial History

👁️  Viewer
├── Read-Only Access
├── View Trial History
├── View Analytics
└── No Edit/Design Permissions
```

## Key Entry Points

| Page | Route | Purpose |
|------|-------|---------|
| **Login.py** | `/` | Authentication & Session Entry |
| **0_Disease_Selection.py** | `/pages/0_Disease_Selection` | Workflow Start |
| **9_AI_Co_Designer.py** | `/pages/9_AI_Co_Designer` | AI Services |
| **10_Tutorial.py** | `/pages/10_Tutorial` | Learning Hub |
| **17_Data_Analytics.py** | `/pages/17_Data_Analytics` | Analytics Dashboard |

## External Dependencies

```
Backend Services:
├── AI Engine (ai_engine/)
├── ToxCast API (live_data_orchestrator.py)
├── Data Downloader (data_downloader.py)
└── Database Layer (models.py, persistence.py)

Frontend:
├── Streamlit UI (pages/, tabs/)
├── Authentication (streamlit_auth.py, auth.py)
└── RBAC System (rbac.py)
```

---

**Last Updated:** March 18, 2026  
**App Type:** Streamlit Multi-Page Application  
**Status:** Production Ready
