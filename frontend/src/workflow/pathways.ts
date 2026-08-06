/**
 * The three study pathways, as ordered sequences of scientific steps.
 *
 * Why this file exists
 * --------------------
 * Before it, every step page hard-coded its own `navigate('/workflow/design')`.
 * That made "Back" a property of whichever page you happened to be on rather
 * than of the study you are conducting, and it meant the three pathways were
 * indistinguishable once you were inside the workflow — the same four steps in
 * the same order however the study began.
 *
 * The sequences here are the single source of truth for what comes next and
 * what came before. `PathwayNav` reads them, the progress indicator reads them,
 * and the tests read them, so the three cannot drift apart.
 *
 * A pathway spans routes, not a subtree
 * -------------------------------------
 * The steps deliberately reach outside `/workflow/*` — a patient assessment
 * begins at `/report` and every pathway ends at `/compare` and `/reports`.
 * A pathway is an ordering imposed *over* the existing routes, which is why
 * nothing here moves a page or invents one.
 *
 * Guidance, not a cage
 * --------------------
 * A pathway says what to do next. It does not restrict where the user may go:
 * every menu entry stays reachable at all times, and visiting a page that is
 * not on the current pathway is legitimate. `stepIndexFor` returning `-1` is
 * the normal, expected answer for an off-pathway page, not an error.
 *
 * Nothing here performs or alters a calculation.
 */

import type { StudyPathway } from '../shell/navigation';

/** How available a step's underlying module genuinely is. */
export type StepAvailability =
  | 'operational'
  | 'limited_prototype'
  | 'not_connected';

export interface PathwayStep {
  /** Stable id. Used by tests and as a React key; never shown to the user. */
  id: string;
  /** Full label, matching the module it opens. */
  label: string;
  /** Compact label for the progress rail. */
  shortLabel: string;
  /** The route this step opens. */
  path: string;
  /** One line on what the step is for. */
  summary: string;
  /**
   * What the module behind this step can actually do.
   *
   * Carried on the step so the pathway cannot promise more than the platform
   * delivers. A step whose engine is not connected still appears — hiding it
   * would make the gap invisible rather than honest — but it is labelled, and
   * `Save & Continue` past it does not imply anything ran.
   */
  availability: StepAvailability;
  /**
   * True when the step must be completed before the next one is meaningful.
   * Advisory only: it drives the "next recommended step" hint and never blocks
   * navigation, which `WorkflowLayout` handles separately for the four steps
   * that genuinely gate on data.
   */
  required?: boolean;
}

/* -------------------------------------------------------------------------
 * Shared steps
 *
 * Defined once and referenced by each pathway, so the same scientific stop
 * cannot acquire a different label or summary depending on how the study
 * began. Only the *order* differs between pathways.
 * ---------------------------------------------------------------------- */

const PATIENT_ASSESSMENT: PathwayStep = {
  id: 'patient-assessment',
  label: 'Patient Assessment',
  shortLabel: 'Patient',
  path: '/report',
  summary:
    'Upload a de-identified report and confirm the clinical context. '
    + 'Extraction is rule-based and unvalidated.',
  availability: 'limited_prototype',
  required: true,
};

const DISEASE_BIOMARKER: PathwayStep = {
  id: 'disease-biomarker',
  label: 'Disease & Biomarker Assessment',
  shortLabel: 'Disease',
  path: '/workflow/disease',
  summary: 'Indication, subtype and therapeutic agent.',
  availability: 'limited_prototype',
  required: true,
};

const RESEARCH_DESIGN: PathwayStep = {
  id: 'research-design',
  label: 'Research Design',
  shortLabel: 'Research',
  path: '/start/research',
  summary: 'State the research purpose the study is answering.',
  availability: 'operational',
  required: true,
};

const NANOPARTICLE_DESIGN: PathwayStep = {
  id: 'nanoparticle-design',
  label: 'Nanoparticle Design',
  shortLabel: 'Design',
  path: '/workflow/design',
  summary: 'Core, surface and stability parameters for the formulation.',
  availability: 'operational',
  required: true,
};

const TARGETING_LIGANDS: PathwayStep = {
  id: 'targeting-ligands',
  label: 'Targeting & Ligands',
  shortLabel: 'Targeting',
  path: '/workflow/targeting',
  summary:
    'Ligand, density and receptor affinity. Leave the ligand empty for '
    + 'passive targeting.',
  availability: 'limited_prototype',
};

const PK_SIMULATION: PathwayStep = {
  id: 'pk-simulation',
  label: 'Pharmacokinetic Simulation',
  shortLabel: 'PK',
  path: '/workflow/review',
  summary: 'Review the inputs, then run the two-compartment model.',
  availability: 'operational',
  required: true,
};

const SCIENTIFIC_READINESS: PathwayStep = {
  id: 'scientific-readiness',
  label: 'Scientific Readiness',
  shortLabel: 'Readiness',
  path: '/scientific-readiness',
  summary:
    'Whether this study\'s recorded data supports each kind of work. '
    + 'Six areas, assessed independently.',
  availability: 'operational',
};

const VALIDATION_REGISTRY: PathwayStep = {
  id: 'validation-registry',
  label: 'Validation Registry',
  shortLabel: 'Validation',
  path: '/validation',
  summary:
    'Record in-vitro experiments against this candidate version. An approved '
    + 'experiment raises one scientific purpose to E3.',
  availability: 'operational',
};

const PROTOCOL_GENERATOR: PathwayStep = {
  id: 'protocol',
  label: 'Protocol Generator',
  shortLabel: 'Protocol',
  path: '/protocol',
  summary: 'Wet-lab synthesis and characterisation protocol.',
  availability: 'not_connected',
};

const EXPERIMENTAL_PLANNING: PathwayStep = {
  id: 'experimental-planning',
  label: 'Experimental Planning',
  shortLabel: 'Planning',
  path: '/experimental-planning',
  summary: 'Plan wet-lab experiments against the design.',
  availability: 'not_connected',
};

const EVIDENCE_VALIDATION: PathwayStep = {
  id: 'evidence',
  label: 'Evidence & Validation',
  shortLabel: 'Evidence',
  path: '/evidence',
  summary: 'Verified status and known blockers of every module used.',
  availability: 'operational',
};

const COMPARE_RESULTS: PathwayStep = {
  id: 'compare',
  label: 'Compare Results',
  shortLabel: 'Compare',
  path: '/compare',
  summary: 'Stored studies aligned field by field. No combined ranking.',
  availability: 'operational',
};

const REPORTS: PathwayStep = {
  id: 'reports',
  label: 'Reports',
  shortLabel: 'Reports',
  path: '/reports',
  summary: 'Generate a report from a stored study.',
  availability: 'limited_prototype',
};

/* Demonstration variants. Same routes, different wording: on this pathway the
   inputs are synthetic, and the labels have to say so at every stop rather
   than only on the first one. */

const DEMO_WORKSPACE: PathwayStep = {
  id: 'demo-workspace',
  label: 'Demo Workspace',
  shortLabel: 'Demo',
  path: '/demo',
  summary:
    'Choose a demonstration scenario. Inputs are synthetic and illustrative; '
    + 'the engines that run on them are the real ones.',
  availability: 'operational',
  required: true,
};

const DEMO_COMPARE: PathwayStep = {
  ...COMPARE_RESULTS,
  id: 'demo-compare',
  label: 'Sample Comparison',
  shortLabel: 'Compare',
  summary:
    'Compare demonstration studies. Every value shown derives from synthetic '
    + 'inputs and describes no real material.',
};

const DEMO_REPORT: PathwayStep = {
  ...REPORTS,
  id: 'demo-report',
  label: 'Demonstration Report',
  shortLabel: 'Report',
  summary:
    'A report generated from synthetic inputs. It is a demonstration of the '
    + 'report format, not a finding about any material.',
};

/* -------------------------------------------------------------------------
 * The three pathways
 * ---------------------------------------------------------------------- */

export const PATHWAY_STEPS: Record<StudyPathway, readonly PathwayStep[]> = {
  patient_assessment: [
    PATIENT_ASSESSMENT,
    DISEASE_BIOMARKER,
    RESEARCH_DESIGN,
    NANOPARTICLE_DESIGN,
    TARGETING_LIGANDS,
    PK_SIMULATION,
    SCIENTIFIC_READINESS,
    VALIDATION_REGISTRY,
    PROTOCOL_GENERATOR,
    EXPERIMENTAL_PLANNING,
    EVIDENCE_VALIDATION,
    COMPARE_RESULTS,
    REPORTS,
  ],

  research_design: [
    RESEARCH_DESIGN,
    DISEASE_BIOMARKER,
    NANOPARTICLE_DESIGN,
    TARGETING_LIGANDS,
    PK_SIMULATION,
    SCIENTIFIC_READINESS,
    VALIDATION_REGISTRY,
    PROTOCOL_GENERATOR,
    EXPERIMENTAL_PLANNING,
    EVIDENCE_VALIDATION,
    COMPARE_RESULTS,
    REPORTS,
  ],

  // Guided versions of the applicable scientific tools, then a sample
  // comparison and a demonstration report. Deliberately shorter: the
  // demonstration exists to show how the platform works, and walking a
  // trainee through two unconnected modules would teach them nothing.
  demo_scenario: [
    DEMO_WORKSPACE,
    DISEASE_BIOMARKER,
    NANOPARTICLE_DESIGN,
    TARGETING_LIGANDS,
    PK_SIMULATION,
    SCIENTIFIC_READINESS,
    DEMO_COMPARE,
    DEMO_REPORT,
  ],
};

export const PATHWAY_LABEL: Record<StudyPathway, string> = {
  patient_assessment: 'Patient-Specific Assessment',
  research_design: 'Research & Nanoparticle Design',
  demo_scenario: 'Demo & Training Workspace',
};

/**
 * A standing caveat for the pathway as a whole, shown wherever the pathway is.
 *
 * Two of the three carry one. They are not interchangeable: synthetic inputs
 * and an unvalidated extractor are different problems, and a single generic
 * "for research use only" would blur both.
 */
export const PATHWAY_CAVEAT: Partial<Record<StudyPathway, string>> = {
  patient_assessment:
    'Patient-specific assessment is a limited prototype. Report extraction is '
    + 'rule-based and has not been validated against clinical ground truth. '
    + 'Confirm every extracted field against the source document before use.',
  demo_scenario:
    'Demonstration data is synthetic and illustrative. It was invented to '
    + 'exercise the interface, describes no real material or person, and no '
    + 'result derived from it is a scientific finding.',
};

/* -------------------------------------------------------------------------
 * Queries
 * ---------------------------------------------------------------------- */

export function stepsFor(pathway: StudyPathway | undefined): readonly PathwayStep[] {
  return PATHWAY_STEPS[pathway ?? 'research_design'] ?? PATHWAY_STEPS.research_design;
}

/**
 * Index of the step whose route is `path`, or `-1`.
 *
 * `-1` is a normal answer, not a failure: the user is entitled to open a page
 * that is not on the current pathway, and callers render an off-pathway state
 * rather than treating it as an error.
 *
 * Matching is on the path prefix at a segment boundary so `/studies/12` still
 * resolves to the `/studies` step, while `/reports` and `/report` — two
 * genuinely different modules — never match each other.
 */
export function stepIndexFor(pathway: StudyPathway | undefined,
                             path: string): number {
  const steps = stepsFor(pathway);
  const exact = steps.findIndex((s) => s.path === path);
  if (exact !== -1) return exact;
  return steps.findIndex(
    (s) => path === s.path || path.startsWith(`${s.path}/`));
}

export function stepFor(pathway: StudyPathway | undefined,
                        path: string): PathwayStep | undefined {
  const index = stepIndexFor(pathway, path);
  return index === -1 ? undefined : stepsFor(pathway)[index];
}

export function previousStep(pathway: StudyPathway | undefined,
                             path: string): PathwayStep | undefined {
  const index = stepIndexFor(pathway, path);
  return index > 0 ? stepsFor(pathway)[index - 1] : undefined;
}

export function nextStep(pathway: StudyPathway | undefined,
                         path: string): PathwayStep | undefined {
  const index = stepIndexFor(pathway, path);
  const steps = stepsFor(pathway);
  return index !== -1 && index < steps.length - 1 ? steps[index + 1] : undefined;
}

export interface PathwayProgress {
  /** 1-based position, or 0 when the page is not on the pathway. */
  position: number;
  total: number;
  /** Whole percent, for the progress bar. 0 when off-pathway. */
  percent: number;
  onPathway: boolean;
}

/**
 * Position within the pathway.
 *
 * The percentage measures *position*, not completeness of the science. Being at
 * step nine of twelve says where you are in a sequence; it says nothing about
 * whether the data supports anything — that is what Scientific Readiness is
 * for, and conflating the two is the exact misreading that framework exists to
 * prevent.
 */
export function progressFor(pathway: StudyPathway | undefined,
                            path: string): PathwayProgress {
  const steps = stepsFor(pathway);
  const index = stepIndexFor(pathway, path);
  if (index === -1) {
    return { position: 0, total: steps.length, percent: 0, onPathway: false };
  }
  return {
    position: index + 1,
    total: steps.length,
    percent: Math.round(((index + 1) / steps.length) * 100),
    onPathway: true,
  };
}

/** Every route that appears on any pathway. Used by tests and the banner. */
export function allPathwayPaths(): string[] {
  const paths = new Set<string>();
  for (const steps of Object.values(PATHWAY_STEPS)) {
    for (const step of steps) paths.add(step.path);
  }
  return [...paths];
}

export const AVAILABILITY_NOTE: Record<StepAvailability, string | undefined> = {
  operational: undefined,
  limited_prototype:
    'This step is a limited prototype. Read its own page for what it can and '
    + 'cannot do.',
  not_connected:
    'The engine behind this step is not connected. The step is shown so the '
    + 'gap is visible; continuing past it does not mean anything ran.',
};
