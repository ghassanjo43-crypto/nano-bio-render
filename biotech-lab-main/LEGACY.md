# LEGACY — pre-correction snapshot. Do not read the science here.

This directory is a snapshot of the Streamlit application **as it stood before
the Phase 1 corrections**. It is kept for one reason and one reason only, stated
below. It is not the current codebase, and the scientific code in it is
superseded.

## Why it has not been deleted

Two things depend on it, and both would break:

1. **`Login.py` at the repository root adds this directory to `sys.path` at
   runtime** (`sys.path.insert(0, ... / "biotech-lab-main")`). The legacy
   Streamlit entry point does not start without it. `components/ui_components.py`
   re-exports from it for the same reason.

2. **Six files exist only here** and nowhere else in the repository:

   ```
   app.py
   pages/0_Features.py
   pages/0_Login.py
   pages/10_Tutorial.py
   pages/12_ML_Training.py
   pages/9_AI_Co_Designer.py
   ```

Removing the directory is therefore a decision about the legacy Streamlit
application, not a packaging cleanup, and it has not been taken here.

## What is superseded, and how

Of 304 files, 281 are byte-identical to the copy at the repository root. **17
differ, and two of those matter scientifically:**

| File | State in this directory |
|---|---|
| `core/scoring.py` | **Pre-fix.** Lacks the shared null-handling contract (DEFECT-D9): `compute_impact()` and `get_recommendations()` disagree about a key that is present but `None`, so the same design dict is accepted by one and raises `TypeError` in the other. |
| `utils/pk_model.py` | **Pre-fix.** Imports `matplotlib.pyplot` at module scope, so importing the two-compartment solver drags in the whole plotting stack. The equations are the same; the import location is not. |

The remaining differences are in `auth.py`, `streamlit_auth.py`,
`design_persistence.py`, `audit_dashboard.py`, the `modules/` package, the
sidebar component, a backend config file and `.gitignore`.

## Which copy is authoritative

**The repository root.** The corrected `core/scoring.py` and `utils/pk_model.py`
at the root are what the FastAPI backend imports, what the golden vectors were
generated from, and what every test in `tests/` exercises.

Nothing in the Phase 1 Scientific Readiness Framework or the Phase 2
Experimental Validation Registry imports from this directory. If you are reading
scientific code, read the root copy.

## If you are considering deleting it

Retire the legacy Streamlit entry point first — `Login.py`,
`components/ui_components.py` and the six files listed above — and confirm
nothing else path-inserts this directory. Deleting it on its own leaves a
working tree whose legacy application cannot start.
