/**
 * Post-login session gate.
 *
 * A returning user chooses: resume the current design, start a new one, or open
 * a previously saved design.
 *
 * The saved list contains **only real drafts this user saved in this browser**.
 * It is never seeded with examples, and when empty it says so plainly.
 */

import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { Alert, Badge, Button, Card, EmptyState } from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { useWorkflow } from '../../workflow/WorkflowContext';
import { WORKFLOW_STEPS } from '../../workflow/steps';
import './SessionStartPage.css';

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? 'unknown date'
    : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export default function SessionStartPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { session, savedDrafts, startNew, loadDraft, deleteDraft, step1Complete }
    = useWorkflow();

  const inProgress = step1Complete || session.furthestStep > 1;
  const resumePath = WORKFLOW_STEPS[Math.min(session.furthestStep - 1, 3)]?.path
    ?? '/workflow/disease';

  const begin = () => { startNew(); navigate('/workflow/disease'); };

  const open = (id: string) => {
    if (loadDraft(id)) navigate('/workflow/disease');
  };

  return (
    <div className="ss">
      <header className="ss__head">
        <p className="eyebrow">Design session</p>
        <h2 className="ss__title">
          Welcome{user?.full_name ? `, ${user.full_name}` : ''}
        </h2>
        <p className="ss__lead">
          Every evaluation begins with a design session: choose the indication and
          therapeutic, define the nanoparticle, then review and run.
        </p>
      </header>

      <div className="ss__choices">
        {inProgress && (
          <Card className="ss__choice ss__choice--resume" accent>
            <span className="ss__choice-icon"><Icon name="refresh" size={22} /></span>
            <h3 className="ss__choice-title">Resume current design</h3>
            <p className="ss__choice-body">
              {session.selection.disease
                ? <>Continue <strong>{session.selection.disease}</strong>
                    {session.selection.subtype && <> — {session.selection.subtype}</>}
                    {session.selection.drug && <> with {session.selection.drug}</>}.</>
                : 'Continue where you left off.'}
            </p>
            <p className="ss__choice-meta">
              Last edited {formatWhen(session.updatedAt)} · at step{' '}
              {Math.min(session.furthestStep, WORKFLOW_STEPS.length)} of {WORKFLOW_STEPS.length}
            </p>
            <Button fullWidth onClick={() => navigate(resumePath)}
                    iconRight={<Icon name="arrow-right" size={15} />}>
              Resume
            </Button>
          </Card>
        )}

        <Card className="ss__choice">
          <span className="ss__choice-icon"><Icon name="hexagon" size={22} /></span>
          <h3 className="ss__choice-title">Start a new design</h3>
          <p className="ss__choice-body">
            Begin a fresh session at Step 1 — Disease &amp; Therapeutic Selection.
          </p>
          <p className="ss__choice-meta">Clears the current unsaved session.</p>
          <Button fullWidth variant={inProgress ? 'secondary' : 'primary'}
                  onClick={begin} data-testid="start-new"
                  iconRight={<Icon name="arrow-right" size={15} />}>
            Start new design
          </Button>
        </Card>

        <Card className="ss__choice">
          <span className="ss__choice-icon"><Icon name="flask" size={22} /></span>
          <h3 className="ss__choice-title">Load a demo scenario</h3>
          <p className="ss__choice-body">
            Start from a ready-made scenario with synthetic inputs, and run the
            genuinely connected engines end to end.
          </p>
          <p className="ss__choice-meta">
            Synthetic demonstration inputs. No stored results.
          </p>
          <Button fullWidth variant="secondary"
                  onClick={() => navigate('/demo')} data-testid="start-demo"
                  iconRight={<Icon name="arrow-right" size={15} />}>
            Open Demo Workspace
          </Button>
        </Card>

        <Card className="ss__choice">
          <span className="ss__choice-icon"><Icon name="document" size={22} /></span>
          <h3 className="ss__choice-title">Assess a medical report</h3>
          <p className="ss__choice-body">
            Upload a report, review its contents and carry the confirmed
            therapeutic context into a design session.
          </p>
          <p className="ss__choice-meta">
            Synthetic and de-identified documents only. Automatic extraction is
            not available — you enter the details yourself.
          </p>
          <Button fullWidth variant="secondary"
                  onClick={() => navigate('/report')} data-testid="start-report"
                  iconRight={<Icon name="arrow-right" size={15} />}>
            Start report assessment
          </Button>
        </Card>

        <Card className="ss__choice">
          <span className="ss__choice-icon"><Icon name="folder" size={22} /></span>
          <h3 className="ss__choice-title">Open a saved design</h3>
          <p className="ss__choice-body">
            {savedDrafts.length > 0
              ? `${savedDrafts.length} saved ${savedDrafts.length === 1 ? 'design' : 'designs'} in this browser.`
              : 'No saved designs yet.'}
          </p>
          <p className="ss__choice-meta">
            Drafts are stored locally. Server-side projects are not yet available.
          </p>
        </Card>
      </div>

      <Card title="Saved designs" subtitle="Real drafts you saved in this browser.">
        {savedDrafts.length === 0 ? (
          <EmptyState
            testId="no-saved-designs"
            icon={<Icon name="folder" size={22} />}
            title="No saved designs"
            action={
              <Button variant="secondary" size="sm" onClick={begin}
                      iconRight={<Icon name="arrow-right" size={15} />}>
                Start your first design
              </Button>
            }
          >
            Use <strong>Save draft</strong> at any step to keep a session here.
            This list shows only designs you actually saved — it is never
            populated with examples.
          </EmptyState>
        ) : (
          <ul className="ss__drafts" data-testid="saved-designs">
            {savedDrafts.map((d) => (
              <li key={d.id}>
                <div className="ss__draft-main">
                  <p className="ss__draft-name">
                    {d.selection.disease || 'Untitled design'}
                    {d.id === session.id && <Badge tone="accent">Current</Badge>}
                  </p>
                  <p className="ss__draft-meta">
                    {d.selection.subtype && <>{d.selection.subtype} · </>}
                    {d.selection.drug && <>{d.selection.drug} · </>}
                    saved {formatWhen(d.updatedAt)}
                  </p>
                </div>
                <div className="ss__draft-actions">
                  <Button size="sm" variant="secondary" onClick={() => open(d.id)}>
                    Open
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => deleteDraft(d.id)}
                          aria-label={`Delete draft ${d.selection.disease || 'Untitled'}`}>
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Alert tone="warn" title="Computational research use only" role="note">
        Outputs are modelled, rule-based results for research planning. They are
        not experimentally validated, not clinically validated, and are not
        regulatory approval predictions, diagnoses or treatment recommendations.
      </Alert>
    </div>
  );
}
