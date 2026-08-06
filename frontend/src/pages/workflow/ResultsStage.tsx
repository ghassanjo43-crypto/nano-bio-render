/**
 * Results & Scientific Assessments.
 *
 * Shows the two calculations that genuinely ran — the design impact score and,
 * when its inputs were complete, the pharmacokinetic simulation — in the
 * context of the session's therapeutic selection, then states honestly which
 * stages could not run.
 *
 * The two results are presented in separate cards, with separate versions and
 * separate limitations, because they are separate calculations. Nothing is
 * fabricated to fill a gap: an absent PK run produces an explicit empty state,
 * never an empty chart or a zeroed profile.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { storeRun } from '../../api/client';
import type { EngineNotRun } from '../../api/types';
import { Alert, Badge, Button, Card } from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { STATUS_META, findNavItem } from '../../shell/navigation';
import { useWorkflow } from '../../workflow/WorkflowContext';
import { ResultPanel } from '../design/ResultPanel';
import { buildRequest } from '../design/schema';
import { buildPkRequest } from './pkSchema';
import { PKPanel } from './PKPanel';
import { blockedExplanation, executionPath } from './pkPathway';
import PathwayBanner from '../../workflow/PathwayBanner';
import './ResultsStage.css';

// The modules where the stages named in the alert below would live. Each one
// carries its own recorded status and summary, so this list cannot claim a
// stage ran, and cannot drift from what the module itself reports.
const PENDING_STAGES = ['disease-biomarker', 'visualisation',
                        'ai-co-designer'] as const;

export default function ResultsStage() {
  const navigate = useNavigate();
  const { session, result, pkResult, resultIsStale, saveDraft, pkInputsReady,
          pkPathway } = useWorkflow();
  const { disease, subtype, drug } = session.selection;

  // One resolution, shared with Step 3 through the workflow context.
  const pkPath = executionPath(pkPathway);

  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const hasSomethingToSave =
    result?.status === 'ok' || pkResult?.status === 'ok';

  /**
   * Persist this run server-side.
   *
   * Only genuine engine responses are sent. A failed or absent calculation is
   * recorded as an engine that did NOT run, with its reason — never as a
   * missing field that a later reader could mistake for an untried engine.
   */
  async function handleSave() {
    setSaving(true);
    setSaveError(null);

    const enginesNotRun: EngineNotRun[] = [];
    if (result?.status !== 'ok') {
      enginesNotRun.push({
        engine: 'Design impact score',
        reason: result?.status === 'error'
          ? `Calculation failed: ${result.error.message}`
          : 'Not run in this session.',
      });
    }
    if (pkResult?.status !== 'ok') {
      enginesNotRun.push({
        engine: 'Pharmacokinetic simulation',
        reason: pkResult?.status === 'error'
          ? `Calculation failed: ${pkResult.error.message}`
          : pkInputsReady
            ? 'Not run in this session.'
            : 'Required inputs were incomplete, so the engine was not called.',
      });
    }
    enginesNotRun.push({
      engine: 'Scientific assessments',
      reason: 'The assessment engines are not connected to this workflow.',
    });

    const outcome = await storeRun({
      name: session.name || 'Untitled design',
      disease: disease || null,
      subtype: subtype || null,
      drug: drug || null,
      design_inputs: result?.status === 'ok'
        ? buildRequest(session.values, session.chips) : null,
      pk_inputs: pkResult?.status === 'ok' ? buildPkRequest(session.pk) : null,
      design_result: result?.status === 'ok' ? result.data : null,
      pk_result: pkResult?.status === 'ok' ? pkResult.data : null,
      engines_not_run: enginesNotRun,
      is_demo: Boolean(session.demo),
      demo_scenario_slug: session.demo?.scenarioSlug ?? null,
      // How the study began, recorded from the session rather than inferred
      // from the route, so a stored study stays truthful about its origin.
      pathway: session.pathway,
      research_purpose: session.researchPurpose ?? null,
    });

    setSaving(false);
    if (outcome.status === 'error') {
      setSaveError(outcome.error.message);
      return;
    }
    setSavedId(outcome.data.id);
  }

  return (
    <>
      {/* Results is a scientific page, so it carries the study context like
          every other one. It is deliberately NOT a pathway step: results are
          a view of the simulation step, and the banner says so rather than
          claiming a position the page does not occupy. */}
      <PathwayBanner />

      {session.demo && (
        <Alert tone="warn" title="Synthetic demonstration data" role="note">
          <p data-testid="demo-session-banner">
            This session was loaded from the demonstration scenario{' '}
            <strong>{session.demo.scenarioName}</strong>. Its inputs are
            synthetic — not patient data, not clinical data, not validated
            experimental data, and not a treatment recommendation. The results
            below were nonetheless calculated by the genuine engines from those
            inputs, and any run you save will be recorded as demo-generated.
          </p>
        </Alert>
      )}

      {/* ------------------------------------------- session context */}
      <Card title="Session" subtitle="The therapeutic context recorded with this calculation.">
        <dl className="rs__context">
          <div><dt>Indication</dt><dd>{disease}</dd></div>
          <div><dt>Subtype</dt><dd>{subtype}</dd></div>
          <div><dt>Therapeutic agent</dt><dd>{drug}</dd></div>
        </dl>
        <p className="rs__contextnote">
          Recorded for traceability. Neither calculation below takes a disease
          as input — the design impact score is computed from formulation
          parameters only, and the pharmacokinetic profile from the dose and
          rate constants only. <strong>Neither result varies with this
          selection</strong>.
        </p>
      </Card>

      {resultIsStale && (
        <Alert tone="warn" title="Inputs changed since this result">
          The session has been edited since these results were calculated. Re-run
          to produce results that match the current inputs.
        </Alert>
      )}

      {/* ------------------------------------------------ the score */}
      <Card
        title="Design impact score"
        subtitle={result?.status === 'ok'
          ? 'Calculated by the canonical scientific scoring engine.'
          : 'No score available for this session.'}
        accent={result?.status === 'ok'}
      >
        {result === null && (
          <div className="rs__empty" data-testid="results-empty">
            <p className="rs__empty-title">No calculation has been run</p>
            <p>
              Return to the review step and select <strong>Run Simulation</strong>.
              Nothing is displayed until the engine returns a real result.
            </p>
            <Button variant="secondary" onClick={() => navigate('/workflow/review')}
                    iconLeft={<Icon name="chevron-left" size={15} />}>
              Back to review
            </Button>
          </div>
        )}

        {result?.status === 'error' && (
          <div data-testid="results-error">
            <Alert tone="danger" title="Score unavailable">
              <p>{result.error.message}</p>
              {result.error.detail && <p className="mono rs__detail">{result.error.detail}</p>}
              <p>
                No score is shown, because none was produced. A failed calculation
                never falls back to a default value.
              </p>
            </Alert>
            <div className="rs__actions">
              <Button variant="secondary" onClick={() => navigate('/workflow/design')}
                      iconLeft={<Icon name="edit" size={15} />}>
                Edit design parameters
              </Button>
              <Button onClick={() => navigate('/workflow/review')}
                      iconLeft={<Icon name="refresh" size={15} />}>
                Back to review
              </Button>
            </div>
          </div>
        )}

        {result?.status === 'ok' && (
          <ResultPanel
            data={result.data}
            onEdit={() => navigate('/workflow/design')}
            onRecalculate={() => navigate('/workflow/review')}
          />
        )}
      </Card>

      {/* ----------------------------------------- pharmacokinetics */}
      <Card
        title="Pharmacokinetic simulation"
        subtitle={pkResult?.status === 'ok'
          ? 'Calculated by the migrated two-compartment model. A separate calculation from the score above.'
          : 'No pharmacokinetic profile available for this session.'}
        accent={pkResult?.status === 'ok'}
      >
        {pkResult === null && (
          <div className="rs__empty" data-testid="pk-empty">
            {/* Three genuinely different situations. The legacy screen
                collapsed them into one and always blamed missing rate
                constants — which for an intravenous study named parameters
                that do not apply and invited the user to invent them. */}
            {pkPath === 'blocked_no_parameter_set' ? (
              <>
                <p className="rs__empty-title">
                  Pharmacokinetic simulation is not yet operational for this
                  therapeutic and route
                </p>
                <p data-testid="pk-empty-reason">
                  {blockedExplanation(session.selection.drug, pkPathway.route,
                                      pkPathway.plan)}
                </p>
                {/* Deliberately NO "supply the required inputs" action: there
                    are no inputs the user could legitimately supply here. The
                    missing item is a reviewed parameter set. */}
                <Button variant="secondary"
                        onClick={() => navigate('/workflow/review')}
                        iconLeft={<Icon name="chevron-left" size={15} />}
                        data-testid="pk-back-to-review">
                  Back to review
                </Button>
              </>
            ) : pkPath === 'undetermined' ? (
              <>
                <p className="rs__empty-title">
                  No administration route was selected
                </p>
                <p data-testid="pk-empty-reason">
                  The administration route determines which pharmacokinetic
                  model applies. None was chosen, so no model was selected and
                  no simulation was executed.{' '}
                  <strong>No concentration–time profile, half-life or AUC
                  exists for this session</strong>, and none is shown.
                </p>
                <Button variant="secondary"
                        onClick={() => navigate('/workflow/review')}
                        iconLeft={<Icon name="chevron-left" size={15} />}
                        data-testid="pk-back-to-review">
                  Select an administration route
                </Button>
              </>
            ) : (
              <>
                <p className="rs__empty-title">
                  {pkInputsReady
                    ? 'The pharmacokinetic simulation has not been run'
                    : 'The pharmacokinetic simulation did not run'}
                </p>
                <p data-testid="pk-empty-reason">
                  {pkInputsReady ? (
                    <>
                      Return to the review step and select{' '}
                      <strong>Run Simulation</strong>. No profile is displayed
                      until the engine returns a real result.
                    </>
                  ) : (
                    <>
                      This study uses the depot absorption model, which requires
                      a dose and four first-order rate constants. They were not
                      all supplied, so the model was not executed.{' '}
                      <strong>No concentration–time profile, half-life or AUC
                      exists for this session</strong>, and none is shown —
                      substituting typical values would report kinetics you
                      never specified.
                    </>
                  )}
                </p>
                <Button variant="secondary"
                        onClick={() => navigate('/workflow/review')}
                        iconLeft={<Icon name="chevron-left" size={15} />}
                        data-testid="pk-back-to-review">
                  {pkInputsReady ? 'Back to review' : 'Supply the required inputs'}
                </Button>
              </>
            )}
          </div>
        )}

        {pkResult?.status === 'error' && (
          <div data-testid="pk-error">
            <Alert tone="danger" title="Pharmacokinetic profile unavailable">
              <p>{pkResult.error.message}</p>
              {pkResult.error.detail && (
                <p className="mono rs__detail">{pkResult.error.detail}</p>
              )}
              <p>
                No curve, half-life or AUC is shown, because none was produced.
                A failed calculation never falls back to a default profile.
              </p>
            </Alert>
            <div className="rs__actions">
              <Button onClick={() => navigate('/workflow/review')}
                      iconLeft={<Icon name="refresh" size={15} />}>
                Back to review
              </Button>
            </div>
          </div>
        )}

        {pkResult?.status === 'ok' && <PKPanel data={pkResult.data} />}
      </Card>

      {/* ------------------------------- stages that could not run */}
      <Card
        title="Scientific assessments"
        subtitle="Stages of the legacy workflow that have not been migrated."
      >
        <Alert tone="info" title="These stages did not run">
          No disease-fit score, safety assessment, regulatory position or
          molecular visualisation was produced for this session. Rather than
          showing placeholder figures, the platform reports the gap.
        </Alert>

        <ul className="rs__pending" data-testid="pending-stages">
          {PENDING_STAGES.map((key) => {
            const item = findNavItem(key);
            const meta = STATUS_META[item.status];
            return (
              <li key={key}>
                <div className="rs__pending-head">
                  <span className="rs__pending-icon" aria-hidden="true">
                    <Icon name={item.icon as never} size={17} />
                  </span>
                  <span className="rs__pending-name">{item.label}</span>
                  <Badge tone={meta.tone} dot>{meta.label}</Badge>
                </div>
                <p className="rs__pending-body">{item.summary}</p>
              </li>
            );
          })}
        </ul>
      </Card>

      {/* ------------------------------------------- persist this run */}
      {hasSomethingToSave && (
        <Card
          title="Save this run"
          subtitle="Store the calculated results server-side so they appear in Simulation History."
        >
          {savedId === null ? (
            <>
              <p className="rs__contextnote">
                Only genuine engine responses are stored, together with the exact
                inputs and engine versions that produced them. Engines that did
                not run are recorded as such, with their reason, so the record
                can never be misread later.
              </p>
              {saveError && (
                <Alert tone="danger" title="Could not save this run">
                  <p>{saveError}</p>
                </Alert>
              )}
              <Button onClick={handleSave} loading={saving}
                      data-testid="save-run"
                      iconLeft={<Icon name="clock" size={15} />}>
                {saving ? 'Saving…' : 'Save run to history'}
              </Button>
            </>
          ) : (
            <>
              <Alert tone="success" title="Run saved">
                <p data-testid="run-saved">
                  Stored as run #{savedId}
                  {session.demo && ', recorded as demo-generated'}. It is now
                  available in Simulation History, where it can be reopened,
                  compared and exported as a report.
                </p>
              </Alert>
              <div className="rs__actions">
                <Button variant="secondary"
                        onClick={() => navigate(`/studies/${savedId}`)}
                        iconRight={<Icon name="arrow-right" size={15} />}>
                  Open the stored run
                </Button>
                <Button variant="ghost" onClick={() => navigate('/history')}
                        iconLeft={<Icon name="clock" size={15} />}>
                  Go to Simulation History
                </Button>
              </div>
            </>
          )}
        </Card>
      )}

      <div className="rs__footer">
        <Button variant="secondary" onClick={saveDraft}
                iconLeft={<Icon name="document" size={15} />}>
          Save draft
        </Button>
        <Button variant="ghost" onClick={() => navigate('/workflow/design')}
                iconLeft={<Icon name="edit" size={15} />}>
          Adjust design
        </Button>
        <Button onClick={() => navigate('/start')}
                iconRight={<Icon name="arrow-right" size={15} />}>
          Start a new design
        </Button>
      </div>
    </>
  );
}
