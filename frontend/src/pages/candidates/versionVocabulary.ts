/**
 * The words this feature is allowed to use about a version.
 *
 * The rule
 * --------
 * **"Latest version" is never displayed.** It is ambiguous between the newest
 * draft and the one currently approved, and those are different claims: one is
 * somebody's work in progress, the other is what the organization stands
 * behind. A screen that says "latest" has told the reader nothing while
 * sounding as though it told them something.
 *
 * So every standing has a name that says which question it answers, and the
 * strings live here rather than inline in the markup — one place to read the
 * whole vocabulary, and one place a test can assert against.
 */

import type {
  CandidateVersionSummary, MaterialClassification, ResultsState,
  VersionStatus,
} from '../../api/candidateVersionClient';

/** The named standings. There is deliberately no `LATEST`. */
export const STANDING_LABEL = {
  currentWorking: 'Latest draft',
  latestApproved: 'Latest approved',
  currentEffective: 'Current effective version',
} as const;

export const STANDING_EXPLANATION = {
  currentWorking:
    'The newest draft. It has not been reviewed and the organization does '
    + 'not stand behind it.',
  latestApproved:
    'The most recent version to carry a formal approval decision.',
  currentEffective:
    'What the organization currently stands behind: the approved version if '
    + 'there is one, otherwise the newest version something relies on.',
} as const;

export type StandingKey = keyof typeof STANDING_LABEL;

export const STATUS_LABEL: Record<VersionStatus, string> = {
  draft: 'Draft',
  locked: 'Locked',
  approved: 'Approved',
  superseded: 'Superseded',
  withdrawn: 'Withdrawn',
};

export const STATUS_EXPLANATION: Record<VersionStatus, string> = {
  draft:
    'Nothing depends on this version yet, so its scientific inputs can still '
    + 'be edited in place.',
  locked:
    'Something depends on this version. Its scientific inputs cannot change; '
    + 'a change means creating a revision.',
  approved:
    'This version carries a formal approval decision. It is still locked and '
    + 'still citable.',
  superseded:
    'A later version has formally taken over. This one stays readable and '
    + 'every decision made on it stays true.',
  withdrawn:
    'Retired without a successor. The record and everything that referenced '
    + 'it remain; the organization no longer stands behind it.',
};

export const RESULTS_LABEL: Record<ResultsState, string> = {
  none: 'Not calculated',
  current: 'Current',
  stale: 'Stale',
  recalculating: 'Recalculating',
};

export const RESULTS_EXPLANATION: Record<ResultsState, string> = {
  none: 'No derived results have been computed for this version.',
  current:
    'Computed for this version’s inputs, under the recorded model and '
    + 'ruleset versions.',
  stale:
    'These numbers were computed for a different formulation. They must be '
    + 'recalculated before they are cited.',
  recalculating:
    'A recalculation has been asked for and has not yet produced a result.',
};

export const CLASSIFICATION_LABEL: Record<MaterialClassification, string> = {
  none: 'No scientific change',
  recalculation: 'Recalculation only',
  scientific_review: 'Scientific reassessment',
  safety_review: 'Safety reassessment',
};

/** The six consequences, in the order they escalate, with reader-facing names. */
export const CONSEQUENCE_LABEL: Record<string, string> = {
  recalculation: 'Recalculation',
  scientific_reassessment: 'Scientific reassessment',
  safety_reassessment: 'Safety reassessment',
  new_approval: 'New approval',
  new_report: 'New report',
  new_cro_package: 'New CRO package',
};

export const CONSEQUENCE_ORDER = [
  'recalculation', 'scientific_reassessment', 'safety_reassessment',
  'new_approval', 'new_report', 'new_cro_package',
] as const;

type Tone = 'neutral' | 'info' | 'warn' | 'danger' | 'success';

export function statusTone(status: VersionStatus): Tone {
  switch (status) {
    case 'approved': return 'success';
    case 'draft': return 'info';
    case 'locked': return 'neutral';
    case 'superseded': return 'warn';
    case 'withdrawn': return 'danger';
    default: return 'neutral';
  }
}

export function resultsTone(state: ResultsState): Tone {
  switch (state) {
    case 'current': return 'success';
    case 'stale': return 'warn';
    case 'recalculating': return 'info';
    default: return 'neutral';
  }
}

export function classificationTone(value: MaterialClassification): Tone {
  switch (value) {
    case 'safety_review': return 'danger';
    case 'scientific_review': return 'warn';
    case 'recalculation': return 'info';
    default: return 'neutral';
  }
}

/**
 * The warnings a version must carry wherever it is shown.
 *
 * Returned as data rather than rendered here so the same set appears on the
 * history row, the detail panel and the comparison column without three
 * chances to word it differently — and so a test can assert that a superseded
 * version is never displayed without its warning.
 */
export interface VersionWarning {
  key: string;
  tone: 'warn' | 'danger' | 'info';
  title: string;
  body: string;
}

export function warningsFor(version: CandidateVersionSummary,
                            effectiveVersionId: number | null
                            ): VersionWarning[] {
  const warnings: VersionWarning[] = [];

  if (version.status === 'superseded' || version.is_historical) {
    warnings.push({
      key: 'superseded',
      tone: 'warn',
      title: 'Superseded version',
      body:
        `${version.label} has been replaced by version `
        + `${version.superseded_by_version_id ?? 'a later revision'}. It stays `
        + 'in the record and every decision made on it stays true — do not '
        + 'use it as the basis for new work.',
    });
  }

  if (version.status === 'withdrawn') {
    warnings.push({
      key: 'withdrawn',
      tone: 'danger',
      title: 'Withdrawn version',
      body:
        `${version.label} was retired without a successor. `
        + (version.lock_reason ? `Reason recorded: ${version.lock_reason}. ` : '')
        + 'The organization no longer stands behind it.',
    });
  }

  if (version.results_state === 'stale') {
    warnings.push({
      key: 'stale-results',
      tone: 'warn',
      title: 'Results are stale',
      body:
        'The numbers shown for this version were computed for '
        + (version.results_inherited_from_id
          ? `version ${version.results_inherited_from_id}, a different formulation. `
          : 'a different formulation. ')
        + 'They must be recalculated before they are cited, and a reassessment '
        + 'is required before this version can carry an approval.',
    });
  }

  if (version.results_state === 'recalculating') {
    warnings.push({
      key: 'recalculating',
      tone: 'info',
      title: 'Recalculation in progress',
      body:
        'A recalculation has been requested. The previous numbers stay '
        + 'unusable until an engine produces new ones for this version.',
    });
  }

  if (version.status === 'draft'
      && effectiveVersionId !== null
      && effectiveVersionId !== version.id) {
    warnings.push({
      key: 'not-effective',
      tone: 'info',
      title: 'Not the current effective version',
      body:
        `${version.label} is a draft. The organization currently stands behind `
        + `version ${effectiveVersionId}.`,
    });
  }

  return warnings;
}

/**
 * Which named standings a version holds. A version can hold more than one.
 *
 * Never returns an unqualified "latest": the three keys are the three
 * questions somebody actually asks, and each answer says which one it answers.
 */
export function standingsFor(version: CandidateVersionSummary, history: {
  current_effective_version_id: number | null;
  latest_approved_version_id: number | null;
  latest_draft_version_id: number | null;
}): StandingKey[] {
  const standings: StandingKey[] = [];
  if (history.latest_draft_version_id === version.id) {
    standings.push('currentWorking');
  }
  if (history.latest_approved_version_id === version.id) {
    standings.push('latestApproved');
  }
  if (history.current_effective_version_id === version.id) {
    standings.push('currentEffective');
  }
  return standings;
}

/** A short, readable rendering of a snapshot value for the comparison table. */
export function displayValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'string') return value === '' ? '—' : value;
  return JSON.stringify(value);
}
