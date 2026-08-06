/**
 * The pathway, study and candidate header shown on every scientific page.
 *
 * Answers three questions the user would otherwise have to reconstruct from
 * memory: which pathway am I on, which study am I editing, and which candidate
 * formulation is on screen. Study and candidate are separate lines because they
 * are separate things — one study may examine several candidates in turn, and a
 * header that showed only "study" would leave the researcher guessing which
 * formulation the numbers in front of them belong to.
 *
 * Privacy: this renders the user-chosen study and candidate names and the
 * pathway. It never receives or renders anything extracted from an uploaded
 * report — see `StudyContextBar` for the same contract on the breadcrumb trail.
 */

import { useLocation } from 'react-router-dom';
import { Alert, Badge } from '../design-system/components';
import { useWorkflow } from './WorkflowContext';
import {
  PATHWAY_CAVEAT, PATHWAY_LABEL, progressFor, stepFor, nextStep,
} from './pathways';
import './PathwayNav.css';

const PATHWAY_TONE = {
  patient_assessment: 'info',
  research_design: 'accent',
  demo_scenario: 'warn',
} as const;

export default function PathwayBanner() {
  const { pathname } = useLocation();
  const { session } = useWorkflow();

  const pathway = session.pathway ?? 'research_design';
  const progress = progressFor(pathway, pathname);
  const current = stepFor(pathway, pathname);
  const next = nextStep(pathway, pathname);
  const caveat = PATHWAY_CAVEAT[pathway];

  return (
    <section className="pwbanner" data-testid="pathway-banner">
      <div className="pwbanner__row">
        <Badge tone={PATHWAY_TONE[pathway]} dot>
          <span data-testid="pathway-name">{PATHWAY_LABEL[pathway]}</span>
        </Badge>

        <dl className="pwbanner__facts">
          <div>
            <dt>Study</dt>
            <dd data-testid="banner-study">
              {session.name?.trim() || 'Untitled study'}
            </dd>
          </div>
          <div>
            <dt>Candidate</dt>
            <dd data-testid="banner-candidate">
              {/* Never invented. An unnamed candidate says so, because a
                  fabricated label would look like a real formulation id. */}
              {session.candidateName?.trim() || 'Not named'}
            </dd>
          </div>
          <div>
            <dt>Step</dt>
            <dd data-testid="banner-step">
              {progress.onPathway
                ? `${progress.position} of ${progress.total} — ${current?.label ?? ''}`
                : 'Not on this pathway'}
            </dd>
          </div>
        </dl>
      </div>

      {progress.onPathway ? (
        <p className="pwbanner__next" data-testid="banner-next">
          {next
            ? <>Next: <strong>{next.label}</strong></>
            : <>This is the final step on this pathway.</>}
        </p>
      ) : (
        <p className="pwbanner__next" data-testid="banner-offpathway">
          This page is not part of the{' '}
          <strong>{PATHWAY_LABEL[pathway]}</strong> pathway. You are free to be
          here; the study is unchanged and the pathway resumes wherever you left
          it.
        </p>
      )}

      {caveat && (
        <Alert tone={pathway === 'demo_scenario' ? 'warn' : 'info'} role="note">
          <p data-testid="pathway-caveat">{caveat}</p>
        </Alert>
      )}
    </section>
  );
}
