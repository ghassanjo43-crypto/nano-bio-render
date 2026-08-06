/**
 * Types and presentation vocabulary for the Experimental Validation Registry.
 *
 * These mirror `app/validation/vocabulary.py`. Labels are duplicated here so
 * the registry renders before the vocabulary request returns, but the
 * *authority* is the backend and a server-supplied label always wins.
 *
 * The one rule the interface must not undermine
 * ---------------------------------------------
 * **E3 is granted by the backend, never inferred here.** No component computes
 * eligibility, and no badge says "eligible" on any basis other than the
 * server's verdict. A client-side rule would be a second, divergent opinion
 * about what counts as evidence.
 */

export type ExperimentStatusId =
  | 'draft' | 'submitted' | 'under_review'
  | 'approved' | 'rejected' | 'revision_required' | 'superseded';

export type PurposeId =
  | 'structural_visualization' | 'formulation_assessment'
  | 'biological_targeting' | 'pharmacokinetic_modelling'
  | 'safety_assessment' | 'cinematic_animation';

export type SubtypeId =
  | 'particle_size_pdi' | 'zeta_potential' | 'drug_loading'
  | 'encapsulation_efficiency' | 'stability' | 'release_profile'
  | 'target_binding' | 'cellular_uptake' | 'cytotoxicity' | 'selectivity'
  | 'intracellular_pathway' | 'hemocompatibility'
  | 'basic_cellular_toxicity' | 'other_in_vitro';

export type AttachmentCategoryId =
  | 'raw_data' | 'processed_data' | 'protocol' | 'laboratory_report'
  | 'image' | 'instrument_export' | 'statistical_output' | 'certificate';

export interface GateResult {
  id: string;
  label: string;
  passed: boolean;
  detail: string;
  remedy: string | null;
  not_applicable: boolean;
}

export interface EligibilityVerdict {
  eligible: boolean;
  purpose: PurposeId;
  requested_level: string | null;
  approved_level: string | null;
  passed_gates: string[];
  failed_gates: string[];
  gates: GateResult[];
  missing_requirements: string[];
  contradiction_warning: string | null;
  explanation: string;
  ruleset_version: string;
}

export interface ExperimentSummary {
  experiment_id: number;
  code: string;
  title: string;
  subtype: SubtypeId;
  subtype_label: string;
  purpose: PurposeId;
  purpose_label: string;
  study_id: number;
  project_id: number | null;
  candidate_id: number;
  version_id: number;
  version_number: number;
  candidate_version_id: number;
  status: ExperimentStatusId;
  status_label: string;
  approved_level: string | null;
  laboratory_name: string | null;
  investigator_name: string | null;
  reviewer_id: number | null;
  created_at: string;
  decision_at: string | null;
  e3_eligible: boolean;
}

export interface AttachmentSummary {
  id: number;
  category: AttachmentCategoryId;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  checksum_sha256: string;
  uploaded_at: string;
}

export interface MeasurementRow {
  id?: number;
  endpoint_name: string;
  sample_group?: string | null;
  replicate_id?: string | null;
  time_point?: string | null;
  dose_value?: number | null;
  dose_unit?: string | null;
  result_numeric?: number | null;
  result_text?: string | null;
  result_unit?: string | null;
  method?: string | null;
  missing_value_reason?: string | null;
  excluded?: boolean;
  exclusion_justification?: string | null;
  normalized_value?: number | null;
  normalization_method?: string | null;
}

export interface VersionDetail {
  id: number;
  experiment_id: number;
  version_number: number;
  candidate_version_id: number;
  status: ExperimentStatusId;
  approved_level: string | null;
  [key: string]: unknown;
  measurements: MeasurementRow[];
  attachments: AttachmentSummary[];
}

export interface ExperimentDetail {
  experiment: {
    id: number; code: string; title: string;
    subtype: SubtypeId; subtype_label: string;
    purpose: PurposeId; purpose_label: string;
    study_id: number; candidate_id: number; project_id: number | null;
  };
  versions: Array<{
    id: number; version_number: number; status: ExperimentStatusId;
    status_label: string; approved_level: string | null;
    created_at: string; superseded_by_version_id: number | null;
  }>;
  current_version?: VersionDetail;
  capabilities?: string[];
}

export interface AuditEventRow {
  id: number;
  event: string;
  actor_id: number | null;
  version_id: number | null;
  summary: string | null;
  created_at: string;
}

/* ------------------------------------------------------------ presentation */

export const STATUS_LABEL: Record<ExperimentStatusId, string> = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under review',
  approved: 'Approved',
  rejected: 'Rejected',
  revision_required: 'Revision required',
  superseded: 'Superseded',
};

/**
 * Tone per status.
 *
 * `rejected` and `superseded` are visually distinct rather than both muted:
 * a rejection is a scientific finding about the work, a supersession is a
 * bookkeeping fact about the version. Collapsing them would hide the first.
 */
export const STATUS_TONE: Record<ExperimentStatusId,
  'neutral' | 'info' | 'accent' | 'success' | 'danger' | 'warn'> = {
  draft: 'neutral',
  submitted: 'info',
  under_review: 'accent',
  approved: 'success',
  rejected: 'danger',
  revision_required: 'warn',
  superseded: 'neutral',
};

export const SUBTYPE_LABEL: Record<SubtypeId, string> = {
  particle_size_pdi: 'Particle size and polydispersity',
  zeta_potential: 'Zeta potential',
  drug_loading: 'Drug loading',
  encapsulation_efficiency: 'Encapsulation efficiency',
  stability: 'Stability',
  release_profile: 'Release profile',
  target_binding: 'Target binding or receptor affinity',
  cellular_uptake: 'Cellular uptake',
  cytotoxicity: 'Cytotoxicity',
  selectivity: 'Selectivity',
  intracellular_pathway: 'Intracellular pathway response',
  hemocompatibility: 'Hemocompatibility',
  basic_cellular_toxicity: 'Basic cellular toxicity',
  other_in_vitro: 'Other in-vitro assay',
};

export const PURPOSE_LABEL: Record<PurposeId, string> = {
  structural_visualization: 'Structural visualization',
  formulation_assessment: 'Formulation assessment',
  biological_targeting: 'Biological targeting',
  pharmacokinetic_modelling: 'Pharmacokinetic modelling',
  safety_assessment: 'Safety assessment',
  cinematic_animation: 'Cinematic animation',
};

export const ATTACHMENT_LABEL: Record<AttachmentCategoryId, string> = {
  raw_data: 'Raw data',
  processed_data: 'Processed data',
  protocol: 'Protocol',
  laboratory_report: 'Laboratory report',
  image: 'Image',
  instrument_export: 'Instrument export',
  statistical_output: 'Statistical output',
  certificate: 'Certificate or provenance document',
};

/**
 * Subtype-specific measurement fields.
 *
 * The brief is explicit that one universal form would be misleading, and it
 * would: a release profile needs a time point, a zeta potential does not, and
 * a form that asked for both would either collect nonsense or teach people to
 * leave scientific fields blank.
 *
 * Each entry declares the endpoints the assay actually produces and the units
 * they are measured in. `null` unit means the endpoint is unitless or the unit
 * varies and must be stated per row.
 */
export interface SubtypeFormSpec {
  /** Endpoints offered by default. The user may still add their own. */
  endpoints: ReadonlyArray<{ name: string; unit: string | null }>;
  /** Whether a time point is scientifically meaningful. */
  timeCourse: boolean;
  /** Whether a dose or concentration applies. */
  doseResponse: boolean;
  /** Whether the assay uses a biological system. */
  cellBased: boolean;
  /** One line on what the measurement means, shown above the table. */
  guidance: string;
}

export const SUBTYPE_FORMS: Record<SubtypeId, SubtypeFormSpec> = {
  particle_size_pdi: {
    endpoints: [
      { name: 'z_average_diameter', unit: 'nm' },
      { name: 'pdi', unit: null },
      { name: 'peak_1_diameter', unit: 'nm' },
    ],
    timeCourse: false, doseResponse: false, cellBased: false,
    guidance: 'Record the weighting basis in the method: intensity-, volume- '
      + 'and number-weighted distributions of one sample differ substantially.',
  },
  zeta_potential: {
    endpoints: [{ name: 'zeta_potential', unit: 'mV' }],
    timeCourse: false, doseResponse: false, cellBased: false,
    guidance: 'A zeta potential without its medium, pH and ionic strength '
      + 'cannot be compared with any other measurement, including a later one '
      + 'of the same sample. State them in the method.',
  },
  drug_loading: {
    endpoints: [
      { name: 'drug_loading', unit: '%' },
      { name: 'drug_to_carrier_ratio', unit: 'mg/mg' },
    ],
    timeCourse: false, doseResponse: false, cellBased: false,
    guidance: 'Loading is mass of payload per mass of carrier. It is not the '
      + 'same quantity as encapsulation efficiency.',
  },
  encapsulation_efficiency: {
    endpoints: [{ name: 'encapsulation_efficiency', unit: '%' }],
    timeCourse: false, doseResponse: false, cellBased: false,
    guidance: 'This is a process yield — the fraction of offered drug that was '
      + 'encapsulated. It is not a quantity of drug per particle.',
  },
  stability: {
    endpoints: [
      { name: 'z_average_diameter', unit: 'nm' },
      { name: 'pdi', unit: null },
      { name: 'encapsulation_retained', unit: '%' },
    ],
    timeCourse: true, doseResponse: false, cellBased: false,
    guidance: 'Record the medium, temperature and duration. A stability result '
      + 'without them describes no particular condition.',
  },
  release_profile: {
    endpoints: [{ name: 'cumulative_release', unit: '%' }],
    timeCourse: true, doseResponse: false, cellBased: false,
    guidance: 'Record sink conditions and the release medium. A profile is a '
      + 'series, so every time point belongs in the table.',
  },
  target_binding: {
    endpoints: [
      { name: 'kd', unit: 'nM' },
      { name: 'bmax', unit: 'fmol/mg' },
      { name: 'percent_bound', unit: '%' },
    ],
    timeCourse: false, doseResponse: true, cellBased: true,
    guidance: 'Affinities from different assay formats are not directly '
      + 'comparable. Name the format in the method.',
  },
  cellular_uptake: {
    endpoints: [
      { name: 'mean_fluorescence_intensity', unit: 'a.u.' },
      { name: 'percent_positive_cells', unit: '%' },
      { name: 'uptake_per_cell', unit: 'pg/cell' },
    ],
    timeCourse: true, doseResponse: true, cellBased: true,
    guidance: 'Distinguish surface binding from internalisation in the method; '
      + 'total-cell fluorescence measures both.',
  },
  cytotoxicity: {
    endpoints: [
      { name: 'viability_percent', unit: '%' },
      { name: 'ic50', unit: 'ug/mL' },
    ],
    timeCourse: false, doseResponse: true, cellBased: true,
    guidance: 'Record the exposure time with the assay. Viability at 24 h and '
      + 'at 72 h are different findings.',
  },
  selectivity: {
    endpoints: [
      { name: 'target_response', unit: '%' },
      { name: 'non_target_response', unit: '%' },
      { name: 'selectivity_index', unit: null },
    ],
    timeCourse: false, doseResponse: true, cellBased: true,
    guidance: 'Selectivity is a comparison. Record the non-target control as '
      + 'its own rows, not only as a ratio.',
  },
  intracellular_pathway: {
    endpoints: [
      { name: 'colocalisation_coefficient', unit: null },
      { name: 'marker_positive_fraction', unit: '%' },
    ],
    timeCourse: true, doseResponse: false, cellBased: true,
    guidance: 'Name the compartment marker. A colocalisation coefficient '
      + 'without one describes nothing in particular.',
  },
  hemocompatibility: {
    endpoints: [
      { name: 'haemolysis', unit: '%' },
      { name: 'platelet_activation', unit: '%' },
    ],
    timeCourse: false, doseResponse: true, cellBased: false,
    guidance: 'Record the blood source and anticoagulant. Both materially '
      + 'change the result.',
  },
  basic_cellular_toxicity: {
    endpoints: [
      { name: 'viability_percent', unit: '%' },
      { name: 'ldh_release', unit: '%' },
    ],
    timeCourse: false, doseResponse: true, cellBased: true,
    guidance: 'A screening-level assay. State plainly in the conclusion that '
      + 'it is not a full toxicological assessment.',
  },
  other_in_vitro: {
    endpoints: [],
    timeCourse: true, doseResponse: true, cellBased: false,
    guidance: 'An unclassified assay must state its own method and endpoints '
      + 'in full — there is no template to fall back on.',
  },
};

export function statusTone(status: string) {
  return STATUS_TONE[status as ExperimentStatusId] ?? 'neutral';
}

export function statusLabel(status: string) {
  return STATUS_LABEL[status as ExperimentStatusId] ?? 'Not recorded';
}

/** Byte size for display. Never rounds a value to zero. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
