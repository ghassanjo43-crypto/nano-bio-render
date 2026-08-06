/**
 * Design workflow field schema.
 *
 * Declarative field definitions drive rendering, validation, the review summary
 * and the API payload, so the four can never drift apart.
 *
 * IMPORTANT: bounds mirror the backend Pydantic schema exactly, and the API
 * field names are those the backend already accepts. Nothing here changes the
 * API contract or the scientific calculation.
 */

import type { DesignScoreRequest } from '../../api/types';

export type StepId = 'core' | 'surface' | 'targeting' | 'stability' | 'review';

export interface NumericFieldDef {
  kind: 'number';
  /** API field name — must exist on DesignScoreRequest. */
  name: keyof DesignScoreRequest;
  label: string;
  unit: string;
  required: boolean;
  min?: number;
  max?: number;
  exclusiveMin?: boolean;
  /** Canonical default applied by the scientific engine when omitted. */
  defaultNote?: string;
  /** Scientific definition shown in the tooltip. */
  definition: string;
  step: StepId;
}

export interface TextFieldDef {
  kind: 'text';
  name: keyof DesignScoreRequest;
  label: string;
  unit: string;
  required: false;
  defaultNote?: string;
  definition: string;
  step: StepId;
}

export interface ChipFieldDef {
  kind: 'chips';
  name: keyof DesignScoreRequest;
  label: string;
  options: readonly string[];
  defaultNote?: string;
  definition: string;
  step: StepId;
}

export type FieldDef = NumericFieldDef | TextFieldDef | ChipFieldDef;

export const LIGAND_OPTIONS = [
  { value: '', label: 'None (passive targeting)' },
  { value: 'GalNAc', label: 'GalNAc' },
  { value: 'Folate', label: 'Folate' },
  { value: 'Transferrin', label: 'Transferrin' },
  { value: 'RGD Peptide', label: 'RGD Peptide' },
  { value: 'Anti-HER2', label: 'Anti-HER2' },
] as const;

export const COATING_OPTIONS = [
  'PEG (Stealth)', 'Hyaluronic Acid', 'Chitosan', 'Albumin',
] as const;

export const FUNCTIONAL_GROUP_OPTIONS = [
  '-COOH (Carboxyl)', '-NH2 (Amino)', '-OH (Hydroxyl)',
] as const;

export const FIELDS: readonly FieldDef[] = [
  /* ------------------------------------------------------------- core */
  {
    kind: 'number', name: 'size_nm', label: 'Particle size', unit: 'nm',
    required: true, min: 0, exclusiveMin: true, max: 10000, step: 'core',
    definition:
      'Core particle diameter. Governs biodistribution, clearance route and '
      + 'the extent to which the formulation can exploit enhanced permeability.',
  },
  {
    kind: 'number', name: 'charge_mv', label: 'Surface charge (zeta potential)',
    unit: 'mV', required: true, min: -200, max: 200, step: 'core',
    definition:
      'Zeta potential of the particle surface. Influences colloidal stability, '
      + 'opsonisation and cellular interaction.',
  },
  {
    kind: 'number', name: 'encapsulation_percent', label: 'Encapsulation efficiency',
    unit: '%', required: true, min: 0, max: 100, step: 'core',
    definition: 'Percentage of payload successfully entrapped within the carrier.',
  },
  {
    kind: 'number', name: 'pdi', label: 'Polydispersity index', unit: '0–1',
    required: false, min: 0, max: 1, step: 'core', defaultNote: '0.15',
    definition:
      'Breadth of the particle size distribution. Lower values indicate a more '
      + 'uniform population.',
  },
  {
    kind: 'number', name: 'hydrodynamic_size_nm', label: 'Hydrodynamic size',
    unit: 'nm', required: false, min: 0, exclusiveMin: true, max: 10000,
    step: 'core', defaultNote: 'particle size × 1.2',
    definition:
      'Diameter including the solvation and coating layer, as measured by '
      + 'dynamic light scattering.',
  },

  /* ---------------------------------------------------------- surface */
  {
    kind: 'chips', name: 'surface_coating', label: 'Surface coating',
    options: COATING_OPTIONS, step: 'surface', defaultNote: 'PEG (Stealth)',
    definition:
      'Coating layers applied to the particle surface. Stealth coatings reduce '
      + 'opsonisation and prolong circulation.',
  },
  {
    kind: 'number', name: 'coating_thickness_nm', label: 'Coating thickness',
    unit: 'nm', required: false, min: 0, step: 'surface', defaultNote: '2.5',
    definition: 'Thickness of the surface coating layer.',
  },
  {
    kind: 'number', name: 'surface_area_nm2', label: 'Surface area', unit: 'nm²',
    required: false, min: 0, step: 'surface', defaultNote: '250',
    definition: 'Accessible surface area available for interaction and functionalisation.',
  },
  {
    kind: 'number', name: 'hydrophobicity_logp', label: 'Hydrophobicity',
    unit: 'LogP', required: false, min: -10, max: 10, step: 'surface',
    defaultNote: '1.5',
    definition:
      'Partition coefficient describing surface hydrophobicity. Excess '
      + 'hydrophobicity promotes aggregation.',
  },
  {
    kind: 'number', name: 'crystallinity_index', label: 'Crystallinity index',
    unit: '%', required: false, min: 0, max: 100, step: 'surface',
    defaultNote: '65',
    definition: 'Degree of crystalline order in the particle matrix, affecting structural stability.',
  },
  {
    kind: 'chips', name: 'functional_groups', label: 'Functional groups',
    options: FUNCTIONAL_GROUP_OPTIONS, step: 'surface', defaultNote: 'none',
    definition: 'Chemical groups presented on the surface for conjugation and biocompatibility.',
  },

  /* -------------------------------------------------------- targeting */
  {
    kind: 'text', name: 'ligand', label: 'Targeting ligand', unit: '',
    required: false, step: 'targeting', defaultNote: 'None',
    definition:
      'Ligand conjugated to the surface for receptor-mediated targeting. '
      + 'Leaving this empty selects passive targeting.',
  },
  {
    kind: 'number', name: 'ligand_density_percent', label: 'Ligand density',
    unit: '%', required: false, min: 0, max: 100, step: 'targeting',
    defaultNote: '0',
    definition: 'Proportion of available surface sites occupied by targeting ligand.',
  },
  {
    kind: 'number', name: 'receptor_binding_kd_nm', label: 'Receptor binding affinity',
    unit: 'Kd, nM', required: false, min: 0, step: 'targeting', defaultNote: '100',
    definition:
      'Dissociation constant for the ligand–receptor pair. Lower values indicate '
      + 'stronger binding.',
  },

  /* -------------------------------------------------- stability / release */
  {
    kind: 'number', name: 'stability_percent', label: 'Formulation stability',
    unit: '%', required: false, min: 0, max: 100, step: 'stability',
    defaultNote: '85',
    definition: 'Retained integrity of the formulation under the intended storage conditions.',
  },
  {
    kind: 'number', name: 'degradation_time_days', label: 'Degradation time',
    unit: 'days', required: false, min: 0, step: 'stability', defaultNote: '30',
    definition: 'Time over which the carrier matrix degrades under physiological conditions.',
  },
  {
    kind: 'number', name: 'release_predictability_percent',
    label: 'Release predictability', unit: '%', required: false, min: 0, max: 100,
    step: 'stability', defaultNote: '85',
    definition: 'Consistency of the payload release profile between batches.',
  },
];

export const STEPS: ReadonlyArray<{
  id: StepId; title: string; short: string; description: string;
}> = [
  {
    id: 'core',
    title: 'Core properties',
    short: 'Core',
    description: 'Physical characteristics of the particle itself. The first three are required.',
  },
  {
    id: 'surface',
    title: 'Surface characteristics',
    short: 'Surface',
    description: 'Coating, chemistry and surface state. All optional — documented defaults apply when omitted.',
  },
  {
    id: 'targeting',
    title: 'Targeting configuration',
    short: 'Targeting',
    description: 'Active targeting strategy. Leave the ligand empty for passive targeting.',
  },
  {
    id: 'stability',
    title: 'Stability & release',
    short: 'Stability',
    description: 'Formulation robustness and payload release behaviour.',
  },
  {
    id: 'review',
    title: 'Review & calculate',
    short: 'Review',
    description: 'Confirm exactly what will be sent to the scientific engine before calculating.',
  },
];

export type FormValues = Record<string, string>;
export type ChipValues = Record<string, string[]>;

export const INITIAL_VALUES: FormValues = {
  size_nm: '100',
  charge_mv: '-5',
  encapsulation_percent: '85',
  pdi: '',
  hydrodynamic_size_nm: '',
  coating_thickness_nm: '',
  surface_area_nm2: '',
  hydrophobicity_logp: '',
  crystallinity_index: '',
  ligand: '',
  ligand_density_percent: '',
  receptor_binding_kd_nm: '',
  stability_percent: '',
  degradation_time_days: '',
  release_predictability_percent: '',
};

export const INITIAL_CHIPS: ChipValues = {
  surface_coating: [],
  functional_groups: [],
};

export function fieldsForStep(step: StepId): FieldDef[] {
  return FIELDS.filter((f) => f.step === step);
}

/** Validate one field. Returns an error message, or undefined when valid. */
export function validateField(def: FieldDef, raw: string): string | undefined {
  if (def.kind === 'chips') return undefined;
  const value = raw.trim();

  if (!value) {
    return def.required ? `${def.label} is required.` : undefined;
  }
  if (def.kind === 'text') return undefined;

  const n = Number(value);
  if (Number.isNaN(n)) return `${def.label} must be a number.`;
  if (def.exclusiveMin && def.min !== undefined && n <= def.min) {
    return `${def.label} must be greater than ${def.min}${def.unit ? ` ${def.unit}` : ''}.`;
  }
  if (!def.exclusiveMin && def.min !== undefined && n < def.min) {
    return `${def.label} must be at least ${def.min}${def.unit ? ` ${def.unit}` : ''}.`;
  }
  if (def.max !== undefined && n > def.max) {
    return `${def.label} must be ${def.max}${def.unit ? ` ${def.unit}` : ''} or less.`;
  }
  return undefined;
}

export function validateStep(step: StepId, values: FormValues): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const def of fieldsForStep(step)) {
    const msg = validateField(def, values[def.name as string] ?? '');
    if (msg) errors[def.name as string] = msg;
  }
  return errors;
}

export function validateAll(values: FormValues): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const def of FIELDS) {
    const msg = validateField(def, values[def.name as string] ?? '');
    if (msg) errors[def.name as string] = msg;
  }
  return errors;
}

/**
 * Build the API payload.
 *
 * Blank optional fields are OMITTED entirely so the scientific engine applies
 * its own documented defaults — the frontend never invents a value.
 */
export function buildRequest(values: FormValues, chips: ChipValues): DesignScoreRequest {
  const request: Record<string, unknown> = {
    size_nm: Number(values.size_nm),
    charge_mv: Number(values.charge_mv),
    encapsulation_percent: Number(values.encapsulation_percent),
  };

  for (const def of FIELDS) {
    const key = def.name as string;
    if (['size_nm', 'charge_mv', 'encapsulation_percent'].includes(key)) continue;

    if (def.kind === 'chips') {
      const selected = chips[key] ?? [];
      if (selected.length > 0) request[key] = selected;
      continue;
    }
    const raw = (values[key] ?? '').trim();
    if (!raw) continue;
    request[key] = def.kind === 'number' ? Number(raw) : raw;
  }

  return request as unknown as DesignScoreRequest;
}

/** Rows for the review summary: what is supplied vs what will be defaulted. */
export function reviewRows(values: FormValues, chips: ChipValues) {
  return FIELDS.map((def) => {
    const key = def.name as string;
    const supplied = def.kind === 'chips'
      ? (chips[key] ?? []).length > 0
      : Boolean((values[key] ?? '').trim());
    const display = def.kind === 'chips'
      ? (chips[key] ?? []).join(', ')
      : (values[key] ?? '').trim();
    return {
      key,
      label: def.label,
      unit: def.kind === 'chips' ? '' : def.unit,
      supplied,
      value: supplied ? display : `default: ${def.defaultNote ?? '—'}`,
      required: def.kind === 'number' ? def.required : false,
      step: def.step,
    };
  });
}
