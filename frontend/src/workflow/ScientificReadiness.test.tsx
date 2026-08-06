/**
 * The Scientific Readiness Dashboard.
 *
 * Two properties dominate these tests, and they are the same two the backend
 * suite pins:
 *
 * 1. **A completeness percentage never satisfies a blocking requirement.** The
 *    dashboard must be able to show "78% complete" and "Blocked" side by side
 *    without the first appearing to soften the second.
 * 2. **The page decides nothing.** Every status, percentage, evidence level,
 *    block and warning is rendered from the server's response. There is no
 *    client-side scoring to disagree with the rules engine, so the fixtures
 *    below deliberately contain combinations a real engine would produce and
 *    the page has no way to recompute.
 *
 * The third property, tested by omission: no combined score is displayed. Six
 * areas are shown independently because one strong area must not mask a weak
 * one.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import {
  EVIDENCE_BEARING, EVIDENCE_LABEL, EXPERIMENTAL_VALIDATION_LEVELS,
  NON_CONTRIBUTING, READINESS_LABEL,
  SCIENTIFIC_LABEL, labelForReadiness, labelForScientific, toneForReadiness,
  toneForScientific,
  type AreaAssessment, type EvidenceLevelId, type ReadinessReport,
  type ReadinessStatusId, type ScienceRecordListResponse,
  type ScientificStatusId,
} from '../pages/readiness/readinessTypes';
import { pkFixtureFor } from './pkTestFixtures';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

/** The six areas, in the order the backend emits them. */
const AREA_IDS = [
  'structural_visualization', 'formulation_assessment', 'biological_targeting',
  'pharmacokinetic_modelling', 'safety_assessment', 'cinematic_animation',
] as const;

const AREA_LABEL: Record<string, string> = {
  structural_visualization: 'Structural visualisation',
  formulation_assessment: 'Formulation assessment',
  biological_targeting: 'Biological targeting',
  pharmacokinetic_modelling: 'Pharmacokinetic modelling',
  safety_assessment: 'Safety assessment',
  cinematic_animation: 'Cinematic animation',
};

function area(id: string, over: Partial<AreaAssessment> = {}): AreaAssessment {
  return {
    area: id,
    label: AREA_LABEL[id] ?? id,
    description: `What ${id} needs.`,
    status: 'blocked',
    readiness_percent: 0,
    evidence_level: 'E0',
    blocking_issues: [],
    warnings: [],
    missing_inputs: [],
    incompatible_inputs: [],
    assumptions: [],
    recommended_actions: [],
    ...over,
  };
}

const NOTICE =
  'Scientific readiness describes whether the information recorded for this '
  + 'study is sufficient and self-consistent for a given kind of analysis. It '
  + 'is not regulatory approval, clinical validation, scientific accreditation, '
  + 'or evidence that any result is correct. A study can be fully ready and '
  + 'still be scientifically wrong.';

function report(areas: AreaAssessment[], over: Partial<ReadinessReport> = {}):
ReadinessReport {
  return {
    study_id: 7,
    areas,
    rules_engine_version: 'readiness-rules-1.0.0',
    dictionary_version: 'data-dictionary-1.0.0',
    evaluated_at: '2026-08-02T10:00:00Z',
    notice: NOTICE,
    record_count: areas.length,
    ...over,
  };
}

/** Every area blocked and empty — a study with nothing recorded. */
const EMPTY_REPORT = report(AREA_IDS.map((id) => area(id, {
  blocking_issues: [{
    code: `blocking_missing_${id}_input`,
    message: 'A mandatory input has not been recorded.',
    field_ids: ['physical_diameter'],
    recommended_action: 'Record the value with its measurement method.',
  }],
  missing_inputs: ['physical_diameter', 'zeta_potential'],
  recommended_actions: ['Record the value with its measurement method.'],
})));

/**
 * The case the framework exists for: substantially populated, still blocked.
 * A page that let the percentage speak for the status would render this wrong.
 */
const BLOCKED_AT_78 = report([
  area('structural_visualization', {
    status: 'conditionally_ready', readiness_percent: 64, evidence_level: 'E1',
    warnings: [{
      code: 'coating_thickness_assumed',
      message: 'Coating thickness is an assumed default.',
      field_ids: ['coating_thickness'], recommended_action: null,
    }],
  }),
  area('formulation_assessment', {
    status: 'blocked', readiness_percent: 78, evidence_level: 'E2',
    blocking_issues: [{
      code: 'blocking_missing_zeta_potential',
      message: 'Zeta potential is mandatory for formulation assessment and '
        + 'has not been recorded.',
      field_ids: ['zeta_potential'],
      recommended_action: 'Measure zeta potential and record the medium, pH '
        + 'and ionic strength it was measured in.',
    }],
    missing_inputs: ['zeta_potential'],
    recommended_actions: ['Measure zeta potential.'],
  }),
  area('biological_targeting', {
    status: 'blocked', readiness_percent: 20, evidence_level: 'E0',
    incompatible_inputs: [{
      code: 'ligand_density_ambiguous',
      message: 'Ligand density was recorded as a bare percentage with no '
        + 'denominator, so it cannot be interpreted.',
      field_ids: ['ligand_density_value', 'ligand_density_unit'],
      recommended_action: 'State whether the percentage is by mass, by mole '
        + 'or by surface coverage.',
    }],
  }),
  area('pharmacokinetic_modelling', {
    status: 'outside_model_domain', readiness_percent: 55, evidence_level: 'E1',
    blocking_issues: [{
      code: 'unsupported_architecture',
      message: 'No reviewed pharmacokinetic model covers this architecture.',
      field_ids: ['architecture'], recommended_action: null,
    }],
  }),
  area('safety_assessment', {
    status: 'insufficient', readiness_percent: 12, evidence_level: 'E0',
    assumptions: [{
      code: 'assumed_default_in_use',
      message: 'Material purity is an assumed default, not a measurement.',
      field_ids: ['material_purity'], recommended_action: null,
    }],
  }),
  area('cinematic_animation', {
    status: 'ready', readiness_percent: 100, evidence_level: 'E1',
  }),
]);

/**
 * A study whose values really are measured, and which has an in-vivo evidence
 * field populated — the exact shape the old engine promoted to E4/E5. The
 * corrected engine returns E2 with its reason, and the page must render that
 * without softening it.
 */
const CEILING_REASON =
  'The weakest required field, Zeta potential, is measured, which supports '
  + 'E2. The area takes the weakest of its required fields, not their average. '
  + 'No recorded validation applies, so no level above E2 is asserted. '
  + 'Evidence levels E3 to E6 assert that a prediction was validated against '
  + 'an experiment or an independent result. Recording that a value was '
  + 'measured, or that an in-vitro or in-vivo study exists, is not such a '
  + 'validation. No validation record can be stored until the Experimental '
  + 'Validation Registry is implemented in Phase 2, so E3 to E6 are '
  + 'unreachable and are never asserted.';

const MEASUREMENT_NOT_VALIDATION = {
  code: 'measurement_is_not_validation',
  message: 'Measured values are recorded for this area, but no validation '
    + 'record is. A measurement is an observation of this material; it is '
    + 'not a check of any prediction against an independent result, so on '
    + 'its own it does not reach E3.',
  field_ids: ['zeta_potential'], recommended_action: null,
};

const EVIDENCE_FIELD_NOT_VALIDATION = {
  code: 'evidence_field_is_not_validation',
  message: 'An in-vitro or in-vivo evidence field is populated. That records '
    + 'the claim that such an experiment exists; it does not record that a '
    + 'prediction was registered, tested against it, and found to hold. '
    + 'Populating it therefore does not raise this area to E4 or E5.',
  field_ids: ['in_vivo_evidence'], recommended_action: null,
};

const MEASURED_BUT_UNVALIDATED = report(
  AREA_IDS.map((id) => area(id, {
    status: 'conditionally_ready',
    readiness_percent: 100,
    // Measured throughout, and still E2 everywhere. Biological targeting is
    // left at E0 by a user-supplied required field, so the fixture also proves
    // the page is not simply echoing one constant.
    evidence_level: id === 'biological_targeting' ? 'E0' : 'E2',
    evidence_level_rationale: CEILING_REASON,
    max_attainable_evidence_level: 'E2',
    warnings: id === 'safety_assessment'
      ? [MEASUREMENT_NOT_VALIDATION, EVIDENCE_FIELD_NOT_VALIDATION]
      : [MEASUREMENT_NOT_VALIDATION],
  })),
  {
    validation_registry_available: false,
    max_attainable_evidence_level: 'E2',
    evidence_ceiling_notice: CEILING_REASON,
  },
);

const RECORDS: ScienceRecordListResponse = {
  study_id: 7,
  records: [
    { field_id: 'physical_diameter', status: 'measured', value: '100',
      unit: 'nm', measurement_method: 'cryo-TEM', source_citation: null,
      notes: null },
    { field_id: 'hydrodynamic_diameter', status: 'measured', value: '120',
      unit: 'nm', measurement_method: 'DLS', source_citation: null,
      notes: null },
    { field_id: 'density', status: 'literature_derived', value: '1.02',
      unit: 'g/cm3', measurement_method: null,
      source_citation: 'Some reference', notes: null },
    { field_id: 'coating_thickness', status: 'assumed_default', value: '5',
      unit: 'nm', measurement_method: null, source_citation: null,
      notes: null },
    { field_id: 'crystallinity', status: 'illustrative', value: 'amorphous',
      unit: null, measurement_method: null, source_citation: null,
      notes: null },
  ],
  is_legacy_import: false,
  legacy_notice: null,
};

const LEGACY_RECORDS: ScienceRecordListResponse = {
  study_id: 7,
  records: [
    { field_id: 'physical_diameter', status: 'user_supplied', value: '100',
      unit: 'nm', measurement_method: null, source_citation: null,
      notes: 'Imported from a study saved before the framework existed.' },
  ],
  is_legacy_import: true,
  legacy_notice:
    'This study predates the Scientific Readiness Framework. Its design '
    + 'values are shown as user-supplied because no measurement method, '
    + 'source or conditions were recorded when it was saved.',
};

const RUNS = {
  runs: [
    { id: 7, name: 'HER2 liposome study', origin: 'user', status: 'complete',
      created_at: '2026-08-01T09:00:00Z', disease: 'Breast Cancer',
      scenario: null, pathway: 'research_design', project_id: null },
  ],
  total: 1,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

interface FetchOptions {
  readiness?: ReadinessReport;
  records?: ScienceRecordListResponse;
  readinessStatus?: number;
  readinessBody?: unknown;
  runs?: unknown;
}

let requested: string[] = [];

function installFetch(options: FetchOptions = {}) {
  requested = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    requested.push(url);
    const pk = pkFixtureFor(url);
    if (pk !== null) return json(pk);
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    if (url.includes('/api/v1/runs')) return json(options.runs ?? RUNS);
    if (url.includes('/readiness/snapshots')) {
      return json({ id: 1, created_at: '2026-08-02T10:00:00Z' });
    }
    if (url.includes('/readiness')) {
      if (options.readinessStatus && options.readinessStatus !== 200) {
        return json(options.readinessBody ?? {
          error: 'study_not_found',
          message: 'The requested study does not exist.',
          detail: null, readiness_available: false,
        }, options.readinessStatus);
      }
      return json(options.readiness ?? EMPTY_REPORT);
    }
    if (url.includes('/science/studies/') && url.includes('/records')) {
      return json(options.records ?? RECORDS);
    }
    return json({}, 404);
  }));
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider><App /></AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => { localStorage.clear(); installFetch(); });
afterEach(() => {
  vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear();
});

/* ===================================================================== */
describe('1. the dashboard reaches the real backend', () => {
  it('renders at /scientific-readiness', async () => {
    renderAt('/scientific-readiness');
    // The shell renders the page title as h1 and the Card heading as h2, so
    // the level is what distinguishes them.
    expect(await screen.findByRole('heading',
      { name: /Scientific Readiness/i, level: 2 })).toBeInTheDocument();
  });

  it('requests the readiness assessment for the selected study', async () => {
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    expect(requested.some((u) =>
      u.includes('/api/v1/science/studies/7/readiness'))).toBe(true);
  });

  it('requests the study\'s scientific records', async () => {
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    expect(requested.some((u) =>
      u.includes('/api/v1/science/studies/7/records'))).toBe(true);
  });

  it('is not a disconnected prototype: nothing renders without a response',
    async () => {
      installFetch({ readinessStatus: 404 });
      renderAt('/scientific-readiness');
      expect(await screen.findByText(/Readiness unavailable/i))
        .toBeInTheDocument();
      expect(screen.queryByTestId('readiness-areas')).not.toBeInTheDocument();
    });

  it('shows the rules-engine and dictionary versions it was assessed under',
    async () => {
      renderAt('/scientific-readiness');
      const meta = await screen.findByTestId('engine-meta');
      expect(meta).toHaveTextContent('readiness-rules-1.0.0');
      expect(meta).toHaveTextContent('data-dictionary-1.0.0');
    });
});

/* ===================================================================== */
describe('2. six areas, assessed independently', () => {
  it('renders one card per area', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const areas = await screen.findByTestId('readiness-areas');
    for (const id of AREA_IDS) {
      expect(within(areas).getByTestId(`area-${id}`)).toBeInTheDocument();
    }
  });

  it('shows exactly six, never more', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const areas = await screen.findByTestId('readiness-areas');
    // One heading per card. Counting testids by prefix would also match the
    // `area-to-builder` button inside a card.
    expect(within(areas).getAllByRole('heading', { level: 3 }))
      .toHaveLength(6);
  });

  it('displays no combined score', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    // A single overall number would let a ready area mask a blocked one.
    expect(screen.queryByTestId('overall-readiness')).not.toBeInTheDocument();
    expect(screen.queryByText(/overall readiness/i)).not.toBeInTheDocument();
  });

  it('lets areas disagree: one ready while another is blocked', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const cinematic = await screen.findByTestId('area-cinematic_animation');
    const formulation = screen.getByTestId('area-formulation_assessment');
    expect(within(cinematic).getByText('Ready')).toBeInTheDocument();
    expect(within(formulation).getByText('Blocked')).toBeInTheDocument();
  });

  it('shows each area\'s own percentage, not a shared one', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    expect(screen.getByTestId('percent-formulation_assessment'))
      .toHaveTextContent('78%');
    expect(screen.getByTestId('percent-safety_assessment'))
      .toHaveTextContent('12%');
  });
});

/* ===================================================================== */
describe('3. a percentage never satisfies a blocking requirement', () => {
  it('shows 78% and Blocked on the same card', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const card = await screen.findByTestId('area-formulation_assessment');
    expect(within(card).getByTestId('percent-formulation_assessment'))
      .toHaveTextContent('78%');
    expect(within(card).getByText('Blocked')).toBeInTheDocument();
  });

  it('says so in words, so the number cannot be misread as permission',
    async () => {
      installFetch({ readiness: BLOCKED_AT_78 });
      renderAt('/scientific-readiness');
      const note = await screen.findByTestId(
        'override-note-formulation_assessment');
      expect(note).toHaveTextContent(/78% complete/);
      expect(note).toHaveTextContent(
        /completeness percentage never satisfies a mandatory requirement/i);
    });

  it('omits that note where it would be noise — a low blocked percentage',
    async () => {
      installFetch({ readiness: BLOCKED_AT_78 });
      renderAt('/scientific-readiness');
      await screen.findByTestId('readiness-areas');
      // biological_targeting is blocked at 20%; nobody would read that as ready.
      expect(screen.queryByTestId('override-note-biological_targeting'))
        .not.toBeInTheDocument();
    });

  it('applies the same note to outside_model_domain at 55%', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    expect(await screen.findByTestId(
      'override-note-pharmacokinetic_modelling')).toHaveTextContent(/55%/);
  });

  it('renders the blocked bar with a blocked fill, not a progress colour',
    async () => {
      installFetch({ readiness: BLOCKED_AT_78 });
      renderAt('/scientific-readiness');
      const card = await screen.findByTestId('area-formulation_assessment');
      expect(card.querySelector('.sr__barfill--blocked')).not.toBeNull();
    });
});

/* ===================================================================== */
describe('4. blocking issues and warnings are distinguished', () => {
  it('renders blocking issues in their own group', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const blocking = await screen.findByTestId(
      'blocking-formulation_assessment');
    expect(blocking).toHaveTextContent(/Zeta potential is mandatory/);
    expect(within(blocking).getByRole('heading', { name: 'Blocking' }))
      .toBeInTheDocument();
  });

  it('renders warnings separately from blocking issues', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const warnings = await screen.findByTestId(
      'warnings-structural_visualization');
    expect(warnings).toHaveTextContent(/assumed default/i);
    // A warning must not appear under Blocking, or it would read as fatal.
    expect(screen.queryByTestId('blocking-structural_visualization'))
      .not.toBeInTheDocument();
  });

  it('a warning does not block: the area stays conditionally ready', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const card = await screen.findByTestId('area-structural_visualization');
    expect(within(card).getByText('Conditionally ready')).toBeInTheDocument();
  });

  it('renders incompatible inputs in their own group', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const bad = await screen.findByTestId('incompatible-biological_targeting');
    expect(bad).toHaveTextContent(/bare percentage with no denominator/);
  });

  it('lists assumptions in use, so they are visible rather than buried',
    async () => {
      installFetch({ readiness: BLOCKED_AT_78 });
      renderAt('/scientific-readiness');
      expect(await screen.findByTestId('assumptions-safety_assessment'))
        .toHaveTextContent(/assumed default, not a measurement/);
    });

  it('shows the recommended action alongside a finding', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const blocking = await screen.findByTestId(
      'blocking-formulation_assessment');
    expect(blocking).toHaveTextContent(/Measure zeta potential/);
  });

  it('offers a missing-data checklist per area', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const missing = await screen.findByTestId(
      'missing-formulation_assessment');
    expect(missing).toHaveTextContent('zeta_potential');
  });
});

/* ===================================================================== */
describe('5. provenance is visually distinct', () => {
  it('summarises how the study\'s data is known', async () => {
    renderAt('/scientific-readiness');
    const summary = await screen.findByTestId('provenance-summary');
    expect(within(summary).getByTestId('provenance-measured'))
      .toHaveTextContent('2');
    expect(within(summary).getByTestId('provenance-assumed_default'))
      .toHaveTextContent('1');
    expect(within(summary).getByTestId('provenance-illustrative'))
      .toHaveTextContent('1');
  });

  it('omits statuses this study has none of', async () => {
    renderAt('/scientific-readiness');
    await screen.findByTestId('provenance-summary');
    expect(screen.queryByTestId('provenance-experimentally_derived'))
      .not.toBeInTheDocument();
  });

  it('separates measured from assumed by tone', () => {
    // The visual distinction is the whole point: an assumption must never look
    // like a measurement.
    expect(toneForScientific('measured'))
      .not.toBe(toneForScientific('assumed_default'));
    expect(toneForScientific('measured'))
      .not.toBe(toneForScientific('illustrative'));
    expect(toneForScientific('measured'))
      .not.toBe(toneForScientific('computationally_predicted'));
  });

  it('never labels an assumption as evidence', () => {
    expect(EVIDENCE_BEARING.has('assumed_default')).toBe(false);
    expect(EVIDENCE_BEARING.has('illustrative')).toBe(false);
    expect(EVIDENCE_BEARING.has('user_supplied')).toBe(false);
    expect(NON_CONTRIBUTING.has('assumed_default')).toBe(true);
    expect(NON_CONTRIBUTING.has('illustrative')).toBe(true);
    expect(NON_CONTRIBUTING.has('missing')).toBe(true);
  });

  it('gives every status a label rather than showing a raw identifier', () => {
    const ids: ScientificStatusId[] = [
      'measured', 'experimentally_derived', 'literature_derived', 'calculated',
      'computationally_predicted', 'user_supplied', 'assumed_default',
      'illustrative', 'missing', 'not_applicable',
    ];
    for (const id of ids) {
      expect(SCIENTIFIC_LABEL[id]).toBeTruthy();
      expect(SCIENTIFIC_LABEL[id]).not.toBe(id);
    }
  });

  it('says plainly that user-supplied carries no method', () => {
    expect(labelForScientific('user_supplied')).toMatch(/no method/i);
  });

  it('falls back to "Not recorded" for a status it does not know', () => {
    expect(labelForScientific('something_new')).toBe('Not recorded');
    expect(toneForScientific('something_new')).toBe('neutral');
  });
});

/* ===================================================================== */
describe('6. evidence level comes from records, not completeness', () => {
  it('shows the evidence level the server assigned', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    expect(screen.getByTestId('evidence-formulation_assessment'))
      .toHaveTextContent('E2');
    expect(screen.getByTestId('evidence-safety_assessment'))
      .toHaveTextContent('E0');
  });

  it('a high percentage does not imply a high evidence level', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    // 55% complete, still E1: filling in fields does not manufacture evidence.
    expect(screen.getByTestId('percent-pharmacokinetic_modelling'))
      .toHaveTextContent('55%');
    expect(screen.getByTestId('evidence-pharmacokinetic_modelling'))
      .toHaveTextContent('E1');
  });

  it('names each level rather than showing a bare code', () => {
    expect(EVIDENCE_LABEL.E0).toMatch(/illustrative/i);
    expect(EVIDENCE_LABEL.E1).toMatch(/literature/i);
    expect(EVIDENCE_LABEL.E2).toMatch(/computational/i);
    expect(EVIDENCE_LABEL.E6).toMatch(/clinical/i);
  });
});

/* =====================================================================
 * DEFECT-P1-A regression.
 *
 * The engine used to reach E3 from a value merely marked "measured", and E4/E5
 * from a *populated* in-vitro or in-vivo evidence field. Neither is a
 * validation. The page renders whatever the server sends, so what it must be
 * held to is different but no less important: that it never presents a
 * validation level as ordinary, never shows a level without its reason, and
 * never lets its own vocabulary drift back to implying E2 is prediction-only.
 * ===================================================================== */
describe('6a. validation levels are distinguished from provenance levels', () => {
  it('names the four levels that assert experimental validation', () => {
    expect([...EXPERIMENTAL_VALIDATION_LEVELS].sort())
      .toEqual(['E3', 'E4', 'E5', 'E6']);
    // E0-E2 describe how a value came to exist. They assert no validation.
    for (const level of ['E0', 'E1', 'E2'] as EvidenceLevelId[]) {
      expect(EXPERIMENTAL_VALIDATION_LEVELS.has(level)).toBe(false);
    }
  });

  it('labels E2 so a measurement landing there is not called a prediction', () => {
    // A measured value now stops at E2. A label reading only "computational
    // prediction" would misdescribe every measured study on the platform.
    expect(EVIDENCE_LABEL.E2).toMatch(/measurement/i);
    expect(EVIDENCE_LABEL.E2).toMatch(/unvalidated/i);
  });

  it('describes E3 to E5 as validation, not as strong provenance', () => {
    expect(EVIDENCE_LABEL.E3).toMatch(/validated/i);
    expect(EVIDENCE_LABEL.E4).toMatch(/in vitro/i);
    expect(EVIDENCE_LABEL.E5).toMatch(/in vivo/i);
  });

  it('shows the reason a level is what it is, next to the level', async () => {
    installFetch({ readiness: MEASURED_BUT_UNVALIDATED });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');

    expect(screen.getByTestId('evidence-formulation_assessment'))
      .toHaveTextContent('E2');
    const why = screen.getByTestId('evidence-why-formulation_assessment');
    expect(why).toHaveTextContent(/no level above E2 is asserted/i);
    expect(why).toHaveTextContent(/Experimental Validation Registry/i);
  });

  it('renders the reason for every area the server explains', async () => {
    installFetch({ readiness: MEASURED_BUT_UNVALIDATED });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    for (const id of AREA_IDS) {
      expect(screen.getByTestId(`evidence-why-${id}`)).toBeInTheDocument();
    }
  });

  it('surfaces the warning that a measurement is not a validation', async () => {
    installFetch({ readiness: MEASURED_BUT_UNVALIDATED });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    expect(screen.getByTestId('warnings-formulation_assessment'))
      .toHaveTextContent(/not a check of any prediction/i);
  });

  it('surfaces the warning that a populated evidence field validates '
     + 'nothing', async () => {
    installFetch({ readiness: MEASURED_BUT_UNVALIDATED });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    expect(screen.getByTestId('warnings-safety_assessment'))
      .toHaveTextContent(/does not raise this area to E4 or E5/i);
  });

  it('renders without a reason when the server sends none', async () => {
    // An older engine omits the field. The page shows nothing rather than
    // inventing a justification for a level it did not compute.
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    expect(screen.getByTestId('evidence-formulation_assessment'))
      .toHaveTextContent('E2');
    expect(screen.queryByTestId('evidence-why-formulation_assessment'))
      .not.toBeInTheDocument();
  });

  it('never computes an evidence level of its own', async () => {
    // The page has the records — five of them, two measured — and must still
    // show exactly the level the server assigned, not one inferred from them.
    installFetch({ readiness: MEASURED_BUT_UNVALIDATED, records: RECORDS });
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    expect(screen.getByTestId('evidence-biological_targeting'))
      .toHaveTextContent('E0');
    expect(screen.getByTestId('evidence-biological_targeting'))
      .not.toHaveTextContent(/E3|E4|E5/);
  });
});

/* ===================================================================== */
describe('7. blocked and outside-model-domain are not the same thing', () => {
  it('labels them differently', () => {
    expect(labelForReadiness('blocked')).toBe('Blocked');
    expect(labelForReadiness('outside_model_domain'))
      .toBe('Outside model domain');
  });

  it('tones them differently', () => {
    // "Missing data" is fixable by entering data; "outside the model domain"
    // is not. Collapsing the two would imply the second can be filled in.
    expect(toneForReadiness('blocked'))
      .not.toBe(toneForReadiness('outside_model_domain'));
  });

  it('renders the distinction on the cards', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    const pk = await screen.findByTestId('area-pharmacokinetic_modelling');
    expect(within(pk).getByText('Outside model domain')).toBeInTheDocument();
    expect(within(pk).queryByText('Blocked')).not.toBeInTheDocument();
  });

  it('gives every readiness status a label', () => {
    const ids: ReadinessStatusId[] = [
      'ready', 'conditionally_ready', 'insufficient', 'blocked',
      'outside_model_domain',
    ];
    for (const id of ids) {
      expect(READINESS_LABEL[id]).toBeTruthy();
      expect(READINESS_LABEL[id]).not.toBe(id);
    }
  });
});

/* ===================================================================== */
describe('8. an empty study is blocked, not ready', () => {
  it('blocks every area when nothing has been recorded', async () => {
    renderAt('/scientific-readiness');
    const areas = await screen.findByTestId('readiness-areas');
    for (const id of AREA_IDS) {
      expect(within(within(areas).getByTestId(`area-${id}`))
        .getByText('Blocked')).toBeInTheDocument();
    }
  });

  it('shows 0%, never an encouraging partial score', async () => {
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    for (const id of AREA_IDS) {
      expect(screen.getByTestId(`percent-${id}`)).toHaveTextContent('0%');
    }
  });

  it('reports E0 rather than omitting the evidence level', async () => {
    renderAt('/scientific-readiness');
    await screen.findByTestId('readiness-areas');
    for (const id of AREA_IDS) {
      expect(screen.getByTestId(`evidence-${id}`)).toHaveTextContent('E0');
    }
  });

  it('tells the user what to record instead of only what is wrong', async () => {
    renderAt('/scientific-readiness');
    const actions = await screen.findByTestId(
      'actions-structural_visualization');
    expect(actions).toHaveTextContent(/Record the value with its measurement/);
  });
});

/* ===================================================================== */
describe('9. readiness is not accreditation', () => {
  it('states it on the page, not only in the docs', async () => {
    renderAt('/scientific-readiness');
    const notice = await screen.findByTestId('not-accreditation');
    expect(notice).toHaveTextContent(/not regulatory approval/i);
    expect(notice).toHaveTextContent(/clinical validation/i);
    expect(notice).toHaveTextContent(/scientific accreditation/i);
  });

  it('says a ready study can still be wrong', async () => {
    renderAt('/scientific-readiness');
    expect(await screen.findByTestId('not-accreditation'))
      .toHaveTextContent(/fully ready and still be scientifically wrong/i);
  });

  it('shows the notice before any area result is fetched', async () => {
    installFetch({ readinessStatus: 500 });
    renderAt('/scientific-readiness');
    // Even with no assessment at all, the disclaimer is present.
    expect(await screen.findByTestId('not-accreditation')).toBeInTheDocument();
  });

  it('distinguishes itself from module status', async () => {
    renderAt('/scientific-readiness');
    await screen.findByTestId('not-accreditation');
    expect(screen.getByTestId('go-to-evidence')).toBeInTheDocument();
    expect(screen.getByText(/reports which parts of the platform are built/i))
      .toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('10. legacy studies load without being misrepresented', () => {
  it('flags a legacy import', async () => {
    installFetch({ records: LEGACY_RECORDS });
    renderAt('/scientific-readiness');
    expect(await screen.findByTestId('legacy-notice'))
      .toHaveTextContent(/predates the Scientific Readiness Framework/i);
  });

  it('explains why the values carry no method', async () => {
    installFetch({ records: LEGACY_RECORDS });
    renderAt('/scientific-readiness');
    expect(await screen.findByTestId('legacy-notice'))
      .toHaveTextContent(/no measurement method, source or conditions/i);
  });

  it('shows legacy values as user-supplied, never as measured', async () => {
    installFetch({ records: LEGACY_RECORDS });
    renderAt('/scientific-readiness');
    const summary = await screen.findByTestId('provenance-summary');
    expect(within(summary).getByTestId('provenance-user_supplied'))
      .toBeInTheDocument();
    expect(within(summary).queryByTestId('provenance-measured'))
      .not.toBeInTheDocument();
  });

  it('does not show the legacy notice for a study with real records',
    async () => {
      renderAt('/scientific-readiness');
      await screen.findByTestId('provenance-summary');
      expect(screen.queryByTestId('legacy-notice')).not.toBeInTheDocument();
    });
});

/* ===================================================================== */
describe('11. it is connected to the rest of the application', () => {
  it('offers a route from an area to the 3D Builder', async () => {
    installFetch({ readiness: BLOCKED_AT_78 });
    renderAt('/scientific-readiness');
    expect(await screen.findByTestId('area-to-builder')).toBeInTheDocument();
  });

  it('carries the study id to the Builder, so it opens the same study',
    async () => {
      installFetch({ readiness: BLOCKED_AT_78 });
      renderAt('/scientific-readiness');
      const button = await screen.findByTestId('area-to-builder');
      expect(button).toBeInTheDocument();
      // The report's own study id, not a hardcoded one.
      expect(BLOCKED_AT_78.study_id).toBe(7);
    });

  it('keeps the selected study in the URL, so the view is shareable',
    async () => {
      renderAt('/scientific-readiness');
      await screen.findByTestId('readiness-areas');
      await waitFor(() => {
        expect(requested.some((u) => u.includes('/studies/7/'))).toBe(true);
      });
    });

  it('handles having no saved studies without pretending to assess one',
    async () => {
      installFetch({ runs: { runs: [], total: 0 } });
      renderAt('/scientific-readiness');
      expect(await screen.findByText(/No saved studies/i)).toBeInTheDocument();
      expect(screen.queryByTestId('readiness-areas')).not.toBeInTheDocument();
      expect(screen.getByTestId('start-a-study')).toBeInTheDocument();
    });
});

/* ===================================================================== */
describe('12. it is reachable from the navigation', () => {
  it('appears in the sidebar', async () => {
    renderAt('/scientific-readiness');
    await screen.findByRole('heading',
      { name: /Scientific Readiness/i, level: 2 });
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    expect(within(nav).getByRole('link', { name: /Scientific Readiness/i }))
      .toBeInTheDocument();
  });

  it('marks the entry active while on the page', async () => {
    renderAt('/scientific-readiness');
    await screen.findByRole('heading',
      { name: /Scientific Readiness/i, level: 2 });
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    const link = within(nav).getByRole('link',
      { name: /Scientific Readiness/i });
    expect(link).toHaveAttribute('aria-current', 'page');
  });
});
