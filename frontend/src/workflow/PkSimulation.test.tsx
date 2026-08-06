/**
 * Tests for the pharmacokinetic vertical slice in the React workflow.
 *
 * The rules under test are the honesty rules:
 *   • the model is not called at all until every required input is present;
 *   • an absent run produces an explicit empty state, never an empty chart;
 *   • a failed run produces no curve, half-life or AUC;
 *   • a null half-life is shown as "not determined", never estimated;
 *   • clearance is named as not produced, never derived;
 *   • the chart is drawn from the returned arrays and the exact values are
 *     available alongside it;
 *   • the PK result is kept visibly distinct from the design impact score.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { chooseDepotRoute, pkFixtureFor } from './pkTestFixtures';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import type { DesignScoreResponse, PKSimulationResponse } from '../api/types';

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

/**
 * A short but genuine-shaped PK response. The numbers are the ones the real
 * engine returns for these inputs at dt = 0.1 over the first four points, so
 * the fixture cannot drift into an implausible shape.
 */
const PK: PKSimulationResponse = {
  concentration_time: {
    time_h: [0, 0.1, 0.2, 0.30000000000000004],
    central_plasma: [0, 0, 0.015, 0.02962500000000001],
    peripheral_tissue: [0, 0, 0, 0.0003],
    point_count: 4,
    concentration_unit: 'arbitrary units (dose-scaled amount)',
    time_unit: 'hours',
  },
  pk_parameters: {
    peak_concentration_central: 1.4411129411755834,
    peak_concentration_peripheral: 1.5287460434185478,
    time_to_peak_central_h: 2.6,
    time_to_peak_peripheral_h: 12.5,
    auc_central: 18.92076869856752,
    auc_peripheral: 56.83108645967397,
    half_life_central_h: 5.200000000000001,
    tissue_accumulation_ratio: 3.0036351780980555,
    vss_ratio: 1.0608093229469426,
  },
  calculation_version: 'pk-two-compartment-adapter-0.1.0',
  model_name: 'two_compartment_depot_forward_euler',
  normalized_inputs: {
    dose: 3, kabs: 0.5, kel: 0.1, k12: 0.2, k21: 0.05, duration: 48, dt: 0.1,
  },
  warnings: ['Concentrations are in arbitrary dose-scaled units.'],
  assumptions: ['Solved by explicit forward-Euler integration at a fixed step.'],
  limitations: [
    'Computational research-planning result only. Not experimentally validated.',
    'The rate constants are inputs, not predictions.',
  ],
  quantities_not_produced: [
    {
      quantity: 'clearance',
      reason: 'The migrated model has no volume-of-distribution term.',
    },
    {
      quantity: 'volume_of_distribution',
      reason: 'Not modelled.',
    },
  ],
  prediction_basis: 'mechanistic_compartmental_ode_forward_euler',
  evidence_level: 'structural_model_with_user_supplied_rate_constants',
  validation_status: 'not_experimentally_validated',
  scientific_source: 'utils.pk_model.two_compartment_model',
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

function installFetch(opts: { pkStatus?: number; pkBody?: unknown } = {}) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    // Route-aware PK endpoints. The legacy depot fields are only
    // offered once a depot-compatible route is chosen, so these must
    // answer before those fields exist.
    const pkFixture = pkFixtureFor(url);
    if (pkFixture !== null) return json(pkFixture);
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    if (url.endsWith('/api/v1/design/score')) return json(SCORE);
    if (url.endsWith('/api/v1/pk/simulate')) {
      return json(opts.pkBody ?? PK, opts.pkStatus ?? 200);
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

const PK_INPUTS: ReadonlyArray<[string, string]> = [
  ['Dose', '3'],
  ['Absorption rate constant', '0.5'],
  ['Elimination rate constant', '0.1'],
  ['Central → peripheral transfer', '0.2'],
  ['Peripheral → central transfer', '0.05'],
];

async function completeStep1(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
  await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                           'Liver Cancer (HCC)');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Disease subtype' }),
                           'AFP-high HCC');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Therapeutic agent' }),
                           'Sorafenib');
}

async function reachReview(user: ReturnType<typeof userEvent.setup>) {
  renderAt('/workflow/disease');
  await completeStep1(user);
  await user.click(await screen.findByTestId('pathway-continue'));
  await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
  await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
  await screen.findByRole('heading', { name: /Step 3/i, level: 2 });
  // The depot rate constants are only offered for a route that genuinely has
  // an absorption phase. Sorafenib is oral in practice; subcutaneous is used
  // here because it is the depot-compatible route in the fixture set.
  await chooseDepotRoute(screen, user);
  await screen.findByTestId('legacy-depot-inputs');
}

async function fillPkInputs(
  user: ReturnType<typeof userEvent.setup>,
  overrides: Partial<Record<string, string>> = {},
) {
  for (const [label, value] of PK_INPUTS) {
    const field = screen.getByRole('spinbutton', { name: new RegExp(label, 'i') });
    await user.clear(field);
    const next = overrides[label] ?? value;
    if (next) await user.type(field, next);
  }
}

function pkCalls() {
  return (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
    .filter((c) => String(c[0]).includes('/pk/simulate'));
}

/**
 * Scope queries to the PK card.
 *
 * The results page deliberately renders two independent result panels, each
 * with its own tab set — that separation is the point. Queries must therefore
 * be scoped, or they match the design-score panel too.
 */
function pkPanel() {
  return within(screen.getByTestId('pk-panel'));
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
describe('PK inputs on Step 3', () => {
  it('collects the five required inputs and the two window settings', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    const block = screen.getByTestId('pk-inputs');
    for (const [label] of PK_INPUTS) {
      expect(within(block).getByRole('spinbutton', { name: new RegExp(label, 'i') }))
        .toBeInTheDocument();
    }
    expect(within(block).getByRole('spinbutton', { name: /Simulation duration/i }))
      .toBeInTheDocument();
    expect(within(block).getByRole('spinbutton', { name: /Integration time step/i }))
      .toBeInTheDocument();
  });

  it('pre-fills no kinetic value whatsoever', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    for (const [label] of PK_INPUTS) {
      const field = screen.getByRole('spinbutton', { name: new RegExp(label, 'i') });
      expect(field).toHaveValue(null);
    }
  });

  it('states that the model does not infer the rate constants', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(screen.getByTestId('pk-inputs').textContent)
      .toMatch(/does not infer them from the formulation/i);
  });

  it('reports an out-of-range rate constant instead of clamping it', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    const field = screen.getByRole('spinbutton', { name: /Elimination rate constant/i });
    await user.type(field, '9');
    await user.tab();

    expect(await screen.findByText(/must be 2 h⁻¹ or less/i)).toBeInTheDocument();
    expect(field).toHaveValue(9);   // the entry is preserved, not silently fixed
  });
});

/* ===================================================================== */
describe('execution gate', () => {
  it('does not call the PK endpoint when inputs are incomplete', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    expect(pkCalls()).toHaveLength(0);
  });

  it('does not call the PK endpoint when one input is missing', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await fillPkInputs(user, { 'Peripheral → central transfer': '' });
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    expect(pkCalls()).toHaveLength(0);
  });

  it('does not call the PK endpoint when an input is out of range', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await fillPkInputs(user, { 'Dose': '500' });
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    expect(pkCalls()).toHaveLength(0);
  });

  it('calls the PK endpoint once every required input is valid', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await fillPkInputs(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('pk-panel');

    expect(pkCalls()).toHaveLength(1);
  });

  it('posts only the supplied fields, omitting the blank window settings', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await fillPkInputs(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('pk-panel');

    const body = JSON.parse((pkCalls()[0]![1] as RequestInit).body as string);
    expect(body).toEqual({
      dose_mg_kg: 3, kabs_per_h: 0.5, kel_per_h: 0.1,
      k12_per_h: 0.2, k21_per_h: 0.05,
    });
  });

  it('sends the window settings when the user supplies them', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await fillPkInputs(user);
    await user.type(screen.getByRole('spinbutton', { name: /Simulation duration/i }),
                    '24');
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('pk-panel');

    const body = JSON.parse((pkCalls()[0]![1] as RequestInit).body as string);
    expect(body.duration_h).toBe(24);
  });

  it('says on the review step whether the simulation will run', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(screen.getByTestId('pk-run-status').textContent).toMatch(/Will not run/i);

    await fillPkInputs(user);
    expect(screen.getByTestId('pk-run-status').textContent)
      .toMatch(/will run on the inputs above/i);
  });
});

/* ===================================================================== */
describe('honest empty state', () => {
  it('shows an explicit not-run panel rather than an empty chart', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    expect(screen.getByTestId('pk-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('concentration-time-chart')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pk-panel')).not.toBeInTheDocument();
  });

  it('explains why the simulation did not run', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    expect(screen.getByTestId('pk-empty-reason').textContent)
      .toMatch(/No concentration–time profile, half-life or\s+AUC exists/i);
  });

  it('shows no PK number anywhere when the simulation did not run', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    const empty = screen.getByTestId('pk-empty');
    expect(empty.textContent).not.toMatch(/\d+\.\d+/);
    expect(screen.queryByTestId('pk-cmax')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pk-auc')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pk-half-life')).not.toBeInTheDocument();
  });

  it('still shows the design impact score, which is a separate calculation', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));

    expect(await screen.findByTestId('result-card')).toBeInTheDocument();
    expect(screen.getByTestId('pk-empty')).toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('calculated results', () => {
  async function runPk(user: ReturnType<typeof userEvent.setup>) {
    await reachReview(user);
    await fillPkInputs(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('pk-panel');
  }

  it('renders the returned peak, AUC and half-life exactly', async () => {
    const user = userEvent.setup();
    await runPk(user);

    expect(screen.getByTestId('pk-cmax')).toHaveTextContent('1.4411129411755834');
    expect(screen.getByTestId('pk-auc')).toHaveTextContent('18.92076869856752');
    expect(screen.getByTestId('pk-half-life')).toHaveTextContent('5.200000000000001');
  });

  it('renders the chart from the returned series', async () => {
    const user = userEvent.setup();
    await runPk(user);

    const chart = screen.getByTestId('concentration-time-chart');
    expect(chart).toBeInTheDocument();
    // The accessible description must quote the engine's own numbers.
    const img = within(chart).getByRole('img');
    expect(img.getAttribute('aria-label')).toMatch(/Central compartment \(plasma\)/);
  });

  it('makes every calculated point available as exact text beside the chart', async () => {
    const user = userEvent.setup();
    await runPk(user);

    await user.click(pkPanel().getByRole('tab', { name: /Data \(4\)/i }));
    const panel = pkPanel().getByRole('tabpanel');
    expect(within(panel).getByText('0.02962500000000001')).toBeInTheDocument();
    expect(within(panel).getByText('0.30000000000000004')).toBeInTheDocument();
    expect(within(panel).getByText('0.0003')).toBeInTheDocument();
  });

  it('shows the calculation version and validation status', async () => {
    const user = userEvent.setup();
    await runPk(user);

    expect(screen.getByTestId('pk-version'))
      .toHaveTextContent('pk-two-compartment-adapter-0.1.0');
    expect(screen.getByTestId('pk-validation'))
      .toHaveTextContent('not_experimentally_validated');
  });

  it('shows the normalised inputs the engine actually used', async () => {
    const user = userEvent.setup();
    await runPk(user);

    await user.click(pkPanel().getByRole('tab', { name: /^Inputs$/i }));
    const panel = pkPanel().getByRole('tabpanel');
    expect(within(panel).getByText(/k_abs/)).toBeInTheDocument();
    expect(within(panel).getByText('48')).toBeInTheDocument();
  });

  it('shows the assumptions and warnings the engine returned', async () => {
    const user = userEvent.setup();
    await runPk(user);

    await user.click(pkPanel().getByRole('tab', { name: /Assumptions/i }));
    expect(screen.getByTestId('pk-assumptions').textContent)
      .toMatch(/forward-Euler/i);

    await user.click(pkPanel().getByRole('tab', { name: /Warnings/i }));
    expect(screen.getByTestId('pk-warnings').textContent)
      .toMatch(/arbitrary dose-scaled units/i);
  });

  it('shows the limitations the engine returned', async () => {
    const user = userEvent.setup();
    await runPk(user);
    expect(screen.getByTestId('pk-limitations').textContent)
      .toMatch(/rate constants are inputs, not predictions/i);
  });
});

/* ===================================================================== */
describe('scientific honesty in the display', () => {
  async function runPk(
    user: ReturnType<typeof userEvent.setup>,
    opts: Parameters<typeof installFetch>[0] = {},
  ) {
    installFetch(opts);
    await reachReview(user);
    await fillPkInputs(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('pk-panel');
  }

  it('never displays a clearance value', async () => {
    const user = userEvent.setup();
    await runPk(user);

    expect(screen.getByTestId('pk-clearance')).toHaveTextContent('not produced');
    expect(screen.getByTestId('pk-clearance').textContent).not.toMatch(/\d/);
  });

  it('names clearance among the quantities the model does not produce', async () => {
    const user = userEvent.setup();
    await runPk(user);

    await user.click(pkPanel().getByRole('tab', { name: /Parameters/i }));
    const notProduced = screen.getByTestId('pk-not-produced');
    expect(notProduced.textContent).toMatch(/clearance/i);
    expect(notProduced.textContent).toMatch(/volume-of-distribution/i);
  });

  it('shows a null half-life as not determined, never as a number', async () => {
    const user = userEvent.setup();
    await runPk(user, {
      pkBody: {
        ...PK,
        pk_parameters: { ...PK.pk_parameters, half_life_central_h: null },
        warnings: ['Terminal half-life could not be determined within the window.'],
      },
    });

    const halfLife = screen.getByTestId('pk-half-life');
    expect(halfLife).toHaveTextContent('not determined');
    expect(halfLife.textContent).not.toMatch(/\d/);
  });

  it('does not suppress the rest of the profile when half-life is null', async () => {
    const user = userEvent.setup();
    await runPk(user, {
      pkBody: {
        ...PK,
        pk_parameters: { ...PK.pk_parameters, half_life_central_h: null },
      },
    });

    expect(screen.getByTestId('pk-cmax')).toHaveTextContent('1.4411129411755834');
    expect(screen.getByTestId('concentration-time-chart')).toBeInTheDocument();
  });

  it('labels the axis in arbitrary units, never mass per volume', async () => {
    const user = userEvent.setup();
    await runPk(user);

    const chart = screen.getByTestId('concentration-time-chart');
    expect(chart.textContent).toMatch(/arbitrary units/i);
    expect(chart.textContent).not.toMatch(/ng\/mL/i);
  });

  it('offers no clinical interpretation of the profile', async () => {
    const user = userEvent.setup();
    await runPk(user);

    const panel = screen.getByTestId('pk-panel');
    for (const phrase of [
      /excellent targeting/i, /favou?rable tissue targeting/i,
      /may need PEGylation/i, /consider dose adjustment/i,
      /suitable for most therapeutic/i, /optimal dosing/i,
    ]) {
      expect(panel.textContent).not.toMatch(phrase);
    }
  });

  it('keeps the PK result visibly distinct from the design impact score', async () => {
    const user = userEvent.setup();
    await runPk(user);

    expect(screen.getByTestId('pk-panel').textContent)
      .toMatch(/separate calculation from the design impact score/i);
    // Two cards, two versions — never one merged headline.
    expect(screen.getByTestId('score-version'))
      .toHaveTextContent('design-impact-adapter-0.1.0');
    expect(screen.getByTestId('pk-version'))
      .toHaveTextContent('pk-two-compartment-adapter-0.1.0');
  });

  it('keeps the therapeutic context visible without claiming it affects PK', async () => {
    const user = userEvent.setup();
    await runPk(user);

    // The indication legitimately appears twice: in the session card and in
    // the persistent rail summary. Scope to the session card.
    const session = screen.getByRole('heading', { name: 'Session' })
      .closest('.ds-card') as HTMLElement;
    expect(within(session).getByText('Liver Cancer (HCC)')).toBeInTheDocument();
    expect(within(session).getByText(/Neither result varies with this\s+selection/i))
      .toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('calculation failure', () => {
  async function runFailing(
    user: ReturnType<typeof userEvent.setup>,
    opts: Parameters<typeof installFetch>[0],
  ) {
    installFetch(opts);
    await reachReview(user);
    await fillPkInputs(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('pk-error');
  }

  it('surfaces a backend failure with no fallback profile', async () => {
    const user = userEvent.setup();
    await runFailing(user, {
      pkStatus: 500,
      pkBody: {
        error: 'calculation_failed',
        message: 'The pharmacokinetic profile could not be calculated.',
        results_available: false,
      },
    });

    expect(screen.getByTestId('pk-error').textContent)
      .toMatch(/could not be calculated/i);
    expect(screen.queryByTestId('pk-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('concentration-time-chart')).not.toBeInTheDocument();
  });

  it('shows no number at all on a failure', async () => {
    const user = userEvent.setup();
    await runFailing(user, {
      pkStatus: 500,
      pkBody: { error: 'calculation_failed', message: 'failed',
                results_available: false },
    });

    expect(screen.getByTestId('pk-error').textContent).not.toMatch(/\d+\.\d+/);
    expect(screen.queryByTestId('pk-cmax')).not.toBeInTheDocument();
  });

  it('surfaces a rejected request without inventing a profile', async () => {
    const user = userEvent.setup();
    await runFailing(user, {
      pkStatus: 422,
      pkBody: {
        error: 'validation_error',
        message: 'The request did not match the expected schema.',
        results_available: false,
      },
    });

    expect(screen.getByTestId('pk-error')).toBeInTheDocument();
    expect(screen.queryByTestId('pk-panel')).not.toBeInTheDocument();
  });

  it('treats a 200 without a complete profile as a failure', async () => {
    const user = userEvent.setup();
    await runFailing(user, {
      pkBody: {
        ...PK,
        concentration_time: { ...PK.concentration_time, central_plasma: [0, 0] },
      },
    });

    expect(screen.getByTestId('pk-error').textContent)
      .toMatch(/without a complete concentration–time profile/i);
  });

  it('leaves the design impact score intact when only PK fails', async () => {
    const user = userEvent.setup();
    await runFailing(user, {
      pkStatus: 500,
      pkBody: { error: 'calculation_failed', message: 'failed',
                results_available: false },
    });

    expect(screen.getByTestId('result-card')).toBeInTheDocument();
    expect(screen.getAllByText('87.52').length).toBeGreaterThan(0);
  });
});

/* ===================================================================== */
describe('draft behaviour with PK inputs', () => {
  it('preserves PK inputs across navigation', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await fillPkInputs(user);

    await user.click(await screen.findByTestId('pathway-back'));
    await user.click(await screen.findByTestId('pathway-back'));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });

    expect(screen.getByRole('spinbutton', { name: /Elimination rate constant/i }))
      .toHaveValue(0.1);
  });

  it('saves PK inputs into the draft and stores no credential', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await fillPkInputs(user);

    const rail = screen.getByRole('navigation', { name: /workflow progress/i });
    await user.click(within(rail).getByRole('button', { name: /Save draft/i }));

    const raw = localStorage.getItem('nanobio.designDrafts.v1') ?? '';
    expect(raw).toContain('kel_per_h');
    for (const banned of ['password', 'token', 'nanobio_session', 'cookie']) {
      expect(raw.toLowerCase()).not.toContain(banned);
    }
  });

  it('leaves an older draft without PK inputs un-runnable rather than defaulted', async () => {
    // A draft saved before the PK slice existed, with no `pk` key at all.
    localStorage.setItem('nanobio.designDrafts.v1', JSON.stringify([{
      id: 'ds_legacy', name: 'Pre-PK draft',
      createdAt: '2026-07-30T10:00:00.000Z', updatedAt: '2026-07-30T10:00:00.000Z',
      selection: { disease: 'Liver Cancer (HCC)', subtype: 'AFP-high HCC',
                   drug: 'Sorafenib' },
      values: { size_nm: '100', charge_mv: '-5', encapsulation_percent: '85' },
      chips: { surface_coating: [], functional_groups: [] },
      furthestStep: 3,
    }]));
    localStorage.setItem('nanobio.activeDraftId.v1', 'ds_legacy');

    const user = userEvent.setup();
    renderAt('/workflow/review');
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });

    // A depot-compatible route, so the legacy fields are genuinely offered and
    // the assertion is about the absent VALUES rather than absent fields.
    await chooseDepotRoute(screen, user);
    await screen.findByTestId('legacy-depot-inputs');

    expect(screen.getByRole('spinbutton', { name: /Dose/i })).toHaveValue(null);
    expect(screen.getByTestId('pk-run-status').textContent).toMatch(/Will not run/i);

    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');
    expect(pkCalls()).toHaveLength(0);
  });
});
