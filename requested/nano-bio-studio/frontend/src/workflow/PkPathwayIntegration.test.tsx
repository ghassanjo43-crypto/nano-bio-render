/**
 * The route-aware workflow is the authoritative execution path.
 *
 * The defect these exist for
 * --------------------------
 * The route-aware planner was implemented but gated nothing. `pkInputsReady`
 * was derived solely from whether the four rate-constant boxes were filled, so
 * for intravenous trastuzumab Step 3 and the Results page still:
 *
 *   * requested `k_abs` and the other three depot rate constants;
 *   * said "The dose and the four first-order rate constants are required…";
 *   * offered "Supply the required inputs", directing the user to invent them;
 *   * would have called the legacy depot engine, which models absorption from
 *     a compartment an intravenous dose never occupies.
 *
 * These tests pin the corrected routing decision at both the pure-function
 * level and through the rendered workflow.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import {
  EMPTY_PK_PATHWAY, blockedExplanation, describeStudy, executionPath,
  isIntravenous, legacyDepotAllowed, mayCallLegacyEngine,
  shouldRequestRateConstants, type PKPathwayState,
} from '../pages/workflow/pkPathway';
import { blockedPlan, pkFixtureFor } from './pkTestFixtures';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

const SCORE = {
  design_impact_score: { delivery: 87.52475247524752, toxicity: 0.8, cost: 80.75 },
  score_version: 'design-impact-adapter-0.1.0',
  component_scores: {
    delivery: { value: 87.52475247524752, scale: '0-100', meaning: 'delivery' },
    toxicity: { value: 0.8, scale: '0-10', meaning: 'toxicity' },
    cost: { value: 80.75, scale: '0-100', meaning: 'cost' },
  },
  normalized_inputs: { Size: 100 },
  warnings: [],
  prediction_basis: 'rule_based_physicochemical_heuristic',
  evidence_level: 'literature_informed_unvalidated',
  validation_status: 'not_experimentally_validated',
  limitations: ['Computational research-planning result only.'],
  scientific_source: 'core.scoring.compute_impact',
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

let calls: string[] = [];

function installFetch() {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    calls.push(url);
    const pk = pkFixtureFor(url);
    if (pk !== null) return json(pk);
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    if (url.endsWith('/api/v1/design/score')) return json(SCORE);
    if (url.includes('/api/v1/runs')) return json({ runs: [], total: 0 });
    return json({}, 404);
  }));
}

const legacyEngineCalls = () =>
  calls.filter((u) => u.endsWith('/api/v1/pk/simulate'));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider><App /></AuthProvider>
    </MemoryRouter>,
  );
}

/** Reach Step 3 with Breast Cancer / HER2-enriched / Trastuzumab. */
async function reachStep3(user: ReturnType<typeof userEvent.setup>) {
  renderAt('/workflow/disease');
  await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
  await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                           'Breast Cancer');
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Disease subtype' }),
    'HER2-enriched (ER-, PR-, HER2+)');
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Therapeutic agent' }),
    'Trastuzumab (Herceptin)');
  await user.click(
    screen.getByRole('button', { name: /Continue to design parameters/i }));
  await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
  await user.click(screen.getByRole('button', { name: /Continue to review/i }));
  await screen.findByRole('heading', { name: /Step 3/i, level: 2 });
}

async function chooseRoute(user: ReturnType<typeof userEvent.setup>,
                           route: string) {
  await user.selectOptions(
    await screen.findByLabelText(/Administration route/i), route);
}

beforeEach(() => { localStorage.clear(); installFetch(); });
afterEach(() => {
  vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear();
});

/* ===================================================================== */
describe('the routing decision (pure)', () => {
  const iv: PKPathwayState = { route: 'iv_infusion', mode: 'guided',
                               plan: blockedPlan() as never };
  const sc: PKPathwayState = { route: 'subcutaneous', mode: 'guided',
                               plan: null };

  it('never allows the depot engine for an intravenous route', () => {
    for (const route of ['iv_bolus', 'iv_infusion']) {
      const state = { ...iv, route };
      expect(isIntravenous(route)).toBe(true);
      expect(legacyDepotAllowed(state)).toBe(false);
      expect(mayCallLegacyEngine(state)).toBe(false);
      expect(shouldRequestRateConstants(state)).toBe(false);
    }
  });

  it('allows the depot engine for extravascular routes', () => {
    for (const route of ['subcutaneous', 'oral', 'intraperitoneal']) {
      const state = { ...sc, route };
      expect(legacyDepotAllowed(state)).toBe(true);
      expect(mayCallLegacyEngine(state)).toBe(true);
      expect(shouldRequestRateConstants(state)).toBe(true);
      expect(executionPath(state)).toBe('legacy_depot');
    }
  });

  it('never allows the depot engine before a route is chosen', () => {
    expect(legacyDepotAllowed(EMPTY_PK_PATHWAY)).toBe(false);
    expect(mayCallLegacyEngine(EMPTY_PK_PATHWAY)).toBe(false);
    expect(executionPath(EMPTY_PK_PATHWAY)).toBe('undetermined');
  });

  it('blocks an IV study with no reviewed parameter set', () => {
    expect(executionPath(iv)).toBe('blocked_no_parameter_set');
  });

  it('uses the route-aware engine when a plan is runnable', () => {
    const runnable = { ...iv, plan: { ...blockedPlan(), runnable: true } as never };
    expect(executionPath(runnable)).toBe('route_aware_guided');
    expect(executionPath({ ...runnable, mode: 'expert_research' }))
      .toBe('route_aware_expert');
  });

  it('describes an IV trastuzumab study in plain words', () => {
    expect(describeStudy('Trastuzumab (Herceptin)', 'iv_infusion'))
      .toBe('IV trastuzumab');
  });
});

/* ===================================================================== */
describe('the replacement explanation', () => {
  it('states the required message for IV trastuzumab', () => {
    const text = blockedExplanation('Trastuzumab (Herceptin)', 'iv_infusion',
                                    blockedPlan() as never);
    expect(text).toContain(
      'PK simulation is not yet operational for IV trastuzumab.');
    expect(text).toContain(
      'A reviewed, route-specific pharmacokinetic model and parameter set '
      + 'have not yet been added.');
    expect(text).toContain('Missing requirements include CL, Vc, Q, Vp');
    expect(text).toContain(
      'plus any nonlinear parameters required by the selected published model');
    expect(text).toContain(
      'No simulation has been executed and no PK results exist.');
  });

  it('never mentions the four first-order rate constants', () => {
    const text = blockedExplanation('Trastuzumab (Herceptin)', 'iv_infusion',
                                    blockedPlan() as never);
    expect(text).not.toMatch(/four first-order rate constants/i);
    expect(text).not.toMatch(/k_abs/i);
  });
});

/* ===================================================================== */
describe('guided IV trastuzumab on Step 3', () => {
  it('never displays the four-rate-constant request', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'iv_infusion');
    await screen.findByTestId('pk-blocked');

    expect(screen.queryByTestId('legacy-depot-inputs')).not.toBeInTheDocument();
    const body = document.body.textContent ?? '';
    expect(body).not.toMatch(/The dose and the four first-order rate constants/i);
  });

  it('requests no k_abs field', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'iv_infusion');
    await screen.findByTestId('pk-blocked');

    expect(screen.queryByRole('spinbutton',
                              { name: /Absorption rate constant/i }))
      .not.toBeInTheDocument();
    expect(await screen.findByTestId('k-abs-not-applicable'))
      .toHaveTextContent(/Not applicable/i);
  });

  it('says the depot constants do not apply', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'iv_infusion');
    expect(await screen.findByTestId('legacy-not-applicable'))
      .toHaveTextContent(/will not be sent to that engine/i);
  });

  it('states the replacement message verbatim', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'iv_infusion');
    const statement = await screen.findByTestId('pk-blocked-statement');
    expect(statement).toHaveTextContent(
      /PK simulation is not yet operational for IV trastuzumab/i);
    expect(statement).toHaveTextContent(/Missing requirements include/i);
    expect(statement).toHaveTextContent(
      /No simulation has been executed and no PK results exist/i);
  });

  it('states that the depot model is not offered as a fallback', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'iv_infusion');
    expect(await screen.findByTestId('pk-no-legacy-fallback'))
      .toHaveTextContent(/never occupies/i);
  });

  it('does not call the legacy depot engine when Run is pressed', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'iv_infusion');
    await screen.findByTestId('pk-blocked');

    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    // The design score still runs; the PK engine must not have been touched.
    expect(legacyEngineCalls()).toHaveLength(0);
  });
});

/* ===================================================================== */
describe('the Results page after a blocked IV study', () => {
  async function runBlockedIvStudy() {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'iv_infusion');
    await screen.findByTestId('pk-blocked');
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');
    return user;
  }

  it('shows the replacement message, not the legacy one', async () => {
    await runBlockedIvStudy();
    const reason = await screen.findByTestId('pk-empty-reason');
    expect(reason).toHaveTextContent(
      /PK simulation is not yet operational for IV trastuzumab/i);
    expect(reason).not.toHaveTextContent(
      /four first-order rate constants are required/i);
  });

  it('does not offer "Supply the required inputs"', async () => {
    await runBlockedIvStudy();
    await screen.findByTestId('pk-empty');
    expect(screen.queryByRole('button',
                              { name: /Supply the required inputs/i }))
      .not.toBeInTheDocument();
    expect(await screen.findByTestId('pk-back-to-review'))
      .toHaveTextContent(/Back to review/i);
  });

  it('shows no half-life, AUC or concentration profile', async () => {
    await runBlockedIvStudy();
    const empty = await screen.findByTestId('pk-empty');
    expect(within(empty).queryByText(/half-life/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('pk-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pk-cmax')).not.toBeInTheDocument();
  });

  it('states plainly that no PK results exist', async () => {
    await runBlockedIvStudy();
    expect(await screen.findByTestId('pk-empty-reason'))
      .toHaveTextContent(/no PK results exist/i);
  });
});

/* ===================================================================== */
describe('extravascular studies keep the legacy depot path', () => {
  it('offers the depot fields for a subcutaneous route', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'subcutaneous');
    expect(await screen.findByTestId('legacy-depot-inputs')).toBeInTheDocument();
    expect(screen.getByRole('spinbutton',
                            { name: /Absorption rate constant/i }))
      .toBeInTheDocument();
  });

  it('does not mark k_abs as not applicable for subcutaneous', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'subcutaneous');
    await screen.findByTestId('legacy-depot-inputs');
    expect(screen.queryByTestId('k-abs-not-applicable'))
      .not.toBeInTheDocument();
    expect(screen.queryByTestId('legacy-not-applicable'))
      .not.toBeInTheDocument();
  });

  it('keeps the route when navigating away and back', async () => {
    // The route is part of the study, not throwaway component state: losing it
    // would silently re-enable the depot engine for an IV study.
    const user = userEvent.setup();
    await reachStep3(user);
    await chooseRoute(user, 'subcutaneous');
    await screen.findByTestId('legacy-depot-inputs');

    await user.click(
      screen.getByRole('button', { name: /Back to design parameters/i }));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
    await user.click(screen.getByRole('button', { name: /Continue to review/i }));
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });

    expect(await screen.findByTestId('legacy-depot-inputs')).toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('expert research mode is separated and labelled', () => {
  it('is visibly separated with its own banner', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await user.selectOptions(await screen.findByLabelText(/Input mode/i),
                             'expert_research');
    const banner = await screen.findByTestId('pk-expert-banner');
    expect(banner).toHaveTextContent(/Expert research mode/i);
  });

  it('labels output as researcher-supplied exploratory, not validated',
     async () => {
       const user = userEvent.setup();
       await reachStep3(user);
       await user.selectOptions(await screen.findByLabelText(/Input mode/i),
                                'expert_research');
       const banner = await screen.findByTestId('pk-expert-banner');
       expect(banner).toHaveTextContent(/your own research/i);
       expect(banner).toHaveTextContent(/not a validated platform prediction/i);
     });

  it('requires model type, route, units, source and assumptions', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await user.selectOptions(await screen.findByLabelText(/Input mode/i),
                             'expert_research');
    const banner = await screen.findByTestId('pk-expert-banner');
    for (const requirement of [/model type/i, /administration route/i,
                               /units/i, /source reference/i, /assumptions/i]) {
      expect(banner).toHaveTextContent(requirement);
    }
  });

  it('states that k_abs is refused for IV routes in expert mode too', async () => {
    const user = userEvent.setup();
    await reachStep3(user);
    await user.selectOptions(await screen.findByLabelText(/Input mode/i),
                             'expert_research');
    expect(await screen.findByTestId('pk-expert-banner'))
      .toHaveTextContent(/refused for intravenous routes/i);
  });

  it('does not describe results as validated trastuzumab predictions',
     async () => {
       const user = userEvent.setup();
       await reachStep3(user);
       await user.selectOptions(await screen.findByLabelText(/Input mode/i),
                                'expert_research');
       await screen.findByTestId('pk-expert-banner');
       const body = document.body.textContent ?? '';
       expect(body).not.toMatch(/validated (trastuzumab )?prediction(?!s?\b.*not)/i);
     });
});
