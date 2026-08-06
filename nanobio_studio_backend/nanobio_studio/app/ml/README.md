# NanoBio Studio™ - Phase 2: ML Preparation Module

## Overview

The ML Preparation Module (Phase 2) extends NanoBio Studio with machine learning capabilities. It provides:

- **Feature Extraction**: Extract 13+ features from LNP formulations
- **Categorical Encoding**: Encode lipid classes, payload types, assay types
- **Numeric Encoding**: Scale and normalize continuous features
- **Training Data Construction**: Build model-ready DataFrames from raw scientific data
- **Data Export**: Export to Parquet (columnar, compressed) and CSV formats
- **Model Training**: Placeholder trainers for particle size, toxicity, and uptake prediction

---

## Architecture

```
app/ml/
├── __init__.py              # Module exports
├── features.py              # Feature extraction service
├── encoders.py              # Categorical and numeric encoding
├── dataframe_builder.py     # Training dataframe construction
├── exporters.py             # Parquet/CSV export utilities
├── trainer.py               # ML model training
└── models/                  # Trained model storage
    ├── particle_size_model.pkl
    ├── particle_size_metadata.json
    ├── toxicity_model.pkl
    └── toxicity_metadata.json
```

---

## Components

### 1. Feature Extractor (`features.py`)

Extracts ML-ready features from LNP formulation records.

**Extracted Features (13+):**
- **Lipid Ratios**: ionizable, helper, sterol, peg (as fractions 0-1)
- **Derived Lipid Features**: ratio variance, ionizable/helper ratio, sterol/peg ratio
- **Physical Properties**: particle size, PDI, zeta potential, encapsulation efficiency
- **Process Parameters**: temperature, buffer pH
- **Target Variables**: toxicity score, uptake score, transfection efficiency

```python
from nanobio_studio.app.ml import FeatureExtractor

extractor = FeatureExtractor()
features = extractor.extract_from_record(lnp_record)
# Returns: ExtractedFeatures with all derived fields

features_list = extractor.extract_batch(lnp_records)
# Batch processing with error handling
```

### 2. Categorical Encoder (`encoders.py`)

Encodes categorical variables for ML models.

**Encoded Categories:**
- **Lipid Classes** (4): ionizable, helper, sterol, peg → 0-3
- **Payload Types** (5): mRNA, siRNA, DNA, protein, small_molecule → 0-4
- **Assay Types** (5): uptake, transfection, toxicity, biodistribution, cytokine_response → 0-4
- **Preparation Methods** (3): microfluidic, manual_mixing, ethanol_injection → 0-2

```python
from nanobio_studio.app.ml import CategoricalEncoder

encoder = CategoricalEncoder()
payload_encoded = encoder.encode_payload_type("mRNA")  # Returns: 0
assay_encoded = encoder.encode_assay_type("uptake")    # Returns: 0
```

### 3. Numeric Encoder (`encoders.py`)

Scales and normalizes continuous features using sklearn.

**Scaling Options:**
- **MinMaxScaler**: Scale to [0, 1] range (default)
- **StandardScaler**: Standardize to mean=0, std=1

```python
from nanobio_studio.app.ml import NumericEncoder

scaler = NumericEncoder(scaler_type="minmax")
scaler.fit(training_data, features=["particle_size_nm", "pdi", "temperature_c"])
scaled_data = scaler.transform(test_data)
```

### 4. Training Dataframe Builder (`dataframe_builder.py`)

Constructs model-ready DataFrames with complete feature engineering pipeline.

```python
from nanobio_studio.app.ml import TrainingDataframeBuilder

builder = TrainingDataframeBuilder(scaler_type="minmax")

# Build from raw records (fit scalers on training data)
df_train = builder.build_from_records(
    training_records,
    fit_scalers=True,  # Fit on training data only
    target_task="particle_size"
)

# Get features and target for specific task
X, y = builder.get_features_for_task("particle_size")
# Returns: (n_samples, 13) features, (n_samples,) targets

# Add test data without refitting
df_test = builder.build_from_records(
    test_records,
    fit_scalers=False  # Use fitted scalers from training
)
```

**DataFrame Properties:**
- Rows: LNP formulations
- Columns: 13 numeric features + ID columns
- Missing values handled (dropout or imputation based on strategy)
- Ready for sklearn/XGBoost/PyTorch

### 5. Data Exporters (`exporters.py`)

Export training DataFrames to optimized formats.

**Parquet Export** (Columnar, Compressed):
```python
from nanobio_studio.app.ml import ParquetExporter

exporter = ParquetExporter(compress="snappy")
exporter.export(df, "dataset.parquet")

# Load back
df_loaded = exporter.read("dataset.parquet")
```

**CSV Export** (Human-Readable):
```python
from nanobio_studio.app.ml import CSVExporter

exporter = CSVExporter()
exporter.export(df, "dataset.csv")
```

**Combined Export** (Both Formats):
```python
from nanobio_studio.app.ml import DatasetExporter

exporter = DatasetExporter()
result = exporter.export_all(df, output_dir="data/ml", dataset_name="training_v1")
# Returns: {"parquet": "...", "csv": "...", "rows": 100, "columns": 13}

# Export train/test split
result = exporter.export_train_test(
    df_train, df_test,
    output_dir="data/ml",
    prefix="lnp_formulations"
)
# Returns split paths for both formats
```

### 6. ML Trainer (`trainer.py`)

Trains predictive models using ensemble methods (Gradient Boosting).

**Prediction Tasks:**
- `particle_size`: Predict particle size (nm)
- `toxicity`: Predict toxicity score (0-1)
- `uptake`: Predict cellular uptake (0-1)

```python
from nanobio_studio.app.ml import MLTrainer

trainer = MLTrainer(model_dir="models")

# Train single model
result = trainer.train(
    records=lnp_records,
    task="particle_size",
    test_size=0.2,
    random_state=42,
    save_model=True
)
# Returns: {
#     "task": "particle_size",
#     "status": "success",
#     "metrics": {
#         "train_r2": 0.87,
#         "test_r2": 0.81,
#         "test_rmse": 12.3,
#         "test_mae": 9.5,
#         "cv_r2_mean": 0.84,
#         "cv_r2_std": 0.03,
#         ...
#     },
#     "top_features": {
#         "particle_size_nm": 0.35,
#         "ionizable_ratio": 0.28,
#         "helper_ratio": 0.15,
#         ...
#     }
# }

# Train all models at once
all_results = trainer.batch_train(lnp_records)

# Make predictions
X_new = df_new[feature_columns]
predictions = trainer.predict("particle_size", X_new)
```

**Model Details:**
- **Algorithm**: Gradient Boosting Regressor
- **n_estimators**: 100 trees
- **learning_rate**: 0.1
- **max_depth**: 5
- **Validation**: 5-fold cross-validation
- **Metrics**: R², RMSE, MAE
- **Feature Importance**: Extracted and ranked

---

## API Endpoints

### Health Check
```
GET /ml/health
```
Check ML module status.

### Dataset Summary
```
GET /ml/summary
```
Get statistics about training dataset:
- Total records
- Complete records (no missing targets)
- Missing values per target
- Feature statistics (mean, std, min, max)
- Encoding information

### Export ML-Ready Data
```
POST /ml/export-ml-ready
?format=parquet&task=particle_size
```
Export complete training dataset in ML-ready format.

### Train Model
```
POST /ml/train-model
{
    "task": "particle_size",
    "test_size": 0.2,
    "random_state": 42
}
```
Train model for specific task. Returns metrics and feature importance.

### Get Models Info
```
GET /ml/models/info
```
Information about available models and their status.

### Extract Features (Single)
```
POST /ml/features/extract
{
    "formulation_id": "FORM-001",
    ...
}
```
Extract features from single record.

### Encode Payload Type
```
POST /ml/encode/payload-type?payload_type=mRNA
```
Encode categorical variable to integer.

### Batch Extract Features
```
POST /ml/batch/extract-features
[
    { record1 },
    { record2 },
    ...
]
```
Extract features from multiple records.

### Build Training Dataset
```
POST /ml/batch/build-dataset
?task=particle_size
[
    { record1 },
    { record2 },
    ...
]
```
Build complete ML-ready dataset from records.

### ML Documentation
```
GET /ml/docs
```
Get comprehensive ML module documentation.

---

## Usage Example

```python
# Complete ML workflow

from nanobio_studio.app.ml import (
    TrainingDataframeBuilder,
    DatasetExporter,
    MLTrainer
)
import pandas as pd
from sklearn.model_selection import train_test_split

# 1. Load experimental records
records = load_from_database()  # 500+ LNP experiments

# 2. Build training dataframe
builder = TrainingDataframeBuilder(scaler_type="minmax")
df = builder.build_from_records(records, fit_scalers=True)

print(f"Dataset shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")

# 3. Export for external analysis
exporter = DatasetExporter()
export_info = exporter.export_all(
    df,
    output_dir="data/ml",
    dataset_name="lnp_v1"
)
print(f"Exported to: {export_info['parquet']}")

# 4. Train models
trainer = MLTrainer(model_dir="models")

for task in ["particle_size", "toxicity", "uptake"]:
    result = trainer.train(records, task=task, test_size=0.2)
    print(f"\n{task} - R²: {result['metrics']['test_r2']:.3f}")
    print(f"Top features: {list(result['top_features'].keys())[:5]}")

# 5. Make predictions on new formulations
X_new = df_new[feature_columns]
particle_size_pred = trainer.predict("particle_size", X_new)
toxicity_pred = trainer.predict("toxicity", X_new)

# 6. Analysis
print(f"Predicted particle size range: {particle_size_pred.min():.1f} - {particle_size_pred.max():.1f} nm")
print(f"Predicted toxicity range: {toxicity_pred.min():.3f} - {toxicity_pred.max():.3f}")
```

---

## Feature Engineering Details

### Lipid Ratio Features
- **Raw**: ionizable_pct, helper_pct, sterol_pct, peg_pct (100% sum)
- **Normalized**: Divide by 100 to get [0, 1] fractions
- **Derived**:
  - `lipid_ratio_variance`: Variance across 4 ratios (measure of balance)
  - `ionizable_helper_ratio`: Ionizable / (Helper + 1e-6)
  - `sterol_peg_ratio`: Sterol / (PEG + 1e-6)

### Physical Properties
- **particle_size_nm**: Direct measurement range 1-1000 nm
- **pdi**: Polydispersity index range 0-1
- **zeta_potential_mv**: Surface charge range -50 to +50 mV
- **encapsulation_efficiency_pct**: Loading success 0-100%

### Process Parameters
- **temperature_c**: Manufacturing temperature
- **buffer_ph**: pH of preparation buffer (0-14)

### Target Variables
- **particle_size_nm**: Numeric regression target
- **toxicity_score**: 0-1 score from assays
- **uptake_score**: 0-1 cellular uptake efficiency

---

## Dependencies

Added to `pyproject.toml`:
- `scikit-learn>=1.3.2` - ML algorithms
- `numpy>=1.26.3` - Numerical operations
- `joblib>=1.3.2` - Model serialization
- `pyarrow>=14.0.0` - Parquet support

---

## Next Steps (Phase 3)

- Deploy trained models to production
- Integrate with Streamlit frontend for real-time predictions
- Add deep learning models (PyTorch)
- Implement model versioning and A/B testing
- Add explainability features (SHAP, LIME)
- Robotic microfluidics integration with ML feedback loop

---

## Notes

- All feature extraction includes error handling and logging
- Training data should have >100 samples for robust models
- Cross-validation (5-fold) prevents overfitting
- Scaler metadata saved for consistent production predictions
- Models saved with metadata for reproducibility and auditing

---

**Module Version**: 0.1.0  
**Phase**: Phase 2 - ML Preparation  
**Status**: Production Ready
