/**
 * Typed client for candidate revision, supersession and version-bound artefacts.
 *
 * The one rule this module enforces at the boundary
 * -------------------------------------------------
 * **Every function takes an exact version id, and there is no overload that
 * takes a candidate id and works out which version was meant.** That is not a
 * stylistic choice: a report generated against "the latest" is a report whose
 * subject depends on when the button was pressed, and two clicks a minute
 * apart can describe different formulations under the same title. The backend
 * refuses an inexact reference; this module makes it impossible to express one.
 *
 * The types below are written from the real response bodies, not from what the
 * screens would find convenient. `candidateVersionClient.contract.test.ts`
 * checks them against HTTP responses captured from the running API rather than
 * against a hand-written mock, because a mock that agrees with the client
 * proves only that one author wrote both.
 *
 * Reuses `apiRequest` from `client.ts`, so this shares one 401 handler, one
 * error shape and one definition of a trustworthy response with everything
 * else.
 */

import { apiRequest as rawApiRequest } from './client';

/** Where a version stands. Deliberately no "latest" — see `VersionStanding`. */
export type VersionStatus =
  | 'draft' | 'locked' | 'approved' | 'superseded' | 'withdrawn';

/** Whether the derived numbers on a version can still be believed. */
export type ResultsState = 'none' | 'current' | 'stale' | 'recalculating';

export type SupersessionState = 'none' | 'proposed' | 'accepted' | 'refused';

export type EvidenceReuse =
  | 'retained_reference' | 'reassessment_required' | 'newly_validated';

export type MaterialClassification =
  | 'none' | 'recalculation' | 'scientific_review' | 'safety_review';

/** One candidate version, exactly as `serialize_candidate_version` returns it. */
export interface CandidateVersionSummary {
  id: number;
  candidate_id: number;
  version_number: number;
  revision_label: string | null;
  /** `revision_label` with a fallback. Always present; prefer this for display. */
  label: string;
  status: VersionStatus;
  results_state: ResultsState;
  results_inherited_from_id: number | null;
  predecessor_version_id: number | null;
  revision_reason: string | null;
  note: string | null;
  snapshot_checksum: string;
  /** The same value under the name this endpoint has always served. */
  checksum: string;
  editable: boolean;
  is_historical: boolean;
  locked_at: string | null;
  lock_reason: string | null;
  supersession_state: SupersessionState;
  superseded_by_version_id: number | null;
  superseded_at: string | null;
  supersession_reason: string | null;
  supersession_decision_id: number | null;
  model_version: string | null;
  ruleset_version: string | null;
  reference_data_version: string | null;
  algorithm_selection: string | null;
  created_at: string;
  created_by: number | null;
  revision: number;
}

/**
 * The three named standings a version can hold.
 *
 * There is no `latest_version_id`, and that absence is the point. "Latest" is
 * ambiguous between the newest draft and the one currently approved, and a
 * screen that shows the wrong one is presenting unreviewed work as though the
 * organization stood behind it.
 */
export interface VersionHistory {
  candidate_id: number;
  candidate_code: string;
  current_effective_version_id: number | null;
  latest_approved_version_id: number | null;
  latest_draft_version_id: number | null;
  versions: CandidateVersionSummary[];
  total: number;
}

export interface FieldChange {
  field: string;
  before: unknown;
  after: unknown;
  kind: 'added' | 'removed' | 'changed';
  scientific: boolean;
}

/** What a change demands, as six independent answers plus the summary level. */
export interface ChangeConsequence {
  requires: MaterialClassification;
  changed_scientific_fields: string[];
  field_classifications?: Record<string, string>;
  identity_only: boolean;
  approval_may_carry_forward: boolean;
  consequences: {
    recalculation: boolean;
    scientific_reassessment: boolean;
    safety_reassessment: boolean;
    new_approval: boolean;
    new_report: boolean;
    new_cro_package: boolean;
  };
  requires_new_report?: boolean;
  requires_new_package?: boolean;
  explanation: string;
}

export interface VersionComparison {
  left: CandidateVersionSummary;
  right: CandidateVersionSummary;
  changed_fields: FieldChange[];
  consequence: ChangeConsequence;
  identical: boolean;
}

export interface RevisionResult extends CandidateVersionSummary {
  /** False when an idempotency key matched, so a retry is visibly a retry. */
  created: boolean;
  predecessor: CandidateVersionSummary;
  changed_fields: FieldChange[];
  consequence: ChangeConsequence;
  notice: string;
}

export interface DependentCounts {
  experiments: number;
  attachments: number;
  simulations: number;
  evidence_assessments: number;
  reports: number;
  exports: number;
  cro_packages: number;
  comparisons: number;
}

export interface VersionDependents {
  candidate_id: number;
  candidate_version_id: number;
  version_label: string;
  status: VersionStatus;
  editable: boolean;
  lock_reason: string | null;
  locked_at: string | null;
  dependents: DependentCounts;
  total_dependents: number;
  explanation: string;
}

export interface SimulationRow {
  id: number;
  kind: string;
  state: 'current' | 'copied_stale' | 'invalidated' | 'failed';
  engine_version: string;
  ruleset_version: string | null;
  inputs_checksum: string;
  is_stale: boolean;
  copied_from_simulation_id: number | null;
  source_candidate_version_id: number | null;
  failure_reason: string | null;
  created_at: string;
  created_by: number | null;
}

export interface EvidenceRow {
  id: number;
  purpose: string;
  level: string | null;
  reuse: EvidenceReuse;
  reuse_label: string;
  source_candidate_version_id: number | null;
  rationale: string;
  ruleset_version: string;
  superseded_by_id: number | null;
  created_at: string;
  assessed_by: number | null;
}

export interface ReportRow {
  id: number;
  title: string;
  version_label: string;
  candidate_version_id: number;
  version_checksum: string;
  content_checksum: string;
  format: string;
  generated_at: string;
  generated_by: number | null;
}

export interface ExportRow {
  id: number;
  format: string;
  version_label: string;
  candidate_version_id: number;
  version_checksum: string;
  content_checksum: string;
  purpose_note: string | null;
  generated_at: string;
  generated_by: number | null;
}

export interface PackageRow {
  id: number;
  package_code: string;
  recipient_name: string;
  quotation_reference: string | null;
  version_label: string;
  candidate_version_id: number;
  version_checksum: string;
  content_checksum: string;
  generated_at: string;
  generated_by: number | null;
}

export interface StoredReport {
  report_id: number;
  candidate_id: number;
  candidate_version_id: number;
  version_label: string;
  version_checksum: string;
  title: string;
  format: string;
  content: Record<string, unknown>;
  content_checksum: string;
  generated_at: string;
  generated_by: number | null;
  /** Always false. Served from stored content, never re-rendered. */
  regenerated: boolean;
  historical: boolean;
  superseded_by_version_id: number | null;
  notice: string;
}

export interface VersionAuditRow {
  id: number;
  event: string;
  actor_id: number | null;
  candidate_id: number | null;
  candidate_version_id: number | null;
  experiment_id: number | null;
  reason: string | null;
  summary: string | null;
  created_at: string;
}

function hasKey<T>(key: string) {
  return (body: unknown): body is T =>
    typeof body === 'object' && body !== null && key in body;
}

/**
 * Candidate endpoints deliberately validate a stable identifying key rather
 * than every optional presentation field.  Keep that runtime policy while
 * adapting the predicate to the endpoint's complete declared response type;
 * otherwise a guard for `{report_id}` is incorrectly rejected for a response
 * that also carries version identity and checksums.
 */
function apiRequest<T>(
  path: string,
  init: RequestInit,
  isValid: (body: unknown) => boolean,
) {
  return rawApiRequest<T>(
    path, init, isValid as (body: unknown) => body is T,
  );
}

const BASE = '/api/v1/validation';

/* ------------------------------------------------------------------ *
 * History and comparison — reads. None of these locks anything.
 * ------------------------------------------------------------------ */

/** GET /api/v1/validation/candidates/{id}/versions */
export function getVersionHistory(candidateId: number, signal?: AbortSignal) {
  return apiRequest<VersionHistory>(
    `${BASE}/candidates/${candidateId}/versions`, { method: 'GET', signal },
    hasKey<VersionHistory>('versions'),
  );
}

/**
 * GET /api/v1/validation/candidate-versions/{a}/compare/{b}
 *
 * Browsing a comparison creates no scientific reliance and locks neither side.
 * Filing one as a record does — see `recordComparison`.
 */
export function compareVersions(leftId: number, rightId: number,
                                signal?: AbortSignal) {
  return apiRequest<VersionComparison>(
    `${BASE}/candidate-versions/${leftId}/compare/${rightId}`,
    { method: 'GET', signal }, hasKey<VersionComparison>('changed_fields'),
  );
}

/** GET /api/v1/validation/candidate-versions/{id}/dependents */
export function getDependents(versionId: number, signal?: AbortSignal) {
  return apiRequest<VersionDependents>(
    `${BASE}/candidate-versions/${versionId}/dependents`,
    { method: 'GET', signal }, hasKey<VersionDependents>('dependents'),
  );
}

/** GET /api/v1/validation/candidate-versions/{id}/audit */
export function getVersionAudit(versionId: number, signal?: AbortSignal) {
  return apiRequest<{ events: VersionAuditRow[]; total: number }>(
    `${BASE}/candidate-versions/${versionId}/audit`, { method: 'GET', signal },
    hasKey<{ events: VersionAuditRow[]; total: number }>('events'),
  );
}

/* ------------------------------------------------------------------ *
 * Revision, supersession and withdrawal
 * ------------------------------------------------------------------ */

/**
 * POST /api/v1/validation/candidate-versions/{id}/revise
 *
 * `reason` is required by the backend and by the form. It is the only part of
 * the record that explains why the formulation changed, and it is read by
 * people who were not there.
 */
export function reviseVersion(versionId: number, payload: {
  design_inputs?: Record<string, unknown> | null;
  reason: string;
  carry_results?: boolean;
  idempotency_key?: string;
}, signal?: AbortSignal) {
  return apiRequest<RevisionResult>(
    `${BASE}/candidate-versions/${versionId}/revise`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<RevisionResult>('consequence'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/propose-supersession */
export function proposeSupersession(versionId: number, payload: {
  successor_version_id: number; reason: string;
}, signal?: AbortSignal) {
  return apiRequest<CandidateVersionSummary & { notice: string }>(
    `${BASE}/candidate-versions/${versionId}/propose-supersession`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<CandidateVersionSummary>('supersession_state'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/supersede */
export function acceptSupersession(versionId: number, payload: {
  successor_version_id: number; reason: string;
  decision_id?: number | null; expected_revision?: number | null;
}, signal?: AbortSignal) {
  return apiRequest<{
    superseded: CandidateVersionSummary;
    successor_version_id: number;
    notice: string;
  }>(
    `${BASE}/candidate-versions/${versionId}/supersede`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ superseded: CandidateVersionSummary }>('superseded'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/refuse-supersession */
export function refuseSupersession(versionId: number, reason: string,
                                   signal?: AbortSignal) {
  return apiRequest<CandidateVersionSummary & { notice: string }>(
    `${BASE}/candidate-versions/${versionId}/refuse-supersession`,
    { method: 'POST', body: JSON.stringify({ reason }), signal },
    hasKey<CandidateVersionSummary>('supersession_state'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/withdraw */
export function withdrawVersion(versionId: number, reason: string,
                                signal?: AbortSignal) {
  return apiRequest<CandidateVersionSummary & { notice: string }>(
    `${BASE}/candidate-versions/${versionId}/withdraw`,
    { method: 'POST', body: JSON.stringify({ reason }), signal },
    hasKey<CandidateVersionSummary>('status'),
  );
}

/* ------------------------------------------------------------------ *
 * Version-bound artefacts. Every one of these locks the version.
 * ------------------------------------------------------------------ */

/** POST /api/v1/validation/candidate-versions/{id}/recalculate */
export function requestRecalculation(versionId: number, reason?: string,
                                     signal?: AbortSignal) {
  return apiRequest<CandidateVersionSummary & { notice: string }>(
    `${BASE}/candidate-versions/${versionId}/recalculate`,
    { method: 'POST', body: JSON.stringify({ reason: reason ?? null }), signal },
    hasKey<CandidateVersionSummary>('results_state'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/simulations */
export function recordSimulation(versionId: number, payload: {
  kind: string; engine_version: string; inputs: Record<string, unknown>;
  result?: Record<string, unknown> | null; failure_reason?: string | null;
  ruleset_version?: string | null;
}, signal?: AbortSignal) {
  return apiRequest<{
    simulation_id: number; candidate_version_id: number; state: string;
    version_locked: boolean; lock_reason: string | null;
    results_state: ResultsState; notice: string;
  }>(
    `${BASE}/candidate-versions/${versionId}/simulations`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ simulation_id: number }>('simulation_id'),
  );
}

/** GET /api/v1/validation/candidate-versions/{id}/simulations */
export function listSimulations(versionId: number, signal?: AbortSignal) {
  return apiRequest<{ simulations: SimulationRow[]; total: number }>(
    `${BASE}/candidate-versions/${versionId}/simulations`,
    { method: 'GET', signal },
    hasKey<{ simulations: SimulationRow[] }>('simulations'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/evidence */
export function recordEvidence(versionId: number, payload: {
  purpose: string; level?: string | null; reuse: EvidenceReuse;
  rationale: string; source_candidate_version_id?: number | null;
  considered_experiment_version_ids?: number[];
}, signal?: AbortSignal) {
  return apiRequest<{
    assessment_id: number; candidate_version_id: number;
    reuse: EvidenceReuse; reuse_label: string;
  }>(
    `${BASE}/candidate-versions/${versionId}/evidence`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ assessment_id: number }>('assessment_id'),
  );
}

/** GET /api/v1/validation/candidate-versions/{id}/evidence */
export function listEvidence(versionId: number, signal?: AbortSignal) {
  return apiRequest<{ assessments: EvidenceRow[]; total: number }>(
    `${BASE}/candidate-versions/${versionId}/evidence`,
    { method: 'GET', signal },
    hasKey<{ assessments: EvidenceRow[] }>('assessments'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/reports */
export function generateReport(versionId: number, payload: {
  title: string; body?: Record<string, unknown>; format?: string;
}, signal?: AbortSignal) {
  return apiRequest<{
    report_id: number; candidate_version_id: number; version_label: string;
    content_checksum: string; generated_at: string; notice: string;
  }>(
    `${BASE}/candidate-versions/${versionId}/reports`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ report_id: number }>('report_id'),
  );
}

/** GET /api/v1/validation/candidate-versions/{id}/reports */
export function listReports(versionId: number, signal?: AbortSignal) {
  return apiRequest<{ reports: ReportRow[]; total: number }>(
    `${BASE}/candidate-versions/${versionId}/reports`, { method: 'GET', signal },
    hasKey<{ reports: ReportRow[] }>('reports'),
  );
}

/**
 * GET /api/v1/validation/candidate-reports/{id}
 *
 * Serves the stored content. `regenerated` is always false, and the screen
 * shows it — a historical report has to say what it said when it was issued.
 */
export function readStoredReport(reportId: number, signal?: AbortSignal) {
  return apiRequest<StoredReport>(
    `${BASE}/candidate-reports/${reportId}`, { method: 'GET', signal },
    hasKey<StoredReport>('content'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/exports */
export function generateExport(versionId: number, payload: {
  format?: string; purpose_note?: string | null;
  payload?: Record<string, unknown> | null;
} = {}, signal?: AbortSignal) {
  return apiRequest<{
    export_id: number; candidate_version_id: number; version_label: string;
    content_checksum: string; manifest: Record<string, unknown>;
  }>(
    `${BASE}/candidate-versions/${versionId}/exports`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ export_id: number }>('export_id'),
  );
}

/** GET /api/v1/validation/candidate-versions/{id}/exports */
export function listExports(versionId: number, signal?: AbortSignal) {
  return apiRequest<{ exports: ExportRow[]; total: number }>(
    `${BASE}/candidate-versions/${versionId}/exports`, { method: 'GET', signal },
    hasKey<{ exports: ExportRow[] }>('exports'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/cro-packages */
export function generateCroPackage(versionId: number, payload: {
  recipient_name: string; package_code: string;
  quotation_reference?: string | null; scope_note?: string | null;
}, signal?: AbortSignal) {
  return apiRequest<{
    package_id: number; package_code: string; candidate_version_id: number;
    version_label: string; content_checksum: string;
    manifest: Record<string, unknown>;
  }>(
    `${BASE}/candidate-versions/${versionId}/cro-packages`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ package_id: number }>('package_id'),
  );
}

/** GET /api/v1/validation/candidate-versions/{id}/cro-packages */
export function listCroPackages(versionId: number, signal?: AbortSignal) {
  return apiRequest<{ packages: PackageRow[]; total: number }>(
    `${BASE}/candidate-versions/${versionId}/cro-packages`,
    { method: 'GET', signal }, hasKey<{ packages: PackageRow[] }>('packages'),
  );
}

/** POST /api/v1/validation/candidate-versions/{id}/comparisons */
export function recordComparison(versionId: number, payload: {
  other_version_id: number; note?: string | null;
}, signal?: AbortSignal) {
  return apiRequest<{
    comparison_id: number; left_version_id: number; right_version_id: number;
    changed_fields: FieldChange[]; consequence: ChangeConsequence;
    material_classification: MaterialClassification; notice: string;
  }>(
    `${BASE}/candidate-versions/${versionId}/comparisons`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ comparison_id: number }>('comparison_id'),
  );
}
