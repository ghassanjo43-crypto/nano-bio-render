/**
 * Scientific Readiness Dashboard.
 *
 * One card per readiness area, assessed independently. There is deliberately no
 * combined score: a single number would let strong structural data mask absent
 * biological evidence, which is the misreading the framework exists to prevent.
 *
 * This page does not replace `/evidence`. That page reports which *modules* are
 * built and connected; this one reports whether *this study's data* supports a
 * given kind of work. A module can be fully operational and a study still
 * blocked, and vice versa.
 *
 * Nothing here computes readiness. Every status, percentage, block and warning
 * comes from the backend rules engine.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getReadiness, getScienceRecords, listRuns } from '../../api/client';
import type { WorkspaceErrorResponse } from '../../api/types';
import {
  Alert, Badge, Button, Card, SelectField, SkeletonBlock,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import {
  EVIDENCE_LABEL, SCIENTIFIC_LABEL, SCIENTIFIC_TONE,
  labelForReadiness, toneForReadiness,
  type AreaAssessment, type ReadinessReport, type ScienceRecordListResponse,
  type ScientificStatusId,
} from './readinessTypes';
import './ScientificReadinessPage.css';

interface StudyOption { id: number; name: string; }

export default function ScientificReadinessPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const studyParam = params.get('study');

  const [studies, setStudies] = useState<StudyOption[] | null>(null);
  const [studyId, setStudyId] = useState<number | null>(
    studyParam ? Number(studyParam) : null);
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [records, setRecords] = useState<ScienceRecordListResponse | null>(null);
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  const [loading, setLoading] = useState(false);

  /* ------------------------------------------------------- study selection */
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      const result = await listRuns({}, controller.signal);
      if (result.status === 'error') { setError(result.error); return; }
      const options = result.data.runs.map((r) => ({ id: r.id, name: r.name }));
      setStudies(options);
      if (studyId === null && options.length > 0) setStudyId(options[0]!.id);
    })();
    return () => controller.abort();
    // Runs once: the study list does not change while the page is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = useCallback(async (id: number, signal?: AbortSignal) => {
    setLoading(true);
    const [assessment, recordList] = await Promise.all([
      getReadiness(id, signal), getScienceRecords(id, signal),
    ]);
    setLoading(false);
    if (assessment.status === 'error') {
      setError(assessment.error); setReport(null); return;
    }
    setError(null);
    setReport(assessment.data);
    setRecords(recordList.status === 'ok' ? recordList.data : null);
  }, []);

  useEffect(() => {
    if (studyId === null) return;
    const controller = new AbortController();
    setParams({ study: String(studyId) }, { replace: true });
    void load(studyId, controller.signal);
    return () => controller.abort();
  }, [studyId, load, setParams]);

  /* ------------------------------------------------- provenance breakdown */
  const provenanceCounts = useMemo(() => {
    const counts = new Map<ScientificStatusId, number>();
    for (const record of records?.records ?? []) {
      counts.set(record.status, (counts.get(record.status) ?? 0) + 1);
    }
    return counts;
  }, [records]);

  return (
    <>
      <Card
        title="Scientific Readiness"
        subtitle={
          'Whether the information recorded for this study is sufficient and '
          + 'self-consistent for each kind of work. Each area is assessed '
          + 'independently.'
        }
        accent
        actions={
          <Button variant="secondary" onClick={() => navigate('/evidence')}
                  iconLeft={<Icon name="shield" size={15} />}
                  data-testid="go-to-evidence">
            Module status
          </Button>
        }
      >
        <Alert tone="warn" title="Readiness is not accreditation">
          <p data-testid="not-accreditation">
            {report?.notice
              ?? 'Scientific readiness describes whether the information '
                 + 'recorded for this study is sufficient and self-consistent '
                 + 'for a given kind of analysis. It is not regulatory '
                 + 'approval, clinical validation, scientific accreditation, or '
                 + 'evidence that any result is correct. A study can be fully '
                 + 'ready and still be scientifically wrong.'}
          </p>
          <p className="sr__hint">
            This page reports on <strong>this study's data</strong>.{' '}
            <strong>Module status</strong> (<span className="mono">/evidence</span>)
            reports which parts of the platform are built and connected. A
            module can be operational while a study remains blocked.
          </p>
        </Alert>

        {studies !== null && studies.length === 0 && (
          <Alert tone="info" title="No saved studies">
            <p>
              Readiness is assessed per study. Save a study first — nothing is
              assessed until there is something to assess.
            </p>
            <Button variant="secondary" onClick={() => navigate('/start')}
                    data-testid="start-a-study">
              Start a study
            </Button>
          </Alert>
        )}

        {studies !== null && studies.length > 0 && (
          <SelectField
            id="sr-study" label="Study" value={studyId === null ? '' : String(studyId)}
            onChange={(e) => setStudyId(Number(e.target.value))}
            options={studies.map((s) => ({ value: String(s.id), label: s.name }))}
          />
        )}

        {error && (
          <Alert tone="danger" title="Readiness unavailable">
            <p>{error.message}</p>
            {error.detail && <p className="mono sr__hint">{error.detail}</p>}
          </Alert>
        )}

        {loading && <SkeletonBlock lines={5} />}

        {records?.is_legacy_import && (
          <Alert tone="info" title="Legacy study">
            <p data-testid="legacy-notice">{records.legacy_notice}</p>
          </Alert>
        )}

        {report && (
          <p className="sr__meta" data-testid="engine-meta">
            Rules engine <span className="mono">{report.rules_engine_version}</span>
            {' · '}dictionary <span className="mono">{report.dictionary_version}</span>
            {' · '}assessed {new Date(report.evaluated_at).toLocaleString()}
            {' · '}{report.record_count} scientific record
            {report.record_count === 1 ? '' : 's'}
          </p>
        )}
      </Card>

      {/* --------------------------------------------- provenance legend */}
      {records && records.records.length > 0 && (
        <Card title="How this study's data is known"
              subtitle="Measured, predicted, literature-derived, assumed, illustrative and missing are visually distinct throughout.">
          <ul className="sr__provenance" data-testid="provenance-summary">
            {(Object.keys(SCIENTIFIC_LABEL) as ScientificStatusId[])
              .filter((s) => (provenanceCounts.get(s) ?? 0) > 0)
              .map((s) => (
                <li key={s} data-testid={`provenance-${s}`}>
                  <Badge tone={SCIENTIFIC_TONE[s]} dot>
                    {SCIENTIFIC_LABEL[s]}
                  </Badge>
                  <strong>{provenanceCounts.get(s)}</strong>
                </li>
              ))}
          </ul>
        </Card>
      )}

      {/* ------------------------------------------------------ area cards */}
      {report && (
        <div className="sr__areas" data-testid="readiness-areas">
          {report.areas.map((area) => (
            <AreaCard key={area.area} area={area} studyId={report.study_id}
                      onNavigate={navigate} />
          ))}
        </div>
      )}
    </>
  );
}

/* ======================================================================= */

function AreaCard({ area, studyId, onNavigate }: {
  area: AreaAssessment;
  studyId: number;
  onNavigate: (to: string) => void;
}) {
  const blocked = area.status === 'blocked'
    || area.status === 'outside_model_domain';

  return (
    <section className="sr__area" data-testid={`area-${area.area}`}>
      <header className="sr__areahead">
        <h3>{area.label}</h3>
        <Badge tone={toneForReadiness(area.status)} dot>
          {labelForReadiness(area.status)}
        </Badge>
      </header>

      <p className="sr__areadesc">{area.description}</p>

      {/* The percentage and the status are shown together, and the card says
          plainly when a high percentage does not mean the work can proceed. */}
      <div className="sr__metrics">
        <div>
          <span className="sr__metriclabel">Completeness</span>
          <span className="sr__metricvalue mono"
                data-testid={`percent-${area.area}`}>
            {area.readiness_percent}%
          </span>
          <div className="sr__bar" aria-hidden="true">
            <div className={`sr__barfill sr__barfill--${
              blocked ? 'blocked' : area.status}`}
                 style={{ width: `${area.readiness_percent}%` }} />
          </div>
        </div>
        <div>
          <span className="sr__metriclabel">Evidence level</span>
          <span className="sr__metricvalue" data-testid={`evidence-${area.area}`}>
            {EVIDENCE_LABEL[area.evidence_level]}
          </span>
          {/* The level is never shown bare. "E2" alone reads as a middling
              score; with its reason it reads as what it is — a statement that
              nothing here has been validated against anything. */}
          {area.evidence_level_rationale && (
            <p className="sr__evidencewhy"
               data-testid={`evidence-why-${area.area}`}>
              {area.evidence_level_rationale}
            </p>
          )}
        </div>
      </div>

      {blocked && area.readiness_percent >= 50 && (
        <p className="sr__override" data-testid={`override-note-${area.area}`}>
          This area is {labelForReadiness(area.status).toLowerCase()} despite
          being {area.readiness_percent}% complete. A completeness percentage
          never satisfies a mandatory requirement.
        </p>
      )}

      {area.blocking_issues.length > 0 && (
        <FindingList title="Blocking" tone="warn" testId={`blocking-${area.area}`}
                     items={area.blocking_issues} />
      )}
      {area.incompatible_inputs.length > 0 && (
        <FindingList title="Incompatible inputs" tone="danger"
                     testId={`incompatible-${area.area}`}
                     items={area.incompatible_inputs} />
      )}
      {area.warnings.length > 0 && (
        <FindingList title="Warnings" tone="info" testId={`warnings-${area.area}`}
                     items={area.warnings} />
      )}
      {area.assumptions.length > 0 && (
        <FindingList title="Assumptions in use" tone="warn"
                     testId={`assumptions-${area.area}`}
                     items={area.assumptions} />
      )}

      {area.missing_inputs.length > 0 && (
        <details className="sr__missing" data-testid={`missing-${area.area}`}>
          <summary>
            Missing data checklist ({area.missing_inputs.length})
          </summary>
          <ul>
            {area.missing_inputs.map((id) => <li key={id} className="mono">{id}</li>)}
          </ul>
        </details>
      )}

      {area.recommended_actions.length > 0 && (
        <div className="sr__actions" data-testid={`actions-${area.area}`}>
          <h4>To complete this area</h4>
          <ol>
            {area.recommended_actions.map((a) => <li key={a}>{a}</li>)}
          </ol>
        </div>
      )}

      <div className="sr__arealinks">
        <Button size="sm" variant="secondary"
                onClick={() => onNavigate('/workflow/design')}>
          Edit design
        </Button>
        {area.area === 'structural_visualization' && (
          <Button size="sm" variant="secondary"
                  onClick={() => onNavigate(`/builder?study=${studyId}`)}
                  data-testid="area-to-builder">
            Open 3D Builder
          </Button>
        )}
        {area.area === 'pharmacokinetic_modelling' && (
          <Button size="sm" variant="secondary"
                  onClick={() => onNavigate('/workflow/review')}>
            PK inputs
          </Button>
        )}
      </div>
    </section>
  );
}

function FindingList({ title, tone, items, testId }: {
  title: string;
  tone: 'warn' | 'danger' | 'info';
  items: Array<{ code: string; message: string; recommended_action: string | null }>;
  testId: string;
}) {
  return (
    <div className={`sr__findings sr__findings--${tone}`} data-testid={testId}>
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item.code}>
            <span>{item.message}</span>
            {item.recommended_action && (
              <span className="sr__action">→ {item.recommended_action}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
