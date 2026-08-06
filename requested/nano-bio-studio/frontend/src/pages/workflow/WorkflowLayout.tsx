/**
 * Shared chrome for the three-stage design workflow.
 *
 * Renders the persistent progress indicator (completed / current / unavailable)
 * and a live session summary, then the active step. A step the user has not
 * unlocked is not navigable and is visibly marked unavailable.
 */

import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom';
import { Alert, Badge, Button } from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { useWorkflow } from '../../workflow/WorkflowContext';
import { WORKFLOW_STEPS, stepStateFor } from '../../workflow/steps';
import './WorkflowLayout.css';

export default function WorkflowLayout() {
  const location = useLocation();
  const { session, step1Complete, step2Complete, saveDraft } = useWorkflow();

  const activeIndex = WORKFLOW_STEPS.findIndex((s) => s.path === location.pathname);

  // Guard: a user cannot deep-link past a step they have not completed.
  if (activeIndex > 0 && !step1Complete) return <Navigate to="/workflow/disease" replace />;
  if (activeIndex > 1 && !step2Complete) return <Navigate to="/workflow/design" replace />;

  const { disease, subtype, drug } = session.selection;

  return (
    <div className="wf">
      {/* ------------------------------------------------ progress rail */}
      <nav className="wf__rail" aria-label="Design workflow progress">
        <ol>
          {WORKFLOW_STEPS.map((step, i) => {
            const state = stepStateFor(i, activeIndex, step1Complete, step2Complete);
            const navigable = state === 'complete' || state === 'current';
            const content = (
              <>
                <span className="wf__rail-marker" aria-hidden="true">
                  {state === 'complete' ? <Icon name="check" size={13} /> : i + 1}
                </span>
                <span className="wf__rail-text">
                  <span className="wf__rail-label">{step.label}</span>
                  <span className="wf__rail-sub">
                    {state === 'locked' ? 'Complete the previous step' : step.summary}
                  </span>
                </span>
              </>
            );
            return (
              <li key={step.id} className={`wf__rail-item is-${state}`}>
                {navigable ? (
                  <NavLink to={step.path} className="wf__rail-link"
                           aria-current={state === 'current' ? 'step' : undefined}>
                    {content}
                  </NavLink>
                ) : (
                  <div className="wf__rail-link" aria-disabled="true">
                    {content}
                    <span className="sr-only">Unavailable</span>
                  </div>
                )}
              </li>
            );
          })}
        </ol>

        <div className="wf__summary">
          <p className="eyebrow">Current session</p>
          {disease ? (
            <dl className="wf__summary-list">
              <div><dt>Disease</dt><dd>{disease}</dd></div>
              {subtype && <div><dt>Subtype</dt><dd>{subtype}</dd></div>}
              {drug && <div><dt>Therapeutic</dt><dd>{drug}</dd></div>}
            </dl>
          ) : (
            <p className="wf__summary-empty">
              No disease selected yet. Selections appear here as you make them.
            </p>
          )}
          <Button variant="secondary" size="sm" fullWidth onClick={saveDraft}
                  iconLeft={<Icon name="document" size={14} />}>
            Save draft
          </Button>
          <p className="wf__summary-note">
            Drafts are stored in this browser only. Server-side project storage
            is not yet available.
          </p>
        </div>
      </nav>

      {/* ------------------------------------------------------- content */}
      <div className="wf__content">
        <Alert tone="warn" title="Computational research use only" role="note">
          Outputs are modelled, rule-based results for research planning. They are{' '}
          <strong>not experimentally validated</strong>, not clinically validated,
          and are not regulatory approval predictions, diagnoses or treatment
          recommendations.
        </Alert>
        <Outlet />
      </div>
    </div>
  );
}

/** Shared footer for step navigation. */
export function StepActions({
  onBack, backLabel = 'Back', onContinue, continueLabel = 'Continue',
  continueDisabled, continueLoading, onSaveDraft, primaryIcon,
}: {
  onBack?: () => void;
  backLabel?: string;
  onContinue?: () => void;
  continueLabel?: string;
  continueDisabled?: boolean;
  continueLoading?: boolean;
  onSaveDraft?: () => void;
  primaryIcon?: React.ReactNode;
}) {
  return (
    <div className="wf__actions">
      <div>
        {onBack && (
          <Button variant="secondary" onClick={onBack}
                  iconLeft={<Icon name="chevron-left" size={15} />}>
            {backLabel}
          </Button>
        )}
      </div>
      <div className="wf__actions-right">
        {onSaveDraft && (
          <Button variant="ghost" onClick={onSaveDraft}
                  iconLeft={<Icon name="document" size={15} />}>
            Save draft
          </Button>
        )}
        {onContinue && (
          <Button onClick={onContinue} disabled={continueDisabled}
                  loading={continueLoading} size="lg"
                  iconRight={primaryIcon ?? <Icon name="chevron-right" size={16} />}>
            {continueLabel}
          </Button>
        )}
      </div>
    </div>
  );
}

/** Small status chip used by step headers. */
export function StepBadge({ complete }: { complete: boolean }) {
  return complete
    ? <Badge tone="success" dot>Complete</Badge>
    : <Badge tone="warn" dot>Incomplete</Badge>;
}
