# AI Engine Module Documentation

## Overview

The **NanoBio Studio AI Engine** is a comprehensive framework for multi-objective nanoparticle design optimization. It provides:

- **Multi-objective Optimization**: Pareto-optimal design discovery
- **Scenario-Based Workflows**: Pre-configured use cases (academic, safety-first, cost-constrained, etc.)
- **Explainability & Analysis**: Sensitivity analysis, toxicity drivers, confidence scoring
- **Audit Trail**: Complete decision tracking for regulatory compliance
- **Reporting**: JSON audit records and HTML reports

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AIEngine Orchestrator                   │
│              (engine.py) - unified interface                │
└──────────────┬──────────────────────────────────────────────┘
               │
     ┌─────────┼──────────┬──────────────┐
     │         │          │              │
     v         v          v              v
┌─────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
│Optimizer│ │Scenario│ │Explainable│ │ Audit & │
│(optuna) │ │Presets │ │Analysis │ │Reporting│
└─────────┘ └────────┘ └─────────┘ └──────────┘
     │         │          │              │
     └─────────┼──────────┬──────────────┘
               │
     ┌─────────┴────────────────────┐
     │                              │
     v                              v
┌──────────────┐           ┌────────────────┐
│Scoring System│           │Simulator Adapter│
│- Efficacy    │           │(pluggable)      │
│- Toxicity    │           └────────────────┘
│- Cost        │
└──────────────┘
```

## Module Structure

### Core Modules

#### 1. **engine.py** - Orchestrator
Main entry point providing a unified interface for optimization workflows.

**Key Classes:**
- `AIEngine`: Main orchestrator class
- `EngineConfig`: Configuration options

**Key Methods:**
- `run_scenario()`: Run pre-configured scenario
- `run_custom()`: Run custom optimization
- `get_pareto_front()`: Extract Pareto-optimal solutions
- `explain_best()`: Generate explainability analysis
- `get_dataframe_report()`: Export to pandas DataFrame
- `get_html_report()`: Generate audit HTML report

**Usage:**
```python
from nanobio_studio.ai_engine import AIEngine, create_engine

# Create engine
engine = create_engine(simulate_fn=my_simulator, log_level="INFO")

# Get available scenarios
scenarios = engine.get_available_scenarios()

# Run optimization
result = engine.run_scenario(
    scenario_key="safety_first",
    design_space=my_space,
    n_trials=300,
    project_id="proj-001"
)

# Get results
best = result.best
pareto = engine.get_pareto_front(result)
explanation = engine.explain_best(result)
```

#### 2. **optimizer.py** - Multi-Objective Optimization
Core Optuna-based optimization with constraint support.

**Key Classes:**
- `OptimizationResult`: Container for optimization results

**Key Functions:**
- `run_optimization()`: Main optimization function

**Features:**
- Pareto-optimal search via Optuna TPE sampler
- Constraint enforcement (toxicity_max, cost_max)
- Hard PDI constraint (0.35)
- Trial-level audit attributes
- Top-K result selection

**Parameters:**
- `space`: Design space configuration
- `weights`: Multi-objective weights
- `n_trials`: Number of iterations
- `seed`: Random seed for reproducibility
- `simulate_fn`: Simulator function
- `constraints`: Optional constraint dictionary

#### 3. **scenarios.py** - Pre-Configured Workflows
Scenario presets for common use cases.

**Key Classes:**
- `ScenarioPreset`: Scenario configuration

**Key Functions:**
- `get_scenarios()`: Get all scenarios
- `get_scenario()`: Get specific scenario
- `list_scenario_keys()`: List available keys
- `validate_scenario()`: Validate configuration

**Available Scenarios:**
1. **academic** - Balanced learning (education/research)
2. **safety_first** - Prioritize safety (translational)
3. **cost_constrained** - Minimize cost (manufacturing)
4. **efficacy_driven** - Maximize efficacy (early research)
5. **balanced** - General purpose
6. **regulatory_compliant** - Strict regulatory standards

### Scoring & Evaluation

#### 4. **objectives.py** - Efficacy Scoring
Computes efficacy from simulation results.

```python
from nanobio_studio.ai_engine import efficacy_proxy, scalarized_score

efficacy = efficacy_proxy(sim_result)
score = scalarized_score(efficacy, toxicity, cost, w_eff, w_safe, w_cost)
```

#### 5. **toxicity.py** - Toxicity Assessment
Hybrid toxicity scoring with driver analysis.

```python
from nanobio_studio.ai_engine import toxicity_score_hybrid

toxicity_score, drivers = toxicity_score_hybrid(design, sim_result)
# drivers: list of risk factors (e.g., "Small size (<50nm)", "High dose")
```

#### 6. **cost.py** - Cost Estimation
Proxy cost/complexity modeling.

```python
from nanobio_studio.ai_engine import cost_score_proxy

cost = cost_score_proxy(design)  # 0-100 scale
```

#### 7. **uncertainty.py** - Confidence Scoring
Simple confidence heuristic (placeholder for ML model).

```python
from nanobio_studio.ai_engine import simple_confidence_from_rules

confidence = simple_confidence_from_rules(toxicity, cost)  # 0-1 scale
```

### Analysis & Explainability

#### 8. **explainability.py** - Sensitivity Analysis
One-at-a-time parameter sensitivity with impact quantification.

```python
from nanobio_studio.ai_engine import explain_design, SensitivityResult

metrics, drivers, sensitivity = explain_design(
    design=best_design,
    weights=weights,
    simulate_fn=simulator,
    space=design_space
)

# sensitivity: List[SensitivityResult]
# - param: parameter name
# - direction: "+" or "-"
# - delta: perturbation size
# - score_change: impact on objective
```

#### 9. **pareto.py** - Pareto Optimization
Dominance analysis and Pareto front extraction.

```python
from nanobio_studio.ai_engine import pareto_front, is_dominated

# Get non-dominated solutions
front = pareto_front(all_candidates)

# Check individual dominance
if is_dominated(candidate_a, candidate_b):
    print("B dominates A")
```

### Reporting & Audit

#### 10. **reporting.py** - Data Reporting
Export results to pandas DataFrame.

```python
from nanobio_studio.ai_engine import candidates_to_df

df = candidates_to_df(result.candidates)
# Columns: Rank, Size, Zeta, Material, Ligand, Payload, Dose, PDI,
#          Efficacy, Toxicity, Cost, Confidence, Top Drivers
```

#### 11. **audit.py** - Audit Trail & Compliance
Complete decision tracking for regulatory compliance.

```python
from nanobio_studio.ai_engine import (
    build_audit_record, record_outcome,
    audit_to_json, audit_to_html
)

# Create audit
audit = build_audit_record(
    scenario_name="Safety-First",
    scenario_key="safety_first",
    space=design_space,
    weights=weights,
    constraints=constraints,
    run_settings=settings
)

# Record outcome
audit = record_outcome(audit, result)

# Export
json_str = audit_to_json(audit)
html_str = audit_to_html(audit)  # Printable report
```

### Simulation Integration

#### 12. **simulator_adapter.py** - Pluggable Simulator
Adapter interface for your simulator.

```python
from nanobio_studio.ai_engine import SimulateFn, simulate_design_placeholder

# Define your simulator
def my_simulator(design: NanoDesign) -> SimulationResult:
    # Run your PK/PD model
    auc = calculate_auc(design)
    cmax = calculate_cmax(design)
    return SimulationResult(auc_target=auc, cmax_target=cmax, ...)

# Pass to engine
engine = AIEngine(simulate_fn=my_simulator)
```

## Usage Examples

### Example 1: Basic Optimization with Scenario

```python
from nanobio_studio.ai_engine import AIEngine, create_engine
from nanobio_studio.ai_engine.schema import DesignSpace, ObjectiveWeights

# 1. Create engine
engine = create_engine(simulate_fn=my_simulator)

# 2. Define design space
space = DesignSpace(
    size_nm_min=50,
    size_nm_max=200,
    charge_mV_min=-30,
    charge_mV_max=30,
    materials=["PLGA", "Lipid", "Gold"],
    ligands=["None", "PEG", "Folate"],
    payloads=["DrugA", "DrugB"],
)

# 3. Run scenario
result = engine.run_scenario(
    scenario_key="safety_first",
    design_space=space,
    n_trials=300,
    project_id="proj-001",
    user_id="user-001"
)

# 4. Get results
print(f"Best design: {result.best.design}")
print(f"Efficacy: {result.best.efficacy:.1f}")
print(f"Toxicity: {result.best.toxicity:.2f}")
print(f"Cost: {result.best.cost:.1f}")

# 5. Extract Pareto front
pareto = engine.get_pareto_front(result)
print(f"Pareto front: {len(pareto)} solutions")

# 6. Get explanation
explanation = engine.explain_best(result, design_space=space)
print(f"Top drivers: {explanation['drivers']}")

# 7. Export report
audit_trail = engine.get_audit_trail()
html_report = engine.get_html_report(audit_trail[0])
with open("report.html", "w") as f:
    f.write(html_report)
```

### Example 2: Custom Weights

```python
from nanobio_studio.ai_engine import AIEngine
from nanobio_studio.ai_engine.schema import ObjectiveWeights

engine = create_engine(simulate_fn=my_simulator)

# Custom weights
weights = ObjectiveWeights(
    efficacy=0.6,  # Emphasize potency
    safety=0.2,
    cost=0.2
)

result = engine.run_custom(
    design_space=space,
    weights=weights,
    n_trials=250
)
```

### Example 3: With Constraints

```python
# Run with hard constraints
result = engine.run_custom(
    design_space=space,
    weights=weights,
    n_trials=300,
    constraints={
        "toxicity_max": 40.0,  # Strict safety
        "cost_max": 50.0       # Cost limit
    }
)
```

## Data Types

### NanoDesign
```python
@dataclass
class NanoDesign:
    size_nm: float              # Particle size (nm)
    zeta_mV: float              # Surface charge (mV)
    material: str               # Material type
    ligand: str                 # Surface ligand
    payload: str                # Encapsulated drug
    dose_mg_per_kg: float       # Administered dose
    pdi: float = 0.2            # Polydispersity index
    extra: Dict[str, Any] = {}  # Additional parameters
```

### ScoredCandidate
```python
@dataclass
class ScoredCandidate:
    design: NanoDesign
    sim: SimulationResult
    efficacy: float             # Efficacy score (0-100)
    toxicity: float             # Toxicity score (0-100)
    cost: float                 # Cost score (0-100)
    confidence: float           # Confidence (0-1)
    drivers: List[str]          # Risk/benefit drivers
```

## Best Practices

1. **Scenario Selection**
   - Use "safety_first" for translational programs
   - Use "cost_constrained" for manufacturing
   - Use "efficacy_driven" for early research

2. **Trial Count**
   - Start with 200 trials (quick iteration)
   - Increase to 300-400 for production
   - Balance between quality and computational cost

3. **Simulator Integration**
   - Start with placeholder, replace gradually
   - Keep simulator function pure (no side effects)
   - Cache expensive calculations

4. **Result Interpretation**
   - Review Pareto front for trade-off understanding
   - Check sensitivity analysis for robustness
   - Validate top drivers against domain knowledge

5. **Compliance & Reporting**
   - Always generate audit trail for regulatory submissions
   - Export HTML report for stakeholder review
   - Keep JSON audit for detailed record keeping

## Configuration

```python
from nanobio_studio.ai_engine.engine import EngineConfig

config = EngineConfig(
    log_level="DEBUG",           # Verbose logging
    enable_audit=True,           # Generate audit trail
    enable_sensitivity=True,     # Sensitivity analysis
    seed=42,                     # Reproducibility
    default_n_trials=250,        # Default trial count
    max_n_trials=1000           # Upper limit
)

engine = AIEngine(simulate_fn=my_simulator, config=config)
```

## Performance

- **Optimization Speed**: ~0.5-1s per trial (with placeholder simulator)
- **Memory**: ~50-100MB for 300 trials
- **Scaling**: Linear with trial count

Optimize for speed early, add expensive simulators later.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No valid candidates" | Check simulator for errors, relax constraints |
| "Empty Pareto front" | Ensure weights sum to ~1.0, increase trials |
| "Slow optimization" | Profile simulator, use placeholder for testing |
| "Reproducibility issues" | Set `seed` parameter explicitly |
| "Memory errors" | Reduce `n_trials` or batch process |

## Further Integration

To integrate with your Streamlit app:

```python
# In tabs/optimize.py
from nanobio_studio.ai_engine import create_engine

st.subheader("🤖 AI Optimization with Scenarios")

engine = create_engine(simulate_fn=my_simulator, log_level="INFO")
scenarios = engine.get_available_scenarios()

scenario_key = st.selectbox(
    "Select Scenario",
    list(scenarios.keys())
)

result = engine.run_scenario(
    scenario_key=scenario_key,
    design_space=my_space,
    n_trials=st.slider("Trials", 50, 500, 200)
)

st.write(f"Best Design: {result.best.design}")
```

---

**Documentation Version**: 1.0  
**Last Updated**: January 15, 2026
