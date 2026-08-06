/**
 * Types and presentation vocabulary for the Scientific Readiness Framework.
 *
 * These mirror `app/science/statuses.py`. The labels are duplicated here rather
 * than fetched, so the dashboard renders correctly before the vocabulary
 * request returns — but the *authority* is the backend, and the page shows the
 * server's own label whenever one is supplied.
 */

export type ScientificStatusId =
  | 'measured'
  | 'experimentally_derived'
  | 'literature_derived'
  | 'calculated'
  | 'computationally_predicted'
  | 'user_supplied'
  | 'assumed_default'
  | 'illustrative'
  | 'missing'
  | 'not_applicable';

export type ReadinessStatusId =
  | 'ready'
  | 'conditionally_ready'
  | 'insufficient'
  | 'blocked'
  | 'outside_model_domain';

export type EvidenceLevelId = 'E0' | 'E1' | 'E2' | 'E3' | 'E4' | 'E5' | 'E6';

export interface Finding {
  code: string;
  message: string;
  field_ids: string[];
  recommended_action: string | null;
}

export interface AreaAssessment {
  area: string;
  label: string;
  description: string;
  status: ReadinessStatusId;
  readiness_percent: number;
  evidence_level: EvidenceLevelId;
  /**
   * Why the level is what it is, and why it is not higher. Optional so a
   * response from an older engine still renders; the page shows nothing rather
   * than inventing a reason.
   */
  evidence_level_rationale?: string;
  /** The highest level this area could reach today, whatever it records. */
  max_attainable_evidence_level?: EvidenceLevelId;
  blocking_issues: Finding[];
  warnings: Finding[];
  missing_inputs: string[];
  incompatible_inputs: Finding[];
  assumptions: Finding[];
  recommended_actions: string[];
}

export interface ReadinessReport {
  study_id: number;
  areas: AreaAssessment[];
  rules_engine_version: string;
  dictionary_version: string;
  evaluated_at: string;
  notice: string;
  record_count: number;
  /** False until the Experimental Validation Registry exists (Phase 2). */
  validation_registry_available?: boolean;
  max_attainable_evidence_level?: EvidenceLevelId;
  evidence_ceiling_notice?: string;
}

export interface ScienceRecord {
  field_id: string;
  status: ScientificStatusId;
  value: unknown;
  unit: string | null;
  measurement_method: string | null;
  source_citation: string | null;
  notes: string | null;
}

export interface ScienceRecordListResponse {
  study_id: number;
  records: ScienceRecord[];
  is_legacy_import: boolean;
  legacy_notice: string | null;
}

/* ------------------------------------------------------------ presentation */

/**
 * Tone per readiness status.
 *
 * `blocked` and `outside_model_domain` are deliberately distinct: the first
 * means "something is missing", the second means "the platform cannot model
 * this at all". Collapsing them would suggest the second is fixable by
 * entering more data.
 */
export const READINESS_TONE: Record<ReadinessStatusId,
  'success' | 'accent' | 'info' | 'warn' | 'neutral' | 'danger'> = {
  ready: 'success',
  conditionally_ready: 'accent',
  insufficient: 'info',
  blocked: 'warn',
  outside_model_domain: 'neutral',
};

export const READINESS_LABEL: Record<ReadinessStatusId, string> = {
  ready: 'Ready',
  conditionally_ready: 'Conditionally ready',
  insufficient: 'Insufficient data',
  blocked: 'Blocked',
  outside_model_domain: 'Outside model domain',
};

/**
 * Tone per scientific status.
 *
 * Measured and experimentally derived share the strongest tone; everything that
 * is not evidence about this material is visually separated from them.
 */
export const SCIENTIFIC_TONE: Record<ScientificStatusId,
  'success' | 'accent' | 'info' | 'warn' | 'neutral'> = {
  measured: 'success',
  experimentally_derived: 'success',
  literature_derived: 'info',
  calculated: 'accent',
  computationally_predicted: 'accent',
  user_supplied: 'warn',
  assumed_default: 'warn',
  illustrative: 'warn',
  missing: 'neutral',
  not_applicable: 'neutral',
};

export const SCIENTIFIC_LABEL: Record<ScientificStatusId, string> = {
  measured: 'Measured',
  experimentally_derived: 'Experimentally derived',
  literature_derived: 'Literature-derived',
  calculated: 'Calculated',
  computationally_predicted: 'Computationally predicted',
  user_supplied: 'User-supplied (no method)',
  assumed_default: 'Assumed default',
  illustrative: 'Illustrative only',
  missing: 'Missing',
  not_applicable: 'Not applicable',
};

/**
 * Mirrors `EVIDENCE_LABEL` in `app/science/statuses.py`.
 *
 * The scale has two halves and they must not be read as one gradient. E0–E2
 * describe the *basis* of a value that has not been validated — a placeholder,
 * a citation, a model output, an instrument reading. E3–E6 assert that
 * something was *validated* against an independent result or an experiment.
 * A measurement is the strongest basis available and is still unvalidated,
 * which is why E2 names both.
 */
export const EVIDENCE_LABEL: Record<EvidenceLevelId, string> = {
  E0: 'E0 — illustrative only',
  E1: 'E1 — literature-derived estimate',
  E2: 'E2 — computational prediction or unvalidated measurement',
  E3: 'E3 — retrospectively validated',
  E4: 'E4 — prospectively validated in vitro',
  E5: 'E5 — validated in vivo',
  E6: 'E6 — supported by clinical evidence',
};

/**
 * Levels that assert experimental validation.
 *
 * Unreachable while the Experimental Validation Registry does not exist. The
 * backend never emits one; this set exists so the page can *say so* rather than
 * leaving a reader to assume a study is merely some distance from E4.
 */
export const EXPERIMENTAL_VALIDATION_LEVELS: ReadonlySet<EvidenceLevelId> =
  new Set(['E3', 'E4', 'E5', 'E6']);

/** Statuses that constitute evidence about this material. */
export const EVIDENCE_BEARING: ReadonlySet<ScientificStatusId> = new Set([
  'measured', 'experimentally_derived',
]);

/** Statuses that must never raise readiness. */
export const NON_CONTRIBUTING: ReadonlySet<ScientificStatusId> = new Set([
  'assumed_default', 'illustrative', 'missing',
]);

export function toneForReadiness(status: string) {
  return READINESS_TONE[status as ReadinessStatusId] ?? 'neutral';
}

export function labelForReadiness(status: string) {
  return READINESS_LABEL[status as ReadinessStatusId] ?? 'Not recorded';
}

export function toneForScientific(status: string) {
  return SCIENTIFIC_TONE[status as ScientificStatusId] ?? 'neutral';
}

export function labelForScientific(status: string) {
  return SCIENTIFIC_LABEL[status as ScientificStatusId] ?? 'Not recorded';
}
