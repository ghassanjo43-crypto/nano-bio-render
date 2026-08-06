/**
 * The four sources a pharmacokinetic input can come from.
 *
 * The defect this exists for: the PK screen presented seven boxes of equal
 * weight — dose, four rate constants, duration, time step — which in a
 * patient-assessment context implied all seven came from the uploaded medical
 * report. They do not, and most of them cannot. A medical report does not
 * contain an intercompartmental rate constant.
 *
 * Grouping inputs by genuine source is the correction. The categories mirror
 * `app/pk/planning.py` exactly, so the interface and the engine cannot disagree
 * about where a number came from.
 */

export type PKInputSource =
  | 'patient_report'
  | 'manual_entry'
  | 'treatment_protocol'
  | 'parameter_library'
  | 'derived'
  | 'simulation_setting'
  | 'expert_override'
  | 'route_definition';

export interface SourceCategory {
  id: string;
  title: string;
  /** What genuinely belongs in this category. */
  description: string;
  sources: readonly PKInputSource[];
  icon: string;
}

/** The four categories, in the order the screen presents them. */
export const SOURCE_CATEGORIES: readonly SourceCategory[] = [
  {
    id: 'patient',
    title: 'Patient data',
    description:
      'Confirmed fields from an uploaded medical report, or values you enter '
      + 'manually when the report does not contain them. Only values the '
      + 'selected model genuinely consumes appear here.',
    sources: ['patient_report', 'manual_entry'],
    icon: 'document',
  },
  {
    id: 'protocol',
    title: 'Treatment protocol',
    description:
      'The prescribed or planned regimen: dose basis, amount, route, infusion '
      + 'duration, interval and number of doses. Selecting a therapeutic for '
      + 'nanoparticle research is not evidence that it was prescribed.',
    sources: ['treatment_protocol'],
    icon: 'list',
  },
  {
    id: 'parameters',
    title: 'Model parameters',
    description:
      'Clearance, volumes and intercompartmental clearance, loaded from a '
      + 'cited and reviewed parameter set. Rate constants are calculated from '
      + 'these, not typed in.',
    sources: ['parameter_library', 'derived', 'route_definition'],
    icon: 'flask',
  },
  {
    id: 'simulation',
    title: 'Simulation settings',
    description:
      'Numerical controls for the solver. These are settings, not findings — '
      + 'they come from neither the medical report nor the literature.',
    sources: ['simulation_setting'],
    icon: 'gear',
  },
];

type Tone = 'success' | 'accent' | 'warn' | 'info' | 'neutral';

/**
 * Tone per source. Indexed with a plain string because the value arrives from
 * the network as `unknown`; `toneForSource` falls back rather than crashing on
 * a source this build does not know about.
 */
export const SOURCE_TONE: Record<PKInputSource, Tone> = {
  patient_report: 'info',
  manual_entry: 'warn',
  treatment_protocol: 'accent',
  parameter_library: 'success',
  derived: 'success',
  simulation_setting: 'neutral',
  expert_override: 'warn',
  route_definition: 'info',
};

/** Tone for a source, defaulting to neutral for anything unrecognised. */
export function toneForSource(source: string): Tone {
  return (SOURCE_TONE as Record<string, Tone>)[source] ?? 'neutral';
}

/**
 * Fallback label for a source the server did not label.
 *
 * The server sends `source_label` with every input; this exists only so an
 * unrecognised source renders as "Source not recorded" rather than blank or,
 * worse, as some other category.
 */
export function fallbackSourceLabel(source: string): string {
  const known: Record<string, string> = {
    patient_report: 'From medical report (confirmed)',
    manual_entry: 'Manually entered',
    treatment_protocol: 'From treatment protocol',
    parameter_library: 'From cited parameter set',
    derived: 'Calculated from cited model parameters',
    simulation_setting: 'Simulation setting',
    expert_override: 'Expert research override',
    route_definition: 'Fixed by administration route',
  };
  return known[source] ?? 'Source not recorded';
}

export const RESEARCH_USE_ONLY_NOTICE =
  'Research Use Only — This simulation does not recommend treatment, '
  + 'determine an individual dose, or replace clinical pharmacology and '
  + 'medical judgment.';
