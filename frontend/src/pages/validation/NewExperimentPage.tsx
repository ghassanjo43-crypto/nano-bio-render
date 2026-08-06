/**
 * New In-Vitro Experiment.
 *
 * Two things are fixed at creation and cannot be changed afterwards: the
 * candidate version the experiment is about, and the scientific purpose it
 * claims. Both are deliberate.
 *
 * The candidate version, because a result must be attributable to the material
 * that was actually tested — re-pointing it later would silently re-attribute
 * the finding. The purpose, because an experiment designed to answer one
 * question must not be re-aimed at another once the results are in.
 *
 * The purpose selector offers only purposes the chosen assay can evidence. A
 * cytotoxicity assay cannot be filed against structural visualization here, and
 * the backend refuses it independently — the interface narrows the choice, the
 * server enforces it.
 */

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createCandidate, createCandidateVersion, createExperiment, listCandidates,
  type CandidateRow,
} from '../../api/registryClient';
import type { WorkspaceErrorResponse } from '../../api/types';
import {
  Alert, Button, Card, SelectField, TextField,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { useWorkflow } from '../../workflow/WorkflowContext';
import PathwayBanner from '../../workflow/PathwayBanner';
import {
  PURPOSE_LABEL, SUBTYPE_FORMS, SUBTYPE_LABEL,
  type PurposeId, type SubtypeId,
} from './registryTypes';
import './ValidationRegistry.css';

/**
 * Which purposes each subtype may claim.
 *
 * Mirrors `SUBTYPE_PERMITTED_PURPOSES` in the backend vocabulary. Duplicated so
 * the form can narrow the choice before a round trip; the backend refuses an
 * incompatible pairing regardless, so this is a convenience and never the
 * control.
 */
const PERMITTED: Record<SubtypeId, PurposeId[]> = {
  particle_size_pdi: ['structural_visualization', 'formulation_assessment'],
  zeta_potential: ['formulation_assessment'],
  drug_loading: ['formulation_assessment'],
  encapsulation_efficiency: ['formulation_assessment'],
  stability: ['formulation_assessment', 'safety_assessment'],
  release_profile: ['formulation_assessment'],
  target_binding: ['biological_targeting'],
  cellular_uptake: ['biological_targeting'],
  cytotoxicity: ['safety_assessment'],
  selectivity: ['biological_targeting', 'safety_assessment'],
  intracellular_pathway: ['biological_targeting'],
  hemocompatibility: ['safety_assessment'],
  basic_cellular_toxicity: ['safety_assessment'],
  other_in_vitro: ['formulation_assessment', 'safety_assessment'],
};

export default function NewExperimentPage() {
  const navigate = useNavigate();
  const { session } = useWorkflow();

  const [candidates, setCandidates] = useState<CandidateRow[] | null>(null);
  const [candidateVersionId, setCandidateVersionId] = useState<string>('');
  const [subtype, setSubtype] = useState<SubtypeId>('cytotoxicity');
  const [purpose, setPurpose] = useState<PurposeId>('safety_assessment');
  const [title, setTitle] = useState('');
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  const [busy, setBusy] = useState(false);

  // Candidate creation, inline. Without it the workflow could not be completed
  // from the interface at all: an experiment needs a frozen candidate version,
  // and until now the only way to make one was an API call.
  const [showCreate, setShowCreate] = useState(false);
  const [newCode, setNewCode] = useState('');
  const [newName, setNewName] = useState('');
  const [versionNote, setVersionNote] = useState('');

  const studyId = session.studyId ?? null;

  useEffect(() => {
    if (studyId === null) return;
    const controller = new AbortController();
    void (async () => {
      const result = await listCandidates(studyId, controller.signal);
      if (result.status === 'ok') setCandidates(result.data.candidates);
    })();
    return () => controller.abort();
  }, [studyId]);

  // Keep the purpose legal whenever the assay changes, rather than letting an
  // incompatible pairing sit in the form until the server rejects it.
  const permitted = useMemo(() => PERMITTED[subtype] ?? [], [subtype]);
  useEffect(() => {
    if (permitted.length > 0 && !permitted.includes(purpose)) {
      setPurpose(permitted[0]!);
    }
  }, [permitted, purpose]);

  const spec = SUBTYPE_FORMS[subtype];

  const handleCreate = async () => {
    if (!candidateVersionId || !title.trim()) return;
    setBusy(true);
    const result = await createExperiment({
      candidate_version_id: Number(candidateVersionId),
      subtype, purpose, title: title.trim(),
    });
    setBusy(false);
    if (result.status === 'error') { setError(result.error); return; }
    navigate(`/validation/experiments/${result.data.experiment_id}`);
  };

  /**
   * Create a candidate and immediately freeze its first version.
   *
   * One action rather than two, because a candidate with no version cannot be
   * experimented on — offering the intermediate state would let a user create
   * something the next step cannot use.
   *
   * The snapshot is taken from the *current session's* design values, which is
   * what makes the frozen version describe the formulation actually on screen
   * rather than an empty placeholder.
   */
  const handleCreateCandidate = async () => {
    if (studyId === null || !newCode.trim() || !newName.trim()) return;
    setBusy(true);
    const created = await createCandidate({
      study_id: studyId, code: newCode.trim(), name: newName.trim(),
    });
    if (created.status === 'error') {
      setBusy(false); setError(created.error); return;
    }
    const snapshot: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(session.values ?? {})) {
      if (String(value ?? '').trim() !== '') snapshot[key] = value;
    }
    const version = await createCandidateVersion(
      created.data.id, snapshot,
      versionNote.trim() || 'Frozen from the current design session.');
    setBusy(false);
    if (version.status === 'error') { setError(version.error); return; }

    const refreshed = await listCandidates(studyId);
    if (refreshed.status === 'ok') setCandidates(refreshed.data.candidates);
    setCandidateVersionId(String(version.data.id));
    setShowCreate(false);
    setNewCode(''); setNewName(''); setVersionNote('');
  };

  const versionOptions = (candidates ?? []).flatMap((candidate) =>
    candidate.versions.map((v) => ({
      value: String(v.id),
      label: `${candidate.code} — ${candidate.name} (version ${v.version_number})`,
    })));

  return (
    <>
      <PathwayBanner />
      <Card
        title="New in-vitro experiment"
        subtitle="Record an experiment against an exact candidate version. The candidate version and the scientific purpose are fixed once the record is created."
        accent
      >
        <Alert tone="info" role="note">
          <p data-testid="new-experiment-note">
            Creating this record grants nothing. It becomes evidence only if it
            passes every eligibility gate and is approved by a reviewer who did
            not perform the work — and then only for the purpose selected here,
            on the candidate version selected here.
          </p>
        </Alert>

        {studyId === null && (
          <Alert tone="warn" title="No study is open">
            <p data-testid="no-study">
              An experiment belongs to a candidate under a study. Open a study
              first — an experiment with no candidate cannot be attributed to
              any material.
            </p>
          </Alert>
        )}

        {candidates !== null && versionOptions.length === 0 && (
          <Alert tone="warn" title="No candidate version">
            <p data-testid="no-candidate-version">
              This study has no frozen candidate version. A candidate version is
              an immutable snapshot of the formulation; without one, a result
              could not be tied to the material that was tested. Create one
              below.
            </p>
          </Alert>
        )}

        {/* ------------------------------------------- candidate creation */}
        {studyId !== null && (
          <div className="vr__guidance" data-testid="candidate-creation">
            {!showCreate ? (
              <Button variant="secondary" size="sm"
                      onClick={() => setShowCreate(true)}
                      data-testid="show-create-candidate">
                Create a candidate and freeze a version
              </Button>
            ) : (
              <>
                <p className="eyebrow">New candidate</p>
                <p className="vr__note">
                  The version is frozen from this session's design values as an
                  immutable snapshot with a checksum. Editing the design
                  afterwards creates a new version rather than changing this
                  one — which is what keeps a result attributable to the
                  material that was actually tested.
                </p>
                <div className="vr__form vr__form--inline">
                  <TextField id="cand-code" label="Candidate code" required
                             type="text" value={newCode}
                             onChange={(e) => setNewCode(e.target.value)}
                             placeholder="CAND-1" />
                  <TextField id="cand-name" label="Candidate name" required
                             type="text" value={newName}
                             onChange={(e) => setNewName(e.target.value)}
                             placeholder="Liposome A" />
                  <TextField id="cand-note" label="Version note" type="text"
                             value={versionNote}
                             onChange={(e) => setVersionNote(e.target.value)}
                             placeholder="Why this version exists" />
                  <Button onClick={handleCreateCandidate} loading={busy}
                          disabled={!newCode.trim() || !newName.trim()}
                          data-testid="create-candidate">
                    Create and freeze
                  </Button>
                  <Button variant="ghost" onClick={() => setShowCreate(false)}
                          data-testid="cancel-create-candidate">
                    Cancel
                  </Button>
                </div>
              </>
            )}
          </div>
        )}

        <div className="vr__form">
          <SelectField
            id="candidate-version" label="Candidate version" required
            value={candidateVersionId}
            onChange={(e) => setCandidateVersionId(e.target.value)}
            options={[{ value: '', label: 'Select a candidate version…' },
                      ...versionOptions]}
            help="Fixed once the experiment is created. A later correction creates a new version rather than re-pointing this one."
          />

          <SelectField
            id="subtype" label="In-vitro experiment subtype" required
            value={subtype}
            onChange={(e) => setSubtype(e.target.value as SubtypeId)}
            options={Object.entries(SUBTYPE_LABEL)
              .map(([v, l]) => ({ value: v, label: l }))}
            help="Determines which measurement fields apply. Each assay has its own form; there is no universal one."
          />

          <SelectField
            id="purpose" label="Scientific purpose this evidences" required
            value={purpose}
            onChange={(e) => setPurpose(e.target.value as PurposeId)}
            options={permitted.map((p) => ({ value: p, label: PURPOSE_LABEL[p] }))}
            help="Only purposes this assay can evidence are offered. An in-vitro measurement cannot evidence a purpose it does not observe."
          />

          <TextField
            id="title" label="Title" required type="text" value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="What this experiment set out to determine"
          />
        </div>

        <div className="vr__guidance" data-testid="subtype-guidance">
          <p className="eyebrow">{SUBTYPE_LABEL[subtype]}</p>
          <p>{spec.guidance}</p>
          {spec.endpoints.length > 0 && (
            <p className="vr__note">
              Default endpoints:{' '}
              {spec.endpoints.map((e) => e.name).join(', ')}. You may record
              others.
            </p>
          )}
        </div>

        {error && (
          <Alert tone="danger" title="Not created">
            <p data-testid="create-error">{error.message}</p>
            {error.detail && <p className="vr__note">{error.detail}</p>}
          </Alert>
        )}

        <div className="vr__actions">
          <Button variant="secondary" onClick={() => navigate('/validation')}>
            Cancel
          </Button>
          <Button onClick={handleCreate} loading={busy}
                  disabled={!candidateVersionId || !title.trim()}
                  data-testid="create-experiment"
                  iconRight={<Icon name="chevron-right" size={15} />}>
            Create draft
          </Button>
        </div>
      </Card>
    </>
  );
}
