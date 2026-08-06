/**
 * Which pharmacokinetic execution path a study may use.
 *
 * The defect this exists for
 * --------------------------
 * `pkInputsReady` was derived solely from whether the four rate-constant boxes
 * were filled in. It knew nothing about the administration route, so for
 * intravenous trastuzumab the workflow still:
 *
 *   * asked for `k_abs` and the other three rate constants;
 *   * offered "Supply the required inputs", directing the user to invent them;
 *   * would have sent the study to the legacy **depot** engine, which models
 *     first-order absorption from an administration site that an IV dose does
 *     not have.
 *
 * The route-aware plan was rendered alongside all of this but gated nothing.
 *
 * This module is the single decision point. Both Step 3 and the Results page
 * resolve through it, so the review screen and the results screen cannot
 * disagree about whether a simulation was permitted to run.
 */

import type { RunPlanResponse } from '../../api/types';

export type PKExecutionPath =
  /** No route chosen yet: nothing may run, nothing is claimed. */
  | 'undetermined'
  /** Route-aware engine, guided mode, with a reviewed parameter set. */
  | 'route_aware_guided'
  /** Route-aware engine with researcher-supplied parameters. */
  | 'route_aware_expert'
  /** Legacy depot engine. Only for routes that genuinely have absorption. */
  | 'legacy_depot'
  /** A reviewed parameter set does not exist for this therapeutic and route. */
  | 'blocked_no_parameter_set';

export interface PKPathwayState {
  /** Administration route id, or null when the user has not chosen one. */
  route: string | null;
  mode: 'guided' | 'expert_research';
  plan: RunPlanResponse | null;
}

export const EMPTY_PK_PATHWAY: PKPathwayState = {
  route: null,
  mode: 'guided',
  plan: null,
};

/** Routes for which the legacy depot model is scientifically compatible. */
const DEPOT_COMPATIBLE_ROUTES = new Set([
  'subcutaneous', 'oral', 'intraperitoneal',
]);

/** Routes with no absorption phase. `k_abs` is meaningless for these. */
const INTRAVENOUS_ROUTES = new Set(['iv_bolus', 'iv_infusion']);

export function isIntravenous(route: string | null): boolean {
  return route !== null && INTRAVENOUS_ROUTES.has(route);
}

/**
 * Whether the legacy depot engine may be used at all.
 *
 * False for every intravenous route — the depot model places the dose in an
 * absorption compartment, which an intravenous dose never occupies. False also
 * when no route has been chosen: running the depot model by default is exactly
 * the behaviour being corrected.
 */
export function legacyDepotAllowed(state: PKPathwayState): boolean {
  if (state.route === null) return false;
  return DEPOT_COMPATIBLE_ROUTES.has(state.route);
}

export function executionPath(state: PKPathwayState): PKExecutionPath {
  if (state.route === null) return 'undetermined';
  if (state.plan?.runnable) {
    return state.mode === 'expert_research'
      ? 'route_aware_expert' : 'route_aware_guided';
  }
  if (legacyDepotAllowed(state)) return 'legacy_depot';
  return 'blocked_no_parameter_set';
}

/**
 * Whether the four legacy rate-constant fields may be requested.
 *
 * Only on the legacy depot path. In every other case asking for them would
 * either be meaningless (intravenous) or would invite the user to override
 * parameters that should come from a cited set.
 */
export function shouldRequestRateConstants(state: PKPathwayState): boolean {
  return executionPath(state) === 'legacy_depot';
}

/** Whether the legacy depot engine may be called for this study. */
export function mayCallLegacyEngine(state: PKPathwayState): boolean {
  return executionPath(state) === 'legacy_depot';
}

/**
 * A short human label for the therapeutic and route, e.g. "IV trastuzumab".
 *
 * Used only in explanatory prose. Falls back to the raw values rather than
 * inventing a name.
 */
export function describeStudy(therapeutic: string | undefined,
                              route: string | null): string {
  const drug = (therapeutic ?? '').replace(/\s*\(.*\)\s*$/, '').trim();
  const prefix = route === 'iv_bolus' ? 'IV bolus '
    : route === 'iv_infusion' ? 'IV '
    : route === 'subcutaneous' ? 'subcutaneous '
    : route === 'oral' ? 'oral '
    : route === 'intraperitoneal' ? 'intraperitoneal '
    : '';
  if (!drug) return prefix ? `${prefix}administration`.trim() : 'this study';
  return `${prefix}${drug.toLowerCase()}`;
}

/**
 * The statement shown when no reviewed parameter set exists.
 *
 * Replaces the legacy "The dose and the four first-order rate constants are
 * required…", which was scientifically wrong for an intravenous therapeutic:
 * the constants it asked for belong to a depot model that does not apply.
 */
export function blockedExplanation(
  therapeutic: string | undefined,
  route: string | null,
  plan: RunPlanResponse | null,
): string {
  const study = describeStudy(therapeutic, route);
  const missing = plan?.missing_inputs?.length
    ? plan.missing_inputs.join(', ')
    : 'CL, Vc, Q and Vp';
  return (
    `PK simulation is not yet operational for ${study}. A reviewed, `
    + 'route-specific pharmacokinetic model and parameter set have not yet '
    + `been added. Missing requirements include ${missing}, plus any `
    + 'nonlinear parameters required by the selected published model. '
    + 'No simulation has been executed and no PK results exist.'
  );
}
