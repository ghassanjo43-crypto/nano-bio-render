/**
 * Typed client for the NanoBio Studio scoring API.
 *
 * Design rule: this module NEVER invents a score. Every failure path returns a
 * structured error, so the UI cannot accidentally render a fabricated or
 * defaulted number when the backend did not produce one.
 */

import type {
  ApiResult,
  ComparisonResponse,
  DemoResetResponse,
  DemoScenarioDetail,
  DemoScenarioListResponse,
  DesignScoreRequest,
  DesignScoreResponse,
  EngineNotRun,
  PKErrorResponse,
  PKResult,
  AdministrationRouteListResponse,
  PKSimulationRequest,
  RunPlanResponse,
  PKSimulationResponse,
  ProjectListResponse,
  ProjectSummary,
  RunDetail,
  RunListResponse,
  ConfirmedField,
  DeidentifyResponse,
  FieldProvenance,
  ReportAssessmentDetail,
  ReportAssessmentListResponse,
  ReportUploadResponse,
  ScoreErrorResponse,
  ScoreResult,
  SyntheticReportListResponse,
} from './types';

/**
 * Prefix for API requests. Empty means same-origin.
 *
 * The default is deliberately empty rather than an absolute backend URL: an
 * absolute URL to a different host makes every request cross-site, and the
 * SameSite=Lax session cookie is then accepted on the login response but never
 * sent afterwards — signing the user out the instant they sign in. The dev
 * server proxies /api, /health and /ready (see vite.config.ts), so same-origin
 * is both correct and sufficient.
 */
export const API_BASE_URL: string =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? '';

/* ------------------------------------------------------------------------ */
/* Session-expiry notification                                               */
/* ------------------------------------------------------------------------ */
/*
 * Sessions have a 30-minute idle timeout. Without this hook the application
 * kept showing a cached user as signed in while every request returned 401, so
 * a user who had stepped away saw "Sign in to continue." inside a page they
 * appeared to be signed into, with no way to recover but a manual reload.
 *
 * Any 401 from a data endpoint now notifies the auth layer, which re-checks the
 * session and lands the user on the login page with an explanation.
 *
 * Deliberately a plain callback rather than a React import: this module must
 * stay framework-free and independently testable. `api/auth.ts` is NOT wired in
 * here — its own 401 during the initial "who am I" check is the normal
 * logged-out path, and routing it through this hook would loop.
 */
type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

/** Register the handler invoked when a data request is rejected as 401. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

function notifyUnauthorized(status: number): void {
  if (status === 401 && unauthorizedHandler) unauthorizedHandler();
}

/**
 * Coerce an error `detail` to something React can actually render.
 *
 * FastAPI's `HTTPException(detail={...})` serialises to a nested OBJECT, e.g.
 * the 401 from `get_current_user`:
 *
 *     {"detail": {"error": "not_authenticated", "message": "Sign in to continue."}}
 *
 * Passing that through unchecked put an object where a string was declared, and
 * any component rendering `{error.detail}` crashed the whole page with
 * "Objects are not valid as a React child". The TypeScript annotation could not
 * catch it: the value crosses the network as `unknown`.
 *
 * Every value entering `detail` now goes through here, so the declared type is
 * enforced at the boundary rather than merely asserted.
 */
function normaliseDetail(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') return value || null;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    const parts = value.map(normaliseDetail).filter(Boolean);
    return parts.length ? parts.join('; ') : null;
  }
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;
    // The platform's own structured-error shape reads best as its message.
    if (typeof record.message === 'string') return record.message;
    try {
      return JSON.stringify(value).slice(0, 500);
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Pull a machine code and human message out of an error body.
 *
 * Handles both shapes the backend produces: the flat structured errors the
 * routes return deliberately, and FastAPI's `{"detail": ...}` envelope from a
 * raised `HTTPException`.
 */
function readErrorBody(body: unknown, status: number): {
  code: string; message: string; detail: string | null;
} {
  const record = (typeof body === 'object' && body !== null)
    ? body as Record<string, unknown> : {};

  const envelope = (typeof record.detail === 'object' && record.detail !== null
                    && !Array.isArray(record.detail))
    ? record.detail as Record<string, unknown> : null;

  const code = typeof record.error === 'string' ? record.error
    : typeof envelope?.error === 'string' ? envelope.error
    : status === 401 ? 'not_authenticated'
    : 'unexpected_error';

  const message = typeof record.message === 'string' ? record.message
    : typeof envelope?.message === 'string' ? envelope.message
    : status === 401
      ? 'Your session is not valid for this page. Sign in to continue.'
      : `The service returned HTTP ${status}.`;

  // When the envelope supplied the message there is no separate detail to add.
  const detail = envelope ? null : normaliseDetail(record.detail);

  return { code, message, detail };
}

function isErrorBody(body: unknown): body is ScoreErrorResponse {
  return (
    typeof body === 'object' &&
    body !== null &&
    'error' in body &&
    'message' in body
  );
}

function isScoreBody(body: unknown): body is DesignScoreResponse {
  return (
    typeof body === 'object' &&
    body !== null &&
    'design_impact_score' in body &&
    'component_scores' in body
  );
}

/** POST /api/v1/design/score */
export async function scoreDesign(
  request: DesignScoreRequest,
  signal?: AbortSignal,
): Promise<ScoreResult> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/api/v1/design/score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // Send the HttpOnly session cookie; the scoring endpoint is protected.
      credentials: 'include',
      body: JSON.stringify(request),
      signal,
    });
  } catch (cause) {
    return {
      status: 'error',
      error: {
        error: 'network_error',
        message:
          'Could not reach the scoring service. Check that the backend is '
          + 'running.',
        detail: cause instanceof Error ? cause.message : String(cause),
        score_available: false,
      },
    };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return {
      status: 'error',
      error: {
        error: 'invalid_response',
        message: 'The scoring service returned a response that was not JSON.',
        detail: `HTTP ${response.status}`,
        score_available: false,
      },
    };
  }

  if (!response.ok) {
    notifyUnauthorized(response.status);
    // `readErrorBody` also normalises `detail`: a raised HTTPException carries
    // an object there, which would crash any component rendering it.
    const { code, message, detail } = readErrorBody(body, response.status);
    return {
      status: 'error',
      error: {
        error: isErrorBody(body) ? body.error : code,
        message: isErrorBody(body) ? body.message : message,
        detail: isErrorBody(body) ? normaliseDetail(body.detail) : detail,
        score_available: false,
      },
    };
  }

  // A 200 that does not carry a score is treated as a failure, never as a
  // reason to display a placeholder.
  if (!isScoreBody(body)) {
    return {
      status: 'error',
      error: {
        error: 'unexpected_response_shape',
        message:
          'The scoring service returned a success status without a score.',
        detail: JSON.stringify(body).slice(0, 500),
        score_available: false,
      },
    };
  }

  return { status: 'ok', data: body };
}

function isPkErrorBody(body: unknown): body is PKErrorResponse {
  return (
    typeof body === 'object' &&
    body !== null &&
    'error' in body &&
    'message' in body
  );
}

/**
 * A 200 only counts as a profile when it actually carries one. A response
 * without both the curve and the derived parameters is treated as a failure,
 * never as a reason to draw an empty or placeholder chart.
 */
function isPkBody(body: unknown): body is PKSimulationResponse {
  if (typeof body !== 'object' || body === null) return false;
  if (!('concentration_time' in body) || !('pk_parameters' in body)) return false;
  const series = (body as PKSimulationResponse).concentration_time;
  return (
    typeof series === 'object' &&
    series !== null &&
    Array.isArray(series.time_h) &&
    Array.isArray(series.central_plasma) &&
    Array.isArray(series.peripheral_tissue) &&
    series.time_h.length > 0 &&
    series.central_plasma.length === series.time_h.length &&
    series.peripheral_tissue.length === series.time_h.length
  );
}

/**
 * POST /api/v1/pk/simulate
 *
 * Same rule as `scoreDesign`: this never invents a profile. Every failure path
 * returns a structured error so the UI cannot render a fabricated curve,
 * half-life or AUC.
 */
export async function simulatePk(
  request: PKSimulationRequest,
  signal?: AbortSignal,
): Promise<PKResult> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/api/v1/pk/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(request),
      signal,
    });
  } catch (cause) {
    return {
      status: 'error',
      error: {
        error: 'network_error',
        message:
          'Could not reach the simulation service. Check that the backend is '
          + 'running.',
        detail: cause instanceof Error ? cause.message : String(cause),
        results_available: false,
      },
    };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return {
      status: 'error',
      error: {
        error: 'invalid_response',
        message: 'The simulation service returned a response that was not JSON.',
        detail: `HTTP ${response.status}`,
        results_available: false,
      },
    };
  }

  if (!response.ok) {
    notifyUnauthorized(response.status);
    const { code, message, detail } = readErrorBody(body, response.status);
    return {
      status: 'error',
      error: {
        error: isPkErrorBody(body) ? body.error : code,
        message: isPkErrorBody(body) ? body.message : message,
        detail: isPkErrorBody(body) ? normaliseDetail(body.detail) : detail,
        results_available: false,
      },
    };
  }

  if (!isPkBody(body)) {
    return {
      status: 'error',
      error: {
        error: 'unexpected_response_shape',
        message:
          'The simulation service returned a success status without a '
          + 'complete concentration–time profile.',
        detail: JSON.stringify(body).slice(0, 500),
        results_available: false,
      },
    };
  }

  return { status: 'ok', data: body };
}

/** GET /health — used for the connection indicator. */
export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE_URL}/health`, { signal, credentials: 'include' });
    return r.ok;
  } catch {
    return false;
  }
}

/* ========================================================================= */
/* Workspace: demo scenarios, stored runs, projects, comparison              */
/* ========================================================================= */

/**
 * Shared JSON request helper for the workspace endpoints.
 *
 * Same rule as the scientific endpoints: every failure path returns a
 * structured error, so a caller can never read data off a failed request. A 200
 * whose body fails the caller's shape check is treated as a failure too.
 */
async function apiRequest<T>(
  path: string,
  init: RequestInit,
  isValid: (body: unknown) => body is T,
): Promise<ApiResult<T>> {
  let response: Response;
  // FormData must NOT carry an explicit Content-Type: the browser has to set it
  // itself so the multipart boundary is included. Forcing application/json here
  // would make every file upload unparseable server-side.
  const isMultipart = typeof FormData !== 'undefined'
    && init.body instanceof FormData;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: 'include',
      headers: (init.body && !isMultipart)
        ? { 'Content-Type': 'application/json' }
        : undefined,
      ...init,
    });
  } catch (cause) {
    return {
      status: 'error',
      error: {
        error: 'network_error',
        message:
          'Could not reach the service. Check that the backend is running.',
        detail: cause instanceof Error ? cause.message : String(cause),
        data_available: false,
      },
    };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return {
      status: 'error',
      error: {
        error: 'invalid_response',
        message: 'The service returned a response that was not JSON.',
        detail: `HTTP ${response.status}`,
        data_available: false,
      },
    };
  }

  if (!response.ok) {
    notifyUnauthorized(response.status);
    const { code, message, detail } = readErrorBody(body, response.status);
    return {
      status: 'error',
      error: { error: code, message, detail, data_available: false },
    };
  }

  if (!isValid(body)) {
    return {
      status: 'error',
      error: {
        error: 'unexpected_response_shape',
        message: 'The service returned a success status without the expected data.',
        detail: JSON.stringify(body).slice(0, 500),
        data_available: false,
      },
    };
  }

  return { status: 'ok', data: body };
}

const hasKeys = <T>(...keys: string[]) => (body: unknown): body is T =>
  typeof body === 'object' && body !== null && keys.every((k) => k in body);

/** GET /api/v1/demo/scenarios */
export function listScenarios(signal?: AbortSignal) {
  return apiRequest<DemoScenarioListResponse>(
    '/api/v1/demo/scenarios', { method: 'GET', signal },
    hasKeys<DemoScenarioListResponse>('scenarios', 'fixture_version'),
  );
}

/** GET /api/v1/demo/scenarios/{slug} */
export function getScenario(slug: string, signal?: AbortSignal) {
  return apiRequest<DemoScenarioDetail>(
    `/api/v1/demo/scenarios/${encodeURIComponent(slug)}`, { method: 'GET', signal },
    hasKeys<DemoScenarioDetail>('slug', 'design_inputs', 'pk_inputs'),
  );
}

/** POST /api/v1/demo/reset */
export function resetDemoData(
  body: { confirm: boolean; include_templates?: boolean; mine_only?: boolean },
) {
  return apiRequest<DemoResetResponse>(
    '/api/v1/demo/reset',
    { method: 'POST', body: JSON.stringify({ mine_only: true, ...body }) },
    hasKeys<DemoResetResponse>('confirmed', 'demo_runs', 'message'),
  );
}

export interface StoreRunBody {
  name: string;
  disease?: string | null;
  subtype?: string | null;
  drug?: string | null;
  design_inputs?: DesignScoreRequest | null;
  pk_inputs?: PKSimulationRequest | null;
  design_result?: DesignScoreResponse | null;
  pk_result?: PKSimulationResponse | null;
  engines_not_run?: EngineNotRun[];
  project_id?: number | null;
  is_demo?: boolean;
  demo_scenario_slug?: string | null;
  /**
   * How the study began. Recorded so the workspace lists can distinguish a
   * patient assessment from a research design without inferring it.
   */
  pathway?: 'patient_assessment' | 'research_design' | 'demo_scenario';
  research_purpose?: string | null;
  report_assessment_id?: number | null;
}

/** POST /api/v1/runs */
export function storeRun(body: StoreRunBody) {
  return apiRequest<RunDetail>(
    '/api/v1/runs', { method: 'POST', body: JSON.stringify(body) },
    hasKeys<RunDetail>('id', 'status', 'engines_run'),
  );
}

/** GET /api/v1/runs */
export function listRuns(
  filters: { origin?: string; pathway?: string; disease?: string;
             scenario?: string; status?: string; project_id?: number } = {},
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
  }
  const query = params.toString();
  return apiRequest<RunListResponse>(
    `/api/v1/runs${query ? `?${query}` : ''}`, { method: 'GET', signal },
    hasKeys<RunListResponse>('runs', 'total'),
  );
}

/** GET /api/v1/runs/{id} */
export function getRun(id: number, signal?: AbortSignal) {
  return apiRequest<RunDetail>(
    `/api/v1/runs/${id}`, { method: 'GET', signal },
    hasKeys<RunDetail>('id', 'status'),
  );
}

/** DELETE /api/v1/runs/{id} */
export function deleteRun(id: number) {
  return apiRequest<{ deleted: boolean; id: number; name: string }>(
    `/api/v1/runs/${id}`, { method: 'DELETE' },
    hasKeys('deleted', 'id'),
  );
}

/** GET /api/v1/runs/compare/select */
export function compareRuns(ids: number[], signal?: AbortSignal) {
  return apiRequest<ComparisonResponse>(
    `/api/v1/runs/compare/select?ids=${ids.join(',')}`, { method: 'GET', signal },
    hasKeys<ComparisonResponse>('runs', 'rows', 'notice'),
  );
}

/** GET /api/v1/projects */
export function listProjects(signal?: AbortSignal) {
  return apiRequest<ProjectListResponse>(
    '/api/v1/projects', { method: 'GET', signal },
    hasKeys<ProjectListResponse>('projects', 'total'),
  );
}

/** POST /api/v1/projects */
export function createProject(body: { name: string; description?: string | null }) {
  return apiRequest<ProjectSummary>(
    '/api/v1/projects', { method: 'POST', body: JSON.stringify(body) },
    hasKeys<ProjectSummary>('id', 'name'),
  );
}

/** DELETE /api/v1/projects/{id} */
export function deleteProject(id: number) {
  return apiRequest<{ deleted: boolean; id: number; runs_preserved: boolean }>(
    `/api/v1/projects/${id}`, { method: 'DELETE' },
    hasKeys('deleted', 'id'),
  );
}

/** POST /api/v1/runs/{id}/project */
export function assignRunToProject(runId: number, projectId: number | null) {
  const query = projectId === null ? '' : `?project_id=${projectId}`;
  return apiRequest<RunDetail>(
    `/api/v1/runs/${runId}/project${query}`, { method: 'POST' },
    hasKeys<RunDetail>('id', 'status'),
  );
}

/* ========================================================================= */
/* Medical Report Assessment                                                 */
/* ========================================================================= */
/*
 * None of these responses may be persisted client-side. Report content is held
 * in component state only and re-fetched when needed; a test asserts nothing
 * report-related reaches localStorage or sessionStorage.
 */

/** GET /api/v1/reports/synthetic */
export function listSyntheticReports(signal?: AbortSignal) {
  return apiRequest<SyntheticReportListResponse>(
    '/api/v1/reports/synthetic', { method: 'GET', signal },
    hasKeys<SyntheticReportListResponse>('reports', 'fixture_version'),
  );
}

/** POST /api/v1/reports/synthetic/{slug} — runs the real upload pipeline. */
export function loadSyntheticReport(slug: string) {
  return apiRequest<ReportUploadResponse>(
    `/api/v1/reports/synthetic/${encodeURIComponent(slug)}`, { method: 'POST' },
    hasKeys<ReportUploadResponse>('assessment_id', 'extraction'),
  );
}

/**
 * POST /api/v1/reports — multipart upload.
 *
 * `attested` is the user's positive declaration that the document contains no
 * real patient information. The server refuses the upload without it; this is
 * not a client-side courtesy check.
 */
export function uploadReport(
  file: File,
  classification: 'synthetic' | 'deidentified' | 'real_patient_data',
  attested: boolean,
) {
  const form = new FormData();
  form.append('file', file);
  form.append('classification', classification);
  form.append('attested', String(attested));
  // No Content-Type header: the browser must set the multipart boundary.
  return apiRequest<ReportUploadResponse>(
    '/api/v1/reports', { method: 'POST', body: form },
    hasKeys<ReportUploadResponse>('assessment_id', 'extraction'),
  );
}

/** GET /api/v1/reports */
export function listReportAssessments(signal?: AbortSignal) {
  return apiRequest<ReportAssessmentListResponse>(
    '/api/v1/reports', { method: 'GET', signal },
    hasKeys<ReportAssessmentListResponse>('assessments', 'policy_statement'),
  );
}

/** GET /api/v1/reports/{id} */
export function getReportAssessment(id: number, signal?: AbortSignal) {
  return apiRequest<ReportAssessmentDetail>(
    `/api/v1/reports/${id}`, { method: 'GET', signal },
    hasKeys<ReportAssessmentDetail>('id', 'clinical_fields'),
  );
}

/** POST /api/v1/reports/{id}/confirm */
export function confirmReportFields(
  id: number,
  fields: Array<Partial<ConfirmedField> & { key: string; provenance: FieldProvenance }>,
) {
  return apiRequest<ReportAssessmentDetail>(
    `/api/v1/reports/${id}/confirm`,
    { method: 'POST', body: JSON.stringify({ fields }) },
    hasKeys<ReportAssessmentDetail>('id', 'status'),
  );
}

/** POST /api/v1/reports/{id}/map */
export function mapReportToWorkflow(
  id: number, body: { disease: string; subtype: string; drug: string },
) {
  return apiRequest<ReportAssessmentDetail>(
    `/api/v1/reports/${id}/map`,
    { method: 'POST', body: JSON.stringify(body) },
    hasKeys<ReportAssessmentDetail>('id', 'status'),
  );
}

/** POST /api/v1/reports/{id}/deidentify */
export function deidentifyReport(id: number) {
  return apiRequest<DeidentifyResponse>(
    `/api/v1/reports/${id}/deidentify`, { method: 'POST' },
    hasKeys<DeidentifyResponse>('text', 'limitations'),
  );
}

/** DELETE /api/v1/reports/{id} */
export function deleteReportAssessment(id: number) {
  return apiRequest<{ deleted: boolean; id: number }>(
    `/api/v1/reports/${id}`, { method: 'DELETE' },
    hasKeys('deleted', 'id'),
  );
}


/* ==========================================================================
 * Route-aware pharmacokinetics
 * ========================================================================== */

/** GET /api/v1/pk/administration-routes */
export function getAdministrationRoutes(signal?: AbortSignal) {
  return apiRequest<AdministrationRouteListResponse>(
    '/api/v1/pk/administration-routes', { method: 'GET', signal },
    hasKeys<AdministrationRouteListResponse>('routes', 'notice'),
  );
}

/**
 * GET /api/v1/pk/plan
 *
 * The plan decides which inputs apply, whether the combination can run at all,
 * and where every value comes from. The client computes none of this.
 */
export function getRunPlan(
  params: { therapeutic: string; route: string; mode?: string },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({
    therapeutic: params.therapeutic,
    route: params.route,
    mode: params.mode ?? 'guided',
  });
  return apiRequest<RunPlanResponse>(
    `/api/v1/pk/plan?${query.toString()}`, { method: 'GET', signal },
    hasKeys<RunPlanResponse>('runnable', 'inputs', 'route'),
  );
}
