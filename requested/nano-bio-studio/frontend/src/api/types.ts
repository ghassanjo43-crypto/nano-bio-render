/**
 * Types mirroring the FastAPI contract for POST /api/v1/design/score.
 *
 * These are hand-maintained against the backend Pydantic schemas. Generating
 * them from the OpenAPI document is a follow-up (see docs/VERTICAL_SLICE.md).
 */

/**
 * Request body for POST /api/v1/design/score.
 *
 * Mirrors the backend Pydantic schema exactly. Required fields are never
 * defaulted by the client; optional fields are OMITTED when blank so the
 * scientific engine applies its own documented defaults. Sending `null` is
 * equivalent to omitting (the DEFECT-D9 null contract).
 */
export interface DesignScoreRequest {
  /** Required. Core particle diameter, nm. */
  size_nm: number;
  /** Required. Zeta potential, mV. */
  charge_mv: number;
  /** Required. Encapsulation efficiency, %. */
  encapsulation_percent: number;

  pdi?: number | null;
  hydrodynamic_size_nm?: number | null;
  stability_percent?: number | null;
  surface_area_nm2?: number | null;
  degradation_time_days?: number | null;
  crystallinity_index?: number | null;
  hydrophobicity_logp?: number | null;
  coating_thickness_nm?: number | null;
  ligand_density_percent?: number | null;
  receptor_binding_kd_nm?: number | null;
  release_predictability_percent?: number | null;

  ligand?: string | null;
  surface_coating?: string[] | null;
  functional_groups?: string[] | null;
}

/**
 * The three canonical outputs of `core.scoring.compute_impact`.
 *
 * Deliberately NOT a single composite number: the candidate replacement
 * "Overall Score" is documented but not implemented pending scientific review.
 */
export interface DesignImpactScore {
  delivery: number;
  toxicity: number;
  cost: number;
}

export interface ComponentScore {
  value: number;
  scale: string;
  meaning: string;
}

export interface DesignScoreResponse {
  design_impact_score: DesignImpactScore;
  score_version: string;
  component_scores: Record<string, ComponentScore>;
  normalized_inputs: Record<string, unknown>;
  warnings: string[];
  prediction_basis: string;
  evidence_level: string;
  validation_status: string;
  limitations: string[];
  scientific_source: string;
}

/**
 * Structured failure. Note there is no score field: a failed calculation never
 * produces a number, favourable or otherwise.
 */
export interface ScoreErrorResponse {
  error: string;
  message: string;
  detail?: string | null;
  score_available: false;
}

/** Discriminated result so callers cannot read a score off a failure. */
export type ScoreResult =
  | { status: 'ok'; data: DesignScoreResponse }
  | { status: 'error'; error: ScoreErrorResponse };

/* ========================================================================= */
/* Pharmacokinetic simulation — POST /api/v1/pk/simulate                     */
/* ========================================================================= */
/*
 * A SEPARATE calculation from the design impact score. It has its own inputs,
 * its own model, its own version and its own limitations. The two are never
 * merged into one object or one headline number.
 */

/**
 * Request body for POST /api/v1/pk/simulate.
 *
 * The five scientific inputs are required and are never defaulted by the
 * client — the simulation simply does not run until the user supplies them.
 * `duration_h` and `time_step_h` are numerical window settings; when omitted
 * the backend applies the legacy documented defaults (48 h, 0.1 h) and says so
 * in `warnings`.
 */
export interface PKSimulationRequest {
  /** Required. Dose, mg/kg. */
  dose_mg_kg: number;
  /** Required. Absorption rate constant, per hour. */
  kabs_per_h: number;
  /** Required. Elimination rate constant, per hour. */
  kel_per_h: number;
  /** Required. Central → peripheral transfer, per hour. */
  k12_per_h: number;
  /** Required. Peripheral → central transfer, per hour. */
  k21_per_h: number;

  duration_h?: number;
  time_step_h?: number;
}

/** The calculated profile. Charts must be drawn from these arrays alone. */
export interface ConcentrationTimeSeries {
  time_h: number[];
  central_plasma: number[];
  peripheral_tissue: number[];
  point_count: number;
  /** Arbitrary dose-scaled units — the model has no volume term. */
  concentration_unit: string;
  time_unit: string;
}

/**
 * Parameters the migrated model genuinely produces.
 *
 * There is deliberately **no clearance field**: the model has no volume term,
 * so none can be derived. See `quantities_not_produced`.
 */
export interface PKParameters {
  peak_concentration_central: number;
  peak_concentration_peripheral: number;
  time_to_peak_central_h: number;
  time_to_peak_peripheral_h: number;
  auc_central: number;
  auc_peripheral: number;
  /** Null when the curve never halves inside the window. Never estimated. */
  half_life_central_h: number | null;
  tissue_accumulation_ratio: number;
  vss_ratio: number;
}

export interface UnproducedQuantity {
  quantity: string;
  reason: string;
}

export interface PKSimulationResponse {
  concentration_time: ConcentrationTimeSeries;
  pk_parameters: PKParameters;
  calculation_version: string;
  model_name: string;
  normalized_inputs: Record<string, number>;
  warnings: string[];
  assumptions: string[];
  limitations: string[];
  quantities_not_produced: UnproducedQuantity[];
  prediction_basis: string;
  evidence_level: string;
  validation_status: string;
  scientific_source: string;
}

/** Structured failure. No curve, half-life or AUC on any failure path. */
export interface PKErrorResponse {
  error: string;
  message: string;
  detail?: string | null;
  results_available: false;
}

/** Discriminated result so callers cannot read a profile off a failure. */
export type PKResult =
  | { status: 'ok'; data: PKSimulationResponse }
  | { status: 'error'; error: PKErrorResponse };

/* ========================================================================= */
/* Demo workspace, stored runs, projects — /api/v1/demo/*, /runs, /projects  */
/* ========================================================================= */

export interface EngineNotRun {
  engine: string;
  reason: string;
}

/**
 * A demonstration scenario.
 *
 * Carries synthetic **inputs** and teaching metadata only. There is deliberately
 * no field on this type that could hold a score, a concentration, a half-life or
 * an assessment verdict — a stored scientific result cannot be expressed here,
 * let alone rendered. Everything a user sees is calculated at runtime by the
 * genuine connected engines.
 */
export interface DemoScenarioSummary {
  slug: string;
  name: string;
  purpose: string;
  disease: string;
  subtype: string;
  drug: string;
  technical: boolean;
  score_runnable: boolean;
  pk_runnable: boolean;
  engines_expected_to_run: string[];
  engine_count_not_running: number;
  fixture_version: string;
  /** Constant badge text. Never clinical, experimental or patient data. */
  data_classification: string;
}

export interface DemoScenarioDetail extends DemoScenarioSummary {
  design_inputs: Record<string, unknown>;
  pk_inputs: Record<string, unknown>;
  assumptions: string[];
  /** What to expect. NOT the engine's output — that always comes from the run. */
  expected_warnings: string[];
  engines_that_will_not_run: EngineNotRun[];
  provenance: string[];
  missing_required_design_inputs: string[];
  missing_required_pk_inputs: string[];
}

export interface DemoScenarioListResponse {
  fixture_version: string;
  scenarios: DemoScenarioSummary[];
  notice: string;
}

export interface RunSummary {
  id: number;
  name: string;
  origin: 'user' | 'demo';
  /** How the study began. See `StudyPathway` in shell/navigation. */
  pathway: 'patient_assessment' | 'research_design' | 'demo_scenario';
  research_purpose: string | null;
  inputs_are_synthetic: boolean;
  /**
   * Identifier of the report a patient-assessment study was established from.
   * An opaque integer: it carries no name, date of birth or other identifier,
   * so it is safe to hold client-side.
   */
  report_assessment_id: number | null;
  demo_scenario_slug: string | null;
  disease: string | null;
  subtype: string | null;
  drug: string | null;
  status: 'complete' | 'partial' | 'blocked';
  engines_run: string[];
  has_design_result: boolean;
  has_pk_result: boolean;
  design_score_version: string | null;
  pk_calculation_version: string | null;
  project_id: number | null;
  created_at: string;
}

export interface RunDetail extends RunSummary {
  design_inputs: DesignScoreRequest | null;
  pk_inputs: PKSimulationRequest | null;
  design_result: DesignScoreResponse | null;
  pk_result: PKSimulationResponse | null;
  engines_not_run: EngineNotRun[];
  demo_fixture_version: string | null;
}

export interface RunListResponse {
  runs: RunSummary[];
  total: number;
}

export interface ComparisonRow {
  label: string;
  source: string;
  key: string;
  /** Parallel to the `runs` array. `null` means never calculated for that run. */
  values: Array<string | number | null>;
  unit_note: string | null;
}

export interface ComparisonResponse {
  runs: RunDetail[];
  rows: ComparisonRow[];
  notice: string;
}

export interface ProjectSummary {
  id: number;
  name: string;
  description: string | null;
  origin: 'user' | 'demo';
  run_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  projects: ProjectSummary[];
  total: number;
}

export interface DemoResetResponse {
  confirmed: boolean;
  deleted: boolean;
  demo_runs: number;
  demo_projects: number;
  demo_templates: number;
  user_runs_preserved: number;
  user_projects_preserved: number;
  message: string;
}

export interface WorkspaceErrorResponse {
  error: string;
  message: string;
  detail?: string | null;
  data_available: false;
}

/** Discriminated result so callers cannot read data off a failure. */
export type ApiResult<T> =
  | { status: 'ok'; data: T }
  | { status: 'error'; error: WorkspaceErrorResponse };

/* ========================================================================= */
/* Medical Report Assessment — /api/v1/reports                               */
/* ========================================================================= */
/*
 * Sensitivity rule for this whole group: nothing here is ever written to
 * localStorage, sessionStorage, a log or an analytics call. Report data lives
 * in component state for the life of the screen and is fetched again when
 * needed. A test asserts client storage stays clean.
 */

/** Where a clinical field's value came from. */
export type FieldProvenance =
  | 'explicitly_stated'
  | 'inferred'
  | 'ambiguous'
  /** The document states two different values and does not reconcile them. */
  | 'conflicting'
  | 'not_found'
  | 'user_entered'
  | 'user_corrected';

export interface ExtractedField {
  key: string;
  label: string;
  value: string | null;
  provenance: FieldProvenance;
  /** Verbatim span from the document supporting `value`. */
  supporting_text: string | null;
  page: number | null;
  /**
   * Heuristic pattern-strength, 0-1. **Not a probability**: 0.9 means the value
   * came from an explicitly labelled field, not that it is 90% likely correct.
   */
  confidence: number;
  /** Competing readings when the document conflicts with itself. */
  alternatives: string[];
  /** Every excerpt supporting the reading, including each side of a conflict. */
  supporting_excerpts: string[];
  note: string | null;
  /** Always false. No connected engine consumes a value from a report. */
  consumed_by_engines: boolean;
}

export interface ExtractionOutcome {
  status: 'completed' | 'failed' | 'document_unreadable' | 'no_engine_connected';
  engine_name: string;
  engine_version: string;
  contract_version: string;
  /** How the text was recovered, e.g. pypdf. */
  reader_name: string | null;
  reader_version: string | null;
  message: string;
  limitations: string[];
  warnings: string[];
  page_count: number | null;
  fields: ExtractedField[];
}

export interface ReportUploadResponse {
  assessment_id: number;
  display_name: string;
  content_hash: string;
  format_key: string;
  size_bytes: number;
  classification: string;
  status: string;
  extraction: ExtractionOutcome;
  intake_warnings: string[];
  document_readable: boolean;
  unreadable_reason: string | null;
  document_text: string | null;
  retain_until: string;
}

export interface ClinicalFieldSpec {
  key: string;
  label: string;
  maps_to_workflow: 'disease' | 'subtype' | 'drug' | null;
  /** Clinically material fields require explicit confirmation. */
  material?: boolean;
}

export interface ConfirmedField {
  key: string;
  value: string | null;
  provenance: FieldProvenance;
  supporting_text: string | null;
  page: number | null;
  original_value: string | null;
  note: string | null;
}

export interface ReportAssessmentSummary {
  id: number;
  display_name: string;
  content_hash: string;
  format_key: string;
  size_bytes: number;
  classification: string;
  fixture_slug: string | null;
  status: 'awaiting_review' | 'confirmed' | 'mapped_to_workflow';
  extraction_status: string;
  extraction_engine: string;
  extraction_engine_version: string;
  mapped_disease: string | null;
  mapped_subtype: string | null;
  mapped_drug: string | null;
  created_at: string;
  retain_until: string;
}

export interface ReportAssessmentDetail extends ReportAssessmentSummary {
  extraction_contract_version: string;
  policy_version: string;
  attested: boolean;
  extraction: ExtractionOutcome | null;
  confirmed_fields: ConfirmedField[] | null;
  document_text: string | null;
  clinical_fields: ClinicalFieldSpec[];
}

export interface ReportAssessmentListResponse {
  assessments: ReportAssessmentSummary[];
  total: number;
  policy_statement: string;
}

export interface SyntheticReportSummary {
  slug: string;
  title: string;
  purpose: string;
  demonstrates: string;
  filename: string;
  size_bytes: number;
  data_classification: string;
}

export interface SyntheticReportListResponse {
  reports: SyntheticReportSummary[];
  fixture_version: string;
  notice: string;
}

export interface DeidentifyResponse {
  text: string;
  redactions: Record<string, number>;
  total_redactions: number;
  version: string;
  limitations: string[];
}


/* ==========================================================================
 * Route-aware pharmacokinetics
 * ========================================================================== */

/** What one administration route implies. Mirrors app/pk/administration.py. */
export interface AdministrationRouteSpec {
  route: string;
  label: string;
  input_function: string;
  description: string;
  /** False for IV routes. When false, k_abs must not be requested. */
  has_absorption_phase: boolean;
  required_dosing_inputs: string[];
  not_applicable_inputs: string[];
  bioavailability_is_free: boolean;
  fixed_bioavailability: number | null;
  fixed_bioavailability_reason: string | null;
  notes: string[];
}

export interface AdministrationRouteListResponse {
  routes: AdministrationRouteSpec[];
  notice: string;
}

export interface PlannedInputOut {
  name: string;
  label: string;
  value: number | string | null;
  unit: string;
  source: string;
  source_label: string;
  report_field: string | null;
  confirmation_status: string | null;
  formula: string | null;
  source_values: Record<string, string> | null;
  editable: boolean;
}

export interface ParameterSetOut {
  id: string;
  version: string;
  therapeutic: string;
  formulation: string;
  route: string;
  population: string;
  indication: string | null;
  model_structure: string;
  source_citation: string;
  validation_status: string;
  date_reviewed: string;
  limitations: string[];
  covariates: string[];
  not_represented: string[];
}

export interface RunPlanResponse {
  therapeutic: string;
  route: string;
  mode: string;
  model_label: string;
  engine_version: string;
  library_version: string;
  runnable: boolean;
  blocking_reasons: string[];
  missing_inputs: string[];
  not_applicable: string[];
  not_represented: string[];
  warnings: string[];
  suitability: string;
  notice: string;
  inputs: PlannedInputOut[];
  parameter_set: ParameterSetOut | null;
}
