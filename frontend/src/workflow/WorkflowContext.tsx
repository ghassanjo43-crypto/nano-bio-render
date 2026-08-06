/**
 * Design-session state for the three-stage scientific workflow.
 *
 * One connected, stateful session spans:
 *   Step 1  Disease & Therapeutic Selection
 *   Step 2  Nanoparticle Design Parameters
 *   Step 3  Review & Run Simulation
 *   →       Results & Scientific Assessments
 *
 * Every selection is preserved when moving forward or backward, and a draft can
 * be saved and resumed.
 *
 * Storage note
 * ------------
 * Drafts are kept in `localStorage`. This holds **design parameters only** —
 * disease/subtype/drug selections and formulation values. It never contains a
 * session token, password or any credential; authentication continues to rely
 * solely on the HttpOnly cookie, which JavaScript cannot read. Drafts are
 * browser-local and are NOT server-persisted, which the UI states plainly.
 */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react';
import type { DemoScenarioDetail, PKResult, ScoreResult } from '../api/types';
import type { StudyPathway } from '../shell/navigation';
import { fingerprint } from './useUnsavedChanges';
import { INITIAL_VALUES, type ChipValues, type FormValues }
  from '../pages/design/schema';
import { EMPTY_PK_PATHWAY, type PKPathwayState }
  from '../pages/workflow/pkPathway';
import { INITIAL_PK_VALUES, pkInputsComplete, type PKValues }
  from '../pages/workflow/pkSchema';

const DRAFT_KEY = 'nanobio.designDrafts.v1';
const ACTIVE_KEY = 'nanobio.activeDraftId.v1';

export interface TherapeuticSelection {
  disease: string;
  subtype: string;
  drug: string;
}

export interface DesignSession {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  selection: TherapeuticSelection;
  values: FormValues;
  chips: ChipValues;
  /**
   * Pharmacokinetic inputs, collected on Step 3 where the run happens —
   * mirroring the legacy simulation page, which gathered its own settings.
   * Every field starts blank: no kinetic value is assumed on the user's behalf.
   */
  pk: PKValues;
  /** Highest step the user has legitimately reached (1-based). */
  furthestStep: number;

  /**
   * How this study began. Recorded on the session and carried through to the
   * stored study, so a patient assessment, a research design and a
   * demonstration stay distinguishable everywhere studies are listed.
   *
   * It also decides which sidebar entry stays active during the shared
   * `/workflow/*` steps — the route alone cannot tell, because all three
   * pathways run the same four steps.
   */
  pathway: StudyPathway;

  /** The second-level research purpose, when the pathway is a research design. */
  researchPurpose?: string;

  /**
   * The project this study belongs to, when one is chosen.
   *
   * Carried on the session so it survives every step of the pathway. Without
   * it, a project selected early would be forgotten by the time the run is
   * saved, and the study would land unfiled.
   */
  projectId?: number | null;

  /**
   * The stored study this session corresponds to, once it has been saved.
   *
   * Needed by the Validation Registry, whose records hang off a study: an
   * experiment with no study cannot be attributed to a candidate, and a
   * candidate with no study belongs to nothing.
   */
  studyId?: number | null;

  /**
   * The formulation under consideration, by name.
   *
   * Distinct from `name`, which names the *study*. One study may examine
   * several candidate formulations in turn, and the header has to be able to
   * say which one is on screen — "study" and "candidate" answer different
   * questions and collapsing them loses the one the researcher needs.
   */
  candidateName?: string;

  /**
   * Provenance of a session loaded from a demonstration scenario.
   *
   * Present only on a demo working copy. It travels with the session so that a
   * run stored from it is recorded as demo-generated and can never be silently
   * presented as the user's own research work.
   *
   * The working copy is fully editable: changing a value here never touches the
   * template, which lives server-side and can be reloaded at any time.
   */
  demo?: {
    scenarioSlug: string;
    scenarioName: string;
    fixtureVersion: string;
  };
}

export const EMPTY_SELECTION: TherapeuticSelection = { disease: '', subtype: '', drug: '' };

function newSession(): DesignSession {
  const now = new Date().toISOString();
  return {
    id: `ds_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
    name: 'Untitled design',
    createdAt: now,
    updatedAt: now,
    selection: { ...EMPTY_SELECTION },
    values: { ...INITIAL_VALUES },
    chips: { surface_coating: [], functional_groups: [] },
    pk: { ...INITIAL_PK_VALUES },
    furthestStep: 1,
    pathway: 'research_design',
    projectId: null,
    studyId: null,
    candidateName: '',
  };
}

/**
 * Repair a session read from storage.
 *
 * Drafts saved before PK inputs existed have no `pk` key. Filling the gap with
 * blanks keeps those drafts loadable and, critically, leaves the simulation
 * un-runnable until the user supplies real values — an old draft must never
 * appear to carry kinetics it never had.
 */
function hydrate(session: DesignSession): DesignSession {
  return {
    ...session,
    values: { ...INITIAL_VALUES, ...(session.values ?? {}) },
    chips: { surface_coating: [], functional_groups: [], ...(session.chips ?? {}) },
    pk: { ...INITIAL_PK_VALUES, ...(session.pk ?? {}) },
    // Drafts saved before pathways existed default to a research design, which
    // is what they were: started from the workflow, not from a report or a demo.
    pathway: session.pathway ?? 'research_design',
    // Drafts predating project and candidate fields get explicit empties, so a
    // reloaded draft reads as "no project chosen" rather than as undefined
    // flowing into a comparison and reporting the study permanently dirty.
    projectId: session.projectId ?? null,
    studyId: session.studyId ?? null,
    candidateName: session.candidateName ?? '',
  };
}

/** The user-editable part of a session, as a comparable string. */
function fingerprintOf(session: DesignSession): string {
  return fingerprint({
    selection: session.selection,
    values: session.values,
    chips: session.chips,
    pk: session.pk,
    name: session.name,
    projectId: session.projectId ?? null,
    candidateName: session.candidateName ?? '',
  });
}

function readDrafts(): DesignSession[] {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? (parsed as DesignSession[]).map(hydrate)
      : [];
  } catch {
    return [];
  }
}

function writeDrafts(drafts: DesignSession[]): void {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(drafts));
  } catch {
    /* storage unavailable (private mode / quota) — drafts simply do not persist */
  }
}

/**
 * The session to open on load: the active draft when there is one.
 *
 * Extracted so the provider and the initial dirty fingerprint read exactly the
 * same session. Computing them separately let them disagree, which reported a
 * freshly restored draft as unsaved.
 */
function readActiveSession(): DesignSession {
  const drafts = readDrafts();
  let activeId: string | null = null;
  try { activeId = localStorage.getItem(ACTIVE_KEY); } catch { /* ignore */ }
  const active = drafts.find((d) => d.id === activeId);
  return active ? hydrate(active) : newSession();
}

interface WorkflowContextValue {
  session: DesignSession;
  /** Drafts actually stored in this browser. Never seeded with examples. */
  savedDrafts: DesignSession[];
  hasResumableSession: boolean;

  setSelection: (patch: Partial<TherapeuticSelection>) => void;
  setValue: (name: string, value: string) => void;
  setChips: (name: string, value: string[]) => void;
  setPkValue: (name: string, value: string) => void;
  setName: (name: string) => void;
  /** Name the formulation currently under consideration. */
  setCandidateName: (name: string) => void;
  /** File the study under a project, or `null` to unfile it. */
  setProjectId: (id: number | null) => void;
  /** Record which stored study this session became when it was saved. */
  setStudyId: (id: number | null) => void;

  /**
   * True when the session differs from the last save.
   *
   * Compared field by field against a snapshot, not by timestamp: `updatedAt`
   * moves on every keystroke and would report a study dirty immediately after
   * a save that changed nothing.
   */
  isDirty: boolean;
  /** Begin a study on a named pathway, discarding any unsaved session. */
  startStudy: (pathway: StudyPathway, researchPurpose?: string) => void;
  reachStep: (step: number) => void;

  saveDraft: () => void;
  startNew: () => void;
  loadDraft: (id: string) => boolean;
  deleteDraft: (id: string) => void;

  /**
   * Populate an isolated working copy from a demonstration scenario.
   *
   * Creates a NEW session id, so the scenario never overwrites work in
   * progress, and runs nothing — the user reviews Steps 1–3 and decides when to
   * calculate.
   */
  loadScenario: (detail: DemoScenarioDetail) => void;

  result: ScoreResult | null;
  setResult: (r: ScoreResult | null) => void;
  /** True once a real calculation has been run for the current inputs. */
  resultIsStale: boolean;

  /**
   * The pharmacokinetic outcome, held SEPARATELY from the design score. They
   * are different calculations; merging them into one result object would blur
   * a distinction the interface is required to keep visible.
   *
   * `null` means the simulation was not run — an honest absence, never an
   * empty or zeroed profile.
   */
  pkResult: PKResult | null;
  setPkResult: (r: PKResult | null) => void;

  step1Complete: boolean;
  step2Complete: boolean;
  /** True only when every scientifically required PK input is present and valid. */
  pkInputsReady: boolean;

  /**
   * Which PK execution path this study may use. Set by the route-aware panel
   * and read by both Step 3 and the Results page, so the review screen and the
   * results screen cannot disagree about whether a simulation was permitted.
   */
  pkPathway: PKPathwayState;
  setPkPathway: (next: PKPathwayState) => void;
}

const WorkflowContext = createContext<WorkflowContextValue | undefined>(undefined);

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [savedDrafts, setSavedDrafts] = useState<DesignSession[]>(() => readDrafts());
  const [session, setSession] = useState<DesignSession>(() => readActiveSession());
  const [result, setResultState] = useState<ScoreResult | null>(null);
  const [pkResult, setPkResultState] = useState<PKResult | null>(null);
  const [resultInputsHash, setResultInputsHash] = useState<string | null>(null);

  /**
   * Fingerprint of the session as it stood at the last save.
   *
   * A session restored from storage is by definition already saved, so it
   * starts clean — otherwise every page load would greet the user with an
   * unsaved-changes warning about work they had already saved.
   */
  const [savedFingerprint, setSavedFingerprint] = useState<string>(
    () => fingerprintOf(readActiveSession()),
  );

  useEffect(() => {
    try { localStorage.setItem(ACTIVE_KEY, session.id); } catch { /* ignore */ }
  }, [session.id]);

  const inputsHash = useMemo(
    () => JSON.stringify([session.selection, session.values, session.chips,
                          session.pk]),
    [session.selection, session.values, session.chips, session.pk],
  );

  const touch = useCallback((patch: Partial<DesignSession>) => {
    setSession((prev) => ({ ...prev, ...patch, updatedAt: new Date().toISOString() }));
  }, []);

  const setSelection = useCallback((patch: Partial<TherapeuticSelection>) => {
    setSession((prev) => {
      const selection = { ...prev.selection, ...patch };
      // Changing a parent invalidates its children, so the user can never carry
      // a drug that does not belong to the selected subtype.
      //
      // A child is cleared ONLY when the caller did not supply it. Without that
      // condition, setting a complete triple in one call (as the Medical Report
      // Assessment pathway does when carrying a confirmed context forward)
      // wiped the subtype and drug it had just been given, and Step 1 arrived
      // half-populated.
      if (patch.disease !== undefined
          && patch.disease !== prev.selection.disease) {
        if (patch.subtype === undefined) selection.subtype = '';
        if (patch.drug === undefined) selection.drug = '';
      }
      if (patch.subtype !== undefined
          && patch.subtype !== prev.selection.subtype
          && patch.drug === undefined) {
        selection.drug = '';
      }
      return { ...prev, selection, updatedAt: new Date().toISOString() };
    });
  }, []);

  const setValue = useCallback((name: string, value: string) => {
    setSession((prev) => ({
      ...prev,
      values: { ...prev.values, [name]: value },
      updatedAt: new Date().toISOString(),
    }));
  }, []);

  const setChips = useCallback((name: string, value: string[]) => {
    setSession((prev) => ({
      ...prev,
      chips: { ...prev.chips, [name]: value },
      updatedAt: new Date().toISOString(),
    }));
  }, []);

  const setPkValue = useCallback((name: string, value: string) => {
    setSession((prev) => ({
      ...prev,
      pk: { ...prev.pk, [name]: value },
      updatedAt: new Date().toISOString(),
    }));
  }, []);

  const setName = useCallback((name: string) => touch({ name }), [touch]);

  const setCandidateName = useCallback(
    (candidateName: string) => touch({ candidateName }), [touch]);

  const setProjectId = useCallback(
    (projectId: number | null) => touch({ projectId }), [touch]);

  const setStudyId = useCallback(
    (studyId: number | null) => touch({ studyId }), [touch]);

  const reachStep = useCallback((step: number) => {
    setSession((prev) => (step > prev.furthestStep
      ? { ...prev, furthestStep: step, updatedAt: new Date().toISOString() }
      : prev));
  }, []);

  const saveDraft = useCallback(() => {
    setSession((prev) => {
      const saved: DesignSession = { ...prev, updatedAt: new Date().toISOString() };
      setSavedDrafts((drafts) => {
        const next = [saved, ...drafts.filter((d) => d.id !== saved.id)];
        writeDrafts(next);
        return next;
      });
      // The study is now clean. Recorded from the session actually written, so
      // the two cannot disagree.
      setSavedFingerprint(fingerprintOf(saved));
      return saved;
    });
  }, []);

  const startNew = useCallback(() => {
    const fresh = newSession();
    setSession(fresh);
    setSavedFingerprint(fingerprintOf(fresh));
    setResultState(null);
    setPkResultState(null);
    setResultInputsHash(null);
  }, []);

  const startStudy = useCallback((pathway: StudyPathway,
                                  researchPurpose?: string) => {
    const fresh = { ...newSession(), pathway, researchPurpose };
    setSession(fresh);
    // A brand-new study has nothing to lose, so it starts clean. Otherwise
    // choosing a pathway would immediately arm the unsaved-changes warning.
    setSavedFingerprint(fingerprintOf(fresh));
    setResultState(null);
    setPkResultState(null);
    setResultInputsHash(null);
  }, []);

  const loadDraft = useCallback((id: string) => {
    const found = readDrafts().find((d) => d.id === id);
    if (!found) return false;
    const loaded = hydrate(found);
    setSession(loaded);
    setSavedFingerprint(fingerprintOf(loaded));
    // Results belong to the run that produced them, not to the inputs. Loading
    // a draft clears both, so no earlier profile can be shown beside newly
    // loaded parameters.
    setResultState(null);
    setPkResultState(null);
    setResultInputsHash(null);
    return true;
  }, []);

  const deleteDraft = useCallback((id: string) => {
    setSavedDrafts((drafts) => {
      const next = drafts.filter((d) => d.id !== id);
      writeDrafts(next);
      return next;
    });
  }, []);

  /**
   * Build an isolated working copy from a scenario template.
   *
   * Values are stringified for the form layer. A field the scenario omits is
   * left BLANK rather than defaulted, which is what makes the deliberately
   * incomplete scenario genuinely block execution instead of quietly running on
   * substituted values.
   */
  const loadScenario = useCallback((detail: DemoScenarioDetail) => {
    const values: FormValues = { ...INITIAL_VALUES };
    for (const key of Object.keys(values)) values[key] = '';
    const chips: ChipValues = { surface_coating: [], functional_groups: [] };

    for (const [key, raw] of Object.entries(detail.design_inputs)) {
      if (raw === null || raw === undefined) continue;
      if (Array.isArray(raw)) {
        chips[key] = raw.map(String);
      } else {
        values[key] = String(raw);
      }
    }

    const pk: PKValues = { ...INITIAL_PK_VALUES };
    for (const key of Object.keys(pk)) pk[key] = '';
    for (const [key, raw] of Object.entries(detail.pk_inputs)) {
      if (raw === null || raw === undefined) continue;
      pk[key] = String(raw);
    }

    const now = new Date().toISOString();
    const loaded: DesignSession = {
      ...newSession(),
      name: detail.name,
      createdAt: now,
      updatedAt: now,
      selection: {
        disease: detail.disease,
        subtype: detail.subtype,
        drug: detail.drug,
      },
      values,
      chips,
      pk,
      // Steps 1 and 2 are populated, so the user may move straight to review —
      // but every value remains editable and the ordinary validation applies.
      furthestStep: 3,
      // A loaded scenario is a demonstration study, whatever it is edited into.
      pathway: 'demo_scenario',
      demo: {
        scenarioSlug: detail.slug,
        scenarioName: detail.name,
        fixtureVersion: detail.fixture_version,
      },
    };
    setSession(loaded);
    // A scenario just loaded from the server matches what is on the server, so
    // it is clean until the user edits it.
    setSavedFingerprint(fingerprintOf(loaded));
    // A freshly loaded scenario has no results. Carrying a previous run's
    // output alongside new inputs would misattribute it.
    setResultState(null);
    setPkResultState(null);
    setResultInputsHash(null);
  }, []);

  const setResult = useCallback((r: ScoreResult | null) => {
    setResultState(r);
    setResultInputsHash(r ? inputsHash : null);
  }, [inputsHash]);

  const setPkResult = useCallback((r: PKResult | null) => {
    setPkResultState(r);
  }, []);

  const step1Complete = Boolean(
    session.selection.disease && session.selection.subtype && session.selection.drug,
  );
  const step2Complete = step1Complete && Boolean(
    (session.values.size_nm ?? '').trim()
    && (session.values.charge_mv ?? '').trim()
    && (session.values.encapsulation_percent ?? '').trim(),
  );

  // Gates execution of the PK model. Deliberately independent of
  // step1/step2 completeness: the design score and the simulation are separate
  // calculations, and one may run without the other.
  const pkInputsReady = pkInputsComplete(session.pk);

  // Deliberately component state rather than part of the persisted draft: the
  // plan is derived from the live parameter library, and a stale cached plan
  // could claim a reviewed set exists after one was withdrawn.
  const [pkPathway, setPkPathway] = useState<PKPathwayState>(EMPTY_PK_PATHWAY);

  const hasResumableSession = Boolean(
    session.selection.disease || session.furthestStep > 1 || savedDrafts.length > 0,
  );

  const isDirty = fingerprintOf(session) !== savedFingerprint;

  const value = useMemo<WorkflowContextValue>(() => ({
    session, savedDrafts, hasResumableSession,
    setSelection, setValue, setChips, setPkValue, setName,
    setCandidateName, setProjectId, setStudyId, isDirty, reachStep,
    saveDraft, startNew, startStudy, loadDraft, deleteDraft, loadScenario,
    result, setResult,
    resultIsStale: result !== null && resultInputsHash !== inputsHash,
    pkResult, setPkResult,
    step1Complete, step2Complete, pkInputsReady,
    pkPathway, setPkPathway,
  }), [session, savedDrafts, hasResumableSession, setSelection, setValue, setChips,
       setPkValue, setName, setCandidateName, setProjectId, setStudyId,
       isDirty, reachStep,
       saveDraft, startNew, startStudy,
       loadDraft, deleteDraft, loadScenario, result, setResult, pkResult, setPkResult, resultInputsHash,
       inputsHash, step1Complete, step2Complete, pkInputsReady, pkPathway]);

  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>;
}

export function useWorkflow(): WorkflowContextValue {
  const ctx = useContext(WorkflowContext);
  if (!ctx) throw new Error('useWorkflow must be used inside a WorkflowProvider');
  return ctx;
}
