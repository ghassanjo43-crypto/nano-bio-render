/**
 * Workflow step definitions and the rules that gate progress.
 *
 * The sequence mirrors the legacy Streamlit application:
 *   0_Disease_Selection → 1_Design_Parameters → 2_Run_Simulation → results.
 */

export type StepState = 'complete' | 'current' | 'upcoming' | 'locked';

export interface WorkflowStep {
  id: string;
  label: string;
  summary: string;
  path: string;
}

export const WORKFLOW_STEPS: readonly WorkflowStep[] = [
  {
    id: 'disease',
    label: 'Disease & Therapeutic',
    summary: 'Indication, subtype and drug',
    path: '/workflow/disease',
  },
  {
    id: 'design',
    label: 'Design Parameters',
    summary: 'Nanoparticle formulation',
    path: '/workflow/design',
  },
  {
    id: 'review',
    label: 'Review & Run',
    summary: 'Confirm, then calculate',
    path: '/workflow/review',
  },
  {
    id: 'results',
    label: 'Results & Assessments',
    summary: 'Scores and scientific status',
    path: '/workflow/results',
  },
];

export function stepStateFor(
  index: number,
  activeIndex: number,
  step1Complete: boolean,
  step2Complete: boolean,
): StepState {
  if (index === activeIndex) return 'current';
  const unlocked =
    index === 0
    || (index === 1 && step1Complete)
    || (index >= 2 && step1Complete && step2Complete);
  if (!unlocked) return 'locked';
  return index < activeIndex ? 'complete' : 'upcoming';
}
