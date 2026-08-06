# nanobio_studio/ai_engine/audit.py

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from nanobio_studio.ai_engine.schema import DesignSpace, ObjectiveWeights


@dataclass
class AuditRecord:
    timestamp_utc: str
    scenario_name: str
    scenario_key: str

    # user / project metadata (optional)
    project_id: Optional[str] = None
    user_id: Optional[str] = None

    # configuration
    design_space: Dict[str, Any] = None
    weights: Dict[str, float] = None
    constraints: Dict[str, Any] = None
    run_settings: Dict[str, Any] = None

    # outcome summary
    best_trial_value: Optional[float] = None
    best_params: Optional[Dict[str, Any]] = None
    best_candidate: Optional[Dict[str, Any]] = None

    # evidence panels
    baseline_summary: Optional[Dict[str, Any]] = None
    explainability_summary: Optional[Dict[str, Any]] = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_audit_record(
    scenario_name: str,
    scenario_key: str,
    space: DesignSpace,
    weights: ObjectiveWeights,
    constraints: Dict[str, Any],
    run_settings: Dict[str, Any],
) -> AuditRecord:
    return AuditRecord(
        timestamp_utc=utc_now_iso(),
        scenario_name=scenario_name,
        scenario_key=scenario_key,
        design_space=asdict(space),
        weights={"efficacy": weights.efficacy, "safety": weights.safety, "cost": weights.cost},
        constraints=constraints,
        run_settings=run_settings,
    )


def record_outcome(
    audit: AuditRecord,
    res,
    baseline_summary: Optional[Dict[str, Any]] = None,
    explainability_summary: Optional[Dict[str, Any]] = None,
) -> AuditRecord:
    audit.best_trial_value = float(res.study.best_value) if getattr(res, "study", None) else None
    audit.best_params = dict(res.study.best_params) if getattr(res, "study", None) else None

    best = res.best
    audit.best_candidate = {
        "design": {
            "size_nm": best.design.size_nm,
            "zeta_mV": best.design.zeta_mV,
            "material": best.design.material,
            "ligand": best.design.ligand,
            "payload": best.design.payload,
            "dose_mg_per_kg": best.design.dose_mg_per_kg,
            "pdi": best.design.pdi,
        },
        "scores": {
            "efficacy": float(best.efficacy),
            "toxicity": float(best.toxicity),
            "cost": float(best.cost),
            "confidence": float(best.confidence),
        },
        "drivers": list(best.drivers[:6]) if best.drivers else [],
    }

    audit.baseline_summary = baseline_summary
    audit.explainability_summary = explainability_summary
    return audit


def audit_to_json(audit: AuditRecord) -> str:
    return json.dumps(asdict(audit), indent=2)


def audit_to_html(audit: AuditRecord) -> str:
    """
    Simple, printable HTML report (government-friendly).
    """
    def esc(x: Any) -> str:
        s = "" if x is None else str(x)
        return (
            s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
        )

    best = audit.best_candidate or {}
    design = (best.get("design") or {})
    scores = (best.get("scores") or {})

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>NanoBio Studio — AI Decision Audit Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 28px; }}
    h1 {{ margin-bottom: 0; }}
    .sub {{ color:#444; margin-top:6px; }}
    .box {{ border: 1px solid #ddd; padding: 14px; border-radius: 10px; margin: 14px 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f5f5f5; }}
    .small {{ color:#555; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>NanoBio Studio — AI Decision Audit Report</h1>
  <div class="sub">Timestamp (UTC): {esc(audit.timestamp_utc)}</div>

  <div class="box">
    <h2>Scenario / Policy Context</h2>
    <p><b>Scenario:</b> {esc(audit.scenario_name)} (key: {esc(audit.scenario_key)})</p>
    <p class="small">{esc((audit.constraints or {}).get("scenario_description",""))}</p>
  </div>

  <div class="box">
    <h2>Run Configuration</h2>
    <p><b>Weights</b>: {esc(audit.weights)}</p>
    <p><b>Constraints</b>: {esc(audit.constraints)}</p>
    <p><b>Run settings</b>: {esc(audit.run_settings)}</p>
  </div>

  <div class="box">
    <h2>Best Candidate Summary</h2>
    <table>
      <tr><th>Parameter</th><th>Value</th></tr>
      <tr><td>Size (nm)</td><td>{esc(design.get("size_nm"))}</td></tr>
      <tr><td>Zeta (mV)</td><td>{esc(design.get("zeta_mV"))}</td></tr>
      <tr><td>Material</td><td>{esc(design.get("material"))}</td></tr>
      <tr><td>Ligand</td><td>{esc(design.get("ligand"))}</td></tr>
      <tr><td>Payload</td><td>{esc(design.get("payload"))}</td></tr>
      <tr><td>Dose (mg/kg)</td><td>{esc(design.get("dose_mg_per_kg"))}</td></tr>
      <tr><td>PDI</td><td>{esc(design.get("pdi"))}</td></tr>
    </table>
    <br/>
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Efficacy</td><td>{esc(scores.get("efficacy"))}</td></tr>
      <tr><td>Toxicity</td><td>{esc(scores.get("toxicity"))}</td></tr>
      <tr><td>Cost</td><td>{esc(scores.get("cost"))}</td></tr>
      <tr><td>Confidence</td><td>{esc(scores.get("confidence"))}</td></tr>
    </table>

    <p><b>Key Drivers:</b> {esc(", ".join(best.get("drivers", [])))}</p>
  </div>

  <div class="box">
    <h2>Evidence of AI Value</h2>
    <p><b>Best trial value:</b> {esc(audit.best_trial_value)}</p>
    <p><b>Best parameters:</b> {esc(audit.best_params)}</p>
    <p><b>Baseline Summary:</b> {esc(audit.baseline_summary)}</p>
    <p><b>Explainability Summary:</b> {esc(audit.explainability_summary)}</p>
  </div>

  <div class="box small">
    <b>Disclaimer:</b> Research and educational use only. Outputs require experimental validation.
  </div>
</body>
</html>"""
