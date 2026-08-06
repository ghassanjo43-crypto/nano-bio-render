/**
 * Route-aware PK panel: the interface half of the k_abs defect.
 *
 * The defect: the PK screen asked for an absorption rate constant regardless of
 * administration route, while the selected therapeutic was intravenous
 * trastuzumab. These tests pin that an IV route states k_abs is not applicable,
 * that a therapeutic with no reviewed parameter set is blocked rather than run,
 * and that inputs are grouped by their genuine source rather than presented as
 * if they all came from the medical report.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import RoutedPKPanel from '../pages/workflow/RoutedPKPanel';
import {
  SOURCE_CATEGORIES, fallbackSourceLabel, toneForSource,
} from '../pages/workflow/pkInputSources';

const ROUTES = {
  notice: 'Research Use Only — This simulation does not recommend treatment.',
  routes: [
    {
      route: 'iv_bolus', label: 'Intravenous bolus',
      input_function: 'instantaneous_central',
      description: 'The entire dose is placed in the central compartment at '
        + 'time zero. There is no absorption phase and no depot compartment.',
      has_absorption_phase: false,
      required_dosing_inputs: ['dose'],
      not_applicable_inputs: ['k_abs', 'infusion_duration_h'],
      bioavailability_is_free: false,
      fixed_bioavailability: 1.0,
      fixed_bioavailability_reason: 'Delivered directly into the circulation.',
      notes: [],
    },
    {
      route: 'iv_infusion', label: 'Intravenous infusion',
      input_function: 'zero_order_central',
      description: 'Constant-rate input into the central compartment. There is '
        + 'no absorption phase and no depot compartment.',
      has_absorption_phase: false,
      required_dosing_inputs: ['dose', 'infusion_duration_h'],
      not_applicable_inputs: ['k_abs'],
      bioavailability_is_free: false,
      fixed_bioavailability: 1.0,
      fixed_bioavailability_reason: 'Delivered directly into the circulation.',
      notes: [],
    },
    {
      route: 'subcutaneous', label: 'Subcutaneous',
      input_function: 'first_order_depot',
      description: 'Absorbed first-order from the injection site.',
      has_absorption_phase: true,
      required_dosing_inputs: ['dose', 'k_abs'],
      not_applicable_inputs: [],
      bioavailability_is_free: true,
      fixed_bioavailability: null,
      fixed_bioavailability_reason: null,
      notes: [],
    },
  ],
};

const BLOCKED_PLAN = {
  therapeutic: 'Trastuzumab (Herceptin)',
  route: 'iv_infusion',
  mode: 'guided',
  model_label: 'Linear two-compartment, intravenous infusion input',
  engine_version: 'pk-route-aware-two-compartment-0.1.0',
  library_version: 'pk-parameter-library-0.1.0',
  runnable: false,
  blocking_reasons: [
    'No reviewed pharmacokinetic parameter set exists for '
    + 'Trastuzumab (Herceptin) administered by intravenous infusion.',
  ],
  missing_inputs: ['CL', 'Vc', 'Q', 'Vp'],
  not_applicable: ['k_abs'],
  not_represented: [],
  warnings: ['No parameters have been substituted, and none have been copied '
             + 'from another therapeutic, formulation, route or population.'],
  suitability: 'Not yet operational for this therapeutic/route combination '
    + '(Trastuzumab (Herceptin) / Intravenous infusion).',
  notice: ROUTES.notice,
  inputs: [
    { name: 'duration_h', label: 'Simulation duration', value: 48, unit: 'h',
      source: 'simulation_setting', source_label: 'Simulation setting',
      report_field: null, confirmation_status: null, formula: null,
      source_values: null, editable: true },
    { name: 'time_step_h', label: 'Integration time step', value: 0.01,
      unit: 'h', source: 'simulation_setting',
      source_label: 'Simulation setting', report_field: null,
      confirmation_status: null, formula: null, source_values: null,
      editable: true },
  ],
  parameter_set: null,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

function installFetch(plan: unknown = BLOCKED_PLAN) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/pk/administration-routes')) return json(ROUTES);
    if (url.includes('/pk/plan')) return json(plan);
    return json({}, 404);
  }));
}

beforeEach(() => installFetch());
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function selectRoute(route: string) {
  const user = userEvent.setup();
  render(<RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
  const select = await screen.findByLabelText(/Administration route/i);
  await user.selectOptions(select, route);
  return user;
}

/* ===================================================================== */
describe('the four input-source categories', () => {
  it('declares exactly four categories', () => {
    expect(SOURCE_CATEGORIES).toHaveLength(4);
    expect(SOURCE_CATEGORIES.map((c) => c.id))
      .toEqual(['patient', 'protocol', 'parameters', 'simulation']);
  });

  it('never files a library parameter under patient data', () => {
    const patient = SOURCE_CATEGORIES.find((c) => c.id === 'patient')!;
    expect(patient.sources).not.toContain('parameter_library');
    expect(patient.sources).not.toContain('derived');
  });

  it('never files a simulation setting under patient data', () => {
    const patient = SOURCE_CATEGORIES.find((c) => c.id === 'patient')!;
    expect(patient.sources).not.toContain('simulation_setting');
  });

  it('states that a selected therapeutic is not a prescription', () => {
    const protocol = SOURCE_CATEGORIES.find((c) => c.id === 'protocol')!;
    expect(protocol.description).toMatch(/not evidence that it was prescribed/i);
  });

  it('renders every category once a route is chosen', async () => {
    await selectRoute('iv_infusion');
    for (const category of SOURCE_CATEGORIES) {
      expect(await screen.findByTestId(`pk-category-${category.id}`))
        .toBeInTheDocument();
    }
  });

  it('labels an unrecognised source honestly rather than guessing', () => {
    expect(fallbackSourceLabel('something_new')).toBe('Source not recorded');
    expect(toneForSource('something_new')).toBe('neutral');
  });
});

/* ===================================================================== */
describe('intravenous routes do not request k_abs', () => {
  it.each(['iv_bolus', 'iv_infusion'])(
    '%s states k_abs is not applicable', async (route) => {
      await selectRoute(route);
      const note = await screen.findByTestId('k-abs-not-applicable');
      expect(note).toHaveTextContent(/Not applicable/i);
      expect(note).toHaveTextContent(/no absorption phase/i);
    });

  it.each(['iv_bolus', 'iv_infusion'])(
    '%s renders no k_abs entry field', async (route) => {
      await selectRoute(route);
      await screen.findByTestId('route-description');
      expect(screen.queryByLabelText(/Absorption rate constant/i))
        .not.toBeInTheDocument();
      expect(screen.queryByTestId('pk-input-k_abs')).not.toBeInTheDocument();
    });

  it('does not describe intravenous administration as a depot', async () => {
    await selectRoute('iv_infusion');
    const description = await screen.findByTestId('route-description');
    expect(description).toHaveTextContent(/no depot compartment/i);
  });

  it('states that bioavailability is fixed by the route', async () => {
    await selectRoute('iv_bolus');
    const description = await screen.findByTestId('route-description');
    expect(description).toHaveTextContent(/Bioavailability \(F\) = 1/);
  });

  it('shows the absorption note only for extravascular routes', async () => {
    await selectRoute('subcutaneous');
    await screen.findByTestId('route-description');
    expect(screen.queryByTestId('k-abs-not-applicable'))
      .not.toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('missing parameter sets block execution', () => {
  it('reports the combination as not yet operational', async () => {
    await selectRoute('iv_infusion');
    const blocked = await screen.findByTestId('pk-blocked');
    expect(blocked).toHaveTextContent(/Not yet operational/i);
  });

  it('names exactly what is missing', async () => {
    await selectRoute('iv_infusion');
    const blocked = await screen.findByTestId('pk-blocked');
    expect(blocked).toHaveTextContent('CL, Vc, Q, Vp');
  });

  it('states that nothing was substituted or borrowed', async () => {
    await selectRoute('iv_infusion');
    const blocked = await screen.findByTestId('pk-blocked');
    expect(blocked).toHaveTextContent(/No values have been substituted/i);
    expect(blocked).toHaveTextContent(/another therapeutic, formulation, route/i);
  });

  it('offers no Run action while blocked', async () => {
    await selectRoute('iv_infusion');
    await screen.findByTestId('pk-blocked');
    expect(screen.queryByTestId('run-routed-simulation'))
      .not.toBeInTheDocument();
    expect(screen.queryByTestId('confirm-provenance')).not.toBeInTheDocument();
  });

  it('shows no fabricated number anywhere while blocked', async () => {
    const { container } = render(
      <RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    const user = userEvent.setup();
    await user.selectOptions(
      await screen.findByLabelText(/Administration route/i), 'iv_infusion');
    await screen.findByTestId('pk-blocked');
    // The only numbers on screen are the simulation settings and the fixed
    // bioavailability — never a concentration, half-life, AUC or rate constant.
    const params = screen.getByTestId('pk-category-parameters');
    expect(params).toHaveTextContent(/No inputs in this category/i);
    expect(container.textContent).not.toMatch(/half-life|AUC|C_?max/i);
  });
});

/* ===================================================================== */
describe('run gating and provenance confirmation', () => {
  const RUNNABLE = {
    ...BLOCKED_PLAN,
    runnable: true,
    blocking_reasons: [],
    missing_inputs: ['dose', 'infusion_duration_h'],
    suitability: 'Two Compartment Linear parameters for Test Compound.',
    warnings: ['Limited exploratory model — not validated for individual '
               + 'dosing or clinical decision-making.'],
    not_represented: ['Target-mediated (nonlinear) elimination.'],
    inputs: [
      ...BLOCKED_PLAN.inputs,
      { name: 'CL', label: 'CL', value: 0.5, unit: 'L/h',
        source: 'parameter_library', source_label: 'From cited parameter set',
        report_field: null, confirmation_status: null, formula: null,
        source_values: { parameter_set: 'test@1.0.0' }, editable: false },
      { name: 'k_el', label: 'k_el', value: 0.1, unit: '1/h',
        source: 'derived',
        source_label: 'Calculated from cited model parameters',
        report_field: null, confirmation_status: null,
        formula: 'k_el = CL / Vc',
        source_values: { CL: '0.5 L/h', Vc: '5.0 L' }, editable: false },
    ],
    parameter_set: {
      id: 'test', version: '1.0.0', therapeutic: 'Test Compound',
      formulation: 'solution', route: 'iv_infusion',
      population: 'Synthetic test values.', indication: null,
      model_structure: 'two_compartment_linear',
      source_citation: 'Synthetic values for testing.',
      validation_status: 'researcher_supplied', date_reviewed: '2026-08-02',
      limitations: ['Synthetic test values.'], covariates: [],
      not_represented: ['Target-mediated (nonlinear) elimination.'],
    },
  };

  it('requires explicit confirmation before running', async () => {
    installFetch(RUNNABLE);
    await selectRoute('iv_infusion');
    const run = await screen.findByTestId('run-routed-simulation');
    expect(run).toBeDisabled();

    await userEvent.setup().click(screen.getByTestId('confirm-provenance'));
    expect(screen.getByTestId('run-routed-simulation')).toBeEnabled();
  });

  it('shows the derivation formula and its source values', async () => {
    installFetch(RUNNABLE);
    await selectRoute('iv_infusion');
    const derived = await screen.findByTestId('pk-input-k_el');
    expect(derived).toHaveTextContent('Calculated from cited model parameters');
    expect(within(derived).getByText('k_el = CL / Vc')).toBeInTheDocument();
    expect(derived).toHaveTextContent('0.5 L/h');
  });

  it('marks derived and library values as not editable', async () => {
    installFetch(RUNNABLE);
    await selectRoute('iv_infusion');
    for (const name of ['CL', 'k_el']) {
      expect(await screen.findByTestId(`pk-input-${name}`))
        .toHaveTextContent(/not editable/i);
    }
  });

  it('surfaces the limited-exploratory-model label', async () => {
    installFetch(RUNNABLE);
    await selectRoute('iv_infusion');
    expect(await screen.findByText(/Limited exploratory model/i))
      .toBeInTheDocument();
  });

  it('lists what the model does not represent', async () => {
    installFetch(RUNNABLE);
    await selectRoute('iv_infusion');
    const provenance = await screen.findByTestId('pk-provenance');
    expect(provenance).toHaveTextContent(/does not represent/i);
    expect(provenance).toHaveTextContent(/Target-mediated/i);
  });

  it('records the parameter set and engine versions for reproducibility',
     async () => {
       installFetch(RUNNABLE);
       await selectRoute('iv_infusion');
       const provenance = await screen.findByTestId('pk-provenance');
       expect(provenance).toHaveTextContent('test@1.0.0');
       expect(provenance).toHaveTextContent('pk-route-aware-two-compartment-0.1.0');
       expect(provenance).toHaveTextContent('pk-parameter-library-0.1.0');
     });

  it('shows the population the parameters describe', async () => {
    installFetch(RUNNABLE);
    await selectRoute('iv_infusion');
    expect(await screen.findByTestId('pk-provenance'))
      .toHaveTextContent(/Synthetic test values/);
  });
});

/* ===================================================================== */
describe('research-use-only protection', () => {
  it('displays the notice before any route is chosen', async () => {
    render(<RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    // Appears as the alert title and inside the notice body.
    expect((await screen.findAllByText(/Research Use Only/i)).length)
      .toBeGreaterThan(0);
    expect(screen.getByText(/does not recommend treatment/i))
      .toBeInTheDocument();
  });

  it('shows nothing until a route is selected', () => {
    render(<RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    expect(screen.queryByTestId('pk-categories')).not.toBeInTheDocument();
    expect(screen.getByText(/Select an administration route/i))
      .toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('planning service unavailable (the HTTP 404 defect)', () => {
  /**
   * Step 3 showed a bare "The service returned HTTP 404 / Not Found" because
   * the running backend predated the route module. The message told the user
   * nothing about what it meant for their study.
   */
  function install404() {
    vi.stubGlobal('fetch', vi.fn(async () =>
      json({ detail: 'Not Found' }, 404)));
  }

  it('states the service is unavailable, not a bare HTTP code', async () => {
    install404();
    render(<RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    const panel = await screen.findByTestId('pk-service-unavailable');
    expect(panel).toHaveTextContent(
      /The PK planning service is unavailable/i);
  });

  it('states that nothing was run and nothing was inferred', async () => {
    install404();
    render(<RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    const panel = await screen.findByTestId('pk-service-unavailable');
    expect(panel).toHaveTextContent(/No simulation has been run/i);
    expect(panel).toHaveTextContent(/no parameters were inferred/i);
  });

  it('does not proceed to PK input', async () => {
    install404();
    render(<RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    await screen.findByTestId('pk-service-unavailable');
    expect(screen.queryByTestId('pk-categories')).not.toBeInTheDocument();
    expect(screen.queryByTestId('run-routed-simulation'))
      .not.toBeInTheDocument();
    expect(screen.queryByTestId('confirm-provenance')).not.toBeInTheDocument();
  });

  it('offers no rate-constant field for the user to invent', async () => {
    install404();
    render(<RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    await screen.findByTestId('pk-service-unavailable');
    for (const label of [/Absorption rate constant/i, /Elimination rate/i,
                         /transfer/i]) {
      expect(screen.queryByLabelText(label)).not.toBeInTheDocument();
    }
  });

  it('shows no scientific value of any kind', async () => {
    install404();
    const { container } = render(
      <RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    await screen.findByTestId('pk-service-unavailable');
    expect(container.textContent).not.toMatch(/half-life|AUC|C_?max|mg\/L/i);
  });

  it('clears a previously loaded plan when a later request fails', async () => {
    // A stale plan left on screen after a failure would look runnable.
    const user = await selectRoute('iv_infusion');
    await screen.findByTestId('pk-categories');

    install404();
    await user.selectOptions(
      screen.getByLabelText(/Administration route/i), 'iv_bolus');

    await screen.findByTestId('pk-service-unavailable');
    expect(screen.queryByTestId('pk-categories')).not.toBeInTheDocument();
  });

  it('still shows the Research Use Only notice', async () => {
    install404();
    render(<RoutedPKPanel therapeutic="Trastuzumab (Herceptin)" />);
    await screen.findByTestId('pk-service-unavailable');
    expect((await screen.findAllByText(/Research Use Only/i)).length)
      .toBeGreaterThan(0);
  });
});
