/**
 * Experiment Details — and the nine sections that make up a complete record.
 *
 * Details · Protocol & Materials · Controls & Replicates · Measurements &
 * Results · Raw Data & Attachments · Quality Assessment · Scientific Review ·
 * Evidence Decision · Version History · Audit History.
 *
 * One page rather than nine routes, because they are nine views of one record
 * and a researcher moves between them constantly while filling it in. Each has
 * its own tab, its own test id and its own heading, so they remain separately
 * addressable and separately testable.
 *
 * Nothing here computes eligibility. Every gate result, badge and level comes
 * from the server; the page renders a verdict it did not form.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  addMeasurements, attachmentDownloadUrl, createRevision, deleteAttachment,
  getAuditHistory, getEligibility, getExperiment, recordDecision, startReview,
  submitVersion, updateDraft, uploadAttachment,
} from '../../api/registryClient';
import type { WorkspaceErrorResponse } from '../../api/types';
import {
  Alert, Badge, Button, Card, DataTable, EmptyState, SelectField,
  SkeletonBlock, Tabs, TextField,
} from '../../design-system/components';
import PathwayBanner from '../../workflow/PathwayBanner';
import {
  ATTACHMENT_LABEL, SUBTYPE_FORMS, formatBytes, statusLabel, statusTone,
  type AttachmentCategoryId, type AttachmentSummary, type AuditEventRow,
  type EligibilityVerdict,
  type ExperimentDetail, type MeasurementRow,
} from './registryTypes';
import './ValidationRegistry.css';

type SectionId =
  | 'details' | 'protocol' | 'controls' | 'measurements' | 'attachments'
  | 'quality' | 'review' | 'evidence' | 'versions' | 'audit';

const SECTIONS: ReadonlyArray<{ id: SectionId; label: string }> = [
  { id: 'details', label: 'Experiment details' },
  { id: 'protocol', label: 'Protocol and materials' },
  { id: 'controls', label: 'Controls and replicates' },
  { id: 'measurements', label: 'Measurements and results' },
  { id: 'attachments', label: 'Raw data and attachments' },
  { id: 'quality', label: 'Quality assessment' },
  { id: 'review', label: 'Scientific review' },
  { id: 'evidence', label: 'Evidence decision' },
  { id: 'versions', label: 'Version history' },
  { id: 'audit', label: 'Audit history' },
];

export default function ExperimentDetailPage() {
  const { experimentId } = useParams();
  const navigate = useNavigate();
  const id = Number(experimentId);

  const [detail, setDetail] = useState<ExperimentDetail | null>(null);
  const [verdict, setVerdict] = useState<EligibilityVerdict | null>(null);
  const [audit, setAudit] = useState<AuditEventRow[]>([]);
  const [section, setSection] = useState<SectionId>('details');
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    const result = await getExperiment(id, signal);
    if (result.status === 'error') { setError(result.error); return; }
    setError(null);
    setDetail(result.data);
    const versionId = result.data.current_version?.id;
    if (versionId) {
      const [elig, trail] = await Promise.all([
        getEligibility(versionId, signal), getAuditHistory(id, signal),
      ]);
      if (elig.status === 'ok') setVerdict(elig.data);
      if (trail.status === 'ok') setAudit(trail.data.events);
    }
  }, [id]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (error && !detail) {
    return (
      <Card title="Experiment unavailable">
        <Alert tone="danger" title="Not found">
          <p data-testid="detail-error">{error.message}</p>
        </Alert>
      </Card>
    );
  }
  if (!detail) return <SkeletonBlock lines={8} />;

  const version = detail.current_version;
  const caps = new Set(detail.capabilities ?? []);
  const editable = caps.has('edit_draft');

  const patch = async (fields: Record<string, unknown>) => {
    if (!version) return;
    setBusy(true);
    const result = await updateDraft(version.id, fields);
    setBusy(false);
    if (result.status === 'error') { setError(result.error); return; }
    await load();
  };

  const act = async (fn: () => Promise<{ status: string }>) => {
    setBusy(true);
    const result = await fn();
    setBusy(false);
    if ((result as { status: string }).status === 'error') {
      setError((result as unknown as { error: WorkspaceErrorResponse }).error);
      return;
    }
    setError(null);
    await load();
  };

  return (
    <>
      <PathwayBanner />

      <Card
        title={detail.experiment.title}
        subtitle={`${detail.experiment.code} · ${detail.experiment.subtype_label}`}
        accent
        actions={
          <div className="vr__headactions">
            <span data-testid="detail-status">
              <Badge tone={statusTone(version?.status ?? 'draft')} dot>
                {statusLabel(version?.status ?? 'draft')}
              </Badge>
            </span>
            <span data-testid="detail-e3">
              <Badge tone={verdict?.eligible ? 'success' : 'neutral'}>
                {verdict?.eligible ? 'E3 eligible' : 'E3 not eligible'}
              </Badge>
            </span>
          </div>
        }
      >
        <dl className="vr__facts" data-testid="detail-facts">
          <div><dt>Scientific purpose</dt>
            <dd data-testid="detail-purpose">{detail.experiment.purpose_label}</dd></div>
          <div><dt>Candidate version</dt>
            <dd data-testid="detail-candidate-version">
              #{version?.candidate_version_id ?? '—'}
            </dd></div>
          <div><dt>Version</dt>
            <dd data-testid="detail-version">v{version?.version_number ?? '—'}</dd></div>
        </dl>

        <p className="vr__note" data-testid="detail-scope">
          An approval here supports <strong>{detail.experiment.purpose_label}</strong>{' '}
          for candidate version #{version?.candidate_version_id} only. It says
          nothing about any other purpose, candidate or study.
        </p>

        {error && (
          <Alert tone="danger" title="Action refused">
            <p data-testid="action-error">{error.message}</p>
            {error.detail && <p className="vr__note">{error.detail}</p>}
          </Alert>
        )}

        <Tabs
          ariaLabel="Experiment record sections"
          active={section}
          onChange={(next) => setSection(next as SectionId)}
          tabs={SECTIONS.map((s) => ({ id: s.id, label: s.label }))}
        />

        <div role="tabpanel" className="vr__panel"
             data-testid={`section-${section}`}>
          {section === 'details' && (
            <DetailsSection version={version} editable={editable}
                            onPatch={patch} busy={busy} />
          )}
          {section === 'protocol' && (
            <ProtocolSection version={version} editable={editable}
                             onPatch={patch} busy={busy} />
          )}
          {section === 'controls' && (
            <ControlsSection version={version} editable={editable}
                             onPatch={patch} busy={busy}
                             subtype={detail.experiment.subtype} />
          )}
          {section === 'measurements' && (
            <MeasurementsSection version={version} editable={editable}
                                 subtype={detail.experiment.subtype}
                                 onReload={load} onError={setError} />
          )}
          {section === 'attachments' && (
            <AttachmentsSection version={version} editable={editable}
                                onReload={load} onError={setError} />
          )}
          {section === 'quality' && (
            <QualitySection version={version} editable={editable}
                            onPatch={patch} busy={busy} />
          )}
          {section === 'review' && (
            <ReviewSection version={version} caps={caps} busy={busy}
                           onSubmit={() => act(() => submitVersion(version!.id) as never)}
                           onStartReview={() => act(() => startReview(version!.id) as never)}
                           onDecision={async (decision, comments) => {
                             setBusy(true);
                             const result = await recordDecision(
                               version!.id, decision, comments);
                             setBusy(false);
                             if (result.status === 'error') {
                               setError(result.error); return;
                             }
                             setError(null);
                             await load();
                           }} />
          )}
          {section === 'evidence' && (
            <EvidenceSection verdict={verdict} />
          )}
          {section === 'versions' && (
            <VersionsSection detail={detail} busy={busy}
                             onRevise={async () => {
                               setBusy(true);
                               const result = await createRevision(version!.id);
                               setBusy(false);
                               if (result.status === 'error') {
                                 setError(result.error); return;
                               }
                               await load();
                             }} />
          )}
          {section === 'audit' && <AuditSection events={audit} />}
        </div>

        <div className="vr__actions">
          <Button variant="secondary" onClick={() => navigate('/validation')}
                  data-testid="back-to-registry">
            Back to registry
          </Button>
        </div>
      </Card>
    </>
  );
}

/* ===================================================================== */

function ReadOnlyNote({ editable }: { editable: boolean }) {
  if (editable) return null;
  return (
    <Alert tone="info" role="note">
      <p data-testid="read-only-note">
        This version is frozen. Submitted and reviewed records are not edited in
        place — a correction creates a new version, which preserves what was
        actually reviewed.
      </p>
    </Alert>
  );
}

function Field({ id, label, value, editable, onCommit, help }: {
  id: string; label: string; value: unknown; editable: boolean;
  onCommit: (v: string) => void; help?: string;
}) {
  const [draft, setDraft] = useState(String(value ?? ''));
  useEffect(() => { setDraft(String(value ?? '')); }, [value]);
  return (
    <TextField
      id={id} label={label} type="text" value={draft} disabled={!editable}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => { if (draft !== String(value ?? '')) onCommit(draft); }}
      help={help}
    />
  );
}

function DetailsSection({ version, editable, onPatch }: {
  version?: Record<string, unknown>; editable: boolean;
  onPatch: (f: Record<string, unknown>) => void; busy: boolean;
}) {
  if (!version) return <EmptyState title="No version" />;
  return (
    <>
      <ReadOnlyNote editable={editable} />
      <div className="vr__form">
        <Field id="scientific_question" label="Scientific question"
               value={version.scientific_question} editable={editable}
               onCommit={(v) => onPatch({ scientific_question: v })}
               help="What this experiment set out to determine." />
        <Field id="hypothesis" label="Hypothesis" value={version.hypothesis}
               editable={editable} onCommit={(v) => onPatch({ hypothesis: v })} />
        <Field id="investigator_name" label="Responsible investigator"
               value={version.investigator_name} editable={editable}
               onCommit={(v) => onPatch({ investigator_name: v })} />
        <Field id="investigator_org" label="Investigator's organization"
               value={version.investigator_org} editable={editable}
               onCommit={(v) => onPatch({ investigator_org: v })} />
        <Field id="laboratory_name" label="Laboratory or CRO"
               value={version.laboratory_name} editable={editable}
               onCommit={(v) => onPatch({ laboratory_name: v })}
               help="A result nobody is named against cannot be followed up." />
        <Field id="start_date" label="Start date (YYYY-MM-DD)"
               value={version.start_date} editable={editable}
               onCommit={(v) => onPatch({ start_date: v })} />
        <Field id="completion_date" label="Completion date (YYYY-MM-DD)"
               value={version.completion_date} editable={editable}
               onCommit={(v) => onPatch({ completion_date: v })} />
      </div>
    </>
  );
}

function ProtocolSection({ version, editable, onPatch }: {
  version?: Record<string, unknown>; editable: boolean;
  onPatch: (f: Record<string, unknown>) => void; busy: boolean;
}) {
  if (!version) return <EmptyState title="No version" />;
  return (
    <>
      <ReadOnlyNote editable={editable} />
      <div className="vr__form">
        <Field id="protocol_identifier" label="Protocol identifier"
               value={version.protocol_identifier} editable={editable}
               onCommit={(v) => onPatch({ protocol_identifier: v })} />
        <Field id="protocol_version" label="Protocol version"
               value={version.protocol_version} editable={editable}
               onCommit={(v) => onPatch({ protocol_version: v })}
               help="The exact version followed, not the latest one." />
        <Field id="nanoparticle_batch" label="Nanoparticle batch or lot"
               value={version.nanoparticle_batch} editable={editable}
               onCommit={(v) => onPatch({ nanoparticle_batch: v })} />
        <Field id="payload_batch" label="Payload batch (if applicable)"
               value={version.payload_batch} editable={editable}
               onCommit={(v) => onPatch({ payload_batch: v })} />
        <Field id="biological_model" label="Biological model"
               value={version.biological_model} editable={editable}
               onCommit={(v) => onPatch({ biological_model: v })} />
        <Field id="cell_line" label="Cell line or cell system"
               value={version.cell_line} editable={editable}
               onCommit={(v) => onPatch({ cell_line: v })} />
        <Field id="cell_source" label="Cell source"
               value={version.cell_source} editable={editable}
               onCommit={(v) => onPatch({ cell_source: v })} />
        <Field id="cell_authentication_status" label="Authentication status"
               value={version.cell_authentication_status} editable={editable}
               onCommit={(v) => onPatch({ cell_authentication_status: v })}
               help="An unauthenticated line is a known source of irreproducible results." />
        <Field id="passage_number" label="Passage number or range"
               value={version.passage_number} editable={editable}
               onCommit={(v) => onPatch({ passage_number: v })} />
        <Field id="assay_method" label="Assay method"
               value={version.assay_method} editable={editable}
               onCommit={(v) => onPatch({ assay_method: v })} />
      </div>
    </>
  );
}

function ControlsSection({ version, editable, onPatch, subtype }: {
  version?: Record<string, unknown>; editable: boolean;
  onPatch: (f: Record<string, unknown>) => void; busy: boolean;
  subtype: keyof typeof SUBTYPE_FORMS;
}) {
  if (!version) return <EmptyState title="No version" />;
  const spec = SUBTYPE_FORMS[subtype];
  return (
    <>
      <ReadOnlyNote editable={editable} />
      <p className="vr__note" data-testid="controls-guidance">
        {spec.cellBased
          ? 'This is a cell-based assay: positive, negative and vehicle '
            + 'controls are expected. Where one genuinely does not apply, '
            + 'record why rather than leaving it blank.'
          : 'This assay is not cell-based. Record the controls used, or state '
            + 'why controls do not apply to this measurement.'}
      </p>
      <div className="vr__form">
        <Field id="control_positive" label="Positive control"
               value={version.control_positive} editable={editable}
               onCommit={(v) => onPatch({ control_positive: v })} />
        <Field id="control_negative" label="Negative control"
               value={version.control_negative} editable={editable}
               onCommit={(v) => onPatch({ control_negative: v })} />
        <Field id="control_vehicle" label="Vehicle control"
               value={version.control_vehicle} editable={editable}
               onCommit={(v) => onPatch({ control_vehicle: v })} />
        <Field id="controls_not_applicable_reason"
               label="Why a control does not apply"
               value={version.controls_not_applicable_reason} editable={editable}
               onCommit={(v) => onPatch({ controls_not_applicable_reason: v })} />
        <Field id="biological_replicates" label="Biological replicates"
               value={version.biological_replicates} editable={editable}
               onCommit={(v) => onPatch({ biological_replicates: Number(v) || null })}
               help="Report the count even when it is one. No universal minimum is imposed; sufficiency is the reviewer's judgement." />
        <Field id="technical_replicates" label="Technical replicates"
               value={version.technical_replicates} editable={editable}
               onCommit={(v) => onPatch({ technical_replicates: Number(v) || null })} />
        <Field id="replicate_justification" label="Replicate justification"
               value={version.replicate_justification} editable={editable}
               onCommit={(v) => onPatch({ replicate_justification: v })} />
        <Field id="acceptance_criteria_json" label="Acceptance criteria (JSON)"
               value={version.acceptance_criteria_json} editable={editable}
               onCommit={(v) => onPatch({ acceptance_criteria_json: v })}
               help='Recorded before results. e.g. [{"endpoint":"viability_percent","comparator":"<=","value":50,"unit":"%"}]' />
      </div>
    </>
  );
}

function MeasurementsSection({ version, editable, subtype, onReload, onError }: {
  version?: Record<string, unknown> & { measurements?: MeasurementRow[] };
  editable: boolean;
  subtype: keyof typeof SUBTYPE_FORMS;
  onReload: () => Promise<void>;
  onError: (e: WorkspaceErrorResponse) => void;
}) {
  const spec = SUBTYPE_FORMS[subtype];
  const [endpoint, setEndpoint] = useState(spec.endpoints[0]?.name ?? '');
  const [value, setValue] = useState('');
  const [unit, setUnit] = useState(spec.endpoints[0]?.unit ?? '');
  const [group, setGroup] = useState('');
  const [replicate, setReplicate] = useState('');
  const [timePoint, setTimePoint] = useState('');
  const [dose, setDose] = useState('');

  if (!version) return <EmptyState title="No version" />;
  const rows = version.measurements ?? [];

  const add = async () => {
    if (!endpoint) return;
    const numeric = value.trim() === '' ? null : Number(value);
    const result = await addMeasurements(version.id as number, [{
      endpoint_name: endpoint,
      sample_group: group || null,
      replicate_id: replicate || null,
      time_point: spec.timeCourse ? (timePoint || null) : null,
      dose_value: spec.doseResponse && dose ? Number(dose) : null,
      result_numeric: Number.isFinite(numeric as number) ? numeric : null,
      result_text: Number.isFinite(numeric as number) ? null : (value || null),
      result_unit: unit || null,
    }]);
    if (result.status === 'error') { onError(result.error); return; }
    setValue(''); setReplicate('');
    await onReload();
  };

  return (
    <>
      <ReadOnlyNote editable={editable} />
      <p className="vr__note" data-testid="measurement-guidance">{spec.guidance}</p>

      {editable && (
        <div className="vr__form vr__form--inline" data-testid="measurement-entry">
          <SelectField
            id="m-endpoint" label="Endpoint" value={endpoint}
            onChange={(e) => {
              setEndpoint(e.target.value);
              const match = spec.endpoints.find((x) => x.name === e.target.value);
              setUnit(match?.unit ?? '');
            }}
            options={[
              ...spec.endpoints.map((e) => ({ value: e.name, label: e.name })),
              { value: '__other', label: 'Other endpoint…' },
            ]}
          />
          {endpoint === '__other' && (
            <TextField id="m-endpoint-other" label="Endpoint name" type="text"
                       value={endpoint === '__other' ? '' : endpoint}
                       onChange={(e) => setEndpoint(e.target.value)} />
          )}
          <TextField id="m-group" label="Sample or group" type="text"
                     value={group} onChange={(e) => setGroup(e.target.value)} />
          <TextField id="m-replicate" label="Replicate" type="text"
                     value={replicate}
                     onChange={(e) => setReplicate(e.target.value)} />
          {spec.timeCourse && (
            <TextField id="m-time" label="Time point" type="text"
                       value={timePoint}
                       onChange={(e) => setTimePoint(e.target.value)} />
          )}
          {spec.doseResponse && (
            <TextField id="m-dose" label="Dose or concentration" type="text"
                       value={dose} onChange={(e) => setDose(e.target.value)} />
          )}
          <TextField id="m-value" label="Result" type="text" value={value}
                     onChange={(e) => setValue(e.target.value)} />
          <TextField id="m-unit" label="Unit" type="text" value={unit}
                     onChange={(e) => setUnit(e.target.value)}
                     help="A numeric result without a unit is not a measurement." />
          <Button onClick={add} data-testid="add-measurement"
                  disabled={!endpoint || !value.trim()}>
            Record measurement
          </Button>
        </div>
      )}

      {rows.length === 0 ? (
        <EmptyState title="No measurements recorded">
          Structured measurements are required. A narrative conclusion cannot be
          checked against the acceptance criteria.
        </EmptyState>
      ) : (
        <DataTable caption="Recorded measurements"
                   head={[
                     { key: 'e', label: 'Endpoint' },
                     { key: 'g', label: 'Group' },
                     { key: 'r', label: 'Replicate' },
                     { key: 'v', label: 'Result', numeric: true },
                     { key: 'u', label: 'Unit' },
                     { key: 'x', label: 'Excluded' },
                   ]}>
          {rows.map((m, i) => (
            <tr key={m.id ?? i} data-testid={`measurement-${i}`}>
              <th scope="row">{m.endpoint_name}</th>
              <td>{m.sample_group ?? '—'}</td>
              <td>{m.replicate_id ?? '—'}</td>
              <td className="is-numeric">
                {m.result_numeric ?? m.result_text
                  ?? (m.missing_value_reason ? 'missing' : '—')}
              </td>
              <td>{m.result_unit ?? '—'}</td>
              <td>{m.excluded ? 'Excluded' : ''}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </>
  );
}

function AttachmentsSection({ version, editable, onReload, onError }: {
  version?: { id: number; attachments?: AttachmentSummary[] };
  editable: boolean;
  onReload: () => Promise<void>;
  onError: (e: WorkspaceErrorResponse) => void;
}) {
  const [category, setCategory] = useState<AttachmentCategoryId>('raw_data');
  const [busy, setBusy] = useState(false);
  if (!version) return <EmptyState title="No version" />;
  const rows = version.attachments ?? [];

  const upload = async (file: File) => {
    setBusy(true);
    const result = await uploadAttachment(version.id, category, file);
    setBusy(false);
    if (result.status === 'error') { onError(result.error); return; }
    await onReload();
  };

  return (
    <>
      <ReadOnlyNote editable={editable} />
      <p className="vr__note" data-testid="attachment-guidance">
        Raw or source data must be attached or referenced. A processed summary
        cannot be its own source. Files are checked on the server for type,
        size and content before anything is stored.
      </p>

      {editable && (
        <div className="vr__form vr__form--inline">
          <SelectField
            id="a-category" label="Category" value={category}
            onChange={(e) => setCategory(e.target.value as AttachmentCategoryId)}
            options={Object.entries(ATTACHMENT_LABEL)
              .map(([v, l]) => ({ value: v, label: l }))}
          />
          <label className="vr__file">
            <span>Choose file</span>
            <input type="file" data-testid="attachment-input" disabled={busy}
                   onChange={(e) => {
                     const file = e.target.files?.[0];
                     if (file) void upload(file);
                   }} />
          </label>
        </div>
      )}

      {rows.length === 0 ? (
        <EmptyState title="No attachments">
          No raw data is attached. The eligibility gate for provenance will not
          pass on attachments alone unless a durable reference is recorded.
        </EmptyState>
      ) : (
        <DataTable caption="Attachments"
                   head={[
                     { key: 'n', label: 'File' },
                     { key: 'c', label: 'Category' },
                     { key: 's', label: 'Size', numeric: true },
                     { key: 'h', label: 'Checksum' },
                     { key: 'a', label: '' },
                   ]}>
          {rows.map((a) => (
            <tr key={a.id} data-testid={`attachment-${a.id}`}>
              <th scope="row">{a.original_filename}</th>
              <td>{ATTACHMENT_LABEL[a.category]}</td>
              <td className="is-numeric">{formatBytes(a.size_bytes)}</td>
              <td className="mono vr__checksum">
                {a.checksum_sha256.slice(0, 12)}…
              </td>
              <td>
                <a href={attachmentDownloadUrl(a.id)}
                   data-testid={`download-${a.id}`}>Download</a>
                {editable && (
                  <Button variant="ghost" size="sm"
                          data-testid={`remove-${a.id}`}
                          onClick={async () => {
                            const result = await deleteAttachment(a.id);
                            if (result.status === 'error') {
                              onError(result.error); return;
                            }
                            await onReload();
                          }}>
                    Remove
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </DataTable>
      )}
    </>
  );
}

function QualitySection({ version, editable, onPatch }: {
  version?: Record<string, unknown>; editable: boolean;
  onPatch: (f: Record<string, unknown>) => void; busy: boolean;
}) {
  if (!version) return <EmptyState title="No version" />;
  return (
    <>
      <ReadOnlyNote editable={editable} />
      <p className="vr__note" data-testid="quality-guidance">
        An unresolved <strong>critical</strong> quality issue blocks E3. Lesser
        issues are recorded and do not block; disclosing one is always better
        than omitting it.
      </p>
      <div className="vr__form">
        <Field id="quality_issues_json" label="Quality issues (JSON)"
               value={version.quality_issues_json} editable={editable}
               onCommit={(v) => onPatch({ quality_issues_json: v })}
               help='e.g. [{"severity":"minor","description":"…","resolved":true}]' />
        <Field id="deviations" label="Deviations from protocol"
               value={version.deviations} editable={editable}
               onCommit={(v) => onPatch({ deviations: v })}
               help="Record 'none' where that is the case; a blank field is ambiguous." />
        <Field id="exclusions" label="Exclusions"
               value={version.exclusions} editable={editable}
               onCommit={(v) => onPatch({ exclusions: v })} />
        <Field id="missing_data" label="Missing data"
               value={version.missing_data} editable={editable}
               onCommit={(v) => onPatch({ missing_data: v })} />
        <Field id="statistical_method" label="Statistical method"
               value={version.statistical_method} editable={editable}
               onCommit={(v) => onPatch({ statistical_method: v })} />
        <Field id="provenance_declaration" label="Provenance declaration"
               value={version.provenance_declaration} editable={editable}
               onCommit={(v) => onPatch({ provenance_declaration: v })} />
        <Field id="investigator_conclusion" label="Investigator conclusion"
               value={version.investigator_conclusion} editable={editable}
               onCommit={(v) => onPatch({ investigator_conclusion: v })} />
      </div>
      {editable && (
        <label className="vr__check">
          <input type="checkbox" data-testid="confirm-disclosures"
                 defaultChecked={Boolean(version.disclosures_confirmed)}
                 onChange={(e) => onPatch({ disclosures_confirmed: e.target.checked })} />
          <span>
            I confirm deviations, exclusions and missing data are disclosed
            above, recording "none" where that is the case.
          </span>
        </label>
      )}
    </>
  );
}

function ReviewSection({ version, caps, busy, onSubmit, onStartReview, onDecision }: {
  version?: Record<string, unknown>;
  caps: Set<string>;
  busy: boolean;
  onSubmit: () => void;
  onStartReview: () => void;
  onDecision: (decision: string, comments: string) => Promise<void>;
}) {
  const [comments, setComments] = useState('');
  if (!version) return <EmptyState title="No version" />;

  return (
    <>
      <p className="vr__note" data-testid="review-guidance">
        A reviewer who performed the experiment cannot approve it. Independence
        is the entire content of the approval gate, and the server enforces it
        whatever this page offers.
      </p>

      {version.decision_comments != null && (
        <Alert tone="info" title="Recorded decision">
          <p data-testid="recorded-decision">{String(version.decision_comments)}</p>
        </Alert>
      )}

      <div className="vr__form">
        {caps.has('submit') && (
          <Button onClick={onSubmit} loading={busy} data-testid="submit-version">
            Submit for review
          </Button>
        )}
        {caps.has('start_review') && (
          <Button onClick={onStartReview} loading={busy}
                  data-testid="start-review">
            Begin scientific review
          </Button>
        )}
        {(caps.has('approve') || caps.has('reject')
          || caps.has('request_revision')) && (
          <>
            <TextField id="decision-comments" label="Reviewer comments" required
                       type="text" value={comments}
                       onChange={(e) => setComments(e.target.value)}
                       help="Required. A decision without a stated reason cannot be reviewed by anybody else." />
            <div className="vr__actions">
              {caps.has('request_revision') && (
                <Button variant="secondary" disabled={!comments.trim()}
                        data-testid="request-revision"
                        onClick={() => onDecision('request_revision', comments)}>
                  Request revision
                </Button>
              )}
              {caps.has('reject') && (
                <Button variant="secondary" disabled={!comments.trim()}
                        data-testid="reject"
                        onClick={() => onDecision('reject', comments)}>
                  Reject
                </Button>
              )}
              {caps.has('approve') && (
                <Button disabled={!comments.trim()} data-testid="approve"
                        onClick={() => onDecision('approve', comments)}>
                  Approve for E3
                </Button>
              )}
            </div>
          </>
        )}
        {caps.size <= 2 && (
          <Alert tone="info" role="note">
            <p data-testid="no-review-capability">
              You cannot act on this record in its current state. That may be
              because you performed the experiment, because your role does not
              permit it, or because the version is already decided.
            </p>
          </Alert>
        )}
      </div>
    </>
  );
}

function EvidenceSection({ verdict }: {
  verdict: EligibilityVerdict | null;
}) {
  if (!verdict) return <SkeletonBlock lines={4} />;
  return (
    <>
      <Alert tone={verdict.eligible ? 'success' : 'info'}
             title={verdict.eligible ? 'Eligible for E3' : 'Not eligible for E3'}>
        <p data-testid="eligibility-explanation">{verdict.explanation}</p>
      </Alert>

      <p className="vr__note" data-testid="ruleset-version">
        Evaluated under ruleset <span className="mono">{verdict.ruleset_version}</span>.
        A stored decision is never recomputed under later rules.
      </p>

      <DataTable caption="Eligibility gates"
                 head={[{ key: 'g', label: 'Gate' },
                        { key: 's', label: 'Result' },
                        { key: 'd', label: 'Detail' }]}>
        {verdict.gates.map((gate) => (
          <tr key={gate.id} data-testid={`gate-${gate.id}`}>
            <th scope="row">{gate.label}</th>
            <td>
              <Badge tone={gate.passed ? 'success' : 'warn'}>
                {gate.not_applicable ? 'Not applicable'
                  : gate.passed ? 'Passed' : 'Failed'}
              </Badge>
            </td>
            <td>
              {gate.detail}
              {gate.remedy && (
                <span className="vr__remedy"> → {gate.remedy}</span>
              )}
            </td>
          </tr>
        ))}
      </DataTable>

      {verdict.missing_requirements.length > 0 && (
        <div className="vr__missing" data-testid="missing-requirements">
          <h4>To become eligible</h4>
          <ol>
            {verdict.missing_requirements.map((r) => <li key={r}>{r}</li>)}
          </ol>
        </div>
      )}

      <p className="vr__note" data-testid="future-levels">
        E4, E5 and E6 — prospective in-vitro, in-vivo and clinical validation —
        are coming in a later phase. They cannot be requested here, and no
        record in this registry can establish one.
      </p>
    </>
  );
}

function VersionsSection({ detail, busy, onRevise }: {
  detail: ExperimentDetail; busy: boolean; onRevise: () => void;
}) {
  return (
    <>
      <p className="vr__note" data-testid="versions-guidance">
        A correction creates a new version. The superseded record keeps its
        decision, its comments and its measurements exactly as they were.
      </p>
      <DataTable caption="Version history"
                 head={[{ key: 'v', label: 'Version' },
                        { key: 's', label: 'Status' },
                        { key: 'l', label: 'Level' },
                        { key: 'c', label: 'Created' },
                        { key: 'x', label: 'Superseded by' }]}>
        {detail.versions.map((v) => (
          <tr key={v.id} data-testid={`version-${v.version_number}`}>
            <th scope="row">v{v.version_number}</th>
            <td><Badge tone={statusTone(v.status)} dot>{v.status_label}</Badge></td>
            <td>{v.approved_level ?? '—'}</td>
            <td>{new Date(v.created_at).toLocaleString()}</td>
            <td>{v.superseded_by_version_id
              ? `v${v.superseded_by_version_id}` : '—'}</td>
          </tr>
        ))}
      </DataTable>
      <Button variant="secondary" onClick={onRevise} loading={busy}
              data-testid="create-revision">
        Create a new version
      </Button>
    </>
  );
}

function AuditSection({ events }: { events: AuditEventRow[] }) {
  return (
    <>
      <p className="vr__note" data-testid="audit-guidance">
        Append-only. Nothing in this application updates or deletes an audit
        row, and the trail outlives the record it describes.
      </p>
      {events.length === 0 ? (
        <EmptyState title="No audit events" />
      ) : (
        <DataTable caption="Audit history"
                   head={[{ key: 't', label: 'When' },
                          { key: 'e', label: 'Event' },
                          { key: 'a', label: 'Actor' },
                          { key: 's', label: 'Summary' }]}>
          {events.map((e) => (
            <tr key={e.id} data-testid={`audit-${e.id}`}>
              <th scope="row">{new Date(e.created_at).toLocaleString()}</th>
              <td>{e.event}</td>
              <td>{e.actor_id ?? '—'}</td>
              <td>{e.summary ?? '—'}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </>
  );
}
