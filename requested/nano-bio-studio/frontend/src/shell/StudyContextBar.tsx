/**
 * Breadcrumb trail and study context header.
 *
 * Privacy contract — enforced by construction, not by convention
 * -------------------------------------------------------------
 * This component receives **only** the fields declared in `StudyContext` below.
 * There is no patient name, date of birth, medical record number or free text
 * from an uploaded report in that type, so none can be rendered here, placed in
 * a browser title, or read out of the DOM by analytics.
 *
 * The study *name* is user-chosen and could in principle be filled with an
 * identifier, so it is rendered in the header only — never in the document
 * title and never in a URL. Route parameters are opaque integer ids.
 */

import { Link, useLocation } from 'react-router-dom';
import { Badge } from '../design-system/components';
import {
  activeNavKeyForPath, findNavItem, groupLabelFor, pageTitleForPath,
  workflowStageForPath,
} from './navigation';
import type { StudyPathway } from './navigation';
import './StudyContextBar.css';

export interface StudyContext {
  pathway: StudyPathway;
  /** User-chosen study name. Never placed in a URL or document title. */
  name?: string;
  /** The indication, for orientation. Not an identifier. */
  disease?: string;
  /** True when the inputs are synthetic. Always shown when true. */
  synthetic?: boolean;
  /** Whether the draft is saved. */
  saveState?: 'saved' | 'unsaved' | 'saving';
}

const PATHWAY_LABEL: Record<StudyPathway, string> = {
  patient_assessment: 'Patient assessment',
  research_design: 'Research design',
  demo_scenario: 'Demonstration',
};

const PATHWAY_TONE = {
  patient_assessment: 'info',
  research_design: 'accent',
  demo_scenario: 'warn',
} as const;

/**
 * A draft persisted before pathways existed, or a record from an older
 * backend, carries no pathway. "Not recorded" is the honest answer; guessing
 * one would put a false claim in the header, and indexing blindly would crash.
 */
function describePathway(pathway: StudyPathway | undefined) {
  if (pathway && pathway in PATHWAY_LABEL) {
    return { label: PATHWAY_LABEL[pathway], tone: PATHWAY_TONE[pathway] };
  }
  return { label: 'Pathway not recorded', tone: 'neutral' as const };
}

const SAVE_LABEL = {
  saved: 'Draft saved',
  saving: 'Saving…',
  unsaved: 'Unsaved changes',
} as const;

export interface Crumb {
  label: string;
  to?: string;
}

/**
 * Build the trail for a path. Exported so it can be tested without rendering.
 *
 * Never includes the study name: a breadcrumb is reflected in navigation
 * history and screen-reader announcements, and the name is user-supplied text.
 */
export function crumbsForPath(path: string, context?: StudyContext): Crumb[] {
  const crumbs: Crumb[] = [{ label: 'Home', to: '/home' }];

  const key = activeNavKeyForPath(path, { pathway: context?.pathway });
  if (!key) return [...crumbs, { label: pageTitleForPath(path) }];

  const group = groupLabelFor(key);
  if (group && group !== 'Start') crumbs.push({ label: group });

  const item = findNavItem(key);
  const stage = workflowStageForPath(path);

  // Inside the workflow the module entry is a link back to its list; the stage
  // is the leaf. Elsewhere the module itself is the leaf.
  if (stage) {
    crumbs.push({ label: item.label, to: item.path });
    crumbs.push({ label: stage });
  } else if (item.path === path) {
    crumbs.push({ label: item.label });
  } else {
    crumbs.push({ label: item.label, to: item.path });
    crumbs.push({ label: pageTitleForPath(path) });
  }

  return crumbs;
}

export default function StudyContextBar({ context }: {
  context?: StudyContext;
}) {
  const { pathname } = useLocation();
  const crumbs = crumbsForPath(pathname, context);
  const last = crumbs.length - 1;

  return (
    <div className="scb" data-testid="study-context-bar">
      <nav aria-label="Breadcrumb" className="scb__crumbs">
        <ol>
          {crumbs.map((crumb, i) => (
            <li key={`${crumb.label}-${i}`}>
              {crumb.to && i !== last
                ? <Link to={crumb.to}>{crumb.label}</Link>
                : <span aria-current={i === last ? 'page' : undefined}>
                    {crumb.label}
                  </span>}
              {i !== last && <span className="scb__sep" aria-hidden="true">/</span>}
            </li>
          ))}
        </ol>
      </nav>

      {context && (
        <div className="scb__study" data-testid="study-context">
          <Badge tone={describePathway(context.pathway).tone}>
            {describePathway(context.pathway).label}
          </Badge>
          {context.name && (
            <span className="scb__name" data-testid="study-name">
              {context.name}
            </span>
          )}
          {context.disease && (
            <span className="scb__disease">{context.disease}</span>
          )}
          {context.synthetic && (
            <Badge tone="warn" data-testid="synthetic-badge">
              Synthetic data
            </Badge>
          )}
          {context.saveState && (
            <span className={`scb__save scb__save--${context.saveState}`}
                  data-testid="save-state">
              {SAVE_LABEL[context.saveState]}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
