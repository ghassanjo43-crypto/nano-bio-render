# AI Engine Quick Start Guide

## 5-Minute Setup

### 1. Import the Engine

```python
from nanobio_studio.ai_engine import create_engine, get_scenarios

# Create engine with your simulator
engine = create_engine(simulate_fn=my_simulator, log_level="INFO")
```

### 2. Define Design Space

```python
from nanobio_studio.ai_engine.schema import DesignSpace

space = DesignSpace(
    size_nm_min=50,
    size_nm_max=200,
    charge_mV_min=-30,
    charge_mV_max=30,
    materials=["PLGA", "Lipid", "Gold"],
    ligands=["None", "PEG", "Folate"],
    payloads=["DrugA", "DrugB"],
)
```

### 3. Run Optimization

```python
# List available scenarios
scenarios = engine.get_available_scenarios()
for key, scenario in scenarios.items():
    print(f"{key}: {scenario.title}")

# Run with preset scenario
result = engine.run_scenario(
    scenario_key="safety_first",
    design_space=space,
    n_trials=200
)
```

### 4. Get Results

```python
best = result.best

print(f"Best Design:")
print(f"  Size: {best.design.size_nm:.1f} nm")
print(f"  Zeta: {best.design.zeta_mV:.1f} mV")
print(f"  Material: {best.design.material}")
print(f"\nScores:")
print(f"  Efficacy: {best.efficacy:.1f}/100")
print(f"  Toxicity: {best.toxicity:.2f}/100")
print(f"  Cost: {best.cost:.1f}/100")
print(f"  Confidence: {best.confidence:.2f}/1")
print(f"\nTop Drivers: {', '.join(best.drivers[:3])}")
```

### 5. Export Results

```python
# Get Pareto front (non-dominated solutions)
pareto = engine.get_pareto_front(result)
print(f"Pareto front: {len(pareto)} solutions")

# Export to spreadsheet
df = engine.get_dataframe_report(result)
df.to_csv("designs.csv", index=False)

# Generate HTML report
audit_trail = engine.get_audit_trail()
html = engine.get_html_report(audit_trail[0])
with open("report.html", "w") as f:
    f.write(html)
```

## Common Scenarios

### Academic/Educational Use

```python
# Balanced learning without strict constraints
result = engine.run_scenario(
    scenario_key="academic",
    design_space=space,
    n_trials=200
)
```

### Translational Research (Safety-First)

```python
# Prioritize safety for pre-clinical/IND
result = engine.run_scenario(
    scenario_key="safety_first",
    design_space=space,
    n_trials=300
)
# Automatically applies: toxicity_max=55.0
```

### Manufacturing & Scale-Up

```python
# Minimize cost while maintaining safety
result = engine.run_scenario(
    scenario_key="cost_constrained",
    design_space=space,
    n_trials=300
)
# Automatically applies: cost_max=55.0
```

### Early Research (Potency Focus)

```python
# Maximize efficacy, reasonable safety
result = engine.run_scenario(
    scenario_key="efficacy_driven",
    design_space=space,
    n_trials=250
)
# Automatically applies: toxicity_max=70.0 (higher tolerance)
```

## Custom Optimization

### With Custom Weights

```python
from nanobio_studio.ai_engine.schema import ObjectiveWeights

weights = ObjectiveWeights(
    efficacy=0.6,    # 60% - potency
    safety=0.2,      # 20% - safety
    cost=0.2         # 20% - cost
)

result = engine.run_custom(
    design_space=space,
    weights=weights,
    n_trials=250
)
```

### With Constraints

```python
result = engine.run_custom(
    design_space=space,
    weights=weights,
    n_trials=300,
    constraints={
        "toxicity_max": 40.0,   # Strict safety limit
        "cost_max": 60.0        # Cost limit
    }
)
```

## Analysis & Explainability

### Sensitivity Analysis

```python
# Understand what drives the best design
explanation = engine.explain_best(result, design_space=space)

print(f"Metrics: {explanation['metrics']}")
print(f"Key Drivers: {explanation['drivers']}")

# Sensitivity results
for param, impact in explanation['sensitivity']:
    print(f"{param}: {impact:+.2f} impact")
```

### Pareto Front Analysis

```python
pareto = engine.get_pareto_front(result)

print(f"Pareto Front ({len(pareto)} solutions):")
for i, design in enumerate(pareto, 1):
    print(f"{i}. Efficacy={design.efficacy:.1f}, "
          f"Toxicity={design.toxicity:.2f}, "
          f"Cost={design.cost:.1f}")
```

### Top Candidates

```python
print("Top 5 Candidates:")
for i, candidate in enumerate(result.candidates[:5], 1):
    print(f"{i}. {candidate.design.material} - "
          f"Eff={candidate.efficacy:.1f}, "
          f"Tox={candidate.toxicity:.2f}, "
          f"Cost={candidate.cost:.1f}")
```

## DataFrame Operations

### Pivot Analysis

```python
df = engine.get_dataframe_report(result)

# Group by material
by_material = df.groupby("Material").agg({
    "Efficacy": "mean",
    "Toxicity (0-100)": "mean",
    "Cost (0-100)": "mean"
})
print(by_material)

# Sort by efficacy
top_efficacy = df.nlargest(10, "Efficacy")
print(top_efficacy[["Rank", "Material", "Efficacy", "Toxicity (0-100)"]])
```

### Statistical Summary

```python
stats = df[["Efficacy", "Toxicity (0-100)", "Cost (0-100)"]].describe()
print(stats)

# Correlation
corr = df[["Size (nm)", "Zeta (mV)", "Efficacy"]].corr()
print(corr)
```

## Integration with Streamlit

```python
import streamlit as st
from nanobio_studio.ai_engine import create_engine, get_scenarios

st.set_page_config(page_title="NanoBio Optimizer", layout="wide")

# Sidebar: Configuration
st.sidebar.header("⚙️ Configuration")

scenarios = get_scenarios()
scenario_key = st.sidebar.selectbox(
    "Select Scenario",
    list(scenarios.keys())
)

n_trials = st.sidebar.slider("Number of Trials", 50, 500, 200)

# Main: Run optimization
st.header("🤖 AI Optimizer")

if st.button("▶️ Run Optimization", key="run_opt"):
    with st.spinner("Optimizing..."):
        engine = create_engine(simulate_fn=my_simulator)
        result = engine.run_scenario(
            scenario_key=scenario_key,
            design_space=design_space,
            n_trials=n_trials
        )
    
    # Display results
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Efficacy", f"{result.best.efficacy:.1f}")
    col2.metric("Toxicity", f"{result.best.toxicity:.2f}")
    col3.metric("Cost", f"{result.best.cost:.1f}")
    col4.metric("Confidence", f"{result.best.confidence:.2f}")
    
    st.subheader("Results Table")
    df = engine.get_dataframe_report(result)
    st.dataframe(df, use_container_width=True)
    
    # Export
    st.download_button(
        "Download CSV",
        df.to_csv(index=False),
        "designs.csv"
    )
```

## Troubleshooting

### "No valid candidates found"

**Cause**: Constraints too strict or simulator returning errors

**Solution**:
```python
# Relax constraints
constraints = {
    "toxicity_max": 60.0,  # Increase from 40 to 60
    "cost_max": 70.0       # Increase from 50 to 70
}

# Or remove constraints
result = engine.run_custom(
    design_space=space,
    weights=weights,
    n_trials=300
    # No constraints
)
```

### "Reproducibility issues"

**Solution**: Always set seed
```python
config = EngineConfig(seed=42)
engine = AIEngine(simulate_fn, config)
```

### "Slow optimization"

**Cause**: Expensive simulator

**Solution**: Start with placeholder
```python
# Fast iteration with placeholder
result = engine.run_scenario(..., n_trials=200)

# Then switch to real simulator when ready
```

### "Memory errors"

**Solution**: Reduce trials or batch process
```python
# Reduce in single run
result = engine.run_scenario(..., n_trials=100)

# Or batch multiple smaller runs
for i in range(3):
    result = engine.run_scenario(..., n_trials=100)
```

## Advanced Configuration

```python
from nanobio_studio.ai_engine.engine import EngineConfig, AIEngine

config = EngineConfig(
    log_level="DEBUG",          # Verbose logging
    enable_audit=True,          # Generate audit trail
    enable_sensitivity=True,    # Sensitivity analysis
    seed=42,                    # Reproducibility
    default_n_trials=250,       # Default trials
    max_n_trials=1000          # Upper limit
)

engine = AIEngine(
    simulate_fn=my_simulator,
    config=config
)
```

## Performance Tips

1. **Fast prototyping** (trial-and-error):
   - Use placeholder simulator
   - Start with 50-100 trials
   - Use "academic" scenario (no constraints)

2. **Production runs**:
   - Use real simulator
   - Use 200-400 trials
   - Use appropriate scenario
   - Enable audit trail

3. **Regulatory submissions**:
   - Use "regulatory_compliant" scenario
   - Use 400+ trials
   - Generate HTML report
   - Keep JSON audit record

## Examples Repository

See also:
- `examples/optimize_basic.py` - Basic optimization
- `examples/optimize_scenarios.py` - All scenarios
- `examples/optimize_custom.py` - Custom weights
- `examples/optimize_with_constraints.py` - Constraint usage

---

**Questions?** See [API_REFERENCE.md](API_REFERENCE.md) for detailed documentation.
