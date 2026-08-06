# Pharmacokinetic input sources, routes and parameter provenance

## 1. The scientific defect

The PK input screen required every user to enter a dose and four first-order
rate constants — `k_abs`, `k_el`, `k12`, `k21` — with no reference to how the
drug is administered. The selected therapeutic was **intravenous trastuzumab**.

`k_abs` is not a cosmetic field. It is genuinely consumed by the engine:

```python
dC_depot  = -kabs * C_depot[i]
dC_plasma = kabs * C_depot[i] - kel * C_plasma[i] - k12 * ... + k21 * ...
```

So a number typed into a box labelled "absorption rate constant" silently
determined the reported concentration–time profile of a drug that has no
absorption phase at all.

### Evidence that the engine cannot represent IV administration

Measured directly against `utils/pk_model.two_compartment_model`, dt = 0.1 h:

| `k_abs` | `C_plasma[0]` | min(C_plasma) | verdict |
|---|---|---|---|
| 1 | 0.000 | 0.000 | absorption phase, not IV |
| 10 | 0.000 | 0.000 | still not IV |
| 20 | 0.000 | **−93.838** | negative concentrations |
| 50 | 0.000 | −3.1×10¹⁴⁶ | diverged |

* `C_plasma[0]` is **always 0**. An IV bolus has the entire dose in the central
  compartment at t = 0. This is unreachable for any `k_abs`.
* The limit `k_abs → ∞` is not numerically available: explicit Euler is stable
  only while `k_abs·dt ≤ 1`, and beyond it the model returns negative amounts.
* `k_abs = 0` yields an all-zero profile, so absorption cannot be switched off.

**Conclusion:** the depot model cannot represent intravenous administration by
any choice of parameters. New equations were required.

### Second defect found during inspection

`t_half_plasma` is documented and displayed as a half-life. It is computed as
the first time after the peak at which the curve falls to half of `C_max`. In a
two-compartment model that is the **distribution** phase, not elimination.

Measured: with `k_el = 0.01 /h` (true elimination t½ = 69.3 h) and rapid
distribution, the reported half-life is **1.4 h** — off by a factor of ~50.

This is recorded as a defect. It is **not** fixed in this slice, because
changing it alters a number the golden vectors pin. It requires its own
reviewed change. The route-aware engine does not report a half-life at all.

---

## 2. Existing model equations and limitations

`utils/pk_model.two_compartment_model`, **unchanged by this work**:

```
dA_depot/dt  = -k_abs · A_depot
dA_central/dt = k_abs · A_depot - k_el · A_central - k12 · A_central + k21 · A_periph
dA_periph/dt  = k12 · A_central - k21 · A_periph
A_depot(0) = dose
```

Explicit forward Euler, fixed step. Limitations, all pre-existing:

* **Extravascular only.** Depot input; no IV bolus or infusion.
* **No volume term.** State variables are dose-scaled amounts, not
  concentrations. The legacy PDF labelled them "ng/mL"; that label was wrong.
* **No clearance derivable** — there is no volume to divide by.
* Single dose only; no interval, no repeat administration.
* Linear only; no saturable or target-mediated elimination.
* No covariates. Age, weight, sex and organ function are not inputs.
* Half-life measures distribution, as above.

---

## 3. The new route-aware model

Added in `app/pk/models.py`, **separately versioned**
(`pk-route-aware-two-compartment-0.1.0`) and running alongside the untouched
depot model. Standard linear two-compartment equations in **amounts**, which
makes the volumes explicit and the output a genuine mg/L concentration:

```
IV bolus       A_c(0) = F·Dose,  A_p(0) = 0
IV infusion    A_c(0) = 0, constant input R₀ = F·Dose/T_inf while t < T_inf
Extravascular  A_d(0) = Dose, input = F·k_a·A_d

dA_c/dt = <input> - (k_el + k12)·A_c + k21·A_p
dA_p/dt =           k12·A_c        - k21·A_p

C_c = A_c/V_c        C_p = A_p/V_p
```

### Verification, not assertion

Checked against the closed-form biexponential IV-bolus solution:

| time step | max relative error |
|---|---|
| 0.1 h | 1.72×10⁻² |
| 0.01 h | 1.70×10⁻³ |
| 0.001 h | 1.70×10⁻⁴ |

First-order convergence, exactly as forward Euler requires. Run as a test
(`test_matches_the_closed_form_iv_bolus_solution`), not documented in prose.

---

## 4. Input sources

Every input is classified. The classification travels with the value into the
pre-run summary and the stored record.

| Source | Meaning |
|---|---|
| `patient_report` | Confirmed field from an uploaded report |
| `manual_entry` | Typed because no confirmed report value existed |
| `treatment_protocol` | The prescribed or planned regimen |
| `parameter_library` | A cited parameter set |
| `derived` | Computed from library parameters, formula recorded |
| `simulation_setting` | A numerical control |
| `expert_override` | A researcher's own edit, audited |

**Which report fields the engine genuinely consumes: none.**

`ModelInputs` has no age, sex, weight, creatinine or diagnosis field — asserted
by `test_the_model_consumes_no_patient_covariate`. Body weight enters only by
resolving a mg/kg dose to milligrams, *before* the model, and is refused rather
than defaulted when absent. Of the 22 extracted clinical fields, only three
(`cancer_indication`, `histological_subtype`, `current_treatment`) map to the
workflow at all, and none reaches the PK equations.

Body weight, age and sex are **not currently extracted** from reports, so the
patient category is populated by manual entry only.

---

## 5. Route-specific behaviour

| Route | Input function | `k_abs` | Requires | F |
|---|---|---|---|---|
| IV bolus | instantaneous central | **Not applicable** | dose | fixed 1.0 |
| IV infusion | zero-order central | **Not applicable** | dose, infusion duration | fixed 1.0 |
| Subcutaneous | first-order depot | required | dose, k_abs | free |
| Oral | first-order depot | required | dose, k_abs | free |
| Intraperitoneal | first-order depot | required | dose, k_abs | free |

A `k_abs` supplied for an IV route is **refused**, not ignored — silently
discarding it would let the user believe it affected the result.

Changing the route resets the confirmation and re-fetches the plan, because the
fields, units, validation rules and compatible parameter sets all change.

---

## 6. The parameter library

`app/pk/parameter_library.py`. Every set must carry: therapeutic, formulation,
route, population, indication, source citation, units, model structure, version,
review date, validation status and limitations. The dataclass makes these
mandatory and rejects a set with a blank citation.

### It ships empty of clinical parameter sets — deliberately

Populating it requires reading an authoritative source (a regulatory product
label or peer-reviewed population-PK publication) and recording the exact
population. **That verification was not performed in this slice**, so no
clinical set is included.

The consequence is intended: IV trastuzumab reports

> Not yet operational for this therapeutic/route combination
> (Trastuzumab (Herceptin) / Intravenous infusion).

with `CL, Vc, Q, Vp` named as missing, and Run disabled. Nothing is substituted
and nothing is borrowed from another drug, route or population.

### To add a trastuzumab set

Required before it may be added:

1. The source in front of you — FDA/EMA label or a named popPK publication.
2. The exact population (indication, line of therapy, n, covariate ranges).
3. Units as published.
4. The model structure it was estimated in. Trastuzumab exhibits **parallel
   linear and nonlinear (target-mediated) elimination**; a set estimated under
   that structure must be recorded as
   `TWO_COMPARTMENT_PARALLEL_LINEAR_MM`, and `derive_rate_constants` will
   correctly refuse it — because `k_el = CL/Vc` assumes a constant clearance.
5. What the simplified engine cannot represent, listed in `not_represented`.

If a linear approximation is entered deliberately, it must be labelled
**"Limited exploratory model — not validated for individual dosing or clinical
decision-making."** The planner adds this automatically whenever a
two-compartment-linear set declares anything in `not_represented`.

---

## 7. Derived rate constants

For a linear two-compartment set only:

```
k_el = CL / Vc      k_12 = Q / Vc      k_21 = Q / Vp
```

* Units are converted to canonical (L, L/h, h) **before** dividing. `CL` in
  mL/h with `Vc` in L gives the right answer; without conversion it would be
  wrong by 1000× and still look plausible.
* Each division asserts its resulting dimension is 1/time. A flow divided by a
  time is refused.
* Every derived value records its formula and the exact source quantities.
* Marked **"Calculated from cited model parameters"**, not editable in guided
  mode, expandable to show the working.
* Refused for one-compartment, parallel-MM and target-mediated structures.

---

## 8. Reproducibility

Stored with every routed run: engine version, library version, parameter-set id
**and version**, model structure, route, full dosing regimen, resolved dose in
mg with its explanation, all simulation settings, the formulas used, expert
overrides, warnings, and a deterministic flag.

Pinning the parameter-set version is what keeps a historical run interpretable
after the library is revised. A run pinned to a withdrawn set returns a 404 on
re-run rather than silently substituting the current version — its original
values remain in the stored record.

---

## 9. Unsupported combinations

**Every therapeutic/route combination is currently unsupported in guided mode**,
because the library contains no verified parameter sets. All of them block with
a named list of what is missing.

Expert research mode accepts researcher-supplied parameters and labels the
output "supplied by the researcher … not a validated platform prediction".

---

## 10. Remaining blockers

| # | Blocker |
|---|---|
| PK-B1 | No verified parameter set for any therapeutic. Requires reading authoritative sources. |
| PK-B2 | Trastuzumab's nonlinear/target-mediated elimination is not implementable by the current engine, which is linear only. |
| PK-B3 | The legacy `t_half_plasma` reports distribution, not elimination. Fixing it changes golden-vector numbers and needs its own reviewed change. |
| PK-B4 | Body weight, age and sex are not extracted from reports, so weight-based dosing is manual-entry only. |
| PK-B5 | No covariate model is implemented, so no patient characteristic can affect a prediction. |
| PK-B6 | No inter-individual variability, no uncertainty quantification, no confidence intervals. |
| PK-B7 | Neither engine has been validated against experimental or clinical data. |
