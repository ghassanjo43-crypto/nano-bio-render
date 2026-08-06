/**
 * Validation Registry — the list, its filters and the dashboard summary.
 *
 * Nothing on this page computes eligibility. Every badge, count and level comes
 * from the server: `e3_eligible` is the backend's verdict, not a rule applied
 * here. A client-side opinion about what counts as evidence would be a second
 * answer to the question the registry exists to answer once.
 *
 * Failed, rejected and superseded records are listed alongside approved ones by
 * default. Hiding them would make the registry a record of successes, which is
 * the opposite of what it is for.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  getRegistryDashboard, listExperiments, listResolutions,
  resolveContradiction,
  type ContradictionResolutionRow, type RegistryDashboard,
  type RegistryFilters,
} from '../../api/registryClient';
import type { WorkspaceErrorResponse } from '../../api/types';
import {
  Alert, Badge, Button, Card, DataTable, EmptyState, SelectField,
  SkeletonBlock, TextField,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { useWorkflow } from '../../workflow/WorkflowContext';
import {
  PURPOSE_LABEL, STATUS_LABEL, SUBTYPE_LABEL, statusLabel, statusTone,
  type ExperimentSummary, type PurposeId,
} from './registryTypes';
import './ValidationRegistry.css';

const STATUS_OPTIONS = Object.entries(STATUS_LABEL);
const SUBTYPE_OPTIONS = Object.entries(SUBTYPE_LABEL);
const PURPOSE_OPTIONS = Object.entries(PURPOSE_LABEL);

export default function ValidationRegistryPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const [rows, setRows] = useState<ExperimentSummary[] | null>(null);
  const [dashboard, setDashboard] = useState<RegistryDashboard | null>(null);
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const { session } = useWorkflow();
  const studyId = session.studyId ?? null;
  const [resolutions, setResolutions] =
    useState<ContradictionResolutionRow[]>([]);
  const [resolvingPurpose, setResolvingPurpose] = useState<string | null>(null);
  const [rationale, setRationale] = useState('');
  const [settle, setSettle] = useState(false);

  const [filters, setFilters] = useState<RegistryFilters>(() => ({
    subtype: params.get('subtype') ?? undefined,
    purpose: params.get('purpose') ?? undefined,
    status: params.get('status') ?? undefined,
    laboratory: params.get('laboratory') ?? undefined,
    investigator: params.get('investigator') ?? undefined,
    e3_eligible: params.get('e3') === 'true' ? true
      : params.get('e3') === 'false' ? false : undefined,
  }));

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    const [list, summary] = await Promise.all([
      listExperiments(filters, signal),
      getRegistryDashboard(filters.study_id, signal),
    ]);
    setLoading(false);
    if (list.status === 'error') { setError(list.error); setRows(null); return; }
    setError(null);
    setRows(list.data.experiments);
    setDashboard(summary.status === 'ok' ? summary.data : null);
    if (studyId !== null) {
      const recorded = await listResolutions(studyId, signal);
      if (recorded.status === 'ok') setResolutions(recorded.data.resolutions);
    }
  }, [filters, studyId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const setFilter = (key: keyof RegistryFilters, value: unknown) => {
    setFilters((prev) => ({ ...prev, [key]: value === '' ? undefined : value }));
    const next = new URLSearchParams(params);
    if (value === '' || value === undefined) next.delete(String(key));
    else next.set(String(key), String(value));
    setParams(next, { replace: true });
  };

  const activeFilterCount = useMemo(
    () => Object.values(filters).filter((v) => v !== undefined && v !== '').length,
    [filters]);

  return (
    <>
      <Card
        title="Experimental Validation Registry"
        subtitle={
          'In-vitro experiments recorded against an exact candidate version. '
          + 'An approved experiment supports E3 for one scientific purpose — '
          + 'not for the candidate or the study as a whole.'
        }
        accent
        actions={
          <Button onClick={() => navigate('/validation/new')}
                  iconLeft={<Icon name="flask" size={15} />}
                  data-testid="new-experiment">
            New in-vitro experiment
          </Button>
        }
      >
        <Alert tone="info" role="note">
          <p data-testid="registry-scope-note">
            E3 means <strong>approved in-vitro evidence for a specific
            scientific purpose, on a specific candidate version</strong>. It
            does not mean the candidate is validated. E4 to E6 — prospective
            in-vitro, in-vivo and clinical validation — are not recorded by this
            milestone and cannot be requested.
          </p>
        </Alert>

        {/* ------------------------------------------------- dashboard */}
        {dashboard && (
          <div className="vr__summary" data-testid="registry-dashboard">
            <div className="vr__stat">
              <span className="vr__statlabel">Experiments</span>
              <strong data-testid="stat-total">{dashboard.total_experiments}</strong>
            </div>
            {(['draft', 'under_review', 'approved', 'rejected'] as const).map(
              (key) => (
                <div className="vr__stat" key={key}>
                  <span className="vr__statlabel">{STATUS_LABEL[key]}</span>
                  <strong data-testid={`stat-${key}`}>
                    {dashboard.by_status[key] ?? 0}
                  </strong>
                </div>
              ))}
            <div className="vr__stat">
              <span className="vr__statlabel">Purposes at E3</span>
              <strong data-testid="stat-e3-purposes">
                {dashboard.purposes_with_e3.length}
              </strong>
            </div>
            {dashboard.purposes_with_contradiction.length > 0 && (
              <div className="vr__stat vr__stat--warn">
                <span className="vr__statlabel">Contradictions</span>
                <strong data-testid="stat-contradictions">
                  {dashboard.purposes_with_contradiction.length}
                </strong>
              </div>
            )}
          </div>
        )}

        {dashboard && dashboard.purposes_with_contradiction.length > 0 && (
          <Alert tone="warn" title="Conflicting approved evidence" role="note">
            <p data-testid="registry-contradiction">
              Approved experiments disagree for:{' '}
              {dashboard.purposes_with_contradiction
                .map((p) => PURPOSE_LABEL[p as PurposeId] ?? p).join(', ')}.
              The evidence level is held until a reviewer records a resolution.
              No record has been discarded and the favourable result has not
              been preferred.
            </p>

            {studyId !== null && dashboard.purposes_with_contradiction.map(
              (purpose) => (
                <div key={purpose} className="vr__resolve"
                     data-testid={`resolve-${purpose}`}>
                  {resolvingPurpose !== purpose ? (
                    <Button variant="secondary" size="sm"
                            data-testid={`open-resolve-${purpose}`}
                            onClick={() => {
                              setResolvingPurpose(purpose);
                              setRationale(''); setSettle(false);
                            }}>
                      Record a resolution
                    </Button>
                  ) : (
                    <>
                      <p className="vr__note" data-testid="resolve-guidance">
                        A resolution records how the conflict should be read.
                        It changes no experiment: every conflicting record
                        keeps its approval, its comments and its measurements.
                        Leaving the level held is a legitimate outcome and is
                        the default.
                      </p>
                      <TextField
                        id={`rationale-${purpose}`} label="Rationale" required
                        type="text" value={rationale}
                        onChange={(e) => setRationale(e.target.value)}
                        help="Required. A resolution without a stated reason cannot be weighed by anybody else."
                      />
                      <label className="vr__check">
                        <input type="checkbox" checked={settle}
                               data-testid={`settle-${purpose}`}
                               onChange={(e) => setSettle(e.target.checked)} />
                        <span>
                          Settle this purpose at E3 despite the conflict.
                          Leave unchecked to keep it held.
                        </span>
                      </label>
                      <div className="vr__actions">
                        <Button variant="ghost"
                                data-testid={`cancel-resolve-${purpose}`}
                                onClick={() => setResolvingPurpose(null)}>
                          Cancel
                        </Button>
                        <Button disabled={!rationale.trim()}
                                data-testid={`submit-resolve-${purpose}`}
                                onClick={async () => {
                                  const result = await resolveContradiction(
                                    studyId, {
                                      purpose,
                                      rationale: rationale.trim(),
                                      resolved_level: settle ? 'E3' : null,
                                    });
                                  if (result.status === 'error') {
                                    setError(result.error); return;
                                  }
                                  setResolvingPurpose(null);
                                  await load();
                                }}>
                          Record resolution
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              ))}
          </Alert>
        )}

        {resolutions.length > 0 && (
          <div className="vr__resolutions" data-testid="resolution-history">
            <p className="eyebrow">Recorded resolutions</p>
            <p className="vr__note">
              Append-only. A later reading supersedes an earlier one; neither
              the resolutions nor the evidence beneath them is rewritten.
            </p>
            <DataTable caption="Contradiction resolutions"
                       head={[{ key: 'p', label: 'Purpose' },
                              { key: 'l', label: 'Outcome' },
                              { key: 'r', label: 'Rationale' },
                              { key: 'w', label: 'When' }]}>
              {resolutions.map((r) => (
                <tr key={r.id} data-testid={`resolution-${r.id}`}>
                  <th scope="row">
                    {PURPOSE_LABEL[r.purpose as PurposeId] ?? r.purpose}
                  </th>
                  <td>{r.resolved_level ?? 'Held'}</td>
                  <td>{r.rationale}</td>
                  <td>
                    {new Date(r.resolved_at).toLocaleString()}
                    {r.superseded_by_id && ' (superseded)'}
                  </td>
                </tr>
              ))}
            </DataTable>
          </div>
        )}

        {/* --------------------------------------------------- filters */}
        <div className="vr__filters" data-testid="registry-filters">
          <SelectField
            id="f-status" label="Status" value={filters.status ?? ''}
            onChange={(e) => setFilter('status', e.target.value)}
            options={[{ value: '', label: 'Any status' },
                      ...STATUS_OPTIONS.map(([v, l]) => ({ value: v, label: l }))]}
          />
          <SelectField
            id="f-subtype" label="Experiment subtype" value={filters.subtype ?? ''}
            onChange={(e) => setFilter('subtype', e.target.value)}
            options={[{ value: '', label: 'Any subtype' },
                      ...SUBTYPE_OPTIONS.map(([v, l]) => ({ value: v, label: l }))]}
          />
          <SelectField
            id="f-purpose" label="Scientific purpose" value={filters.purpose ?? ''}
            onChange={(e) => setFilter('purpose', e.target.value)}
            options={[{ value: '', label: 'Any purpose' },
                      ...PURPOSE_OPTIONS.map(([v, l]) => ({ value: v, label: l }))]}
          />
          <SelectField
            id="f-e3" label="E3 eligibility"
            value={filters.e3_eligible === undefined ? ''
              : String(filters.e3_eligible)}
            onChange={(e) => setFilter('e3_eligible',
              e.target.value === '' ? undefined : e.target.value === 'true')}
            options={[
              { value: '', label: 'Any' },
              { value: 'true', label: 'E3 eligible' },
              { value: 'false', label: 'Not E3 eligible' },
            ]}
          />
          <TextField
            id="f-lab" label="Laboratory or CRO" type="text"
            value={filters.laboratory ?? ''}
            onChange={(e) => setFilter('laboratory', e.target.value)}
          />
          <TextField
            id="f-inv" label="Investigator" type="text"
            value={filters.investigator ?? ''}
            onChange={(e) => setFilter('investigator', e.target.value)}
          />
          {activeFilterCount > 0 && (
            <Button variant="ghost" size="sm" data-testid="clear-filters"
                    onClick={() => { setFilters({}); setParams({}, { replace: true }); }}>
              Clear {activeFilterCount} filter{activeFilterCount === 1 ? '' : 's'}
            </Button>
          )}
        </div>

        {error && (
          <Alert tone="danger" title="Registry unavailable">
            <p>{error.message}</p>
          </Alert>
        )}

        {loading && <SkeletonBlock lines={5} />}

        {/* ----------------------------------------------------- list */}
        {rows !== null && rows.length === 0 && !loading && (
          <EmptyState icon={<Icon name="flask" size={20} />}
                      title="No experiments match">
            {activeFilterCount > 0
              ? 'No experiment matches these filters. Clear them to see the '
                + 'whole registry, including rejected and superseded records.'
              : 'No in-vitro experiment has been recorded yet. Nothing is '
                + 'promoted to E3 until one is approved.'}
          </EmptyState>
        )}

        {rows !== null && rows.length > 0 && (
          <DataTable
            caption="Recorded in-vitro experiments"
            head={[
              { key: 'code', label: 'Code' },
              { key: 'title', label: 'Title' },
              { key: 'subtype', label: 'Subtype' },
              { key: 'purpose', label: 'Purpose' },
              { key: 'status', label: 'Status' },
              { key: 'e3', label: 'E3' },
            ]}
          >
            {rows.map((row) => (
              <tr key={row.version_id} data-testid={`registry-row-${row.code}`}>
                <th scope="row">
                  <button type="button" className="vr__link"
                          onClick={() => navigate(
                            `/validation/experiments/${row.experiment_id}`)}
                          data-testid={`open-${row.code}`}>
                    {row.code}
                  </button>
                  <span className="vr__version">v{row.version_number}</span>
                </th>
                <td>{row.title}</td>
                <td>{row.subtype_label}</td>
                <td>{row.purpose_label}</td>
                <td>
                  <span data-testid={`status-${row.code}`}>
                    <Badge tone={statusTone(row.status)} dot>
                      {statusLabel(row.status)}
                    </Badge>
                  </span>
                </td>
                <td>
                  {/* The server's verdict, rendered. Never recomputed here. */}
                  <span data-testid={`e3-${row.code}`}>
                    <Badge tone={row.e3_eligible ? 'success' : 'neutral'}>
                      {row.e3_eligible ? 'E3 eligible' : 'E3 not eligible'}
                    </Badge>
                  </span>
                </td>
              </tr>
            ))}
          </DataTable>
        )}

        {rows !== null && (
          <p className="vr__note" data-testid="registry-total">
            {rows.length} experiment{rows.length === 1 ? '' : 's'} shown.
            Rejected, inconclusive and superseded records are listed too — a
            registry of successes would not be a registry.
          </p>
        )}
      </Card>
    </>
  );
}
