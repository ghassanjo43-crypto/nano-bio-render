/**
 * A single stored run, opened from Simulation History — and the source of the
 * downloadable report.
 *
 * Everything shown is read back from the stored record. Nothing is recomputed
 * here, so what you see is exactly what the engines returned at the time of the
 * run, together with the engine versions that produced it.
 *
 * The report is generated in the browser from that same stored record, so it
 * cannot drift from what the screen shows.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getRun } from '../../api/client';
import type { RunDetail, WorkspaceErrorResponse } from '../../api/types';
import {
  Alert, Badge, Button, Card, DataTable, SkeletonBlock,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { PKPanel } from '../workflow/PKPanel';
import { ResultPanel } from '../design/ResultPanel';
import { buildReport, downloadReport } from './report';
import './WorkspacePages.css';

export default function RunDetailPage() {
  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    const id = Number(runId);
    if (!Number.isFinite(id)) return;
    const result = await getRun(id, signal);
    if (result.status === 'error') { setError(result.error); return; }
    setError(null);
    setRun(result.data);
  }, [runId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (error) {
    return (
      <Card title="Run unavailable">
        <Alert tone="danger" title={error.message}>
          {error.detail && <p className="mono wp__detail">{error.detail}</p>}
          <p>No stored record was returned, so nothing is displayed.</p>
        </Alert>
        <Button variant="secondary" onClick={() => navigate('/history')}
                iconLeft={<Icon name="chevron-left" size={15} />}>
          Back to history
        </Button>
      </Card>
    );
  }

  if (run === null) {
    return <Card title="Loading run"><SkeletonBlock lines={5} /></Card>;
  }

  return (
    <>
      <Card
        title={run.name}
        subtitle="A stored record. Values are read back exactly as the engines returned them."
        accent
        actions={
          <Button onClick={() => downloadReport(buildReport(run))}
                  iconLeft={<Icon name="document" size={15} />}
                  data-testid="download-report">
            Download report
          </Button>
        }
      >
        {run.origin === 'demo' && (
          <Alert tone="warn" title="Synthetic demonstration data" role="note">
            <p data-testid="demo-run-banner">
              This run was produced from the demonstration scenario{' '}
              <code>{run.demo_scenario_slug}</code> (fixture set{' '}
              <code>{run.demo_fixture_version}</code>). Its inputs are synthetic.
              They are not patient data, not clinical data, not validated
              experimental data, and not a treatment recommendation. The results
              below were nonetheless calculated by the genuine engines from those
              inputs.
            </p>
          </Alert>
        )}

        <dl className="wp__context">
          <div><dt>Indication</dt><dd>{run.disease ?? '—'}</dd></div>
          <div><dt>Subtype</dt><dd>{run.subtype ?? '—'}</dd></div>
          <div><dt>Therapeutic agent</dt><dd>{run.drug ?? '—'}</dd></div>
          <div><dt>Recorded</dt><dd>{new Date(run.created_at).toLocaleString()}</dd></div>
        </dl>
        <p className="wp__note">
          Recorded for traceability. Neither engine takes a disease as input, so
          this context did not affect any value below.
        </p>

        <section className="wp__section">
          <h3 className="wp__subhead">
            Engines executed
            <Badge tone={run.status === 'complete' ? 'success'
                        : run.status === 'partial' ? 'warn' : 'neutral'} dot>
              {run.status}
            </Badge>
          </h3>
          {run.engines_run.length === 0 ? (
            <p className="wp__note" data-testid="no-engines-run">
              No engine produced a result for this run.
            </p>
          ) : (
            <ul className="wp__list" data-testid="engines-run">
              {run.engines_run.map((e) => (
                <li key={e}><Icon name="check" size={14} />{e}</li>
              ))}
            </ul>
          )}

          <h3 className="wp__subhead">Engines that did not run</h3>
          {run.engines_not_run.length === 0 ? (
            <p className="wp__note">None recorded.</p>
          ) : (
            <ul className="wp__notlist" data-testid="engines-not-run">
              {run.engines_not_run.map((e) => (
                <li key={e.engine}>
                  <span className="wp__notname">{e.engine}</span>
                  <span className="wp__notreason">{e.reason}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </Card>

      <Card title="Design impact score"
            subtitle={run.design_result
              ? 'As calculated at the time of the run.'
              : 'Not calculated for this run.'}>
        {run.design_result ? (
          <ResultPanel
            data={run.design_result}
            onEdit={() => navigate('/workflow/design')}
            onRecalculate={() => navigate('/workflow/review')}
          />
        ) : (
          <p className="wp__none" data-testid="no-design-result">
            No design impact score was produced for this run, so none is shown.
          </p>
        )}
      </Card>

      <Card title="Pharmacokinetic simulation"
            subtitle={run.pk_result
              ? 'As calculated at the time of the run.'
              : 'Not calculated for this run.'}>
        {run.pk_result ? (
          <PKPanel data={run.pk_result} />
        ) : (
          <p className="wp__none" data-testid="no-pk-result">
            No pharmacokinetic profile was produced for this run, so no curve,
            half-life or AUC is shown.
          </p>
        )}
      </Card>

      <Card title="Stored inputs"
            subtitle="The exact request bodies sent to each engine, so the run can be reproduced.">
        <h3 className="wp__subhead">Design inputs</h3>
        {run.design_inputs ? (
          <DataTable dense caption="Stored design inputs"
                     head={[{ key: 'p', label: 'Field' },
                            { key: 'v', label: 'Value', numeric: true }]}>
            {Object.entries(run.design_inputs).map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{k}</th>
                <td className="is-numeric">
                  {Array.isArray(v) ? v.join(', ') : String(v)}
                </td>
              </tr>
            ))}
          </DataTable>
        ) : <p className="wp__none">Not recorded.</p>}

        <h3 className="wp__subhead">Pharmacokinetic inputs</h3>
        {run.pk_inputs ? (
          <DataTable dense caption="Stored PK inputs"
                     head={[{ key: 'p', label: 'Field' },
                            { key: 'v', label: 'Value', numeric: true }]}>
            {Object.entries(run.pk_inputs).map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{k}</th>
                <td className="is-numeric">{String(v)}</td>
              </tr>
            ))}
          </DataTable>
        ) : <p className="wp__none">Not recorded.</p>}
      </Card>

      <div className="wp__footer">
        <Button variant="secondary" onClick={() => navigate('/history')}
                iconLeft={<Icon name="chevron-left" size={15} />}>
          Back to history
        </Button>
        <Button variant="ghost" onClick={() => navigate(`/compare?ids=${run.id}`)}
                iconLeft={<Icon name="compare" size={15} />}>
          Compare with another run
        </Button>
      </div>
    </>
  );
}
