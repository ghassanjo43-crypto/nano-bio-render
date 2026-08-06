/**
 * Compare Designs — aligned view of genuine stored runs.
 *
 * The rule this page exists to respect: **no combined ranking**. There is no
 * approved formula for combining Delivery, Toxicity, Cost and pharmacokinetic
 * outputs into a single figure (blocker B5 in docs/MODULE_INVENTORY.md), so
 * this page aligns the genuinely calculated values side by side and stops.
 * It never declares a winner, never sums, never averages, never sorts by
 * "best".
 *
 * A value a run does not have is rendered as "not calculated" — never as zero,
 * and never borrowed from another run.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { compareRuns } from '../../api/client';
import type { ComparisonResponse, WorkspaceErrorResponse } from '../../api/types';
import {
  Alert, Badge, Button, Card, DataTable, EmptyState, SkeletonBlock,
} from '../../design-system/components';
import { ConcentrationTimeChart } from '../../charts/ConcentrationTimeChart';
import { Icon } from '../../shell/Icon';
import './WorkspacePages.css';

/** Full precision. The comparison is a record, not a summary. */
function cell(value: string | number | null): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="wp__none">not calculated</span>;
  }
  return String(value);
}

export default function ComparePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const ids = (params.get('ids') ?? '')
    .split(',').map((s) => Number(s.trim())).filter((n) => Number.isFinite(n) && n > 0);

  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (ids.length < 2) { setData(null); return; }
    setLoading(true);
    const result = await compareRuns(ids, signal);
    setLoading(false);
    if (result.status === 'error') { setError(result.error); setData(null); return; }
    setError(null);
    setData(result.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get('ids')]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  // Only runs that genuinely produced a profile contribute a curve.
  const pkRuns = (data?.runs ?? []).filter((r) => r.pk_result !== null);

  return (
    <>
      <Card
        title="Compare Designs"
        subtitle="Genuine stored runs, aligned field by field."
        accent={data !== null}
        actions={
          <Button variant="secondary" onClick={() => navigate('/history')}
                  iconLeft={<Icon name="clock" size={15} />}>
            Choose runs in History
          </Button>
        }
      >
        {ids.length < 2 && (
          <EmptyState title="Select two or more runs to compare"
                      testId="compare-empty">
            Open <strong>Simulation History</strong>, tick between two and four
            stored runs, then choose Compare. Nothing is shown here until real
            runs are selected.
            <div className="wp__emptyactions">
              <Button onClick={() => navigate('/history')}
                      iconRight={<Icon name="arrow-right" size={15} />}>
                Go to Simulation History
              </Button>
            </div>
          </EmptyState>
        )}

        {loading && <SkeletonBlock lines={5} />}

        {error && (
          <Alert tone="danger" title="Comparison unavailable">
            <p>{error.message}</p>
            {error.detail && <p className="mono wp__detail">{error.detail}</p>}
          </Alert>
        )}

        {data && (
          <>
            <Alert tone="info" title="How to read this comparison" role="note">
              <p data-testid="compare-notice">{data.notice}</p>
            </Alert>

            <div className="wp__comparehead">
              {data.runs.map((r, i) => (
                <div className="wp__comparecol" key={r.id}>
                  <span className="wp__colindex">Run {i + 1}</span>
                  <span className="wp__colname">{r.name}</span>
                  {r.origin === 'demo' && (
                    <Badge tone="warn">Synthetic demonstration data</Badge>
                  )}
                  <span className="wp__coldate">
                    {new Date(r.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>

            <DataTable
              caption="Aligned comparison"
              head={[
                { key: 'field', label: 'Field' },
                ...data.runs.map((r, i) => ({
                  key: `run-${r.id}`, label: `Run ${i + 1}`, numeric: true,
                })),
              ]}
            >
              {data.rows.map((row) => (
                <tr key={`${row.source}.${row.key}`}
                    data-testid={`compare-row-${row.key}`}>
                  <th scope="row">
                    {row.label}
                    {row.unit_note && (
                      <span className="wp__unitnote">{row.unit_note}</span>
                    )}
                  </th>
                  {row.values.map((v, i) => (
                    <td key={i} className="is-numeric">{cell(v)}</td>
                  ))}
                </tr>
              ))}
            </DataTable>

            {/* --------------------------------------- PK curves side by side */}
            {pkRuns.length > 0 && (
              <section className="wp__section">
                <h3 className="wp__subhead">
                  Pharmacokinetic profiles
                  <Badge tone="neutral">{pkRuns.length} of {data.runs.length} runs</Badge>
                </h3>
                <p className="wp__note">
                  Each chart is drawn from that run's own stored series. The
                  vertical axes are dose-scaled compartment amounts in arbitrary
                  units and are <strong>not</strong> concentrations, so the
                  charts are shown separately rather than overlaid on a shared
                  axis — overlaying values from different runs would imply a
                  common scale the model does not define.
                </p>
                <div className="wp__charts">
                  {pkRuns.map((r) => (
                    <figure className="wp__chartcell" key={r.id}>
                      <figcaption className="wp__chartcap">{r.name}</figcaption>
                      <ConcentrationTimeChart
                        time={r.pk_result!.concentration_time.time_h}
                        timeUnit={r.pk_result!.concentration_time.time_unit}
                        concentrationUnit={
                          r.pk_result!.concentration_time.concentration_unit}
                        series={[
                          { key: 'central', label: 'Central (plasma)',
                            values: r.pk_result!.concentration_time.central_plasma },
                          { key: 'peripheral', label: 'Peripheral (tissue)',
                            values: r.pk_result!.concentration_time.peripheral_tissue },
                        ]}
                      />
                    </figure>
                  ))}
                </div>
              </section>
            )}

            {/* --------------------------------------------- engines not run */}
            <section className="wp__section">
              <h3 className="wp__subhead">Engines that did not run</h3>
              <div className="wp__notgrid">
                {data.runs.map((r, i) => (
                  <div key={r.id}>
                    <p className="wp__notrunhead">Run {i + 1} — {r.name}</p>
                    {r.engines_not_run.length === 0 ? (
                      <p className="wp__note">Every attempted engine returned a result.</p>
                    ) : (
                      <ul className="wp__notlist">
                        {r.engines_not_run.map((e) => (
                          <li key={e.engine}>
                            <span className="wp__notname">{e.engine}</span>
                            <span className="wp__notreason">{e.reason}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <Alert tone="warn" title="No overall ranking is produced">
              These measures use different scales and different directions of
              improvement, and no approved formula exists for combining them.
              The platform therefore does not name a best design, and does not
              sort, sum or average across the columns above.
            </Alert>
          </>
        )}
      </Card>
    </>
  );
}
