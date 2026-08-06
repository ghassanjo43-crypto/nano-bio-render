/**
 * Pharmacokinetic simulation input schema.
 *
 * Declarative field definitions drive rendering, validation, the review summary
 * and the API payload, so the four cannot drift apart. Bounds mirror the
 * backend Pydantic schema exactly, which in turn mirrors the legacy Streamlit
 * widget ranges in `modules/design.py` and `modules/simulation.py`.
 *
 * Two deliberate differences from the design-parameter form:
 *
 *  1. **Nothing is pre-filled.** The five scientific inputs start empty. The
 *     legacy application pre-populated them from a defaults dictionary, which
 *     meant a user could run a "simulation" whose kinetics they never chose.
 *     Here the simulation simply does not run until the values are supplied.
 *  2. **The window settings are optional**, because duration and time step are
 *     numerical settings rather than properties of the system. Left blank they
 *     are omitted from the request, and the engine applies — and reports — its
 *     own documented defaults.
 */

import type { PKSimulationRequest } from '../../api/types';

export interface PKFieldDef {
  /** API field name — must exist on PKSimulationRequest. */
  name: keyof PKSimulationRequest;
  label: string;
  symbol: string;
  unit: string;
  required: boolean;
  min: number;
  max: number;
  /** Allowed discrete values, when the engine only accepts a fixed set. */
  choices?: readonly number[];
  /** Documented engine default, shown when the field is left blank. */
  defaultNote?: string;
  /** Scientific definition shown beneath the field. */
  definition: string;
}

/** The integration steps the engine accepts. Mirrors the backend enum. */
export const TIME_STEP_CHOICES = [0.05, 0.1, 0.25, 0.5, 1.0] as const;

export const PK_FIELDS: readonly PKFieldDef[] = [
  {
    name: 'dose_mg_kg', label: 'Dose', symbol: 'D', unit: 'mg/kg',
    required: true, min: 0.1, max: 100,
    definition:
      'Administered dose per kilogram of body weight. The whole dose is placed '
      + 'in the depot compartment at time zero.',
  },
  {
    name: 'kabs_per_h', label: 'Absorption rate constant', symbol: 'k_abs',
    unit: 'h⁻¹', required: true, min: 0.01, max: 5,
    definition:
      'First-order rate at which the dose leaves the depot and enters the '
      + 'central compartment.',
  },
  {
    name: 'kel_per_h', label: 'Elimination rate constant', symbol: 'k_el',
    unit: 'h⁻¹', required: true, min: 0.001, max: 2,
    definition:
      'First-order rate of removal from the central compartment. Elimination '
      + 'occurs only from the central compartment in this model.',
  },
  {
    name: 'k12_per_h', label: 'Central → peripheral transfer', symbol: 'k_12',
    unit: 'h⁻¹', required: true, min: 0.01, max: 2,
    definition:
      'First-order transfer of drug from the central (plasma) compartment into '
      + 'the peripheral (tissue) compartment.',
  },
  {
    name: 'k21_per_h', label: 'Peripheral → central transfer', symbol: 'k_21',
    unit: 'h⁻¹', required: true, min: 0.01, max: 2,
    definition:
      'First-order return of drug from the peripheral compartment to the '
      + 'central compartment.',
  },
  {
    name: 'duration_h', label: 'Simulation duration', symbol: 'T', unit: 'hours',
    required: false, min: 12, max: 168, defaultNote: '48',
    definition:
      'Length of the simulated window. AUC is integrated over this window only '
      + 'and is not extrapolated beyond it.',
  },
  {
    name: 'time_step_h', label: 'Integration time step', symbol: 'Δt',
    unit: 'hours', required: false, min: 0.05, max: 1,
    choices: TIME_STEP_CHOICES, defaultNote: '0.1',
    definition:
      'Fixed step of the explicit forward-Euler solver. The step size is part '
      + 'of the model’s numerical identity: results computed at different '
      + 'steps are not interchangeable.',
  },
];

export type PKValues = Record<string, string>;

/** Every field starts blank. No kinetic value is ever assumed on the user’s behalf. */
export const INITIAL_PK_VALUES: PKValues = {
  dose_mg_kg: '',
  kabs_per_h: '',
  kel_per_h: '',
  k12_per_h: '',
  k21_per_h: '',
  duration_h: '',
  time_step_h: '',
};

export const REQUIRED_PK_FIELDS: readonly string[] =
  PK_FIELDS.filter((f) => f.required).map((f) => f.name as string);

/** Validate one PK field. Returns an error message, or undefined when valid. */
export function validatePkField(def: PKFieldDef, raw: string): string | undefined {
  const value = (raw ?? '').trim();

  if (!value) {
    return def.required
      ? `${def.label} is required — the simulation will not run without it.`
      : undefined;
  }

  const n = Number(value);
  if (!Number.isFinite(n)) return `${def.label} must be a number.`;

  if (def.choices && !def.choices.includes(n)) {
    return `${def.label} must be one of ${def.choices.join(', ')} ${def.unit}.`;
  }
  if (n < def.min) return `${def.label} must be at least ${def.min} ${def.unit}.`;
  if (n > def.max) return `${def.label} must be ${def.max} ${def.unit} or less.`;
  return undefined;
}

export function validatePkValues(values: PKValues): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const def of PK_FIELDS) {
    const msg = validatePkField(def, values[def.name as string] ?? '');
    if (msg) errors[def.name as string] = msg;
  }
  return errors;
}

/**
 * True only when every scientifically required input is present AND valid.
 *
 * This is the gate on execution: the PK model is not called at all until it
 * holds. An incomplete set produces an honest "not run" state, never a partial
 * or assumed profile.
 */
export function pkInputsComplete(values: PKValues): boolean {
  for (const def of PK_FIELDS) {
    const raw = (values[def.name as string] ?? '').trim();
    if (def.required && !raw) return false;
    if (validatePkField(def, raw)) return false;
  }
  return true;
}

/**
 * Build the API payload.
 *
 * Blank optional fields are OMITTED entirely so the engine applies its own
 * documented defaults — the frontend never invents a value.
 */
export function buildPkRequest(values: PKValues): PKSimulationRequest {
  const request: Record<string, number> = {};
  for (const def of PK_FIELDS) {
    const key = def.name as string;
    const raw = (values[key] ?? '').trim();
    if (!raw) continue;
    request[key] = Number(raw);
  }
  return request as unknown as PKSimulationRequest;
}

/** Rows for the review summary: what is supplied vs what will be defaulted. */
export function pkReviewRows(values: PKValues) {
  return PK_FIELDS.map((def) => {
    const key = def.name as string;
    const raw = (values[key] ?? '').trim();
    return {
      key,
      label: def.label,
      symbol: def.symbol,
      unit: def.unit,
      required: def.required,
      supplied: Boolean(raw),
      value: raw || (def.required ? 'not supplied' : `default: ${def.defaultNote}`),
    };
  });
}
