/**
 * Shared fixtures for the route-aware PK endpoints.
 *
 * The legacy depot fields on Step 3 are now shown only for a route that
 * genuinely has an absorption phase. Tests that exercise that path therefore
 * have to choose one, which is itself the point: the depot model is reachable
 * where it is scientifically compatible and unreachable where it is not.
 */

/** Minimal route list covering one depot route and both IV routes. */
export const PK_ROUTES_RESPONSE = {
  notice: 'Research Use Only — This simulation does not recommend treatment, '
    + 'determine an individual dose, or replace clinical pharmacology and '
    + 'medical judgment.',
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
      description: 'The dose is placed at the injection site and transferred '
        + 'into the central compartment by a first-order absorption process.',
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

/** A blocked plan: no reviewed parameter set exists for the combination. */
export function blockedPlan(therapeutic = 'Trastuzumab (Herceptin)',
                            route = 'iv_infusion') {
  return {
    therapeutic, route, mode: 'guided',
    model_label: 'Linear two-compartment',
    engine_version: 'pk-route-aware-two-compartment-0.1.0',
    library_version: 'pk-parameter-library-0.1.0',
    runnable: false,
    blocking_reasons: [
      `No reviewed pharmacokinetic parameter set exists for ${therapeutic}.`,
    ],
    missing_inputs: ['CL', 'Vc', 'Q', 'Vp'],
    not_applicable: route.startsWith('iv_') ? ['k_abs'] : [],
    not_represented: [],
    warnings: [],
    suitability: 'Not yet operational for this therapeutic/route combination.',
    notice: PK_ROUTES_RESPONSE.notice,
    inputs: [
      { name: 'duration_h', label: 'Simulation duration', value: 48, unit: 'h',
        source: 'simulation_setting', source_label: 'Simulation setting',
        report_field: null, confirmation_status: null, formula: null,
        source_values: null, editable: true },
    ],
    parameter_set: null,
  };
}

/**
 * Route a PK request to the right fixture.
 *
 * Returns null when the URL is not a PK endpoint, so callers can fall through
 * to their own handlers.
 */
export function pkFixtureFor(url: string): unknown | null {
  if (url.includes('/api/v1/pk/administration-routes')) {
    return PK_ROUTES_RESPONSE;
  }
  if (url.includes('/api/v1/pk/plan')) {
    const route = /route=([a-z_]+)/.exec(url)?.[1] ?? 'iv_infusion';
    const therapeutic = decodeURIComponent(
      /therapeutic=([^&]*)/.exec(url)?.[1] ?? 'Unknown').replace(/\+/g, ' ');
    return blockedPlan(therapeutic, route);
  }
  return null;
}

/** Select a depot-compatible route so the legacy fields become available. */
export async function chooseDepotRoute(
  screen: { findByLabelText: (m: RegExp) => Promise<HTMLElement> },
  user: { selectOptions: (el: HTMLElement, v: string) => Promise<void> },
): Promise<void> {
  const select = await screen.findByLabelText(/Administration route/i);
  await user.selectOptions(select, 'subcutaneous');
}
