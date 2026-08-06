/**
 * Candidate version history, revision, comparison and supersession.
 *
 * What this screen is responsible for getting right
 * -------------------------------------------------
 * 1. **Never saying "latest version".** Every standing is named: latest draft,
 *    latest approved, current effective version. The three are different
 *    claims and a screen that conflates them presents unreviewed work as
 *    something the organization stands behind.
 * 2. **Warning wherever a version is shown, not only where somebody
 *    remembered.** Superseded, withdrawn and stale-results warnings come from
 *    one function (`warningsFor`) so the history row, the detail panel and the
 *    comparison column cannot word them differently or omit one.
 * 3. **Refusing to submit a revision without a meaningful reason.** The reason
 *    is the only part of the record that explains why the formulation changed,
 *    and it is read by people who were not there. Enforced here so the user
 *    finds out before the round trip, and again by the backend so a client
 *    that skips this cannot get past it.
 * 4. **Showing consequences as consequences.** A change is not "material" in
 *    the abstract; it demands a recalculation, or a scientific reassessment,
 *    or a safety one — and separately a new approval, a new report, a new CRO
 *    package. All six come from the server and are displayed as six answers.
 *
 * No scientific judgement is made here. Every classification, consequence and
 * standing is the server's; this renders them.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  acceptSupersession, compareVersions, generateCroPackage, generateExport,
  generateReport, getDependents, getVersionAudit, getVersionHistory,
  listCroPackages, listEvidence, listExports, listReports, listSimulations,
  proposeSupersession, readStoredReport, recordComparison,
  requestRecalculation, reviseVersion, withdrawVersion,
  type CandidateVersionSummary, type EvidenceRow, type ExportRow,
  type PackageRow, type ReportRow, type SimulationRow, type StoredReport,
  type VersionAuditRow, type VersionComparison, type VersionDependents,
  type VersionHistory,
} from '../../api/candidateVersionClient';
import type { WorkspaceErrorResponse } from '../../api/types';
import {
  Alert, Badge, Button, Card, EmptyState, SkeletonBlock, TextField,
} from '../../design-system/components';
import {
  CLASSIFICATION_LABEL, CONSEQUENCE_LABEL, CONSEQUENCE_ORDER,
  RESULTS_EXPLANATION, RESULTS_LABEL, STANDING_EXPLANATION, STANDING_LABEL,
  STATUS_EXPLANATION, STATUS_LABEL, classificationTone, displayValue,
  resultsTone, standingsFor, statusTone, warningsFor,
} from './versionVocabulary';
import './CandidateVersions.css';

/** The minimum a reason has to be before it explains anything. */
export const MINIMUM_REASON_LENGTH = 12;

export function reasonProblem(reason: string): string | null {
  const trimmed = reason.trim();
  if (trimmed === '') {
    return 'A revision needs a reason. It is the only part of the record that '
      + 'explains why the formulation changed.';
  }
  if (trimmed.length < MINIMUM_REASON_LENGTH) {
    return `Say a little more — at least ${MINIMUM_REASON_LENGTH} characters. `
      + 'This is read by people who were not there.';
  }
  return null;
}

interface Props {
  candidateId: number;
  /** Injected by the route; separated so tests can drive the panel directly. */
  onNavigateToReport?: (reportId: number) => void;
}

export default function CandidateVersionsPage({ candidateId }: Props) {
  const [history, setHistory] = useState<VersionHistory | null>(null);
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await getVersionHistory(candidateId);
    setLoading(false);
    if (result.status === 'ok') {
      setHistory(result.data);
      setError(null);
      setSelectedId((current) => (
        current !== null
        && result.data.versions.some((v) => v.id === current)
          ? current
          : result.data.current_effective_version_id
            ?? result.data.latest_draft_version_id
            ?? result.data.versions[result.data.versions.length - 1]?.id
            ?? null));
    } else {
      setError(result.error);
    }
  }, [candidateId]);

  useEffect(() => { void load(); }, [load]);

  const selected = useMemo(
    () => history?.versions.find((v) => v.id === selectedId) ?? null,
    [history, selectedId]);

  if (loading && history === null) {
    return <SkeletonBlock lines={6} />;
  }

  if (error !== null && history === null) {
    return (
      <Alert tone="danger" title="The version history could not be loaded">
        <p>{error.message}</p>
        {error.detail && <p>{error.detail}</p>}
      </Alert>
    );
  }

  if (history === null || history.versions.length === 0) {
    return (
      <EmptyState title="No versions yet">
        <p>
          This candidate has no recorded version. A version is created when the
          formulation is first frozen, and everything scientific hangs off one.
        </p>
      </EmptyState>
    );
  }

  return (
    <div className="cv">
      <StandingSummary history={history} />

      <div className="cv__layout">
        <section className="cv__history" aria-labelledby="cv-history-heading">
          <h2 id="cv-history-heading" className="cv__heading">
            Version history
          </h2>
          <ol className="cv__list">
            {[...history.versions].reverse().map((version) => (
              <li key={version.id}>
                <VersionRow
                  version={version}
                  history={history}
                  selected={version.id === selectedId}
                  onSelect={() => setSelectedId(version.id)} />
              </li>
            ))}
          </ol>
        </section>

        <section className="cv__detail" aria-live="polite">
          {selected === null ? (
            <EmptyState title="Select a version">
              <p>Choose a version to see what depends on it.</p>
            </EmptyState>
          ) : (
            <VersionDetail version={selected} history={history}
                           onChanged={load} />
          )}
        </section>
      </div>
    </div>
  );
}

/* ==================================================================== */
/* Standing summary                                                      */
/* ==================================================================== */

function StandingSummary({ history }: { history: VersionHistory }) {
  const byId = new Map(history.versions.map((v) => [v.id, v]));
  const rows: Array<[keyof typeof STANDING_LABEL, number | null]> = [
    ['currentEffective', history.current_effective_version_id],
    ['latestApproved', history.latest_approved_version_id],
    ['currentWorking', history.latest_draft_version_id],
  ];

  return (
    <Card title={`Candidate ${history.candidate_code}`}>
      <dl className="cv__standings">
        {rows.map(([key, versionId]) => {
          const version = versionId === null ? null : byId.get(versionId);
          return (
            <div className="cv__standing" key={key}>
              <dt>{STANDING_LABEL[key]}</dt>
              <dd data-testid={`standing-${key}`}>
                {version
                  ? `${version.label} (${STATUS_LABEL[version.status]})`
                  : 'None'}
              </dd>
              <p className="cv__standingnote">{STANDING_EXPLANATION[key]}</p>
            </div>
          );
        })}
      </dl>
      <p className="cv__note">
        Each standing is named because “latest version” is ambiguous between the
        newest draft and the one currently approved, and those are different
        claims.
      </p>
    </Card>
  );
}

/* ==================================================================== */
/* One row in the history                                                */
/* ==================================================================== */

function VersionRow({ version, history, selected, onSelect }: {
  version: CandidateVersionSummary;
  history: VersionHistory;
  selected: boolean;
  onSelect: () => void;
}) {
  const standings = standingsFor(version, history);
  const warnings = warningsFor(version, history.current_effective_version_id);

  return (
    <button
      type="button"
      className={`cv__row${selected ? ' cv__row--selected' : ''}`}
      aria-pressed={selected}
      aria-label={`${version.label}, ${STATUS_LABEL[version.status]}`}
      onClick={onSelect}
    >
      <span className="cv__rowhead">
        <strong>{version.label}</strong>
        <Badge tone={statusTone(version.status)} dot>
          {STATUS_LABEL[version.status]}
        </Badge>
        <Badge tone={resultsTone(version.results_state)}>
          {RESULTS_LABEL[version.results_state]}
        </Badge>
      </span>

      {standings.length > 0 && (
        <span className="cv__standingtags">
          {standings.map((key) => (
            <Badge key={key} tone="accent">{STANDING_LABEL[key]}</Badge>
          ))}
        </span>
      )}

      {version.revision_reason && (
        <span className="cv__reason">{version.revision_reason}</span>
      )}

      {warnings.length > 0 && (
        <span className="cv__rowwarn">
          {warnings.map((w) => (
            <span key={w.key} className={`cv__flag cv__flag--${w.tone}`}>
              {w.title}
            </span>
          ))}
        </span>
      )}

      <span className="cv__meta">
        {new Date(version.created_at).toLocaleString()}
        {' · '}
        <span className="cv__checksum" title={version.snapshot_checksum}>
          {version.snapshot_checksum.slice(0, 12)}
        </span>
      </span>
    </button>
  );
}

/* ==================================================================== */
/* Detail panel                                                          */
/* ==================================================================== */

function VersionDetail({ version, history, onChanged }: {
  version: CandidateVersionSummary;
  history: VersionHistory;
  onChanged: () => Promise<void> | void;
}) {
  const warnings = warningsFor(version, history.current_effective_version_id);

  return (
    <div className="cv__panel">
      <header className="cv__panelhead">
        <h2 className="cv__heading">{version.label}</h2>
        <Badge tone={statusTone(version.status)} dot>
          {STATUS_LABEL[version.status]}
        </Badge>
      </header>

      {warnings.map((warning) => (
        <Alert key={warning.key} tone={warning.tone} title={warning.title}
               role={warning.tone === 'danger' ? 'alert' : 'status'}>
          <p>{warning.body}</p>
        </Alert>
      ))}

      <p className="cv__note">{STATUS_EXPLANATION[version.status]}</p>
      <p className="cv__note">
        {RESULTS_LABEL[version.results_state]}
        {' — '}
        {RESULTS_EXPLANATION[version.results_state]}
      </p>

      <DependentsPanel versionId={version.id} />
      <RevisionForm version={version} onChanged={onChanged} />
      <RecalculationControl version={version} onChanged={onChanged} />
      <ComparisonPanel version={version} history={history} />
      <ArtifactsPanel version={version} onChanged={onChanged} />
      <SupersessionPanel version={version} history={history}
                         onChanged={onChanged} />
      <AuditPanel versionId={version.id} />
    </div>
  );
}

/* ==================================================================== */
/* What depends on it                                                    */
/* ==================================================================== */

function DependentsPanel({ versionId }: { versionId: number }) {
  const [data, setData] = useState<VersionDependents | null>(null);

  useEffect(() => {
    let live = true;
    void getDependents(versionId).then((result) => {
      if (live && result.status === 'ok') setData(result.data);
    });
    return () => { live = false; };
  }, [versionId]);

  if (data === null) return null;

  const entries = Object.entries(data.dependents).filter(([, n]) => n > 0);

  return (
    <Card title="What depends on this version">
      {entries.length === 0 ? (
        <p className="cv__note" data-testid="dependents-none">
          {data.explanation}
        </p>
      ) : (
        <>
          <ul className="cv__deps" data-testid="dependents-list">
            {entries.map(([kind, count]) => (
              <li key={kind}>
                <strong>{count}</strong>{' '}
                {kind.replace(/_/g, ' ')}
              </li>
            ))}
          </ul>
          <p className="cv__note">{data.explanation}</p>
          {data.lock_reason && (
            <p className="cv__note" data-testid="lock-reason">
              Locked because {data.lock_reason}.
            </p>
          )}
        </>
      )}
    </Card>
  );
}

/* ==================================================================== */
/* Revision                                                              */
/* ==================================================================== */

function RevisionForm({ version, onChanged }: {
  version: CandidateVersionSummary;
  onChanged: () => Promise<void> | void;
}) {
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [result, setResult] =
    useState<Awaited<ReturnType<typeof reviseVersion>> | null>(null);

  const problem = reasonProblem(reason);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (problem !== null) return;

    setBusy(true);
    const response = await reviseVersion(version.id, { reason: reason.trim() });
    setBusy(false);

    if (response.status === 'ok') {
      setResult(response);
      setReason('');
      setTouched(false);
      setFailure(null);
      await onChanged();
    } else {
      setFailure(response.error.message);
    }
  }

  return (
    <Card title="Create a revision">
      <p className="cv__note">
        The predecessor is not touched: not superseded, not withdrawn, not
        re-pointed. The revision starts as a draft and carries no approval.
      </p>

      <form onSubmit={submit} className="cv__form" noValidate>
        <TextField
          id="revision-reason"
          label="Why is this revision being created?"
          required
          value={reason}
          error={touched && problem ? problem : undefined}
          help="Read by people who were not there. Say what changed and why."
          onChange={(event) => setReason(event.target.value)}
          onBlur={() => setTouched(true)} />

        <Button type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Create revision'}
        </Button>
      </form>

      {failure && (
        <Alert tone="danger" title="The revision was refused">
          <p>{failure}</p>
        </Alert>
      )}

      {result?.status === 'ok' && (
        <Alert tone="info" title={`${result.data.label} created`}>
          <p>{result.data.notice}</p>
          <ConsequenceList consequence={result.data.consequence} />
        </Alert>
      )}
    </Card>
  );
}

/* ==================================================================== */
/* Material-change classification                                        */
/* ==================================================================== */

export function ConsequenceList({ consequence }: {
  consequence: VersionComparison['consequence'];
}) {
  return (
    <div className="cv__consequence" data-testid="consequence">
      <p>
        <Badge tone={classificationTone(consequence.requires)}>
          {CLASSIFICATION_LABEL[consequence.requires]}
        </Badge>
      </p>
      <p className="cv__note">{consequence.explanation}</p>

      <ul className="cv__consequences">
        {CONSEQUENCE_ORDER.map((key) => {
          const required = consequence.consequences?.[key] ?? false;
          return (
            <li key={key} data-testid={`consequence-${key}`}
                className={required ? 'cv__req' : 'cv__req cv__req--no'}>
              <span aria-hidden="true">{required ? '●' : '○'}</span>
              {' '}
              {CONSEQUENCE_LABEL[key]}
              {': '}
              <strong>{required ? 'required' : 'not required'}</strong>
            </li>
          );
        })}
      </ul>

      {consequence.identity_only === false && (
        <p className="cv__note" data-testid="no-carry-forward">
          No approval carries forward to this version.
        </p>
      )}
    </div>
  );
}

/* ==================================================================== */
/* Recalculation                                                         */
/* ==================================================================== */

function RecalculationControl({ version, onChanged }: {
  version: CandidateVersionSummary;
  onChanged: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (version.results_state !== 'stale') return null;

  async function request() {
    setBusy(true);
    const result = await requestRecalculation(
      version.id, 'Inputs changed in this revision');
    setBusy(false);
    if (result.status === 'ok') {
      setMessage(result.data.notice);
      await onChanged();
    } else {
      setMessage(result.error.message);
    }
  }

  return (
    <Card title="Reassessment required">
      <p className="cv__note">
        These results were computed for a different formulation. Recalculating
        does not by itself restore an approval — a scientific reassessment is
        still required before this version can carry one.
      </p>
      <Button onClick={request} disabled={busy} variant="secondary">
        {busy ? 'Requesting…' : 'Request recalculation'}
      </Button>
      {message && <p className="cv__note" role="status">{message}</p>}
    </Card>
  );
}

/* ==================================================================== */
/* Structured side-by-side comparison                                    */
/* ==================================================================== */

function ComparisonPanel({ version, history }: {
  version: CandidateVersionSummary;
  history: VersionHistory;
}) {
  const others = history.versions.filter((v) => v.id !== version.id);
  const [otherId, setOtherId] = useState<number | null>(
    version.predecessor_version_id ?? others[others.length - 1]?.id ?? null);
  const [comparison, setComparison] = useState<VersionComparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [filed, setFiled] = useState<string | null>(null);

  useEffect(() => { setComparison(null); }, [version.id, otherId]);

  if (others.length === 0) return null;

  async function compare() {
    if (otherId === null) return;
    setBusy(true);
    const result = await compareVersions(otherId, version.id);
    setBusy(false);
    if (result.status === 'ok') setComparison(result.data);
  }

  async function file() {
    if (otherId === null) return;
    const result = await recordComparison(version.id, {
      other_version_id: otherId,
      note: 'Filed from the version comparison screen',
    });
    setFiled(result.status === 'ok'
      ? result.data.notice
      : result.error.message);
  }

  return (
    <Card title="Compare with another version">
      <div className="cv__compareform">
        <label className="ds-field__label" htmlFor="compare-with">
          Compare against
        </label>
        <select id="compare-with" className="ds-input"
                value={otherId ?? ''}
                onChange={(event) => setOtherId(Number(event.target.value))}>
          {others.map((other) => (
            <option key={other.id} value={other.id}>
              {other.label} — {STATUS_LABEL[other.status]}
            </option>
          ))}
        </select>
        <Button onClick={compare} disabled={busy || otherId === null}
                variant="secondary">
          {busy ? 'Comparing…' : 'Compare'}
        </Button>
      </div>

      {comparison !== null && (
        <>
          {comparison.identical ? (
            <p className="cv__note" data-testid="comparison-identical">
              These two versions have identical scientific inputs.
            </p>
          ) : (
            <div className="cv__tablewrap">
              <table className="cv__table" data-testid="comparison-table">
                <caption className="cv__caption">
                  Field-by-field comparison of {comparison.left.label} and
                  {' '}{comparison.right.label}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Field</th>
                    <th scope="col">{comparison.left.label}</th>
                    <th scope="col">{comparison.right.label}</th>
                    <th scope="col">Kind</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.changed_fields.map((change) => (
                    <tr key={change.field}
                        className={change.scientific
                          ? 'cv__scientific' : undefined}>
                      <th scope="row">
                        {change.field}
                        {change.scientific && (
                          <Badge tone="warn">scientific</Badge>
                        )}
                      </th>
                      <td>{displayValue(change.before)}</td>
                      <td>{displayValue(change.after)}</td>
                      <td>{change.kind}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <ConsequenceList consequence={comparison.consequence} />

          <Button onClick={file} variant="secondary">
            File this comparison as a record
          </Button>
          <p className="cv__note">
            Browsing a comparison locks nothing. Filing one says it is the basis
            of what happens next, and locks both versions.
          </p>
          {filed && <p className="cv__note" role="status">{filed}</p>}
        </>
      )}
    </Card>
  );
}

/* ==================================================================== */
/* Version-specific artefacts                                            */
/* ==================================================================== */

function ArtifactsPanel({ version, onChanged }: {
  version: CandidateVersionSummary;
  onChanged: () => Promise<void> | void;
}) {
  const [simulations, setSimulations] = useState<SimulationRow[]>([]);
  const [evidence, setEvidence] = useState<EvidenceRow[]>([]);
  const [reports, setReports] = useState<ReportRow[]>([]);
  const [exports, setExports] = useState<ExportRow[]>([]);
  const [packages, setPackages] = useState<PackageRow[]>([]);
  const [opened, setOpened] = useState<StoredReport | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [sims, ev, reps, exps, pkgs] = await Promise.all([
      listSimulations(version.id), listEvidence(version.id),
      listReports(version.id), listExports(version.id),
      listCroPackages(version.id),
    ]);
    if (sims.status === 'ok') setSimulations(sims.data.simulations);
    if (ev.status === 'ok') setEvidence(ev.data.assessments);
    if (reps.status === 'ok') setReports(reps.data.reports);
    if (exps.status === 'ok') setExports(exps.data.exports);
    if (pkgs.status === 'ok') setPackages(pkgs.data.packages);
  }, [version.id]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function makeReport() {
    setBusy(true);
    await generateReport(version.id, {
      title: `${version.label} summary`, body: {},
    });
    setBusy(false);
    await refresh();
    await onChanged();
  }

  async function makeExport() {
    setBusy(true);
    await generateExport(version.id, { format: 'json' });
    setBusy(false);
    await refresh();
    await onChanged();
  }

  async function makePackage() {
    setBusy(true);
    await generateCroPackage(version.id, {
      recipient_name: 'Contract laboratory',
      package_code: `PKG-${version.id}-${Date.now()}`,
    });
    setBusy(false);
    await refresh();
    await onChanged();
  }

  async function open(reportId: number) {
    const result = await readStoredReport(reportId);
    if (result.status === 'ok') setOpened(result.data);
  }

  return (
    <Card title={`Records for ${version.label}`}>
      <p className="cv__note">
        Everything listed here names this exact version. Work recorded against
        another revision is not shown, and is not evidence for this one.
      </p>

      <h3 className="cv__subheading">Simulations</h3>
      {simulations.length === 0
        ? <p className="cv__note">None recorded against this version.</p>
        : (
          <ul className="cv__records" data-testid="simulations">
            {simulations.map((row) => (
              <li key={row.id}>
                {row.kind} · {row.engine_version}
                {row.is_stale && (
                  <span data-testid="stale-simulation">
                    {' '}
                    <Badge tone="warn">Stale</Badge>
                    {row.source_candidate_version_id !== null && (
                      <span className="cv__note">
                        {' '}copied from version {row.source_candidate_version_id}
                      </span>
                    )}
                  </span>
                )}
                {row.state === 'failed' && (
                  <> <Badge tone="danger">Failed</Badge> {row.failure_reason}</>
                )}
              </li>
            ))}
          </ul>
        )}

      <h3 className="cv__subheading">Evidence</h3>
      {evidence.length === 0
        ? <p className="cv__note">No evidence assessed for this version.</p>
        : (
          <ul className="cv__records" data-testid="evidence">
            {evidence.map((row) => (
              <li key={row.id}>
                {row.purpose.replace(/_/g, ' ')}
                {' — '}
                <strong>{row.level ?? 'no level held'}</strong>
                {' · '}
                <Badge tone="info">{row.reuse_label}</Badge>
                {row.source_candidate_version_id !== null && (
                  <span className="cv__note">
                    {' '}gathered on version {row.source_candidate_version_id}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

      <h3 className="cv__subheading">Reports</h3>
      {reports.length === 0
        ? <p className="cv__note">None generated from this version.</p>
        : (
          <ul className="cv__records" data-testid="reports">
            {reports.map((row) => (
              <li key={row.id}>
                <button type="button" className="cv__link"
                        onClick={() => open(row.id)}>
                  {row.title}
                </button>
                {' — '}{row.version_label}
              </li>
            ))}
          </ul>
        )}

      {opened && (
        <Alert tone="info" title={`${opened.title} (${opened.version_label})`}>
          <p data-testid="stored-report-notice">{opened.notice}</p>
          <p className="cv__note">
            Version {opened.candidate_version_id} · checksum{' '}
            {opened.version_checksum.slice(0, 12)}
          </p>
          {opened.historical && (
            <p data-testid="historical-report">
              This report describes a superseded version. It remains a true
              record of what was concluded then.
            </p>
          )}
        </Alert>
      )}

      <h3 className="cv__subheading">Exports and packages</h3>
      <ul className="cv__records" data-testid="exports">
        {exports.map((row) => (
          <li key={`e${row.id}`}>
            Export {row.format} · {row.version_label} ·{' '}
            {row.content_checksum.slice(0, 12)}
          </li>
        ))}
        {packages.map((row) => (
          <li key={`p${row.id}`}>
            CRO package {row.package_code} · {row.version_label} ·{' '}
            {row.recipient_name}
          </li>
        ))}
      </ul>
      {exports.length === 0 && packages.length === 0 && (
        <p className="cv__note">None generated from this version.</p>
      )}

      <div className="cv__actions">
        <Button onClick={makeReport} disabled={busy} variant="secondary">
          Generate report
        </Button>
        <Button onClick={makeExport} disabled={busy} variant="secondary">
          Generate export
        </Button>
        <Button onClick={makePackage} disabled={busy} variant="secondary">
          Generate CRO package
        </Button>
      </div>
    </Card>
  );
}

/* ==================================================================== */
/* Supersession                                                          */
/* ==================================================================== */

function SupersessionPanel({ version, history, onChanged }: {
  version: CandidateVersionSummary;
  history: VersionHistory;
  onChanged: () => Promise<void> | void;
}) {
  const successors = history.versions.filter(
    (v) => v.version_number > version.version_number
      && v.status !== 'draft');
  const [successorId, setSuccessorId] = useState<number | null>(
    successors[0]?.id ?? null);
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);

  const problem = reasonProblem(reason);
  const supersedable = version.status === 'locked'
    || version.status === 'approved';

  if (!supersedable) return null;

  async function act(kind: 'propose' | 'accept') {
    setTouched(true);
    if (problem !== null || successorId === null) return;

    const result = kind === 'propose'
      ? await proposeSupersession(version.id, {
        successor_version_id: successorId, reason: reason.trim(),
      })
      : await acceptSupersession(version.id, {
        successor_version_id: successorId, reason: reason.trim(),
        expected_revision: version.revision,
      });

    if (result.status === 'ok') {
      setMessage(kind === 'propose'
        ? 'Proposed. Somebody with approval authority has to agree.'
        : 'Superseded. Everything that referenced the older version still '
          + 'refers to it.');
      setRefusal(null);
      await onChanged();
    } else {
      setRefusal(result.error.message);
      setMessage(null);
    }
  }

  async function retire() {
    setTouched(true);
    if (problem !== null) return;
    const result = await withdrawVersion(version.id, reason.trim());
    if (result.status === 'ok') {
      setMessage(result.data.notice);
      setRefusal(null);
      await onChanged();
    } else {
      setRefusal(result.error.message);
    }
  }

  return (
    <Card title="Supersession">
      <p className="cv__note">
        Proposing is not deciding. An author may put their revision forward;
        only somebody with approval authority — and not the author of the
        successor — may agree that it replaces what the organization stands
        behind.
      </p>

      {successors.length === 0 ? (
        <p className="cv__note" data-testid="no-successor">
          There is no later version that has left draft, so nothing can take
          over yet.
        </p>
      ) : (
        <>
          <label className="ds-field__label" htmlFor="successor">
            Successor
          </label>
          <select id="successor" className="ds-input" value={successorId ?? ''}
                  onChange={(e) => setSuccessorId(Number(e.target.value))}>
            {successors.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label} — {STATUS_LABEL[s.status]}
              </option>
            ))}
          </select>
        </>
      )}

      <TextField
        id="supersession-reason"
        label="Reason"
        required
        value={reason}
        error={touched && problem ? problem : undefined}
        onChange={(e) => setReason(e.target.value)}
        onBlur={() => setTouched(true)} />

      <div className="cv__actions">
        {successors.length > 0 && (
          <>
            <Button variant="secondary" onClick={() => act('propose')}>
              Propose supersession
            </Button>
            <Button onClick={() => act('accept')}>
              Accept supersession
            </Button>
          </>
        )}
        <Button variant="ghost" onClick={retire}>
          Withdraw this version
        </Button>
      </div>

      {message && <p className="cv__note" role="status">{message}</p>}
      {refusal && (
        <Alert tone="danger" title="Refused">
          <p>{refusal}</p>
        </Alert>
      )}
    </Card>
  );
}

/* ==================================================================== */
/* Audit                                                                 */
/* ==================================================================== */

function AuditPanel({ versionId }: { versionId: number }) {
  const [events, setEvents] = useState<VersionAuditRow[] | null>(null);

  useEffect(() => {
    let live = true;
    void getVersionAudit(versionId).then((result) => {
      if (live) setEvents(result.status === 'ok' ? result.data.events : []);
    });
    return () => { live = false; };
  }, [versionId]);

  if (events === null || events.length === 0) return null;

  return (
    <Card title="History of this version">
      <ol className="cv__records" data-testid="version-audit">
        {events.map((event) => (
          <li key={event.id}>
            <strong>{event.event.replace(/_/g, ' ')}</strong>
            {event.summary && <> — {event.summary}</>}
            {event.reason && <span className="cv__note"> ({event.reason})</span>}
          </li>
        ))}
      </ol>
      <p className="cv__note">
        Append-only. Nothing in this application updates or deletes an entry.
      </p>
    </Card>
  );
}
