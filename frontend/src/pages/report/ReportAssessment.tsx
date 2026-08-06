/**
 * Medical Report Assessment — upload, review, confirm, and carry into the workflow.
 *
 * Honesty contract for this screen
 * --------------------------------
 *  • **No extraction engine is connected.** The screen says so plainly and
 *    every field arrives as "not found". It never presents a value the document
 *    did not yield.
 *  • Each field shows its provenance. "The report states this" and "you typed
 *    this" are visually different things, and an inferred or ambiguous reading
 *    cannot be confirmed without an explicit decision — the server rejects it
 *    too, so this is not merely a UI courtesy.
 *  • Confirmed values populate **therapeutic context only**. They do not reach
 *    any calculation, and the screen says that where the user will read it.
 *  • **Nothing here touches client storage.** Report content lives in component
 *    state and is re-fetched when needed. A test asserts localStorage and
 *    sessionStorage stay clean.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  confirmReportFields, deleteReportAssessment, listSyntheticReports,
  loadSyntheticReport, mapReportToWorkflow, uploadReport,
} from '../../api/client';
import type {
  ClinicalFieldSpec, FieldProvenance, ReportUploadResponse,
  SyntheticReportSummary, WorkspaceErrorResponse,
} from '../../api/types';
import {
  Alert, Badge, Button, Card, DataTable, SelectField, SkeletonBlock, TextField,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { DISEASES, drugsFor, subtypesFor } from '../../workflow/diseaseData';
import { useWorkflow } from '../../workflow/WorkflowContext';
import './ReportAssessment.css';

type Stage = 'intake' | 'review';

/** Human labels and tone for each provenance value. */
const PROVENANCE_META: Record<FieldProvenance,
  { label: string; tone: 'success' | 'warn' | 'danger' | 'neutral' | 'accent';
    hint: string }> = {
  explicitly_stated: { label: 'Stated in report', tone: 'success',
    hint: 'The document says this in so many words.' },
  inferred: { label: 'Inferred', tone: 'warn',
    hint: 'Derived from context, not stated. Must be accepted or replaced.' },
  ambiguous: { label: 'Ambiguous', tone: 'warn',
    hint: 'The document supports more than one reading. Resolve it yourself.' },
  conflicting: { label: 'Conflicting', tone: 'danger',
    hint: 'The document states two different values and does not reconcile '
      + 'them. Both are shown; choose or type the correct one.' },
  not_found: { label: 'Not in report', tone: 'neutral',
    hint: 'The document does not contain this. Leave blank or enter it yourself.' },
  user_entered: { label: 'You entered', tone: 'accent',
    hint: 'Typed by you. Not attributed to the document.' },
  user_corrected: { label: 'You corrected', tone: 'accent',
    hint: 'You overrode the extracted value. The original is retained.' },
};

/**
 * Readings that must not be auto-promoted to a confirmed value.
 *
 * The server enforces the same rule, so this is a usability affordance rather
 * than the control itself: a client that skipped it would still be refused.
 */
function needsDecision(provenance: FieldProvenance): boolean {
  return provenance === 'inferred' || provenance === 'ambiguous'
    || provenance === 'conflicting';
}

interface FieldState {
  key: string;
  label: string;
  mapsTo: 'disease' | 'subtype' | 'drug' | null;
  value: string;
  provenance: FieldProvenance;
  originalValue: string | null;
  originalProvenance: FieldProvenance;
  supportingText: string | null;
  page: number | null;
  confidence: number;
  alternatives: string[];
  supportingExcerpts: string[];
  note: string | null;
}

export default function ReportAssessment() {
  const navigate = useNavigate();
  const { setSelection, reachStep } = useWorkflow();

  const [stage, setStage] = useState<Stage>('intake');
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const [synthetic, setSynthetic] = useState<SyntheticReportSummary[] | null>(null);
  const [syntheticNotice, setSyntheticNotice] = useState('');

  const [file, setFile] = useState<File | null>(null);
  const [classification, setClassification] =
    useState<'synthetic' | 'deidentified'>('synthetic');
  const [attested, setAttested] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const [upload, setUpload] = useState<ReportUploadResponse | null>(null);
  const [specs, setSpecs] = useState<ClinicalFieldSpec[]>([]);
  const [fields, setFields] = useState<FieldState[]>([]);

  const [disease, setDisease] = useState('');
  const [subtype, setSubtype] = useState('');
  const [drug, setDrug] = useState('');
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      const result = await listSyntheticReports(controller.signal);
      if (result.status === 'ok') {
        setSynthetic(result.data.reports);
        setSyntheticNotice(result.data.notice);
      } else {
        setSynthetic([]);
      }
    })();
    return () => controller.abort();
  }, []);

  /** Build editable field rows from an upload response. */
  const enterReview = useCallback((response: ReportUploadResponse,
                                   fieldSpecs: ClinicalFieldSpec[]) => {
    setUpload(response);
    setSpecs(fieldSpecs);
    setFields(response.extraction.fields.map((f) => {
      const spec = fieldSpecs.find((s) => s.key === f.key);
      return {
        key: f.key,
        label: f.label,
        mapsTo: spec?.maps_to_workflow ?? null,
        value: f.value ?? '',
        provenance: f.provenance,
        originalValue: f.value,
        originalProvenance: f.provenance,
        supportingText: f.supporting_text,
        page: f.page,
        confidence: f.confidence ?? 0,
        alternatives: f.alternatives ?? [],
        supportingExcerpts: f.supporting_excerpts ?? [],
        note: f.note,
      };
    }));
    setConfirmed(false);
    setStage('review');
  }, []);

  /** Field specs are not on the upload response; derive them from the fields. */
  function specsFrom(response: ReportUploadResponse): ClinicalFieldSpec[] {
    const mapping: Record<string, 'disease' | 'subtype' | 'drug'> = {
      cancer_indication: 'disease',
      histological_subtype: 'subtype',
      current_treatment: 'drug',
    };
    return response.extraction.fields.map((f) => ({
      key: f.key, label: f.label, maps_to_workflow: mapping[f.key] ?? null,
    }));
  }

  async function handleUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    const result = await uploadReport(file, classification, attested);
    setBusy(false);
    if (result.status === 'error') { setError(result.error); return; }
    enterReview(result.data, specsFrom(result.data));
  }

  async function handleLoadSynthetic(slug: string) {
    setBusy(true);
    setError(null);
    const result = await loadSyntheticReport(slug);
    setBusy(false);
    if (result.status === 'error') { setError(result.error); return; }
    enterReview(result.data, specsFrom(result.data));
  }

  /**
   * Accept an inferred, ambiguous or conflicting reading as-is.
   *
   * This is the ONLY route from an unresolved reading to a confirmable one, and
   * it is a deliberate act. The value becomes `user_corrected` — the human took
   * responsibility for it — while `originalValue` preserves what the engine
   * actually found, so the override stays visible as an override.
   */
  function acceptField(key: string) {
    setFields((prev) => prev.map((f) => (
      f.key === key && f.originalValue
        ? { ...f, value: f.originalValue, provenance: 'user_corrected' }
        : f
    )));
    setConfirmed(false);
  }

  /**
   * Editing a field records it as user-entered (or user-corrected when an
   * engine had produced a value). The value never keeps a report-derived
   * provenance it no longer deserves.
   */
  function editField(key: string, value: string) {
    setFields((prev) => prev.map((f) => {
      if (f.key !== key) return f;
      const wasEngineValue = f.originalValue !== null
        && f.provenance !== 'user_entered' && f.provenance !== 'user_corrected';
      return {
        ...f,
        value,
        provenance: value
          ? (wasEngineValue ? 'user_corrected' : 'user_entered')
          : 'not_found',
      };
    }));
    setConfirmed(false);
  }

  async function handleConfirm() {
    if (!upload) return;
    setBusy(true);
    setError(null);
    const result = await confirmReportFields(upload.assessment_id,
      fields.map((f) => ({
        key: f.key,
        value: f.value || null,
        provenance: f.provenance,
        supporting_text: f.supportingText,
        page: f.page,
        original_value: f.originalValue,
      })));
    setBusy(false);
    if (result.status === 'error') { setError(result.error); return; }
    setConfirmed(true);

    // Offer the confirmed indication as a starting point, but only when it is
    // an exact match for a curated one. A near-miss is left for the user.
    const indication = fields.find((f) => f.mapsTo === 'disease')?.value ?? '';
    if (DISEASES.some((d) => d.name === indication)) setDisease(indication);
  }

  async function handleContinue() {
    if (!upload || !disease || !subtype || !drug) return;
    setBusy(true);
    setError(null);
    const result = await mapReportToWorkflow(upload.assessment_id,
                                             { disease, subtype, drug });
    setBusy(false);
    if (result.status === 'error') { setError(result.error); return; }

    setSelection({ disease, subtype, drug });
    reachStep(2);
    navigate('/workflow/disease');
  }

  async function handleDiscard() {
    if (!upload) return;
    setBusy(true);
    await deleteReportAssessment(upload.assessment_id);
    setBusy(false);
    setUpload(null);
    setFields([]);
    setFile(null);
    setAttested(false);
    if (fileInput.current) fileInput.current.value = '';
    setStage('intake');
  }

  /* =================================================================== */
  if (stage === 'review' && upload) {
    return (
      <ReviewStage
        upload={upload}
        fields={fields}
        specs={specs}
        error={error}
        busy={busy}
        confirmed={confirmed}
        disease={disease}
        subtype={subtype}
        drug={drug}
        onEditField={editField}
        onAccept={acceptField}
        onConfirm={handleConfirm}
        onDisease={(v) => { setDisease(v); setSubtype(''); setDrug(''); }}
        onSubtype={(v) => { setSubtype(v); setDrug(''); }}
        onDrug={setDrug}
        onContinue={handleContinue}
        onDiscard={handleDiscard}
      />
    );
  }

  return (
    <>
      <Card
        title="Medical Report Assessment"
        subtitle="Upload a report, review its contents, and carry the confirmed context into a design session."
        accent
      >
        <Alert tone="warn" title="Extraction is automatic but unvalidated"
               role="note">
          <p data-testid="extraction-status">
            Clinical fields are read from the document by a{' '}
            <strong>rule-based extractor</strong>. It is not a trained model, has
            not been calibrated against annotated reports, and its accuracy is
            unmeasured. Every value it returns is shown with the exact excerpt
            and page that produced it, <strong>so check each one against the
            document before confirming</strong>. Inferred, ambiguous and
            contradictory readings are flagged and never confirmed for you.
          </p>
          <p data-testid="ocr-status">
            A <strong>scanned</strong> PDF has no text layer, and no optical
            character recognition engine is installed. Such a document is
            reported as unreadable rather than guessed at; enter its details
            manually.
          </p>
        </Alert>

        <Alert tone="danger" title="Synthetic and de-identified documents only"
               role="note">
          <p data-testid="phi-policy">
            Real patient reports are <strong>refused</strong>. This deployment
            has no encryption at rest, no enforced retention schedule and no
            recorded legal basis for processing patient data. The restriction is
            a deliberate scope decision, not an oversight, and it is enforced by
            the server.
          </p>
        </Alert>

        {error && (
          <div data-testid="upload-error">
            <Alert tone="danger" title="Upload refused">
              <p>{error.message}</p>
              {error.detail && <p className="ra__detail">{error.detail}</p>}
            </Alert>
          </div>
        )}

        {/* ------------------------------------------------- upload */}
        <section className="ra__block" aria-labelledby="ra-upload">
          <h3 className="ra__head" id="ra-upload">Upload a document</h3>
          <p className="ra__note">
            Accepted: plain text (<code>.txt</code>), Markdown
            (<code>.md</code>) and PDF (<code>.pdf</code>), up to 15 MB. The file
            type is determined from the file's contents, never from its name.
            PDFs are stored but their text cannot be displayed — no PDF reader is
            installed.
          </p>

          <input
            ref={fileInput}
            id="report-file"
            type="file"
            accept=".txt,.md,.markdown,.pdf"
            className="ra__file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            aria-label="Medical report document"
          />

          <div className="ra__intake">
            <SelectField
              id="classification"
              label="Document classification"
              value={classification}
              onChange={(e) => setClassification(
                e.target.value as 'synthetic' | 'deidentified')}
              options={[
                { value: 'synthetic', label: 'Synthetic — fabricated test document' },
                { value: 'deidentified', label: 'De-identified — identifiers already removed' },
              ]}
              help="Real patient reports cannot be accepted and are refused by the server."
            />
          </div>

          <label className="ra__attest">
            <input
              type="checkbox"
              checked={attested}
              onChange={(e) => setAttested(e.target.checked)}
              data-testid="attestation"
            />
            <span>
              I confirm this document contains <strong>no real patient
              information</strong>. This declaration is recorded with the
              assessment and is auditable.
            </span>
          </label>

          <Button onClick={handleUpload} disabled={!file || !attested || busy}
                  loading={busy} data-testid="submit-upload"
                  iconLeft={<Icon name="document" size={15} />}>
            Upload and review
          </Button>
          {!attested && file && (
            <p className="ra__blocked" data-testid="attestation-required">
              The attestation is required before this document can be uploaded.
            </p>
          )}
        </section>

        {/* ---------------------------------------------- synthetic */}
        <section className="ra__block" aria-labelledby="ra-synth">
          <h3 className="ra__head" id="ra-synth">
            Or load a synthetic demonstration report
          </h3>
          <p className="ra__note" data-testid="synthetic-notice">
            {syntheticNotice || 'Fabricated documents for testing the workflow.'}
          </p>

          {synthetic === null && <SkeletonBlock lines={3} />}

          {synthetic !== null && (
            <div className="ra__fixtures" data-testid="synthetic-reports">
              {synthetic.map((r) => (
                <article className="ra__fixture" key={r.slug}
                         data-testid={`synthetic-${r.slug}`}>
                  <Badge tone="warn" dot>{r.data_classification}</Badge>
                  <h4 className="ra__fixtitle">{r.title}</h4>
                  <p className="ra__fixbody">{r.purpose}</p>
                  <p className="ra__fixdemo"><strong>Demonstrates:</strong>{' '}
                    {r.demonstrates}</p>
                  <Button variant="secondary" disabled={busy}
                          onClick={() => handleLoadSynthetic(r.slug)}
                          iconRight={<Icon name="arrow-right" size={15} />}>
                    Load this report
                  </Button>
                </article>
              ))}
            </div>
          )}
        </section>
      </Card>
    </>
  );
}

/* ===================================================================== */
/* Review stage                                                          */
/* ===================================================================== */

function ReviewStage(props: {
  upload: ReportUploadResponse;
  fields: FieldState[];
  specs: ClinicalFieldSpec[];
  error: WorkspaceErrorResponse | null;
  busy: boolean;
  confirmed: boolean;
  disease: string;
  subtype: string;
  drug: string;
  onEditField: (key: string, value: string) => void;
  onAccept: (key: string) => void;
  onConfirm: () => void;
  onDisease: (v: string) => void;
  onSubtype: (v: string) => void;
  onDrug: (v: string) => void;
  onContinue: () => void;
  onDiscard: () => void;
}) {
  const {
    upload, fields, error, busy, confirmed, disease, subtype, drug,
    onEditField, onAccept, onConfirm, onDisease, onSubtype, onDrug, onContinue,
    onDiscard,
  } = props;

  const notFound = fields.filter((f) => f.provenance === 'not_found').length;
  const unresolved = fields.filter((f) => needsDecision(f.provenance));
  const stated = fields.filter((f) => f.provenance === 'explicitly_stated');
  const entered = fields.filter(
    (f) => f.provenance === 'user_entered' || f.provenance === 'user_corrected');

  return (
    <>
      <Card
        title="Review extracted information"
        subtitle="Check every field against the document before confirming."
        accent
        actions={
          <Button variant="ghost" onClick={onDiscard} disabled={busy}
                  data-testid="discard-report">
            Discard this document
          </Button>
        }
      >
        <dl className="ra__meta">
          <div><dt>Document</dt><dd>{upload.display_name}</dd></div>
          <div><dt>Classification</dt>
            <dd><Badge tone="warn">{upload.classification}</Badge></dd></div>
          <div><dt>Extraction engine</dt>
            <dd data-testid="engine-version">
              <code>{upload.extraction.engine_name}</code>{' '}
              <code>{upload.extraction.engine_version}</code>
            </dd></div>
          <div><dt>Contract version</dt>
            <dd><code>{upload.extraction.contract_version}</code></dd></div>
        </dl>

        <Alert tone="warn" title="What the platform did with this document"
               role="note">
          <p data-testid="extraction-message">{upload.extraction.message}</p>
        </Alert>

        {upload.intake_warnings.length > 0 && (
          <ul className="ra__warnings" data-testid="intake-warnings">
            {upload.intake_warnings.map((w) => (
              <li key={w}><Icon name="info" size={14} /><span>{w}</span></li>
            ))}
          </ul>
        )}

        {error && (
          <div data-testid="review-error">
            <Alert tone="danger" title="Could not save">
              <p>{error.message}</p>
              {error.detail && <p className="ra__detail">{error.detail}</p>}
            </Alert>
          </div>
        )}

        <div className="ra__counts">
          <span><strong>{notFound}</strong> not found in the report</span>
          <span><strong>{entered.length}</strong> entered by you</span>
          <span><strong>{stated.length}</strong> read from the document</span>
          {unresolved.length > 0 && (
            <span className="ra__needs" data-testid="needs-decision">
              <strong>{unresolved.length}</strong> need an explicit decision
            </span>
          )}
        </div>
      </Card>

      {/* ------------------------------------------------- document */}
      <Card title="The document"
            subtitle={upload.document_readable
              ? 'Read the report here and enter the details below.'
              : 'This document cannot be displayed.'}>
        {upload.document_readable && upload.document_text ? (
          <pre className="ra__document" data-testid="document-text">
            {upload.document_text}
          </pre>
        ) : (
          <Alert tone="info" title="Document text unavailable">
            <p data-testid="unreadable-reason">
              {upload.unreadable_reason
                ?? 'The text of this document cannot be displayed.'}
            </p>
          </Alert>
        )}
      </Card>

      {/* --------------------------------------------------- fields */}
      <Card title="Clinical fields"
            subtitle="Every field records where its value came from.">
        <p className="ra__note">
          A field left blank stays <em>not in report</em> — it is never filled
          with a guess. Anything you type is recorded as entered by you, and is
          not attributed to the document.
        </p>

        <DataTable
          caption="Clinical fields with provenance"
          head={[
            { key: 'f', label: 'Field' },
            { key: 'v', label: 'Value' },
            { key: 'p', label: 'Provenance' },
            { key: 's', label: 'Supporting text' },
          ]}
        >
          {fields.map((f) => {
            const meta = PROVENANCE_META[f.provenance];
            return (
              <tr key={f.key} data-testid={`field-${f.key}`}>
                <th scope="row">
                  {f.label}
                  {f.mapsTo && (
                    <span className="ra__mapsto">
                      maps to {f.mapsTo}
                    </span>
                  )}
                </th>
                <td>
                  {/* The row header already names the field, so the input's
                      visible label is hidden to avoid repeating it. It stays in
                      the DOM for screen readers and label-based queries. */}
                  <div className="ra__inputcell">
                    <TextField
                      id={`field-input-${f.key}`}
                      label={f.label}
                      value={f.value}
                      onChange={(e) => onEditField(f.key, e.target.value)}
                      placeholder="not in report"
                      className="ra__fieldinput"
                    />
                  </div>
                </td>
                <td>
                  <Badge tone={meta.tone} dot>{meta.label}</Badge>
                  {f.provenance !== 'not_found'
                    && f.provenance !== 'user_entered' && (
                    <span className="ra__conf" title={
                      'Heuristic pattern-strength, not a probability.'
                    }>
                      match strength {f.confidence.toFixed(2)}
                    </span>
                  )}
                  <span className="ra__provhint">{meta.hint}</span>

                  {/* An unresolved reading needs a deliberate act, so the
                      action to accept it is offered here rather than the user
                      having to retype a value the engine already found. */}
                  {needsDecision(f.provenance) && f.originalValue && (
                    <Button size="sm" variant="secondary"
                            className="ra__accept"
                            onClick={() => onAccept(f.key)}
                            data-testid={`accept-${f.key}`}>
                      Accept this reading
                    </Button>
                  )}
                </td>
                <td>
                  {f.supportingExcerpts.length > 0 || f.supportingText ? (
                    <>
                      {(f.supportingExcerpts.length
                        ? f.supportingExcerpts
                        : [f.supportingText!]).map((excerpt, i) => (
                        <blockquote className="ra__quote" key={i}>
                          “{excerpt}”
                          {f.page && <cite>page {f.page}</cite>}
                        </blockquote>
                      ))}
                      {f.alternatives.length > 0 && (
                        <p className="ra__alts" data-testid={`alts-${f.key}`}>
                          <strong>Also stated:</strong>{' '}
                          {f.alternatives.join('; ')}
                        </p>
                      )}
                    </>
                  ) : (
                    <span className="ra__nosupport">
                      not stated in the document
                    </span>
                  )}
                  {f.note && <p className="ra__fieldnote">{f.note}</p>}
                </td>
              </tr>
            );
          })}
        </DataTable>

        <div className="ra__actions">
          <Button onClick={onConfirm} loading={busy} disabled={busy}
                  data-testid="confirm-fields"
                  iconLeft={<Icon name="check" size={15} />}>
            {confirmed ? 'Re-confirm these fields' : 'Confirm these fields'}
          </Button>
          {confirmed && (
            <span className="ra__confirmed" data-testid="fields-confirmed">
              Confirmed. Choose the therapeutic context below.
            </span>
          )}
        </div>
      </Card>

      {/* -------------------------------------------------- mapping */}
      <Card title="Therapeutic context"
            subtitle="Carried into Disease & Therapeutic Selection for traceability.">
        <Alert tone="info" title="This does not affect any calculation"
               role="note">
          <p data-testid="no-calculation-effect">
            The connected engines take no disease as input: the design impact
            score is computed from formulation parameters only, and the
            pharmacokinetic model from a dose and four rate constants only.
            Nothing in this report can change a calculated number.
          </p>
        </Alert>

        <p className="ra__note">
          The combination must exist in the platform's curated mapping. An
          invalid combination is refused rather than stored.
        </p>

        <div className="ra__mapgrid">
          <SelectField
            id="map-disease" label="Indication" value={disease}
            onChange={(e) => onDisease(e.target.value)}
            options={[{ value: '', label: 'Select an indication' },
                      ...DISEASES.map((d) => ({ value: d.name, label: d.name }))]}
          />
          <SelectField
            id="map-subtype" label="Disease subtype" value={subtype}
            disabled={!disease}
            onChange={(e) => onSubtype(e.target.value)}
            options={[{ value: '', label: 'Select a subtype' },
                      ...subtypesFor(disease).map(
                        (s) => ({ value: s.name, label: s.name }))]}
          />
          <SelectField
            id="map-drug" label="Therapeutic agent" value={drug}
            disabled={!subtype}
            onChange={(e) => onDrug(e.target.value)}
            options={[{ value: '', label: 'Select an agent' },
                      ...drugsFor(disease, subtype).map(
                        (d) => ({ value: d, label: d }))]}
          />
        </div>

        <Button
          onClick={onContinue}
          disabled={!confirmed || !disease || !subtype || !drug || busy}
          loading={busy}
          data-testid="continue-to-workflow"
          iconRight={<Icon name="arrow-right" size={15} />}
        >
          Continue to design parameters
        </Button>
        {!confirmed && (
          <p className="ra__blocked" data-testid="confirm-first">
            Confirm the clinical fields above before continuing.
          </p>
        )}
      </Card>
    </>
  );
}
