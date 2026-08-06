/**
 * The Validation Registry interface.
 *
 * The property that dominates this suite: **the page decides nothing.** E3
 * eligibility, gate results, statuses and levels all come from the server and
 * are rendered as received. A client-side rule would be a second, divergent
 * opinion about what counts as evidence — which is the failure the registry
 * exists to prevent — so the fixtures below deliberately contain combinations
 * the page has no way to recompute.
 *
 * The second property: **unfavourable records stay visible.** Rejected,
 * superseded and not-eligible experiments appear in the list by default. A
 * registry that showed only successes would not be a registry.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import { pkFixtureFor } from './pkTestFixtures';
import {
  PURPOSE_LABEL, SUBTYPE_FORMS, SUBTYPE_LABEL, formatBytes, statusLabel,
  statusTone, type ExperimentStatusId, type SubtypeId,
} from '../pages/validation/registryTypes';
import { stepsFor } from './pathways';
import { NAV_ITEMS } from '../shell/navigation';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

const EXPERIMENTS = [
  {
    experiment_id: 1, code: 'EXP-0001', title: 'Cytotoxicity of candidate A',
    subtype: 'cytotoxicity', subtype_label: 'Cytotoxicity',
    purpose: 'safety_assessment', purpose_label: 'Safety assessment',
    study_id: 7, project_id: null, candidate_id: 3,
    version_id: 11, version_number: 1, candidate_version_id: 5,
    status: 'approved', status_label: 'Approved', approved_level: 'E3',
    laboratory_name: 'In-house', investigator_name: 'A. Investigator',
    reviewer_id: 2, created_at: '2026-08-01T09:00:00Z',
    decision_at: '2026-08-02T09:00:00Z', e3_eligible: true,
  },
  {
    experiment_id: 2, code: 'EXP-0002', title: 'Uptake, incomplete controls',
    subtype: 'cellular_uptake', subtype_label: 'Cellular uptake',
    purpose: 'biological_targeting', purpose_label: 'Biological targeting',
    study_id: 7, project_id: null, candidate_id: 3,
    version_id: 12, version_number: 2, candidate_version_id: 5,
    status: 'rejected', status_label: 'Rejected', approved_level: null,
    laboratory_name: 'Contract CRO', investigator_name: 'B. Scientist',
    reviewer_id: 2, created_at: '2026-08-03T09:00:00Z',
    decision_at: '2026-08-04T09:00:00Z', e3_eligible: false,
  },
  {
    experiment_id: 3, code: 'EXP-0003', title: 'Zeta potential, draft',
    subtype: 'zeta_potential', subtype_label: 'Zeta potential',
    purpose: 'formulation_assessment', purpose_label: 'Formulation assessment',
    study_id: 7, project_id: null, candidate_id: 3,
    version_id: 13, version_number: 1, candidate_version_id: 5,
    status: 'draft', status_label: 'Draft', approved_level: null,
    laboratory_name: null, investigator_name: null, reviewer_id: null,
    created_at: '2026-08-05T09:00:00Z', decision_at: null, e3_eligible: false,
  },
];

const DASHBOARD = {
  study_id: 7, total_experiments: 3,
  by_status: { draft: 1, submitted: 0, under_review: 0, approved: 1,
               rejected: 1, revision_required: 0, superseded: 0 },
  by_purpose: { safety_assessment: 1, biological_targeting: 1,
                formulation_assessment: 1 },
  approved_by_purpose: { safety_assessment: 1 },
  purposes_with_e3: ['safety_assessment'],
  purposes_with_contradiction: [],
  registry_version: 'validation-registry-2.1.0',
};

const VERDICT = {
  eligible: false,
  purpose: 'safety_assessment',
  requested_level: 'E3', approved_level: null,
  passed_gates: ['candidate_version_linkage', 'protocol_recorded'],
  failed_gates: ['raw_data_available', 'independent_approval'],
  gates: [
    { id: 'candidate_version_linkage', label: 'Linked to an exact candidate version',
      passed: true, detail: 'Linked.', remedy: null, not_applicable: false },
    { id: 'protocol_recorded', label: 'Protocol and protocol version recorded',
      passed: true, detail: 'Recorded.', remedy: null, not_applicable: false },
    { id: 'raw_data_available', label: 'Raw or source data attached or referenced',
      passed: false,
      detail: 'Neither raw data nor a reference to it is recorded.',
      remedy: 'Attach the instrument output.', not_applicable: false },
    { id: 'independent_approval', label: 'Independent scientific approval',
      passed: false, detail: 'The experiment version has not been approved.',
      remedy: 'Submit the experiment for scientific review.',
      not_applicable: false },
  ],
  missing_requirements: ['Attach the instrument output.',
                         'Submit the experiment for scientific review.'],
  contradiction_warning: null,
  explanation: 'Not eligible for E3. 2 gate(s) failed.',
  ruleset_version: 'validation-registry-2.1.0',
};

const DETAIL = {
  experiment: {
    id: 1, code: 'EXP-0001', title: 'Cytotoxicity of candidate A',
    subtype: 'cytotoxicity', subtype_label: 'Cytotoxicity',
    purpose: 'safety_assessment', purpose_label: 'Safety assessment',
    study_id: 7, candidate_id: 3, project_id: null,
  },
  versions: [
    { id: 11, version_number: 2, status: 'draft', status_label: 'Draft',
      approved_level: null, created_at: '2026-08-05T09:00:00Z',
      superseded_by_version_id: null },
    { id: 10, version_number: 1, status: 'superseded',
      status_label: 'Superseded', approved_level: null,
      created_at: '2026-08-01T09:00:00Z', superseded_by_version_id: 11 },
  ],
  current_version: {
    id: 11, experiment_id: 1, version_number: 2, candidate_version_id: 5,
    status: 'draft', approved_level: null,
    scientific_question: 'Does candidate A reduce viability?',
    protocol_identifier: 'PROT-01', protocol_version: '1.2',
    laboratory_name: 'In-house', investigator_name: 'A. Investigator',
    biological_replicates: 3, technical_replicates: 3,
    measurements: [
      { id: 1, endpoint_name: 'viability_percent', sample_group: '10 ug/mL',
        replicate_id: 'R1', result_numeric: 41, result_unit: '%',
        excluded: false },
    ],
    attachments: [
      { id: 21, category: 'raw_data', original_filename: 'plate-reads.csv',
        mime_type: 'text/csv', size_bytes: 2048,
        checksum_sha256: 'a'.repeat(64), uploaded_at: '2026-08-05T10:00:00Z' },
    ],
  },
  capabilities: ['view', 'view_audit', 'edit_draft', 'add_attachment', 'submit'],
};

const AUDIT = {
  experiment_id: 1,
  events: [
    { id: 1, event: 'created', actor_id: 1, version_id: 11,
      summary: 'EXP-0001 v1 created', created_at: '2026-08-01T09:00:00Z' },
    { id: 2, event: 'submitted', actor_id: 1, version_id: 10,
      summary: 'submitted; version frozen',
      created_at: '2026-08-02T09:00:00Z' },
  ],
  total: 2,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

let requested: string[] = [];

function installFetch(over: Record<string, unknown> = {}) {
  requested = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    requested.push(url);
    const pk = pkFixtureFor(url);
    if (pk !== null) return json(pk);
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    if (url.includes('/api/v1/runs')) return json({ runs: [], total: 0 });
    if (url.includes('/validation/dashboard')) {
      return json(over.dashboard ?? DASHBOARD);
    }
    if (url.includes('/validation/experiments/1/audit')) return json(AUDIT);
    if (url.includes('/validation/experiments/1')) {
      return json(over.detail ?? DETAIL);
    }
    if (url.includes('/validation/experiments')) {
      return json(over.experiments
        ?? { experiments: EXPERIMENTS, total: EXPERIMENTS.length });
    }
    if (url.includes('/eligibility')) return json(over.verdict ?? VERDICT);
    if (url.includes('/validation/studies/') && url.includes('/candidates')) {
      return json({ candidates: [] });
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
describe('1. the registry list', () => {
  it('renders at /validation', async () => {
    renderAt('/validation');
    expect(await screen.findByRole('heading',
      { name: /Experimental Validation Registry/i, level: 2 }))
      .toBeInTheDocument();
  });

  it('states what E3 does and does not mean', async () => {
    renderAt('/validation');
    const note = await screen.findByTestId('registry-scope-note');
    expect(note).toHaveTextContent(/specific scientific purpose/i);
    expect(note).toHaveTextContent(/does not mean the candidate is validated/i);
  });

  it('says E4 to E6 cannot be requested', async () => {
    renderAt('/validation');
    expect(await screen.findByTestId('registry-scope-note'))
      .toHaveTextContent(/E4 to E6/);
  });

  it('lists every experiment, including the rejected one', async () => {
    renderAt('/validation');
    await screen.findByTestId('registry-row-EXP-0001');
    expect(screen.getByTestId('registry-row-EXP-0002')).toBeInTheDocument();
    expect(screen.getByTestId('registry-row-EXP-0003')).toBeInTheDocument();
  });

  it('says plainly that unfavourable records are shown', async () => {
    renderAt('/validation');
    expect(await screen.findByTestId('registry-total'))
      .toHaveTextContent(/Rejected, inconclusive and superseded records/i);
  });

  it('renders the E3 badge the server sent, for each row', async () => {
    renderAt('/validation');
    expect(await screen.findByTestId('e3-EXP-0001'))
      .toHaveTextContent('E3 eligible');
    expect(screen.getByTestId('e3-EXP-0002'))
      .toHaveTextContent('E3 not eligible');
    expect(screen.getByTestId('e3-EXP-0003'))
      .toHaveTextContent('E3 not eligible');
  });

  it('never infers eligibility from status', async () => {
    // EXP-0002 is rejected and not eligible; EXP-0003 is a draft and not
    // eligible. Both come from the server, not from a rule here.
    installFetch({
      experiments: {
        experiments: [{ ...EXPERIMENTS[2], e3_eligible: true }], total: 1,
      },
    });
    renderAt('/validation');
    // A draft the server calls eligible renders as eligible: the page has no
    // opinion of its own to override it with.
    expect(await screen.findByTestId('e3-EXP-0003'))
      .toHaveTextContent('E3 eligible');
  });

  it('shows each status badge', async () => {
    renderAt('/validation');
    expect(await screen.findByTestId('status-EXP-0001'))
      .toHaveTextContent('Approved');
    expect(screen.getByTestId('status-EXP-0002')).toHaveTextContent('Rejected');
    expect(screen.getByTestId('status-EXP-0003')).toHaveTextContent('Draft');
  });
});

/* ===================================================================== */
describe('2. the dashboard', () => {
  it('summarises counts by status', async () => {
    renderAt('/validation');
    expect(await screen.findByTestId('stat-total')).toHaveTextContent('3');
    expect(screen.getByTestId('stat-approved')).toHaveTextContent('1');
    expect(screen.getByTestId('stat-rejected')).toHaveTextContent('1');
    expect(screen.getByTestId('stat-draft')).toHaveTextContent('1');
  });

  it('counts purposes that reached E3', async () => {
    renderAt('/validation');
    expect(await screen.findByTestId('stat-e3-purposes')).toHaveTextContent('1');
  });

  it('shows no contradiction stat when there is none', async () => {
    renderAt('/validation');
    await screen.findByTestId('registry-dashboard');
    expect(screen.queryByTestId('stat-contradictions')).not.toBeInTheDocument();
  });

  it('warns when approved evidence conflicts, and says nothing was preferred',
     async () => {
    installFetch({
      dashboard: { ...DASHBOARD,
                   purposes_with_contradiction: ['safety_assessment'] },
    });
    renderAt('/validation');
    const warning = await screen.findByTestId('registry-contradiction');
    expect(warning).toHaveTextContent(/held until a reviewer/i);
    expect(warning).toHaveTextContent(/has not been preferred/i);
  });
});

/* ===================================================================== */
describe('3. filters', () => {
  it('offers every filter the brief requires', async () => {
    renderAt('/validation');
    await screen.findByTestId('registry-filters');
    for (const id of ['f-status', 'f-subtype', 'f-purpose', 'f-e3', 'f-lab',
                      'f-inv']) {
      expect(document.getElementById(id)).toBeInTheDocument();
    }
  });

  it('sends the chosen filter to the server rather than filtering locally',
     async () => {
    const user = userEvent.setup();
    renderAt('/validation');
    await screen.findByTestId('registry-filters');
    await user.selectOptions(document.getElementById('f-status')!, 'approved');
    expect(requested.some((u) => u.includes('status=approved'))).toBe(true);
  });

  it('filters by E3 eligibility through the server', async () => {
    const user = userEvent.setup();
    renderAt('/validation');
    await screen.findByTestId('registry-filters');
    await user.selectOptions(document.getElementById('f-e3')!, 'true');
    expect(requested.some((u) => u.includes('e3_eligible=true'))).toBe(true);
  });

  it('offers to clear active filters', async () => {
    const user = userEvent.setup();
    renderAt('/validation');
    await screen.findByTestId('registry-filters');
    await user.selectOptions(document.getElementById('f-status')!, 'draft');
    expect(await screen.findByTestId('clear-filters')).toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('4. experiment detail and its sections', () => {
  it('renders every required section tab', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');

    for (const [tab, section] of [
      ['Protocol and materials', 'protocol'],
      ['Controls and replicates', 'controls'],
      ['Measurements and results', 'measurements'],
      ['Raw data and attachments', 'attachments'],
      ['Quality assessment', 'quality'],
      ['Scientific review', 'review'],
      ['Evidence decision', 'evidence'],
      ['Version history', 'versions'],
      ['Audit history', 'audit'],
    ] as const) {
      await user.click(screen.getByRole('tab', { name: tab }));
      expect(await screen.findByTestId(`section-${section}`))
        .toBeInTheDocument();
    }
  });

  it('states the scope of an approval on the record itself', async () => {
    renderAt('/validation/experiments/1');
    const scope = await screen.findByTestId('detail-scope');
    expect(scope).toHaveTextContent(/Safety assessment/);
    expect(scope).toHaveTextContent(/nothing about any other purpose/i);
  });

  it('shows the candidate version the experiment is tied to', async () => {
    renderAt('/validation/experiments/1');
    expect(await screen.findByTestId('detail-candidate-version'))
      .toHaveTextContent('#5');
  });

  it('renders the gate results the server returned', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Evidence decision' }));

    expect(await screen.findByTestId('gate-raw_data_available'))
      .toHaveTextContent(/Failed/);
    expect(screen.getByTestId('gate-protocol_recorded'))
      .toHaveTextContent(/Passed/);
  });

  it('lists what is missing, with the remedy', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Evidence decision' }));
    expect(await screen.findByTestId('missing-requirements'))
      .toHaveTextContent(/Attach the instrument output/);
  });

  it('records the ruleset version a decision was made under', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Evidence decision' }));
    expect(await screen.findByTestId('ruleset-version'))
      .toHaveTextContent('validation-registry-2.1.0');
  });

  it('says E4 to E6 are for a later phase', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Evidence decision' }));
    expect(await screen.findByTestId('future-levels'))
      .toHaveTextContent(/later phase/i);
  });

  it('shows the version history including the superseded version', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Version history' }));
    expect(await screen.findByTestId('version-1')).toHaveTextContent(/Superseded/);
    expect(screen.getByTestId('version-2')).toHaveTextContent(/Draft/);
  });

  it('shows the audit trail and says it is append-only', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Audit history' }));
    expect(await screen.findByTestId('audit-guidance'))
      .toHaveTextContent(/Append-only/i);
    expect(screen.getByTestId('audit-1')).toBeInTheDocument();
  });

  it('shows structured measurements rather than a narrative only', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Measurements and results' }));
    const row = await screen.findByTestId('measurement-0');
    expect(row).toHaveTextContent('viability_percent');
    expect(row).toHaveTextContent('41');
    expect(row).toHaveTextContent('%');
  });

  it('shows an attachment with its checksum and never a path', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Raw data and attachments' }));
    const row = await screen.findByTestId('attachment-21');
    expect(row).toHaveTextContent('plate-reads.csv');
    expect(row).toHaveTextContent('aaaaaaaaaaaa');
    expect(row.textContent).not.toMatch(/[A-Za-z]:\\|\/var\/|\/home\//);
  });
});

/* ===================================================================== */
describe('5. subtype-specific forms', () => {
  it('gives every subtype its own specification', () => {
    for (const id of Object.keys(SUBTYPE_LABEL) as SubtypeId[]) {
      expect(SUBTYPE_FORMS[id]).toBeDefined();
      expect(SUBTYPE_FORMS[id].guidance.length).toBeGreaterThan(30);
    }
  });

  it('does not present one universal measurement form', () => {
    // The specifications genuinely differ: a release profile is a time course,
    // a zeta potential is not; a cytotoxicity assay is dose-response, a drug
    // loading measurement is not.
    expect(SUBTYPE_FORMS.release_profile.timeCourse).toBe(true);
    expect(SUBTYPE_FORMS.zeta_potential.timeCourse).toBe(false);
    expect(SUBTYPE_FORMS.cytotoxicity.doseResponse).toBe(true);
    expect(SUBTYPE_FORMS.drug_loading.doseResponse).toBe(false);
    expect(SUBTYPE_FORMS.cytotoxicity.cellBased).toBe(true);
    expect(SUBTYPE_FORMS.particle_size_pdi.cellBased).toBe(false);
  });

  it('names endpoints appropriate to each assay', () => {
    expect(SUBTYPE_FORMS.zeta_potential.endpoints[0]!.unit).toBe('mV');
    expect(SUBTYPE_FORMS.cytotoxicity.endpoints
      .some((e) => e.name === 'viability_percent')).toBe(true);
    expect(SUBTYPE_FORMS.release_profile.endpoints
      .some((e) => e.name === 'cumulative_release')).toBe(true);
  });

  it('leaves the unclassified assay without a template, and says so', () => {
    expect(SUBTYPE_FORMS.other_in_vitro.endpoints).toHaveLength(0);
    expect(SUBTYPE_FORMS.other_in_vitro.guidance)
      .toMatch(/no template to fall back on/i);
  });

  it('offers the subtype-appropriate entry fields on the page', async () => {
    const user = userEvent.setup();
    renderAt('/validation/experiments/1');
    await screen.findByTestId('section-details');
    await user.click(screen.getByRole('tab', { name: 'Measurements and results' }));
    // Cytotoxicity: dose applies, time course does not.
    expect(await screen.findByTestId('measurement-entry')).toBeInTheDocument();
    expect(document.getElementById('m-dose')).toBeInTheDocument();
    expect(document.getElementById('m-time')).not.toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('6. new experiment', () => {
  it('renders the creation form', async () => {
    renderAt('/validation/new');
    expect(await screen.findByRole('heading',
      { name: /New in-vitro experiment/i, level: 2 })).toBeInTheDocument();
  });

  it('says that creating a record grants nothing', async () => {
    renderAt('/validation/new');
    expect(await screen.findByTestId('new-experiment-note'))
      .toHaveTextContent(/grants nothing/i);
  });

  it('offers only purposes the chosen assay can evidence', async () => {
    renderAt('/validation/new');
    const purpose = await screen.findByLabelText(/Scientific purpose/i);
    const options = within(purpose as HTMLElement)
      .getAllByRole('option').map((o) => (o as HTMLOptionElement).value);
    // Default subtype is cytotoxicity, which may only claim safety.
    expect(options).toEqual(['safety_assessment']);
  });

  it('never offers pharmacokinetics or animation for an in-vitro assay',
     async () => {
    const user = userEvent.setup();
    renderAt('/validation/new');
    const subtype = await screen.findByLabelText(/subtype/i);
    for (const value of ['cellular_uptake', 'release_profile', 'stability']) {
      await user.selectOptions(subtype as HTMLElement, value);
      const purpose = screen.getByLabelText(/Scientific purpose/i);
      const options = within(purpose as HTMLElement)
        .getAllByRole('option').map((o) => (o as HTMLOptionElement).value);
      expect(options).not.toContain('pharmacokinetic_modelling');
      expect(options).not.toContain('cinematic_animation');
    }
  });

  it('shows the guidance for the selected assay', async () => {
    const user = userEvent.setup();
    renderAt('/validation/new');
    const subtype = await screen.findByLabelText(/subtype/i);
    await user.selectOptions(subtype as HTMLElement, 'zeta_potential');
    expect(await screen.findByTestId('subtype-guidance'))
      .toHaveTextContent(/medium, pH and ionic strength/i);
  });
});

/* ===================================================================== */
describe('7. navigation and pathway integration', () => {
  it('adds the registry to the menu', () => {
    const item = NAV_ITEMS.find((i) => i.key === 'validation-registry');
    expect(item).toBeDefined();
    expect(item!.path).toBe('/validation');
  });

  it('describes the registry without overclaiming', () => {
    const item = NAV_ITEMS.find((i) => i.key === 'validation-registry')!;
    expect(item.summary).toMatch(/only that purpose/i);
    expect(item.summary).toMatch(/candidate version/i);
  });

  it('places the registry on the research pathway', () => {
    const ids = stepsFor('research_design').map((s) => s.id);
    expect(ids).toContain('validation-registry');
  });

  it('places the registry on the patient pathway', () => {
    const ids = stepsFor('patient_assessment').map((s) => s.id);
    expect(ids).toContain('validation-registry');
  });

  it('keeps it off the demonstration pathway', () => {
    // A demonstration must not file experiments into the real registry.
    const ids = stepsFor('demo_scenario').map((s) => s.id);
    expect(ids).not.toContain('validation-registry');
  });

  it('places it after Scientific Readiness on both study pathways', () => {
    for (const pathway of ['research_design', 'patient_assessment'] as const) {
      const ids = stepsFor(pathway).map((s) => s.id);
      expect(ids.indexOf('validation-registry'))
        .toBeGreaterThan(ids.indexOf('scientific-readiness'));
    }
  });

  it('reaches the registry from the sidebar', async () => {
    renderAt('/validation');
    const nav = await screen.findByRole('navigation',
                                        { name: 'Main navigation' });
    expect(within(nav).getByRole('link', { name: /Validation Registry/i }))
      .toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('8. presentation helpers', () => {
  it('labels every status', () => {
    const ids: ExperimentStatusId[] = ['draft', 'submitted', 'under_review',
      'approved', 'rejected', 'revision_required', 'superseded'];
    for (const id of ids) {
      expect(statusLabel(id)).toBeTruthy();
      expect(statusLabel(id)).not.toBe(id);
    }
  });

  it('distinguishes rejected from superseded', () => {
    // A rejection is a finding about the work; a supersession is bookkeeping.
    expect(statusTone('rejected')).not.toBe(statusTone('superseded'));
  });

  it('falls back rather than showing a raw identifier', () => {
    expect(statusLabel('something_new')).toBe('Not recorded');
    expect(statusTone('something_new')).toBe('neutral');
  });

  it('never rounds a file size to zero', () => {
    expect(formatBytes(1)).toBe('1 B');
    expect(formatBytes(2048)).toBe('2.0 kB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });

  it('labels every purpose', () => {
    for (const label of Object.values(PURPOSE_LABEL)) {
      expect(label.length).toBeGreaterThan(5);
    }
  });
});
