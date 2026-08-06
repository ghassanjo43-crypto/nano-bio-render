# NanoBio Studio™ — Backend Foundation Layer

**Production-Ready Backend for AI Nanomedicine Platform**

Developed by **Experts Group FZE**

---

## 📋 Overview

NanoBio Studio™ Backend is the scientific data foundation layer for an advanced AI-driven nanomedicine platform. This backend provides:

- **Universal LNP Data Schema**: Pydantic-based schemas for all lipid nanoparticle (LNP) experiment data
- **Production Database Layer**: PostgreSQL with SQLAlchemy ORM for robust data persistence  
- **Smart Data Ingestion**: JSON and CSV importers with automatic validation and normalization
- **Comprehensive QC Engine**: Built-in validation rules for scientific quality assurance
- **REST API**: FastAPI-based API for integration with AI models, frontends, and robotic systems
- **Future-Ready Architecture**: Modular design supporting AI model training, simulation, and digital twins

This phase focuses on **clean, scalable backend architecture** rather than UI. The system can ingest experiment records, validate them against scientific constraints, and provide queryable storage for downstream AI training and analysis.

---

## 🏗️ Architecture

### Folder Structure

```
nanobio_studio_backend/
├── nanobio_studio/
│   ├── app/
│   │   ├── core/              # Configuration and logging
│   │   ├── db/                # Database session and models
│   │   ├── schemas/           # Pydantic models
│   │   ├── services/          # Business logic
│   │   ├── repositories/      # Data access layer
│   │   ├── api/               # FastAPI routes
│   │   ├── ingestion/         # JSON/CSV importers
│   │   ├── qc/                # Validation rules
│   │   ├── ml/                # 🆕 Phase 2: ML preparation modules
│   │   └── utils/             # Helper functions
│   └── main.py                # Main FastAPI app
├── alembic/                   # Database migrations
├── tests/                     # Unit and integration tests
├── data/                      # Sample data files
├── .env.example              # Environment template
├── pyproject.toml            # Python project metadata
└── README.md                 # This file
```

---

## 🆕 Phase 2: Machine Learning Preparation (NEW!)

NanoBio Studio now includes **ML-ready data preparation modules** for training predictive models:

### ML Capabilities
- **Feature Extraction**: Extract 13+ ML features from LNP formulations (ratios, physical properties, derived metrics)
- **Categorical Encoding**: Encode lipid classes, payload types, assay types, preparation methods
- **Numeric Scaling**: MinMax or Standard scaling for continuous features
- **Training Data Construction**: Build model-ready DataFrames with complete pipeline
- **Data Export**: Export to Parquet (fast, compressed) or CSV (human-readable)
- **Model Training**: Train Gradient Boosting models for:
  - Particle size prediction
  - Toxicity prediction
  - Cellular uptake prediction

### New API Endpoints (12 endpoints)
```
GET  /ml/health                      # Module health check
GET  /ml/summary                     # Dataset statistics
POST /ml/export-ml-ready             # Export ML-ready data
POST /ml/train-model                 # Train prediction model
GET  /ml/models/info                 # Model information
POST /ml/features/extract            # Extract features
POST /ml/batch/extract-features      # Batch feature extraction
POST /ml/batch/build-dataset         # Build training dataset
```

### Quick ML Workflow
```python
from nanobio_studio.app.ml import TrainingDataframeBuilder, MLTrainer

# 1. Build training dataset
builder = TrainingDataframeBuilder(scaler_type="minmax")
df = builder.build_from_records(lnp_records, fit_scalers=True)

# 2. Train models
trainer = MLTrainer()
result = trainer.train(lnp_records, task="particle_size")
print(f"Model R²: {result['metrics']['test_r2']:.3f}")

# 3. Make predictions
predictions = trainer.predict("particle_size", X_new)
```

See [PHASE2_ML_IMPLEMENTATION.md](PHASE2_ML_IMPLEMENTATION.md) for complete ML documentation.

---

## 📦 Tech Stack

- **Python 3.11+** — Modern Python with type hints
- **PostgreSQL** — Robust relational database
- **SQLAlchemy 2.x** — ORM with async support
- **Pydantic v2** — Data validation and serialization
- **FastAPI** — High-performance async API framework
- **scikit-learn** — Machine learning algorithms (NEW in Phase 2)
- **pandas** — Data manipulation and ML prep
- **Alembic** — Database schema migrations
- **pytest** — Comprehensive testing framework
- **loguru** — Structured logging

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 13+ (or Docker PostgreSQL)
- Git

### 2. Installation

Clone the repository:

```bash
git clone <repository-url>
cd nanobio_studio_backend
```

Create a Python virtual environment:

```bash
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux/macOS:
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -e ".[dev]"
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and configure your PostgreSQL connection:

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/nanobio_studio
API_TITLE=NanoBio Studio Backend API
DEBUG=True
LOG_LEVEL=INFO
```

### 4. Database Setup

Initialize the database (creates tables):

```bash
# Using Python directly
python -c "from nanobio_studio.app.db.session import init_db;  \
           import asyncio; asyncio.run(init_db())"
```

Or with Alembic:

```bash
alembic upgrade head
```

### 5. Load Sample Data

Import sample LNP records:

```bash
python -c "
from nanobio_studio.app.ingestion.json_importer import JSONImporter
importer = JSONImporter()
records = importer.import_file('data/sample_lnp_records.json')
print(f'Imported {len(records)} records')
"
```

### 6. Start the API

Run the FastAPI development server:

```bash
uvicorn nanobio_studio.app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at:

- **API**: http://localhost:8000
- **Docs (Swagger UI)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 📚 Domain Model

### Core Entities

The system models the complete LNP experimental workflow:

```
Lipids (4 classes) → Formulation → Process Conditions → Characterization
                           ↓
                       Payload
                           ↓
                    Biological Model
                           ↓
                        Assays → Experiment
```

#### Lipids

Four classes of lipids compose formulations:

- **Ionizable**: Reversible charge for delivery (e.g., SM-102)
- **Helper**: Structural support (e.g., DSPC)
- **Sterol**: Rigidity and membrane interactions (e.g., Cholesterol)
- **PEG**: Pegylation for stability (e.g., DMG-PEG2000)

#### Payloads

Therapeutic agents delivered:

- mRNA (e.g., vaccines)
- siRNA (gene knockdown)
- DNA (gene therapy)
- Protein (direct delivery)
- Small molecules (drugs)

#### Formulations

Defined by lipid ratios and payload:

```python
{
    "ionizable_percent": 50.0,
    "helper_percent": 10.0,
    "sterol_percent": 38.5,
    "peg_percent": 1.5
    # Must sum to 100%
}
```

#### Process Conditions

Manufacturing parameters:

- Method: microfluidic, manual_mixing, ethanol_injection
- Flow rates, buffer pH, temperature, etc.

#### Characterization

Physical properties:

- Particle size (nm)
- PDI (polydispersity index)
- Zeta potential (mV)
- Encapsulation efficiency (%)
- Stability (hours)

#### Biological Models

Test systems:

- Cell lines (HepG2, RAW264.7, etc.)
- Organoids
- Animal models (mouse, rat, etc.)

#### Assays

Experimental readouts:

- Uptake
- Transfection efficiency
- Toxicity
- Biodistribution
- Cytokine response

---

## 📤 Data Import

### JSON Import

Import complete nested LNP records from JSON:

```bash
POST /ingestion/json-upload

# Include JSON file with:
# {
#   "experiment": {...},
#   "formulation": {...},
#   "process_conditions": {...},
#   "characterization": {...},
#   "biological_model": {...},
#   "assays": [...],
#   "qc_status": "pass"
# }
```

### CSV Import

Import flattened records from CSV:

```bash
POST /ingestion/csv-upload

# Column naming convention:
# exp_experiment_id, lipid_ionizable_name, ratio_ionizable,
# payload_type, process_method, char_particle_size_nm, etc.
```

### Example Import with Python

```python
from nanobio_studio.app.ingestion.json_importer import JSONImporter

importer = JSONImporter()
records = importer.import_file("data/my_records.json")

for record in records:
    if record["qc_status"] == "pass":
        print(f"✓ {record['original']['experiment']['experiment_name']}")
    else:
        print(f"✗ Validation errors: {record.get('validation_error')}")
```

---

## ✅ QC Validation

The QC engine automatically validates:

1. **Lipid Ratios Sum** — Must total 100% ± 0.1% tolerance
2. **Required Lipid Classes** — All four classes (ionizable, helper, sterol, peg) present
3. **Particle Size Range** — Between 1-1000 nm (typical)
4. **PDI Validity** — Between 0 and 1
5. **Encapsulation Efficiency** — Between 0 and 100%
6. **pH Range** — Between 0 and 14
7. **Temperature** — Between -273°C and 500°C (physically sensible)
8. **Assay Data Completeness** — Required fields populated

### Custom QC

Add custom rules by subclassing `QCRule`:

```python
from nanobio_studio.app.qc.validators import QCRule

class CustomRule(QCRule):
    def __init__(self):
        super().__init__("My custom rule", "warning")
    
    def check(self, record):
        # Your validation logic
        return (passed: bool, message: str)
```

---

## 🔌 API Endpoints

### Health

```
GET  /health              # System status
GET  /ready               # Readiness check
```

### Ingestion

```
POST /ingestion/json-upload    # Import JSON file
POST /ingestion/csv-upload     # Import CSV file
```

### Query

```
GET  /query/summary             # Database statistics
GET  /query/lipids              # List all lipids
GET  /query/formulations        # List all formulations
GET  /query/formulation/{id}    # Get formulation detail
```

### Example Requests

```bash
# Health check
curl http://localhost:8000/health

# Get summary stats
curl http://localhost:8000/query/summary

# Get all lipids
curl http://localhost:8000/query/lipids

# Get formulation detail
curl http://localhost:8000/query/formulation/1
```

---

## 🧪 Testing

Run the test suite:

```bash
pytest tests/

# With coverage report
pytest tests/ --cov=nanobio_studio --cov-report=html

# Run specific test file
pytest tests/test_schemas.py -v

# Run specific test
pytest tests/test_schemas.py::TestSchemaValidation::test_valid_lnp_record -v
```

### Test Files

- `test_schemas.py` — Pydantic schema validation
- `test_qc.py` — QC rule validation
- `test_importers.py` — JSON/CSV import functionality
- `test_api.py` — API endpoint tests

---

## 🗄️ Database Migrations

### Creating Migrations

Auto-generate migration from model changes:

```bash
alembic revision --autogenerate -m "Add new field to Formulation"
```

### Running Migrations

Upgrade to latest version:

```bash
alembic upgrade head
```

Downgrade one step:

```bash
alembic downgrade -1
```

View migration history:

```bash
alembic history
```

---

## 📝 Logging

Configure logging in `.env`:

```env
LOG_LEVEL=INFO    # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

Logs are written to:

- **Console**: Colored output
- **Files**: `logs/nanobio_studio_YYYY-MM-DD.log`

### Using Logger in Code

```python
from nanobio_studio.app.core.logging import get_logger

log = get_logger("module_name")
log.info("Information message")
log.warning("Warning message")
log.error("Error message")
```

---

## 🔒 Security Considerations

### Current State (Development)

- No authentication/authorization yet
- CORS allows all origins (for development)
- Debug mode enabled by default

### Production Deployment

Before deploying to production:

1. **Enable Authentication** — Add JWT or OAuth2
2. **Restrict CORS** — Specify allowed origins only
3. **Database Security** — Use parametrized queries (SQLAlchemy does this)
4. **Environment Variables** — Never hardcode secrets in code
5. **HTTPS/TLS** — Use reverse proxy (nginx, Apache)
6. **Rate Limiting** — Add rate limit middleware
7. **Input Validation** — Already provided by Pydantic
8. **Audit Logging** — Log all data modifications

Example production settings:

```env
DEBUG=False
ENVIRONMENT=production
CORS_ORIGINS=["https://yourdomain.com"]
SECRET_KEY=<generate-strong-random-key>
DATABASE_URL=postgresql+psycopg://prod_user:secure_pass@prod_db:5432/nanobio
```

---

## 📖 Development

### Code Style

Uses `black`, `ruff`, and `mypy`:

```bash
# Format code
black nanobio_studio/ tests/

# Lint
ruff check nanobio_studio/ tests/

# Type checking
mypy nanobio_studio/
```

### Project Standard

- Type hints everywhere
- Docstrings for all modules, classes, functions
- Clear separation of concerns
- No "clever" code — prioritize readability
- Comprehensive error handling

---

## 🐛 Troubleshooting

### Database Connection Error

```
Error: could not connect to server
```

**Solution**: Ensure PostgreSQL is running and connection string is correct:

```bash
# Test PostgreSQL connection
psql postgresql://user:password@localhost:5432/nanobio_studio

# Verify in .env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/nanobio_studio
```

### Import Errors

```
ModuleNotFoundError: No module named 'nanobio_studio'
```

**Solution**: Install package in development mode:

```bash
pip install -e .
```

### Validation Errors on Import

```
ValidationError: 1 validation error...
```

**Solution**: Check JSON schema matches LNPRecord structure. Use `/docs` to see expected format.

---

## 🔮 Future Roadmap

Phase 2:

- [ ] AI model integration (scikit-learn, PyTorch)
- [ ] Advanced querying (filters, pagination)
- [ ] Authentication and authorization (JWT)
- [ ] Batch processing for large datasets
- [ ] Performance optimization and caching

Phase 3:

- [ ] LIBRIS robotic microfluidics integration
- [ ] PK/PD simulation engine
- [ ] Digital twin simulation
- [ ] Advanced analytics dashboard
- [ ] Multi-user collaboration features

---

## 📞 Support & Issues

For bugs, feature requests, or questions:

- **Email**: info@expertsgroup.me
- **Documentation**: (Coming soon)
- **Issue Tracker**: GitHub Issues

---

## 📄 License

**Proprietary — Experts Group FZE**

Unauthorized use, reproduction, or distribution is prohibited.

---

## 🤝 Contributing

Internal contributors: Please follow the code standards and testing requirements in `CONTRIBUTING.md` (coming soon).

---

---

**NanoBio Studio™** — Advancing Nanomedicine with AI

*Experts Group FZE © 2026 · All Rights Reserved*
