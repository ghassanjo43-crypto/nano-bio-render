# PK-B1 — IV trastuzumab: Phase 1 evidence assessment

**Status: assessment only. No parameter set has been added and no scientific
code has been modified. IV trastuzumab remains blocked.**

Date: 2026-08-02. Assessed by: automated evidence review, pending human
scientific review before any implementation.

---

## 1. Recommended published model

**Quartino AL, Li H, Kirschbrown WP, et al. "Population pharmacokinetic and
covariate analyses of intravenous trastuzumab (Herceptin®), a HER2-targeted
monoclonal antibody, in patients with a variety of solid tumors."**
*Cancer Chemotherapy and Pharmacology* 2018;83(2):329–340.
doi:10.1007/s00280-018-3728-z

### Why this one

| Criterion | Quartino 2018 (recommended) | Quartino 2015 (HannaH) |
|---|---|---|
| Route | **Intravenous only** | SC + IV pooled |
| n | **1,582 patients, 18 trials, 26,040 samples** | 595 patients, 1 trial |
| Indications | MBC 810, EBC 391, AGC 274, other 107, HV 6 | EBC only |
| Purpose | Characterise IV disposition | Support SC manual-syringe comparison |

The task is IV trastuzumab. The 2018 analysis is IV-only, an order of magnitude
larger, and spans the indications this platform offers. The 2015 HannaH model
pooled subcutaneous and intravenous data to support a subcutaneous formulation
comparison; its bioavailability and absorption terms are irrelevant to an IV
route, and its population is a single early-breast-cancer trial.

**Both models were considered and one was chosen. No value is taken from the
other.** Per requirement 4, parameters are never mixed across studies — the
alternative set is recorded in §9 for completeness only.

---

## 2. Formulation, route, population, indication, regimen

| Field | Value |
|---|---|
| Therapeutic | Trastuzumab |
| Product | Herceptin® (innovator). *"no patients received biosimilars"* |
| Formulation | Intravenous solution |
| Route | Intravenous infusion |
| Population | 1,582 patients across 18 phase I–III trials |
| Indications | Metastatic breast cancer (810), early breast cancer (391), advanced gastric cancer (274), other solid tumours (107), healthy volunteers (6) |
| Regimen (label) | 8 mg/kg loading then 6 mg/kg q3w; or 4 mg/kg loading then 2 mg/kg weekly |
| Software | NONMEM 7.2, FOCE with interaction |

---

## 3. Complete parameter table

All values from Table of the 2018 paper. RSE% as published.

| Parameter | Estimate | Unit | RSE% | Dimension |
|---|---|---|---|---|
| Linear CL | **0.127** | L/day | 2.36 | volume/time |
| Vc (non-AGC) | **2.62** | L | 0.79 | volume |
| Vc (AGC) | **3.63** | L | 1.94 | volume |
| Q | **0.544** | L/day | 3.38 | volume/time |
| Vp | **2.97** | L | 1.81 | volume |
| Vmax | **8.81** | mg/day | 1.44 | mass/time |
| Km | **8.92** | mg/L | 8.61 | mass/volume |

### Interindividual variability

| Parameter | IIV (%) |
|---|---|
| CL | 40.1 |
| Vc | 24.6 |
| Vp | 49.5 |
| Km | **139** — authors attribute this to *"limited data available at low concentrations around Km"* |

### Residual error

Combined: proportional **19.7%** + additive **1.38 µg/mL**.

### Covariate model

Reference values: body weight 66 kg, SGOT/AST 24 IU/L, albumin 4 g/dL.

Linear CL depends on: **baseline body weight, AST, albumin, gastric cancer,
liver metastases**. Vc depends on **tumour type** (AGC vs non-AGC).

> `CLi = θ1·(TTYPE==MBC|EBC|HV) + θ9·(TTYPE==AGC) + θ8·(TTYPE==Others) ·`
> `(Wt/66)^θ7 · (SGOT/24)^θ10 · (ALBU/4)^θ11 · e^(θ12·LMET=Y) · e^ηCL`
>
> `Vci = [θ2·(TTYPE==Non-AGC) + θ13·(TTYPE==AGC)] · e^ηVc`

**The individual θ indices are not resolvable from the retrieved text.**
Implementing the covariate model requires the full parameter table from the
publication itself. Until then, only the typical-value (reference-covariate)
parameters above are usable, and only for population-level simulation.

---

## 4. Model equations

Two-compartment, **parallel linear and Michaelis–Menten elimination from the
central compartment**, IV input:

```
C  = A_c / Vc

dA_c/dt = R_input
          − (CL/Vc)·A_c                  ← linear elimination
          − Vmax·C/(Km + C)              ← saturable (target-mediated)
          − (Q/Vc)·A_c + (Q/Vp)·A_p      ← distribution

dA_p/dt =   (Q/Vc)·A_c − (Q/Vp)·A_p
```

where `R_input = Dose/T_inf` during the infusion and 0 afterwards.

---

## 5. Independent verification

Every value was re-extracted in a second, independently-prompted read of the
same source, and the set was checked for internal consistency.

### Micro-constants from the linear pathway

```
k_el = CL/Vc = 0.127/2.62 = 0.04847 /day  (0.002020 /h)
k_12 = Q/Vc  = 0.544/2.62 = 0.20763 /day
k_21 = Q/Vp  = 0.544/2.97 = 0.18316 /day
```

### Half-life cross-check

Biexponential roots: α = 0.41803/day, β = 0.02124/day →

* distribution t½ = **1.66 days**
* terminal t½ = **32.6 days**

The paper cites a terminal half-life of **25–30 days** for the q3w regimen.
The computed value is consistent with that range and slightly above it, as
expected: this calculation uses the linear pathway alone, whereas the real
model eliminates faster through the saturable pathway. **The set is internally
coherent.**

`Vss = Vc + Vp = 5.59 L` — plausible for an IgG1 monoclonal antibody.

### How much does the nonlinear pathway matter?

Nonlinear clearance = `Vmax/(Km + C)`:

| C (mg/L) | Linear CL (L/day) | Nonlinear CL (L/day) | Nonlinear share |
|---|---|---|---|
| 0.5 | 0.127 | 0.935 | **88.0%** |
| 1 | 0.127 | 0.888 | 87.5% |
| 5 | 0.127 | 0.633 | 83.3% |
| 8.92 (=Km) | 0.127 | 0.494 | 79.5% |
| 20 | 0.127 | 0.305 | 70.6% |
| 100 | 0.127 | 0.081 | 38.9% |
| 200 | 0.127 | 0.042 | 24.9% |

**This is the decisive finding.** At trough concentrations the saturable
pathway carries the large majority of clearance. A linear-only approximation
would not be "slightly imprecise" — it would systematically overestimate
exposure in the region that matters most for trough-based decisions, and would
misrepresent washout entirely.

---

## 6. Compatibility with the current engine

**Incompatible. IV trastuzumab must stay blocked.**

`app/pk/models.py` implements linear elimination only:

```python
d_central = (absorption + infusion - (k_el + k12) * a_central[i] + k21 * a_periph[i])
```

There is no `Vmax`/`Km` term and no concentration-dependent clearance.

The existing guard already refuses the published structure — verified by
constructing the real parameter set and calling the deriver:

```
REFUSED: incompatible_model_structure
  k_el = CL/Vc assumes a constant clearance. In a model with saturable or
  target-mediated elimination, clearance varies with concentration and no
  single k_el exists.
```

This is the correct behaviour and required no change. The platform is already
designed to refuse exactly this case.

### Missing functionality

| # | Required | Present? |
|---|---|---|
| E1 | Michaelis–Menten elimination term `Vmax·C/(Km+C)` | No |
| E2 | `TWO_COMPARTMENT_PARALLEL_LINEAR_MM` execution path | No (enum exists; no solver) |
| E3 | Stiff-safe integration — MM terms make the ODE stiff near saturation | No (forward Euler only) |
| E4 | Covariate equations (weight, AST, albumin, tumour type, liver mets) | No |
| E5 | `mg/day` and `IU/L` units; mass/time dimension | `mg` and `L/day` exist; **mass/time does not** |
| E6 | Loading-plus-maintenance regimens (8 then 6 mg/kg) | Partially — repeat dosing exists, differing loading dose does not |

---

## 7. Applicability

**Population-level exploratory simulation only.**

This is a population model with 40% IIV on clearance and **139% on Km**. It
describes what a population does on average; it does not predict an individual.
It is suitable for:

* illustrating the shape of an IV trastuzumab concentration–time profile;
* comparing dosing regimens at the population level;
* teaching why saturable elimination matters.

It is **not** suitable for, and must never be presented as:

* individual dose selection or dose adjustment;
* therapeutic drug monitoring;
* any clinical decision;
* any statement about a specific patient.

The platform-wide *Research Use Only* notice applies and is not sufficient on
its own — a model this specific needs the limitation stated at the point of
display.

---

## 8. Validation evidence

| Method | Reported |
|---|---|
| Estimation | NONMEM 7.2, FOCE with interaction |
| Standard errors | Bootstrap |
| Predictive check | Visual predictive checks |
| External validation | **Not reported** |

Stated limitations (authors'):

* inter-occasion variability was not estimated, *"potentially inflating residual
  variability estimates"*;
* *"physiologic mechanisms explaining lower gastric cancer clearance remain
  unknown"*;
* Km is poorly identified (RSE 8.61% on the estimate but 139% IIV) because of
  *"limited data available at low concentrations around Km"*.

---

## 9. Alternative model, recorded but not adopted

**Quartino AL, Hillenbach C, Li J, et al.** *Cancer Chemother Pharmacol*
2015;77:77–88. doi:10.1007/s00280-015-2922-5 — HannaH (NCT00950300), n=595
HER2+ early breast cancer, SC 600 mg q3w and IV 8→6 mg/kg q3w pooled.

Linear CL 0.111 L/day · Vmax 11.9 mg/day · Km 33.9 mg/L · Vc 2.91 L ·
Q 0.445 L/day · Vp 3.06 L · F(SC) 0.771 · Ka 0.404 /day.
Covariates: `CL = 0.111·(WT/68)^1.04·(ALT/19)^0.144`, `Vc = 2.91·(WT/68)^0.443`,
`Vp = 3.06·(WT/68)^0.500`. IIV: CL 30.0%, Vc 19.1%, Vp 50.4%, F 13.0%.
Residual: proportional 23.9% + additive 4.48 µg/mL.

Note the two studies disagree substantially on **Km (33.9 vs 8.92 mg/L)** and
**Vmax (11.9 vs 8.81 mg/day)**. This is precisely why values must not be mixed:
each Vmax belongs with its own Km, and a hybrid would describe neither
population. Recorded here for the reviewer, not for use.

---

## 10. Uncertainties and limitations of this assessment

1. **Individual θ indices in the covariate equation are unresolved.** The
   retrieved text gives the equation's form but not the mapping of θ7–θ13 to
   values. The full publication table is required before covariates can be
   implemented.
2. **The FDA label was not retrieved.** The 2024 Herceptin label PDF returned
   HTTP 404. Corroboration comes from the peer-reviewed literature and a
   secondary summary, not from the label itself. A reviewer should confirm
   against the current label or EMA SmPC.
3. **Parameter values were extracted from full text via automated retrieval,
   not read off the typeset table by a human.** Two independent extractions
   agreed, and the set passes an internal half-life consistency check — but a
   human must confirm against the published table before these values are
   encoded.
4. **Assay and concentration units.** Km is stated in mg/L; the residual error
   is stated in µg/mL. These are numerically equal (1 mg/L = 1 µg/mL) but the
   unit registry must treat them as the same dimension, which it already does.
5. No assessment of biosimilar equivalence. The model describes Herceptin®
   only.

---

## 11. Proposed implementation (Phase 2 — requires approval)

**Nothing below has been implemented.**

### Engine

1. Add a `parallel_linear_mm` elimination option to `app/pk/models.py`,
   preserving the existing linear path bit-for-bit.
2. Solve with a stiff-capable integrator, or forward Euler at a step verified
   against a reference solution. **The step must be justified, not assumed** —
   MM terms are stiff near saturation, and the existing engine's Euler scheme
   already produced negative concentrations for large rate constants.
3. Add `Dimension.MASS_PER_TIME` and the `mg/day` unit.
4. Support a distinct loading dose in `DoseRegimen`.

### Library

5. Add the parameter set under `ModelStructure.TWO_COMPARTMENT_PARALLEL_LINEAR_MM`
   with `validation_status = PUBLISHED_POPULATION_PK`, the full citation, and
   `not_represented` listing: individual prediction, covariate effects (until
   implemented), inter-occasion variability, ADA effects, biosimilars.
6. `derive_rate_constants` must **continue** to refuse this structure. The MM
   path consumes CL, Vc, Q, Vp and Vmax, Km directly — it must never route
   through `k_el = CL/Vc`.

### Verification tests

| # | Test |
|---|---|
| V1 | With `Vmax = 0`, the MM solver reproduces the linear solver exactly. |
| V2 | With `C ≫ Km`, nonlinear clearance → `Vmax/C`; with `C ≪ Km` → `Vmax/Km`. |
| V3 | Linear-pathway-only terminal t½ = 32.6 days (the check in §5). |
| V4 | Simulated 8→6 mg/kg q3w steady-state trough falls in the published range. |
| V5 | Concentrations are non-negative and monotone-decreasing after infusion end at the chosen step size. |
| V6 | Halving the time step changes Cmax/AUC by less than a stated tolerance. |
| V7 | The parameter set is refused for any route other than IV infusion. |
| V8 | `derive_rate_constants` still refuses the MM structure. |
| V9 | Existing golden vectors unchanged. |
| V10 | Output is labelled population-level exploratory, never individual. |

### Gate

Do not implement until a human with pharmacology background has confirmed the
parameter table against the publication and signed off §10.1–10.3.

---

## Sources

* Quartino AL, Li H, Kirschbrown WP, et al. *Cancer Chemother Pharmacol*
  2018;83(2):329–340. doi:10.1007/s00280-018-3728-z —
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6394489/
* Quartino AL, Hillenbach C, Li J, et al. *Cancer Chemother Pharmacol*
  2015;77:77–88. doi:10.1007/s00280-015-2922-5 —
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4706584
* Bruno R, et al. Population pharmacokinetics of trastuzumab in patients with
  HER2+ metastatic breast cancer. PMID 15868146 — identified, not used.
