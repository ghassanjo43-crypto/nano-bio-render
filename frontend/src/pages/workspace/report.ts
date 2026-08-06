/**
 * Report generation from a stored run.
 *
 * The report is assembled **only** from the stored record, so it cannot drift
 * from what the screen shows and cannot contain a value no engine produced.
 *
 * Every report states, without exception:
 *   • whether the inputs were synthetic demonstration data;
 *   • the therapeutic context, and that it did not affect the calculation;
 *   • the exact formulation and pharmacokinetic inputs;
 *   • which engines executed and which did not, with reasons;
 *   • the genuinely calculated outputs and their units;
 *   • the model versions;
 *   • warnings, assumptions and limitations as the engines returned them;
 *   • the scientific validation status;
 *   • a research-use-only disclaimer.
 *
 * Unit terminology is fixed: pharmacokinetic outputs are "dose-scaled
 * compartment amount". They are never called a concentration and never labelled
 * ng/mL — the model has no volume term.
 */

import type { RunDetail } from '../../api/types';

const RULE = '='.repeat(78);
const THIN = '-'.repeat(78);

/** The unit phrase for this PK engine. Fixed, and asserted by test. */
export const PK_AMOUNT_UNIT = 'dose-scaled compartment amount (arbitrary units)';

function section(title: string): string {
  return `\n${RULE}\n${title.toUpperCase()}\n${RULE}\n`;
}

function kv(label: string, value: unknown): string {
  const shown = value === null || value === undefined || value === ''
    ? 'not recorded'
    : Array.isArray(value) ? (value.length ? value.join(', ') : '(none)')
    : String(value);
  return `  ${label.padEnd(38, '.')} ${shown}\n`;
}

function list(items: readonly string[], bullet = '  - '): string {
  if (items.length === 0) return '  (none reported)\n';
  return items.map((i) => `${bullet}${i}\n`).join('');
}

/**
 * Build the plain-text report body for a stored run.
 *
 * Plain text rather than PDF: it is auditable, diffable, has no binary
 * dependency, and every character in it can be traced to the stored record.
 * A typeset PDF is a presentation concern for a later slice.
 */
export function buildReport(run: RunDetail): { filename: string; body: string } {
  const lines: string[] = [];

  lines.push(RULE);
  lines.push('NANOBIO STUDIO — CALCULATION REPORT');
  lines.push(RULE);
  lines.push('');
  lines.push('RESEARCH USE ONLY. This report is a computational research-planning');
  lines.push('output. It is not experimentally validated, not clinically validated,');
  lines.push('not a regulatory approval prediction, not a diagnosis, not a dosing or');
  lines.push('treatment recommendation, and not a substitute for wet-lab or in-vivo');
  lines.push('study.');
  lines.push('');

  // ---------------------------------------------------------- provenance
  lines.push(section('1. Record'));
  lines.push(kv('Run name', run.name));
  lines.push(kv('Run id', run.id));
  lines.push(kv('Recorded at', new Date(run.created_at).toISOString()));
  lines.push(kv('Status', run.status));

  if (run.origin === 'demo') {
    lines.push('');
    lines.push('  *** SYNTHETIC DEMONSTRATION DATA ***');
    lines.push('  The inputs in this report came from a built-in demonstration');
    lines.push('  scenario. They are synthetic. They are NOT patient data, NOT');
    lines.push('  clinical data, NOT validated experimental data, NOT a treatment');
    lines.push('  recommendation, and NOT a known-successful formulation.');
    lines.push('  The results were nonetheless calculated by the genuine engines');
    lines.push('  from those synthetic inputs.');
    lines.push('');
    lines.push(kv('Demonstration scenario', run.demo_scenario_slug));
    lines.push(kv('Fixture set version', run.demo_fixture_version));
  } else {
    lines.push(kv('Data origin', 'User-entered inputs'));
  }

  // ------------------------------------------------------------- context
  lines.push(section('2. Therapeutic context'));
  lines.push(kv('Indication', run.disease));
  lines.push(kv('Subtype', run.subtype));
  lines.push(kv('Therapeutic agent', run.drug));
  lines.push('');
  lines.push('  Recorded for traceability only. Neither connected engine accepts a');
  lines.push('  disease as an input, so this context did not affect any value in');
  lines.push('  this report.');

  // -------------------------------------------------------------- inputs
  lines.push(section('3. Formulation inputs'));
  if (run.design_inputs) {
    for (const [k, v] of Object.entries(run.design_inputs)) lines.push(kv(k, v));
  } else {
    lines.push('  Not recorded — the design engine was not run.\n');
  }

  lines.push(section('4. Pharmacokinetic inputs'));
  if (run.pk_inputs) {
    for (const [k, v] of Object.entries(run.pk_inputs)) lines.push(kv(k, v));
    lines.push('');
    lines.push('  Rate constants are INPUTS, not predictions. The model does not');
    lines.push('  derive them from the formulation above.');
  } else {
    lines.push('  Not recorded — the pharmacokinetic engine was not run.\n');
  }

  // ------------------------------------------------------------- engines
  lines.push(section('5. Engines executed'));
  lines.push(list(run.engines_run.length ? run.engines_run
                                         : ['(no engine produced a result)']));

  lines.push(section('6. Engines NOT executed'));
  if (run.engines_not_run.length === 0) {
    lines.push('  None recorded.\n');
  } else {
    for (const e of run.engines_not_run) {
      lines.push(`  - ${e.engine}\n      reason: ${e.reason}\n`);
    }
  }

  // ------------------------------------------------------------- results
  lines.push(section('7. Calculated results — design impact score'));
  if (run.design_result) {
    const d = run.design_result;
    lines.push(kv('Delivery (0-100, higher is better)',
                  d.design_impact_score.delivery));
    lines.push(kv('Toxicity (0-10, lower is better)',
                  d.design_impact_score.toxicity));
    lines.push(kv('Cost (0-100, lower is better)', d.design_impact_score.cost));
    lines.push('');
    lines.push(kv('Model / formula version', d.score_version));
    lines.push(kv('Scientific source', d.scientific_source));
    lines.push(kv('Prediction basis', d.prediction_basis));
    lines.push(kv('Evidence level', d.evidence_level));
    lines.push(kv('Validation status', d.validation_status));
    lines.push('');
    lines.push('  No single composite "overall score" is produced: the candidate');
    lines.push('  formula is documented but not implemented, pending scientific');
    lines.push('  review.');
    lines.push('');
    lines.push(THIN);
    lines.push('  Warnings');
    lines.push(THIN);
    lines.push(list(d.warnings));
    lines.push(THIN);
    lines.push('  Limitations');
    lines.push(THIN);
    lines.push(list(d.limitations));
  } else {
    lines.push('  NOT CALCULATED. No design impact score exists for this run, so');
    lines.push('  none is reported. No default or substitute value is supplied.\n');
  }

  lines.push(section('8. Calculated results — pharmacokinetic simulation'));
  if (run.pk_result) {
    const p = run.pk_result;
    const par = p.pk_parameters;
    lines.push(`  All amounts below are expressed as ${PK_AMOUNT_UNIT}.\n`);
    lines.push('  The model has no volume-of-distribution term, so these are NOT');
    lines.push('  concentrations and must NOT be read as ng/mL.\n');
    lines.push('');
    lines.push(kv('Peak amount, central compartment',
                  par.peak_concentration_central));
    lines.push(kv('Time to peak, central (h)', par.time_to_peak_central_h));
    lines.push(kv('Peak amount, peripheral compartment',
                  par.peak_concentration_peripheral));
    lines.push(kv('Time to peak, peripheral (h)', par.time_to_peak_peripheral_h));
    lines.push(kv('AUC, central (amount x h)', par.auc_central));
    lines.push(kv('AUC, peripheral (amount x h)', par.auc_peripheral));
    lines.push(kv('Terminal half-life, central (h)',
                  par.half_life_central_h === null
                    ? 'not determined within the simulated window'
                    : par.half_life_central_h));
    lines.push(kv('Tissue accumulation ratio', par.tissue_accumulation_ratio));
    lines.push(kv('Peak ratio (peripheral/central)', par.vss_ratio));
    lines.push(kv('Profile points calculated', p.concentration_time.point_count));
    lines.push('');
    lines.push(kv('Calculation version', p.calculation_version));
    lines.push(kv('Model', p.model_name));
    lines.push(kv('Scientific source', p.scientific_source));
    lines.push(kv('Prediction basis', p.prediction_basis));
    lines.push(kv('Evidence level', p.evidence_level));
    lines.push(kv('Validation status', p.validation_status));

    lines.push('');
    lines.push(THIN);
    lines.push('  Quantities this model does NOT produce');
    lines.push(THIN);
    for (const q of p.quantities_not_produced) {
      lines.push(`  - ${q.quantity}\n      ${q.reason}\n`);
    }

    lines.push(THIN);
    lines.push('  Assumptions');
    lines.push(THIN);
    lines.push(list(p.assumptions));
    lines.push(THIN);
    lines.push('  Warnings');
    lines.push(THIN);
    lines.push(list(p.warnings));
    lines.push(THIN);
    lines.push('  Limitations');
    lines.push(THIN);
    lines.push(list(p.limitations));
  } else {
    lines.push('  NOT CALCULATED. No concentration-time profile, half-life or AUC');
    lines.push('  exists for this run, so none is reported. No default or');
    lines.push('  substitute profile is supplied.\n');
  }

  // ---------------------------------------------------------- disclaimer
  lines.push(section('9. Scientific validation status'));
  lines.push('  Every value in this report is a computational research-planning');
  lines.push('  result produced by rule-based or structural models that have NOT');
  lines.push('  been calibrated against experimental data.');
  lines.push('');
  lines.push('  This report is NOT:');
  lines.push('    - experimentally validated');
  lines.push('    - clinically validated');
  lines.push('    - a regulatory approval prediction');
  lines.push('    - a diagnosis');
  lines.push('    - a dosing or treatment recommendation');
  lines.push('    - a substitute for wet-lab or in-vivo study');
  lines.push('');
  lines.push(RULE);
  lines.push('END OF REPORT');
  lines.push(RULE);

  const stamp = new Date(run.created_at).toISOString().slice(0, 10);
  const safe = run.name.replace(/[^a-zA-Z0-9-_]+/g, '_').slice(0, 60);
  const prefix = run.origin === 'demo' ? 'DEMO_' : '';

  return {
    filename: `${prefix}nanobio_run${run.id}_${safe}_${stamp}.txt`,
    body: lines.join('\n'),
  };
}

/** Trigger a browser download of the generated report. */
export function downloadReport(report: { filename: string; body: string }): void {
  const blob = new Blob([report.body], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = report.filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
