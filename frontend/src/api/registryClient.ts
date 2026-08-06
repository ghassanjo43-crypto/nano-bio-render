/**
 * Typed client for the Experimental Validation Registry.
 *
 * Every function here is a transport. **None of them decides eligibility.**
 * E3 is granted by the backend evaluator and this module only carries the
 * verdict — a client-side rule would be a second, divergent opinion about what
 * counts as evidence, which is the exact failure the registry exists to
 * prevent.
 *
 * Reuses `apiRequest` from `client.ts` so the registry shares one 401 handler,
 * one error shape and one definition of a trustworthy response.
 */

import { apiRequest } from './client';
import type {
  AuditEventRow, EligibilityVerdict, ExperimentDetail, ExperimentSummary,
  MeasurementRow, VersionDetail,
} from '../pages/validation/registryTypes';

export interface RegistryFilters {
  study_id?: number;
  project_id?: number;
  candidate_id?: number;
  subtype?: string;
  purpose?: string;
  status?: string;
  laboratory?: string;
  investigator?: string;
  reviewer_id?: number;
  e3_eligible?: boolean;
}

function toQuery(filters: RegistryFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue;
    params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

function hasKey<T>(key: string) {
  return (body: unknown): body is T =>
    typeof body === 'object' && body !== null && key in body;
}

export interface ExperimentListResponse {
  experiments: ExperimentSummary[];
  total: number;
}

export interface RegistryDashboard {
  study_id: number | null;
  total_experiments: number;
  by_status: Record<string, number>;
  by_purpose: Record<string, number>;
  approved_by_purpose: Record<string, number>;
  purposes_with_e3: string[];
  purposes_with_contradiction: string[];
  registry_version: string;
}

/** GET /api/v1/validation/experiments */
export function listExperiments(filters: RegistryFilters = {},
                                signal?: AbortSignal) {
  return apiRequest<ExperimentListResponse>(
    `/api/v1/validation/experiments${toQuery(filters)}`,
    { method: 'GET', signal },
    hasKey<ExperimentListResponse>('experiments'),
  );
}

/** GET /api/v1/validation/dashboard */
export function getRegistryDashboard(studyId?: number, signal?: AbortSignal) {
  const query = studyId === undefined ? '' : `?study_id=${studyId}`;
  return apiRequest<RegistryDashboard>(
    `/api/v1/validation/dashboard${query}`, { method: 'GET', signal },
    hasKey<RegistryDashboard>('by_status'),
  );
}

/** GET /api/v1/validation/vocabulary */
export function getRegistryVocabulary(signal?: AbortSignal) {
  return apiRequest<Record<string, unknown>>(
    '/api/v1/validation/vocabulary', { method: 'GET', signal },
    hasKey<Record<string, unknown>>('subtypes'),
  );
}

/** GET /api/v1/validation/experiments/{id} */
export function getExperiment(experimentId: number, signal?: AbortSignal) {
  return apiRequest<ExperimentDetail>(
    `/api/v1/validation/experiments/${experimentId}`,
    { method: 'GET', signal }, hasKey<ExperimentDetail>('experiment'),
  );
}

/** POST /api/v1/validation/experiments */
export function createExperiment(payload: {
  candidate_version_id: number; subtype: string; purpose: string;
  title: string; code?: string; performed_by?: number;
}, signal?: AbortSignal) {
  return apiRequest<{ experiment_id: number; version_id: number }>(
    '/api/v1/validation/experiments',
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ experiment_id: number; version_id: number }>('experiment_id'),
  );
}

/** PATCH /api/v1/validation/versions/{id} */
export function updateDraft(versionId: number,
                            fields: Record<string, unknown>,
                            signal?: AbortSignal) {
  return apiRequest<{ version_id: number; updated: string[] }>(
    `/api/v1/validation/versions/${versionId}`,
    { method: 'PATCH', body: JSON.stringify(fields), signal },
    hasKey<{ version_id: number; updated: string[] }>('version_id'),
  );
}

/** GET /api/v1/validation/versions/{id} */
export function getVersion(versionId: number, signal?: AbortSignal) {
  return apiRequest<VersionDetail>(
    `/api/v1/validation/versions/${versionId}`, { method: 'GET', signal },
    hasKey<VersionDetail>('id'),
  );
}

/** POST /api/v1/validation/versions/{id}/measurements */
export function addMeasurements(versionId: number, rows: MeasurementRow[],
                                signal?: AbortSignal) {
  return apiRequest<{ recorded: number }>(
    `/api/v1/validation/versions/${versionId}/measurements`,
    { method: 'POST', body: JSON.stringify({ rows }), signal },
    hasKey<{ recorded: number }>('recorded'),
  );
}

/** POST /api/v1/validation/versions/{id}/submit */
export function submitVersion(versionId: number, signal?: AbortSignal) {
  return apiRequest<{ status: string }>(
    `/api/v1/validation/versions/${versionId}/submit`,
    { method: 'POST', signal }, hasKey<{ status: string }>('status'),
  );
}

/** POST /api/v1/validation/versions/{id}/review */
export function startReview(versionId: number, signal?: AbortSignal) {
  return apiRequest<{ status: string }>(
    `/api/v1/validation/versions/${versionId}/review`,
    { method: 'POST', signal }, hasKey<{ status: string }>('status'),
  );
}

/** POST /api/v1/validation/versions/{id}/decision */
export function recordDecision(versionId: number, decision: string,
                               comments: string, signal?: AbortSignal) {
  return apiRequest<{ status: string; eligibility: EligibilityVerdict | null }>(
    `/api/v1/validation/versions/${versionId}/decision`,
    { method: 'POST', body: JSON.stringify({ decision, comments }), signal },
    hasKey<{ status: string; eligibility: EligibilityVerdict | null }>('status'),
  );
}

/** POST /api/v1/validation/versions/{id}/revision */
export function createRevision(versionId: number,
                               candidateVersionId?: number,
                               signal?: AbortSignal) {
  return apiRequest<{ version_id: number; version_number: number }>(
    `/api/v1/validation/versions/${versionId}/revision`,
    {
      method: 'POST',
      body: JSON.stringify({ candidate_version_id: candidateVersionId ?? null }),
      signal,
    },
    hasKey<{ version_id: number; version_number: number }>('version_id'),
  );
}

/** GET /api/v1/validation/versions/{id}/eligibility */
export function getEligibility(versionId: number, signal?: AbortSignal) {
  return apiRequest<EligibilityVerdict>(
    `/api/v1/validation/versions/${versionId}/eligibility`,
    { method: 'GET', signal }, hasKey<EligibilityVerdict>('gates'),
  );
}

export interface StudyEvidenceResponse {
  study_id: number;
  by_purpose: Record<string, {
    purpose: string;
    level: string | null;
    experiments: Array<Record<string, unknown>>;
    contradiction: string | null;
    ruleset_versions?: string[];
  }>;
  registry_version: string;
}

/** GET /api/v1/validation/studies/{id}/evidence */
export function getStudyEvidence(studyId: number, signal?: AbortSignal) {
  return apiRequest<StudyEvidenceResponse>(
    `/api/v1/validation/studies/${studyId}/evidence`,
    { method: 'GET', signal }, hasKey<StudyEvidenceResponse>('by_purpose'),
  );
}

/** GET /api/v1/validation/experiments/{id}/audit */
export function getAuditHistory(experimentId: number, signal?: AbortSignal) {
  return apiRequest<{ events: AuditEventRow[]; total: number }>(
    `/api/v1/validation/experiments/${experimentId}/audit`,
    { method: 'GET', signal },
    hasKey<{ events: AuditEventRow[]; total: number }>('events'),
  );
}

export interface CandidateRow {
  id: number;
  code: string;
  name: string;
  description: string | null;
  versions: Array<{
    id: number; version_number: number; checksum: string;
    note: string | null; created_at: string;
  }>;
}

/** GET /api/v1/validation/studies/{id}/candidates */
export function listCandidates(studyId: number, signal?: AbortSignal) {
  return apiRequest<{ candidates: CandidateRow[] }>(
    `/api/v1/validation/studies/${studyId}/candidates`,
    { method: 'GET', signal }, hasKey<{ candidates: CandidateRow[] }>('candidates'),
  );
}

/** POST /api/v1/validation/candidates/{id}/versions */
export function createCandidateVersion(candidateId: number,
                                       designInputs: Record<string, unknown>,
                                       note?: string, signal?: AbortSignal) {
  return apiRequest<{ id: number; version_number: number; checksum: string }>(
    `/api/v1/validation/candidates/${candidateId}/versions`,
    {
      method: 'POST',
      body: JSON.stringify({ design_inputs: designInputs, note: note ?? null }),
      signal,
    },
    hasKey<{ id: number; version_number: number; checksum: string }>('id'),
  );
}

/**
 * POST /api/v1/validation/versions/{id}/attachments
 *
 * Sent as multipart so the browser sets the boundary; no Content-Type is
 * supplied here. The backend re-derives the type from the bytes regardless —
 * a declared type is a claim, not a fact.
 */
export function uploadAttachment(versionId: number, category: string,
                                 file: File, signal?: AbortSignal) {
  const form = new FormData();
  form.append('file', file);
  return apiRequest<{ id: number; checksum_sha256: string }>(
    `/api/v1/validation/versions/${versionId}/attachments`
    + `?category=${encodeURIComponent(category)}`,
    { method: 'POST', body: form, signal },
    hasKey<{ id: number; checksum_sha256: string }>('id'),
  );
}

/** DELETE /api/v1/validation/attachments/{id} */
export function deleteAttachment(attachmentId: number, signal?: AbortSignal) {
  return apiRequest<{ removed: number }>(
    `/api/v1/validation/attachments/${attachmentId}`,
    { method: 'DELETE', signal }, hasKey<{ removed: number }>('removed'),
  );
}

/** The download URL. Addressed by id; no filesystem path is ever exposed. */
export function attachmentDownloadUrl(attachmentId: number): string {
  return `/api/v1/validation/attachments/${attachmentId}`;
}

/** POST /api/v1/validation/candidates */
export function createCandidate(payload: {
  study_id: number; code: string; name: string; description?: string;
}, signal?: AbortSignal) {
  return apiRequest<{ id: number; code: string; name: string }>(
    '/api/v1/validation/candidates',
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<{ id: number; code: string; name: string }>('id'),
  );
}

export interface ContradictionResolutionRow {
  id: number;
  purpose: string;
  resolved_level: string | null;
  rationale: string;
  resolved_by: number | null;
  resolved_at: string;
  considered_version_ids: string;
  superseded_by_id: number | null;
}

/** POST /api/v1/validation/studies/{id}/contradictions */
export function resolveContradiction(studyId: number, payload: {
  purpose: string; rationale: string; resolved_level?: string | null;
  candidate_version_id?: number | null;
}, signal?: AbortSignal) {
  return apiRequest<ContradictionResolutionRow>(
    `/api/v1/validation/studies/${studyId}/contradictions`,
    { method: 'POST', body: JSON.stringify(payload), signal },
    hasKey<ContradictionResolutionRow>('id'),
  );
}

/** GET /api/v1/validation/studies/{id}/contradictions */
export function listResolutions(studyId: number, signal?: AbortSignal) {
  return apiRequest<{ resolutions: ContradictionResolutionRow[] }>(
    `/api/v1/validation/studies/${studyId}/contradictions`,
    { method: 'GET', signal },
    hasKey<{ resolutions: ContradictionResolutionRow[] }>('resolutions'),
  );
}
