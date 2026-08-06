/**
 * The three pathway controls, plus progress and the next recommended step.
 *
 * Rendered at the foot of every page that sits on a study pathway:
 *
 *   ← Back            the previous step *on the pathway*, never history.back()
 *   Save & Continue → validate, save, then open the next step
 *   Save & Exit       save and return to My Studies
 *
 * Back follows the pathway, not history
 * -------------------------------------
 * `history.back()` returns to whatever the user last looked at, which after a
 * detour into the 3D Builder or Evidence page is not the previous scientific
 * step. Reading the previous step from `pathways.ts` means Back always means
 * the same thing: one stop earlier in this study's sequence.
 *
 * Continue saves first
 * --------------------
 * `Save & Continue` writes the draft *before* navigating. That is what makes
 * Back safe: by the time the next page renders, the previous page's work is
 * already persisted, so returning to it cannot lose anything.
 */

import { useCallback, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Alert, Button, Dialog } from '../design-system/components';
import { Icon } from '../shell/Icon';
import { useWorkflow } from './WorkflowContext';
import {
  AVAILABILITY_NOTE, nextStep, previousStep, progressFor, stepFor, stepsFor,
} from './pathways';
import { LEAVE_PROMPT, useBeforeUnloadWarning, useGuardedNavigate }
  from './useUnsavedChanges';
import './PathwayNav.css';

export interface PathwayNavProps {
  /**
   * Run before continuing. Return false to stay put — used by steps with
   * their own validation, so Continue cannot skip past an invalid form.
   */
  onBeforeContinue?: () => boolean;
  /** Replaces the default label when a step's action is not simply "continue". */
  continueLabel?: string;
  /** Disable Continue, e.g. while a calculation is running. */
  continueDisabled?: boolean;
  /** Hide Continue entirely on a terminal step. */
  hideContinue?: boolean;
}

/** Where Save & Exit goes. The saved-studies list, which is what was saved. */
export const EXIT_PATH = '/studies';

export default function PathwayNav({
  onBeforeContinue, continueLabel, continueDisabled, hideContinue,
}: PathwayNavProps) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { session, saveDraft, isDirty } = useWorkflow();

  const pathway = session.pathway;
  const previous = previousStep(pathway, pathname);
  const next = nextStep(pathway, pathname);
  const current = stepFor(pathway, pathname);
  const progress = progressFor(pathway, pathname);

  const [savedNote, setSavedNote] = useState(false);

  useBeforeUnloadWarning(isDirty);

  const go = useCallback((to: string) => navigate(to), [navigate]);
  const { pending, guardedNavigate, discardAndGo, saveAndGo, cancel } =
    useGuardedNavigate(isDirty, go, saveDraft);

  /**
   * Back moves without prompting, and that is deliberate.
   *
   * Stepping back cannot lose anything: the session lives in `WorkflowContext`
   * for as long as the application is mounted, so every value typed on this
   * page is still there when the user returns to it — a property the existing
   * suite pins directly ("preserves PK inputs across navigation").
   *
   * Warning here would therefore raise an alarm about a loss that cannot
   * happen, and a confirmation that fires when nothing is at risk is worse
   * than none: it teaches people to click through the one that matters. The
   * real risk is a full page unload, which `useBeforeUnloadWarning` covers.
   */
  const handleBack = () => {
    if (!previous) return;
    navigate(previous.path);
  };

  const handleContinue = () => {
    if (onBeforeContinue && !onBeforeContinue()) return;
    saveDraft();
    if (next) navigate(next.path);
  };

  /**
   * Save & Exit leaves the study workflow, which is where loss becomes real.
   *
   * Two cases:
   *
   * * The page's data is valid — save it and go. Nothing to warn about.
   * * The page reports its data invalid — it cannot be saved as it stands, so
   *   leaving genuinely discards the unsaved edits. That is the case the
   *   confirmation exists for, and it offers a way to keep the work rather
   *   than only "lose it" or "stay".
   */
  const handleExit = () => {
    if (onBeforeContinue && !onBeforeContinue() && isDirty) {
      guardedNavigate(EXIT_PATH, 'exit');
      return;
    }
    saveDraft();
    setSavedNote(true);
    navigate(EXIT_PATH);
  };

  // Off-pathway pages get no controls: inventing a "previous step" for a page
  // the pathway does not contain would send the user somewhere arbitrary.
  if (!progress.onPathway) return null;

  const availabilityNote = current
    ? AVAILABILITY_NOTE[current.availability]
    : undefined;

  return (
    <div className="pwnav" data-testid="pathway-nav">
      {availabilityNote && (
        <Alert tone="info" role="note">
          <p data-testid="pathway-availability-note">{availabilityNote}</p>
        </Alert>
      )}

      <div className="pwnav__next" data-testid="pathway-next">
        {next ? (
          <>
            <span className="pwnav__nextlabel">Next recommended step</span>
            <strong>{next.label}</strong>
            <span className="pwnav__nextsummary">{next.summary}</span>
          </>
        ) : (
          <>
            <span className="pwnav__nextlabel">Final step</span>
            <strong>{current?.label ?? 'End of pathway'}</strong>
            <span className="pwnav__nextsummary">
              This is the last step on this pathway. Saving keeps the study in
              My Studies, where it can be reopened at any time.
            </span>
          </>
        )}
      </div>

      <div className="pwnav__actions">
        <div>
          <Button
            variant="secondary"
            onClick={handleBack}
            disabled={!previous}
            data-testid="pathway-back"
            iconLeft={<Icon name="chevron-left" size={15} />}
          >
            {previous ? `Back: ${previous.shortLabel}` : 'Back'}
          </Button>
          {!previous && (
            <span className="pwnav__hint" data-testid="pathway-back-hint">
              First step on this pathway
            </span>
          )}
        </div>

        <div className="pwnav__right">
          <Button
            variant="ghost"
            onClick={handleExit}
            data-testid="pathway-save-exit"
            iconLeft={<Icon name="document" size={15} />}
          >
            Save &amp; Exit
          </Button>
          {!hideContinue && (
            <Button
              onClick={handleContinue}
              disabled={continueDisabled || !next}
              size="lg"
              data-testid="pathway-continue"
              iconRight={<Icon name="chevron-right" size={16} />}
            >
              {continueLabel ?? 'Save & Continue'}
            </Button>
          )}
        </div>
      </div>

      {savedNote && (
        <p className="pwnav__saved" role="status">Study saved.</p>
      )}

      {/* ------------------------------------------- unsaved-change guard */}
      <Dialog
        open={pending !== null}
        onClose={cancel}
        title={LEAVE_PROMPT.title}
        footer={
          <div className="pwnav__modalactions">
            <Button variant="ghost" onClick={cancel}
                    data-testid="unsaved-cancel">
              {LEAVE_PROMPT.cancel}
            </Button>
            <Button variant="secondary" onClick={discardAndGo}
                    data-testid="unsaved-discard">
              {LEAVE_PROMPT.discard}
            </Button>
            <Button onClick={saveAndGo} data-testid="unsaved-save">
              {LEAVE_PROMPT.save}
            </Button>
          </div>
        }
      >
        <p data-testid="unsaved-changes-body">{LEAVE_PROMPT.body}</p>
      </Dialog>
    </div>
  );
}

/**
 * The progress rail for the active pathway.
 *
 * Separate from the controls so a page can show where the study is without
 * also showing Back/Continue — the Results stage does exactly that.
 */
export function PathwayProgress() {
  const { pathname } = useLocation();
  const { session } = useWorkflow();
  const navigate = useNavigate();

  const steps = stepsFor(session.pathway);
  const progress = progressFor(session.pathway, pathname);

  return (
    <div className="pwprog" data-testid="pathway-progress">
      <div className="pwprog__head">
        <span data-testid="pathway-position">
          {progress.onPathway
            ? `Step ${progress.position} of ${progress.total}`
            : `Not on the current pathway (${progress.total} steps)`}
        </span>
        <span className="pwprog__percent">{progress.percent}%</span>
      </div>
      <div className="pwprog__bar" aria-hidden="true">
        <div className="pwprog__fill" style={{ width: `${progress.percent}%` }} />
      </div>
      <ol className="pwprog__steps">
        {steps.map((step, index) => {
          const state = !progress.onPathway ? 'upcoming'
            : index + 1 < progress.position ? 'done'
              : index + 1 === progress.position ? 'current' : 'upcoming';
          return (
            <li key={step.id} className={`pwprog__step is-${state}`}>
              {/* Every step stays clickable. The pathway recommends an order;
                  it does not lock the user out of the rest of the platform. */}
              <button type="button" onClick={() => navigate(step.path)}
                      data-testid={`pathway-step-${step.id}`}
                      aria-current={state === 'current' ? 'step' : undefined}>
                {step.shortLabel}
              </button>
            </li>
          );
        })}
      </ol>
      <p className="pwprog__note">
        Position in the pathway. This is not a measure of scientific
        completeness — see Scientific Readiness for that.
      </p>
    </div>
  );
}
