/**
 * Tests for the Demo Workspace, scenario loading, history, comparison and
 * report generation.
 *
 * The rules under test are the honesty rules:
 *   • a scenario carries synthetic inputs, never a stored result;
 *   • loading a scenario runs nothing — execution stays a deliberate action;
 *   • the working copy is isolated and fully editable;
 *   • a demo-origin run is labelled as such everywhere it appears;
 *   • an incomplete scenario genuinely blocks execution;
 *   • history, projects and comparison show only real stored records;
 *   • reports state engines run, engines not run, versions, units and the
 *     research-use-only disclaimer.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { chooseDepotRoute, pkFixtureFor } from './pkTestFixtures';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import type {
  DemoScenarioDetail, DemoScenarioListResponse, DesignScoreResponse,
  PKSimulationResponse, RunDetail,
} from '../api/types';
import { buildReport, PK_AMOUNT_UNIT } from '../pages/workspace/report';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

const SCORE: DesignScoreResponse = {
  design_impact_score: { delivery: 87.52475247524752, toxicity: 0.8, cost: 80.75 },
  score_version: 'design-impact-adapter-0.1.0',
  component_scores: {
    delivery: { value: 87.52475247524752, scale: '0-100', meaning: 'delivery' },
    toxicity: { value: 0.8, scale: '0-10', meaning: 'toxicity' },
    cost: { value: 80.75, scale: '0-100', meaning: 'cost' },
  },
  normalized_inputs: { Size: 100, Charge: -5, Encapsulation: 85 },
  warnings: [],
  prediction_basis: 'rule_based_physicochemical_heuristic',
  evidence_level: 'literature_informed_unvalidated',
  validation_status: 'not_experimentally_validated',
  limitations: ['Computational research-planning result only.'],
  scientific_source: 'core.scoring.compute_impact',
};

const PK: PKSimulationResponse = {
  concentration_time: {
    time_h: [0, 0.1, 0.2], central_plasma: [0, 0, 0.015],
    peripheral_tissue: [0, 0, 0], point_count: 3,
    concentration_unit: 'arbitrary units (dose-scaled amount)',
    time_unit: 'hours',
  },
  pk_parameters: {
    peak_concentration_central: 1.4411129411755834,
    peak_concentration_peripheral: 1.5287460434185478,
    time_to_peak_central_h: 2.6, time_to_peak_peripheral_h: 12.5,
    auc_central: 18.92076869856752, auc_peripheral: 56.83108645967397,
    half_life_central_h: 5.2, tissue_accumulation_ratio: 3.0,
    vss_ratio: 1.06,
  },
  calculation_version: 'pk-two-compartment-adapter-0.1.0',
  model_name: 'two_compartment_depot_forward_euler',
  normalized_inputs: { dose: 3, kabs: 0.5, kel: 0.1, k12: 0.2, k21: 0.05,
                       duration: 48, dt: 0.1 },
  warnings: ['Concentrations are in arbitrary dose-scaled units.'],
  assumptions: ['Explicit forward-Euler integration at a fixed step.'],
  limitations: ['Not experimentally validated.'],
  quantities_not_produced: [
    { quantity: 'clearance', reason: 'The model has no volume term.' },
  ],
  prediction_basis: 'mechanistic_compartmental_ode_forward_euler',
  evidence_level: 'structural_model_with_user_supplied_rate_constants',
  validation_status: 'not_experimentally_validated',
  scientific_source: 'utils.pk_model.two_compartment_model',
};

const COMPLETE_SCENARIO: DemoScenarioDetail = {
  slug: 'liver-hcc-galnac',
  name: 'Liver cancer (HCC) — GalNAc hepatocyte-targeted particle',
  purpose: 'Reference scenario sitting inside every documented optimum band.',
  disease: 'Liver Cancer (HCC)',
  subtype: 'AFP-high HCC',
  drug: 'Sorafenib',
  technical: false,
  score_runnable: true,
  pk_runnable: true,
  engines_expected_to_run: ['Design impact score', 'Pharmacokinetic simulation'],
  engine_count_not_running: 3,
  fixture_version: 'demo-scenarios-1.0.0',
  data_classification: 'Synthetic demonstration data',
  design_inputs: {
    size_nm: 100, charge_mv: -5, encapsulation_percent: 85, pdi: 0.15,
    ligand: 'GalNAc', surface_coating: ['PEG (Stealth)'],
  },
  pk_inputs: {
    dose_mg_kg: 3.0, kabs_per_h: 0.5, kel_per_h: 0.1, k12_per_h: 0.2,
    k21_per_h: 0.05, duration_h: 48,
  },
  assumptions: ['All values are synthetic demonstration inputs.'],
  expected_warnings: ['Few or no interpretation warnings.'],
  engines_that_will_not_run: [
    { engine: 'Regulatory verdict', reason: 'Uncalibrated threshold.' },
  ],
  provenance: ['Legacy documented defaults for the 23-field design schema.'],
  missing_required_design_inputs: [],
  missing_required_pk_inputs: [],
};

const BLOCKED_SCENARIO: DemoScenarioDetail = {
  ...COMPLETE_SCENARIO,
  slug: 'technical-incomplete-inputs',
  name: 'Technical — incomplete design, execution blocked',
  purpose: 'Demonstrates that the platform refuses to calculate rather than filling gaps.',
  disease: 'Breast Cancer',
  subtype: 'Triple-Negative (ER-, PR-, HER2-)',
  drug: 'Paclitaxel',
  technical: true,
  score_runnable: false,
  pk_runnable: false,
  engines_expected_to_run: [],
  design_inputs: { size_nm: 105, charge_mv: -6, pdi: 0.16 },
  pk_inputs: { dose_mg_kg: 3.0, kabs_per_h: 0.5 },
  missing_required_design_inputs: ['encapsulation_percent'],
  missing_required_pk_inputs: ['kel_per_h', 'k12_per_h', 'k21_per_h'],
};

const SCENARIO_LIST: DemoScenarioListResponse = {
  fixture_version: 'demo-scenarios-1.0.0',
  scenarios: [COMPLETE_SCENARIO, BLOCKED_SCENARIO],
  notice: 'Synthetic demonstration inputs. These scenarios are not patient data, '
    + 'not clinical data, not validated experimental data, not treatment '
    + 'recommendations, and not known-successful formulations.',
};

const STORED_RUN: RunDetail = {
  id: 7, name: 'Liver demo run', origin: 'demo',
  pathway: 'demo_scenario', research_purpose: null,
  inputs_are_synthetic: true, report_assessment_id: null,
  demo_scenario_slug: 'liver-hcc-galnac', disease: 'Liver Cancer (HCC)',
  subtype: 'AFP-high HCC', drug: 'Sorafenib', status: 'complete',
  engines_run: ['Design impact score', 'Pharmacokinetic simulation'],
  has_design_result: true, has_pk_result: true,
  design_score_version: 'design-impact-adapter-0.1.0',
  pk_calculation_version: 'pk-two-compartment-adapter-0.1.0',
  project_id: null, created_at: '2026-08-01T10:00:00.000Z',
  design_inputs: { size_nm: 100, charge_mv: -5, encapsulation_percent: 85 },
  pk_inputs: { dose_mg_kg: 3, kabs_per_h: 0.5, kel_per_h: 0.1,
               k12_per_h: 0.2, k21_per_h: 0.05 },
  design_result: SCORE, pk_result: PK,
  engines_not_run: [
    { engine: 'Scientific assessments', reason: 'No profile for this indication.' },
  ],
  demo_fixture_version: 'demo-scenarios-1.0.0',
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

interface FetchOpts {
  runs?: unknown;
  runDetail?: unknown;
  comparison?: unknown;
  projects?: unknown;
}

function installFetch(opts: FetchOpts = {}) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    // Route-aware PK endpoints. The legacy depot fields are only
    // offered once a depot-compatible route is chosen, so these must
    // answer before those fields exist.
    const pkFixture = pkFixtureFor(url);
    if (pkFixture !== null) return json(pkFixture);
    // Storing a run returns the created record, not the listing.
    if (url.endsWith('/api/v1/runs') && init?.method === 'POST') {
      return json({ ...STORED_RUN, id: 42 }, 201);
    }
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    if (url.endsWith('/api/v1/design/score')) return json(SCORE);
    if (url.endsWith('/api/v1/pk/simulate')) return json(PK);
    if (url.endsWith('/api/v1/demo/scenarios')) return json(SCENARIO_LIST);
    if (url.includes('/api/v1/demo/scenarios/')) {
      const slug = url.split('/').pop();
      return json(slug === BLOCKED_SCENARIO.slug ? BLOCKED_SCENARIO
                                                 : COMPLETE_SCENARIO);
    }
    if (url.includes('/api/v1/demo/reset')) {
      return json({ confirmed: false, deleted: false, demo_runs: 2,
                    demo_projects: 0, demo_templates: 0,
                    user_runs_preserved: 5, user_projects_preserved: 1,
                    message: 'Nothing was deleted. Confirming would remove 2 '
                      + 'demo run(s), leaving 5 user run(s) untouched.' });
    }
    if (url.includes('/api/v1/runs/compare/select')) {
      return json(opts.comparison ?? {
        runs: [STORED_RUN, { ...STORED_RUN, id: 8, name: 'Breast demo run' }],
        rows: [
          { label: 'Indication', source: 'context', key: 'disease',
            values: ['Liver Cancer (HCC)', 'Breast Cancer'], unit_note: null },
          { label: 'AUC, central', source: 'pk_param', key: 'auc_central',
            values: [18.92076869856752, null],
            unit_note: 'Dose-scaled compartment amount in arbitrary units.' },
        ],
        notice: 'Values are copied verbatim. No overall ranking is produced.',
      });
    }
    if (/\/api\/v1\/runs\/\d+$/.test(url)) {
      return json(opts.runDetail ?? STORED_RUN);
    }
    if (url.includes('/api/v1/runs')) {
      return json(opts.runs ?? { runs: [STORED_RUN], total: 1 });
    }
    if (url.includes('/api/v1/projects')) {
      return json(opts.projects ?? { projects: [], total: 0 });
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

function calls() {
  return (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
}

beforeEach(() => {
  localStorage.clear();
  installFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

/* ===================================================================== */
describe('demo workspace listing', () => {
  it('is reachable from the sidebar after login', async () => {
    renderAt('/start');
    const nav = await screen.findByRole('navigation', { name: /Main navigation/i });
    expect(within(nav).getByText('Demo Workspace')).toBeInTheDocument();
  });

  it('lists the scenarios with their disease context and purpose', async () => {
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    const card = screen.getByTestId('scenario-liver-hcc-galnac');
    expect(within(card).getByText('AFP-high HCC')).toBeInTheDocument();
    expect(within(card).getByText('Sorafenib')).toBeInTheDocument();
    expect(card.textContent).toMatch(/Reference scenario/i);
  });

  it('shows the synthetic-data classification on every card', async () => {
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    for (const slug of ['liver-hcc-galnac', 'technical-incomplete-inputs']) {
      expect(screen.getByTestId(`scenario-${slug}`).textContent)
        .toMatch(/Synthetic demonstration data/i);
    }
  });

  it('states plainly that the scenarios are not clinical or patient data', async () => {
    renderAt('/demo');
    const notice = await screen.findByTestId('demo-notice');
    expect(notice.textContent).toMatch(/not patient data/i);
    expect(notice.textContent).toMatch(/not clinical data/i);
    expect(notice.textContent).toMatch(/not validated experimental data/i);
    expect(notice.textContent).toMatch(/not treatment recommendations/i);
  });

  it('shows which engines can and cannot run for each scenario', async () => {
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    const blocked = screen.getByTestId('scenario-technical-incomplete-inputs');
    expect(blocked.textContent).toMatch(/inputs incomplete/i);
  });

  it('displays the fixture-set version', async () => {
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    expect(screen.getByText('demo-scenarios-1.0.0')).toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('scenario preview', () => {
  async function openPreview(user: ReturnType<typeof userEvent.setup>,
                             slug = 'liver-hcc-galnac') {
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    const card = screen.getByTestId(`scenario-${slug}`);
    await user.click(within(card).getByRole('button', { name: /Preview/i }));
    await screen.findByTestId('scenario-preview');
  }

  it('shows every input before loading', async () => {
    const user = userEvent.setup();
    await openPreview(user);
    const preview = screen.getByTestId('scenario-preview');
    expect(preview.textContent).toMatch(/Particle size \(nm\)/);
    expect(preview.textContent).toMatch(/k_abs/);
    expect(preview.textContent).toMatch(/GalNAc/);
  });

  it('shows assumptions, expected warnings and provenance', async () => {
    const user = userEvent.setup();
    await openPreview(user);
    const preview = screen.getByTestId('scenario-preview');
    expect(preview.textContent).toMatch(/synthetic demonstration inputs/i);
    expect(preview.textContent).toMatch(/Warnings you should expect/i);
    expect(preview.textContent).toMatch(/legacy documented defaults/i);
  });

  it('names the engines that will not run, with reasons', async () => {
    const user = userEvent.setup();
    await openPreview(user);
    const notRun = screen.getByTestId('engines-not-run');
    expect(notRun.textContent).toMatch(/Regulatory verdict/);
    expect(notRun.textContent).toMatch(/Uncalibrated threshold/);
  });

  it('marks the deliberately absent inputs on the blocked scenario', async () => {
    const user = userEvent.setup();
    await openPreview(user, 'technical-incomplete-inputs');
    const preview = screen.getByTestId('scenario-preview');
    expect(preview.textContent).toMatch(/deliberately not supplied/);
    expect(screen.getByTestId('no-engines').textContent)
      .toMatch(/no engine will be called/i);
  });

  it('repeats the synthetic classification inside the preview', async () => {
    const user = userEvent.setup();
    await openPreview(user);
    expect(screen.getByTestId('scenario-preview').textContent)
      .toMatch(/not patient data/i);
  });

  it('runs no calculation while previewing', async () => {
    const user = userEvent.setup();
    await openPreview(user);
    expect(calls().filter((c) => String(c[0]).includes('/design/score')))
      .toHaveLength(0);
    expect(calls().filter((c) => String(c[0]).includes('/pk/simulate')))
      .toHaveLength(0);
  });
});

/* ===================================================================== */
describe('loading a scenario', () => {
  async function loadScenario(user: ReturnType<typeof userEvent.setup>,
                              slug = 'liver-hcc-galnac') {
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    const card = screen.getByTestId(`scenario-${slug}`);
    await user.click(within(card).getByRole('button', { name: /Load scenario/i }));
    await screen.findByTestId('scenario-preview');
    await user.click(screen.getByTestId('confirm-load'));
  }

  it('populates Step 1 with the scenario context', async () => {
    const user = userEvent.setup();
    await loadScenario(user);
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    expect(screen.getByRole('combobox', { name: 'Indication' }))
      .toHaveValue('Liver Cancer (HCC)');
    expect(screen.getByRole('combobox', { name: 'Therapeutic agent' }))
      .toHaveValue('Sorafenib');
  });

  it('populates Step 2 design parameters', async () => {
    const user = userEvent.setup();
    await loadScenario(user);
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    await user.click(screen.getByRole('button', { name: /Continue to design parameters/i }));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
    expect(screen.getByRole('textbox', { name: /Particle size/i }))
      .toHaveValue('100');
  });

  it('populates Step 3 pharmacokinetic inputs', async () => {
    const user = userEvent.setup();
    await loadScenario(user);
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    await user.click(screen.getByRole('button', { name: /Continue to design parameters/i }));
    await user.click(await screen.findByRole('button', { name: /Continue to review/i }));
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });
    // The scenario supplies k_abs, so it is a depot study by construction.
    // The depot fields appear once a compatible route is chosen.
    await chooseDepotRoute(screen, user);
    await screen.findByTestId('legacy-depot-inputs');
    expect(screen.getByRole('spinbutton', { name: /Elimination rate constant/i }))
      .toHaveValue(0.1);
  });

  it('runs nothing automatically on load', async () => {
    const user = userEvent.setup();
    await loadScenario(user);
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    expect(calls().filter((c) => String(c[0]).includes('/design/score')))
      .toHaveLength(0);
    expect(calls().filter((c) => String(c[0]).includes('/pk/simulate')))
      .toHaveLength(0);
  });

  it('lets the user edit a loaded value without touching the template', async () => {
    const user = userEvent.setup();
    await loadScenario(user);
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    await user.click(screen.getByRole('button', { name: /Continue to design parameters/i }));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });

    const size = screen.getByRole('textbox', { name: /Particle size/i });
    await user.clear(size);
    await user.type(size, '145');
    expect(size).toHaveValue('145');

    // No write of any kind was issued against the scenario template.
    const writes = calls().filter(
      (c) => String(c[0]).includes('/demo/scenarios')
        && (c[1] as RequestInit | undefined)?.method
        && (c[1] as RequestInit).method !== 'GET');
    expect(writes).toHaveLength(0);
  });

  it('blocks execution for the deliberately incomplete scenario', async () => {
    const user = userEvent.setup();
    await loadScenario(user, 'technical-incomplete-inputs');
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    await user.click(screen.getByRole('button', { name: /Continue to design parameters/i }));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });

    // Encapsulation was deliberately omitted rather than defaulted.
    expect(screen.getByRole('textbox', { name: /Encapsulation efficiency/i }))
      .toHaveValue('');

    // Attempting to advance is refused: the step validates and stays put,
    // flagging the required field instead of substituting a value.
    await user.click(screen.getByRole('button', { name: /Continue to review/i }));
    expect(screen.getByRole('heading', { name: /Step 2/i, level: 2 }))
      .toBeInTheDocument();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Encapsulation efficiency is required/i);

    // And nothing was calculated.
    expect(calls().filter((c) => String(c[0]).includes('/design/score')))
      .toHaveLength(0);
  });
});

/* ===================================================================== */
describe('demo provenance travels with the run', () => {
  async function runLoadedScenario(user: ReturnType<typeof userEvent.setup>) {
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    await user.click(within(screen.getByTestId('scenario-liver-hcc-galnac'))
      .getByRole('button', { name: /Load scenario/i }));
    await screen.findByTestId('scenario-preview');
    await user.click(screen.getByTestId('confirm-load'));
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    await user.click(screen.getByRole('button', { name: /Continue to design parameters/i }));
    await user.click(await screen.findByRole('button', { name: /Continue to review/i }));
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });
    // Depot scenario: select the compatible route so the legacy engine is
    // genuinely permitted to run.
    await chooseDepotRoute(screen, user);
    await screen.findByTestId('legacy-depot-inputs');
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');
  }

  it('labels the results page as synthetic demonstration data', async () => {
    const user = userEvent.setup();
    await runLoadedScenario(user);
    expect(screen.getByTestId('demo-session-banner').textContent)
      .toMatch(/not patient data/i);
  });

  it('calculates the results with the real engines', async () => {
    const user = userEvent.setup();
    await runLoadedScenario(user);
    expect(calls().filter((c) => String(c[0]).includes('/design/score')))
      .toHaveLength(1);
    expect(calls().filter((c) => String(c[0]).includes('/pk/simulate')))
      .toHaveLength(1);
    expect(screen.getAllByText('87.52').length).toBeGreaterThan(0);
  });

  it('records the run as demo-generated when saved', async () => {
    const user = userEvent.setup();
    await runLoadedScenario(user);
    await user.click(screen.getByTestId('save-run'));
    await screen.findByTestId('run-saved');

    const post = calls().find((c) => String(c[0]).endsWith('/api/v1/runs')
      && (c[1] as RequestInit)?.method === 'POST');
    const body = JSON.parse((post![1] as RequestInit).body as string);
    expect(body.is_demo).toBe(true);
    expect(body.demo_scenario_slug).toBe('liver-hcc-galnac');
  });

  it('sends only genuine engine responses when saving', async () => {
    const user = userEvent.setup();
    await runLoadedScenario(user);
    await user.click(screen.getByTestId('save-run'));
    await screen.findByTestId('run-saved');

    const post = calls().find((c) => String(c[0]).endsWith('/api/v1/runs')
      && (c[1] as RequestInit)?.method === 'POST');
    const body = JSON.parse((post![1] as RequestInit).body as string);
    expect(body.design_result.design_impact_score.delivery)
      .toBe(87.52475247524752);
    expect(body.pk_result.calculation_version)
      .toBe('pk-two-compartment-adapter-0.1.0');
    // Unmigrated engines are recorded as not-run, with reasons.
    const notRun = body.engines_not_run.map((e: { engine: string }) => e.engine);
    expect(notRun).toContain('Scientific assessments');
  });
});

/* ===================================================================== */
describe('demo reset', () => {
  it('reports the exact scope before deleting anything', async () => {
    const user = userEvent.setup();
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    await user.click(screen.getByRole('button', { name: /Reset demo data/i }));

    const scope = await screen.findByTestId('reset-scope');
    expect(scope.textContent).toMatch(/Nothing was deleted/i);
    expect(scope.textContent).toMatch(/5 user run\(s\) untouched/i);
  });

  it('states that genuine user work is never deleted', async () => {
    const user = userEvent.setup();
    renderAt('/demo');
    await screen.findByTestId('scenario-cards');
    await user.click(screen.getByRole('button', { name: /Reset demo data/i }));
    await screen.findByTestId('reset-scope');
    expect(screen.getByText(/never deleted by this action/i)).toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('simulation history', () => {
  it('lists genuine stored runs', async () => {
    renderAt('/history');
    expect(await screen.findByTestId('run-row-7')).toBeInTheDocument();
    expect(screen.getByText('Liver demo run')).toBeInTheDocument();
  });

  it('labels demonstration runs as synthetic on every row', async () => {
    renderAt('/history');
    const row = await screen.findByTestId('run-row-7');
    expect(within(row).getByText(/Synthetic inputs/i)).toBeInTheDocument();
    expect(within(row).getByText(/Demonstration/i)).toBeInTheDocument();
  });

  it('shows an honest empty state, never invented activity', async () => {
    installFetch({ runs: { runs: [], total: 0 } });
    renderAt('/history');
    const empty = await screen.findByTestId('history-empty');
    expect(empty.textContent).toMatch(/never populated with example activity/i);
    expect(empty.textContent).not.toMatch(/\d+\.\d+/);
  });

  it('shows an honest empty state for projects', async () => {
    renderAt('/projects');
    const empty = await screen.findByTestId('projects-empty');
    expect(empty.textContent).toMatch(/never populated with examples/i);
  });

  it('surfaces an API failure without fabricating rows', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) return json({ status: 'healthy' });
      if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
      return json({ error: 'server_error', message: 'History unavailable.',
                    data_available: false }, 500);
    }));
    renderAt('/history');
    // The phrase appears both as the alert title and in its body; either is fine.
    expect((await screen.findAllByText(/History unavailable/i)).length)
      .toBeGreaterThan(0);
    expect(screen.queryByTestId('run-row-7')).not.toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('stored run detail', () => {
  it('opens a stored run and shows its calculated results', async () => {
    renderAt('/history/7');
    expect(await screen.findByTestId('result-card')).toBeInTheDocument();
    expect(screen.getByTestId('pk-panel')).toBeInTheDocument();
  });

  it('flags a demo-origin run with its scenario and fixture version', async () => {
    renderAt('/history/7');
    const banner = await screen.findByTestId('demo-run-banner');
    expect(banner.textContent).toMatch(/liver-hcc-galnac/);
    expect(banner.textContent).toMatch(/demo-scenarios-1\.0\.0/);
    expect(banner.textContent).toMatch(/not patient data/i);
  });

  it('lists engines that ran and engines that did not', async () => {
    renderAt('/history/7');
    await screen.findByTestId('engines-run');
    expect(screen.getByTestId('engines-run').textContent)
      .toMatch(/Design impact score/);
    expect(screen.getByTestId('engines-not-run').textContent)
      .toMatch(/Scientific assessments/);
  });

  it('reports an absent result honestly', async () => {
    installFetch({
      runDetail: { ...STORED_RUN, pk_result: null, has_pk_result: false,
                   status: 'partial' },
    });
    renderAt('/history/7');
    const none = await screen.findByTestId('no-pk-result');
    expect(none.textContent).toMatch(/no curve, half-life or AUC is shown/i);
  });
});

/* ===================================================================== */
describe('compare designs', () => {
  it('requires a selection before showing anything', async () => {
    renderAt('/compare');
    expect(await screen.findByTestId('compare-empty')).toBeInTheDocument();
  });

  it('aligns two stored runs field by field', async () => {
    renderAt('/compare?ids=7,8');
    await screen.findByTestId('compare-row-disease');
    const row = screen.getByTestId('compare-row-disease');
    expect(row.textContent).toMatch(/Liver Cancer \(HCC\)/);
    expect(row.textContent).toMatch(/Breast Cancer/);
  });

  it('shows an uncalculated value as not calculated, never as zero', async () => {
    renderAt('/compare?ids=7,8');
    const row = await screen.findByTestId('compare-row-auc_central');
    expect(row.textContent).toMatch(/not calculated/i);
    expect(row.textContent).not.toMatch(/\b0\b/);
  });

  it('states that no overall ranking is produced', async () => {
    renderAt('/compare?ids=7,8');
    await screen.findByTestId('compare-notice');
    // Stated twice on purpose: in the API notice and in the closing alert.
    expect(screen.getAllByText(/No overall ranking is produced/i).length)
      .toBeGreaterThan(0);
  });

  it('carries the dose-scaled unit note on PK rows', async () => {
    renderAt('/compare?ids=7,8');
    const row = await screen.findByTestId('compare-row-auc_central');
    expect(row.textContent).toMatch(/dose-scaled compartment amount/i);
    expect(row.textContent).not.toMatch(/ng\/mL/i);
  });
});

/* ===================================================================== */
describe('report generation', () => {
  it('names the engines that ran and those that did not', () => {
    const { body } = buildReport(STORED_RUN);
    expect(body).toMatch(/ENGINES EXECUTED/);
    expect(body).toMatch(/ENGINES NOT EXECUTED/);
    expect(body).toMatch(/Scientific assessments/);
    expect(body).toMatch(/No profile for this indication/);
  });

  it('identifies synthetic demonstration input', () => {
    const { body, filename } = buildReport(STORED_RUN);
    expect(body).toMatch(/SYNTHETIC DEMONSTRATION DATA/);
    expect(body).toMatch(/NOT patient data/);
    expect(body).toMatch(/liver-hcc-galnac/);
    expect(filename.startsWith('DEMO_')).toBe(true);
  });

  it('does not mark a user-created run as demo', () => {
    const { body, filename } = buildReport({ ...STORED_RUN, origin: 'user',
                                             demo_scenario_slug: null });
    expect(body).not.toMatch(/SYNTHETIC DEMONSTRATION DATA/);
    expect(body).toMatch(/User-entered inputs/);
    expect(filename.startsWith('DEMO_')).toBe(false);
  });

  it('uses dose-scaled compartment amount and never ng/mL', () => {
    const { body } = buildReport(STORED_RUN);
    expect(body).toContain(PK_AMOUNT_UNIT);
    expect(body).toMatch(/NOT\s+concentrations/);
    // ng/mL may appear only inside an explicit denial.
    for (const line of body.split('\n')) {
      if (/ng\/ml/i.test(line)) expect(line).toMatch(/NOT/);
    }
  });

  it('records the model versions and validation status', () => {
    const { body } = buildReport(STORED_RUN);
    expect(body).toMatch(/design-impact-adapter-0\.1\.0/);
    expect(body).toMatch(/pk-two-compartment-adapter-0\.1\.0/);
    expect(body).toMatch(/not_experimentally_validated/);
  });

  it('carries the research-use-only disclaimer', () => {
    const { body } = buildReport(STORED_RUN);
    expect(body).toMatch(/RESEARCH USE ONLY/);
    expect(body).toMatch(/not a diagnosis/i);
    expect(body).toMatch(/not a dosing or/i);
  });

  it('states the therapeutic context and its irrelevance to the maths', () => {
    const { body } = buildReport(STORED_RUN);
    expect(body).toMatch(/Liver Cancer \(HCC\)/);
    expect(body).toMatch(/did not affect any value/i);
  });

  it('reports an absent result as not calculated', () => {
    const { body } = buildReport({ ...STORED_RUN, pk_result: null });
    expect(body).toMatch(/NOT CALCULATED/);
    expect(body).toMatch(/No default or/);
  });

  it('includes the exact inputs so the run can be reproduced', () => {
    const { body } = buildReport(STORED_RUN);
    expect(body).toMatch(/size_nm/);
    expect(body).toMatch(/kel_per_h/);
  });

  it('states that rate constants are inputs, not predictions', () => {
    const { body } = buildReport(STORED_RUN);
    expect(body).toMatch(/Rate constants are INPUTS, not predictions/);
  });
});
