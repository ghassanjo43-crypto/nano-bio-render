/**
 * Route-aware pharmacokinetic input panel.
 *
 * What changed and why
 * --------------------
 * The previous panel asked every user for an absorption rate constant `k_abs`
 * regardless of how the drug is given. For intravenous trastuzumab there is no
 * absorption phase and no depot — and `k_abs` is genuinely consumed by the old
 * depot engine, so any number entered silently shaped the reported profile of a
 * drug that has no absorption step.
 *
 * This panel asks the server which model the selected route implies, and renders
 * only the fields that model genuinely uses. Fields the route makes meaningless
 * are shown as **Not applicable** with the reason, rather than hidden silently —
 * a user who expected to enter `k_abs` should learn why it is absent.
 *
 * Nothing here computes a pharmacokinetic value. Every number displayed comes
 * from the server's run plan.
 */

import { useCallback, useEffect, useState } from 'react';
import { getAdministrationRoutes, getRunPlan } from '../../api/client';
import type {
  AdministrationRouteSpec, RunPlanResponse, WorkspaceErrorResponse,
} from '../../api/types';
import {
  Alert, Badge, Button, Card, SelectField, SkeletonBlock,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import {
  RESEARCH_USE_ONLY_NOTICE, SOURCE_CATEGORIES,
  fallbackSourceLabel, toneForSource,
} from './pkInputSources';
import { blockedExplanation, isIntravenous, type PKPathwayState }
  from './pkPathway';
import './RoutedPKPanel.css';

export interface RoutedPKPanelProps {
  therapeutic: string;
  /**
   * Previously chosen route and mode, so the selection survives navigating
   * away from Step 3 and back. Without this the panel remounted empty and the
   * study silently lost its route — and with it the reason the legacy depot
   * engine was off-limits.
   */
  initial?: PKPathwayState;
  /**
   * Reports the route, mode and plan upward. The parent stores it so the whole
   * workflow — including the Results page — gates on the same decision.
   */
  onPathwayChange?: (state: PKPathwayState) => void;
}

export default function RoutedPKPanel({ therapeutic, onPathwayChange, initial }:
                                      RoutedPKPanelProps) {
  const [routes, setRoutes] = useState<AdministrationRouteSpec[] | null>(null);
  const [route, setRoute] = useState<string>(initial?.route ?? '');
  const [mode, setMode] = useState<'guided' | 'expert_research'>(
    initial?.mode ?? 'guided');
  const [plan, setPlan] = useState<RunPlanResponse | null>(null);
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  // Distinguishes "the planning service is not reachable" from "the service
  // answered and the combination is blocked". The two look nothing alike to a
  // user, and conflating them previously produced a bare "HTTP 404 Not Found".
  const [serviceDown, setServiceDown] = useState(false);
  const [showWorking, setShowWorking] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      const result = await getAdministrationRoutes(controller.signal);
      if (result.status === 'error') {
        setError(result.error);
        setServiceDown(true);
        return;
      }
      setServiceDown(false);
      setRoutes(result.data.routes);
    })();
    return () => controller.abort();
  }, []);

  const refreshPlan = useCallback(async (signal?: AbortSignal) => {
    if (!route || !therapeutic) {
      setPlan(null);
      onPathwayChange?.({ route: route || null, mode, plan: null });
      return;
    }
    const result = await getRunPlan({ therapeutic, route, mode }, signal);
    if (result.status === 'error') {
      setError(result.error);
      setServiceDown(true);
      // The plan is cleared, not left stale. Without a plan there is no
      // parameter set, no derived constant and no Run action — a failed
      // request must never leave the screen in a runnable-looking state.
      setPlan(null);
      // The route is still reported: it is what makes the legacy depot engine
      // off-limits for an intravenous study even when planning is unreachable.
      onPathwayChange?.({ route, mode, plan: null });
      return;
    }
    setError(null);
    setServiceDown(false);
    setPlan(result.data);
    onPathwayChange?.({ route, mode, plan: result.data });
  }, [therapeutic, route, mode, onPathwayChange]);

  useEffect(() => {
    const controller = new AbortController();
    // Changing the route invalidates any confirmation: the fields, the units
    // and the compatible parameter sets are all different now.
    setConfirmed(false);
    void refreshPlan(controller.signal);
    return () => controller.abort();
  }, [refreshPlan]);

  const routeSpec = routes?.find((r) => r.route === route);

  return (
    <Card
      title="Pharmacokinetic simulation inputs"
      subtitle={
        'Inputs are grouped by where they genuinely come from. A medical '
        + 'report does not contain model rate constants, and this screen no '
        + 'longer implies that it does.'
      }
      accent
    >
      <Alert tone="warn" title="Research Use Only">
        <p>{RESEARCH_USE_ONLY_NOTICE}</p>
      </Alert>

      {serviceDown && (
        <div data-testid="pk-service-unavailable">
          <Alert tone="danger" title="Pharmacokinetic planning unavailable">
            <p>
              The PK planning service is unavailable. No simulation has been run
              and no parameters were inferred.
            </p>
            <p className="rpk__nodefault">
              Nothing on this screen has been substituted or estimated. The
              administration route, the model and its parameters are all
              determined by the planning service, so no pharmacokinetic input
              is offered until it responds.
            </p>
            {error && (
              <p className="mono rpk__detail">
                {error.message}
                {error.detail ? ` — ${error.detail}` : ''}
              </p>
            )}
          </Alert>
        </div>
      )}

      {/* ------------------------------------------------- route selection */}
      <div className="rpk__controls">
        <SelectField
          id="pk-route" label="Administration route" value={route}
          onChange={(e) => setRoute(e.target.value)}
          options={[
            { value: '', label: 'Select a route…' },
            ...(routes ?? []).map((r) => ({ value: r.route, label: r.label })),
          ]}
        />
        <SelectField
          id="pk-mode" label="Input mode" value={mode}
          onChange={(e) => setMode(e.target.value as typeof mode)}
          options={[
            { value: 'guided', label: 'Guided (reviewed parameters)' },
            { value: 'expert_research', label: 'Expert research mode' },
          ]}
        />
      </div>

      {mode === 'expert_research' && (
        <div className="rpk__expert" data-testid="pk-expert-banner">
          <Badge tone="warn">Expert research mode</Badge>
          <p>
            Parameters you supply here are <strong>your own research
            inputs</strong>. Any result produced from them is a
            researcher-supplied exploratory result — it is not a validated
            platform prediction, and must not be described as a validated
            prediction for this therapeutic.
          </p>
          <p className="rpk__nodefault">
            A parameter set must declare its model type, administration route,
            values with units, source reference and assumptions before it can be
            used. An absorption rate constant is refused for intravenous routes
            in expert mode exactly as it is in guided mode.
          </p>
        </div>
      )}

      {routeSpec && (
        <div className="rpk__routeinfo" data-testid="route-description">
          <p>{routeSpec.description}</p>
          {!routeSpec.has_absorption_phase && (
            <p className="rpk__nokabs" data-testid="k-abs-not-applicable">
              <Icon name="info" size={15} />{' '}
              <strong>Absorption rate constant (k_abs): Not applicable.</strong>{' '}
              {routeSpec.label} administration has no absorption phase and no
              depot compartment, so this parameter has no role in the equations.
            </p>
          )}
          {routeSpec.fixed_bioavailability !== null && (
            <p className="rpk__fixedf">
              Bioavailability (F) = {routeSpec.fixed_bioavailability}.{' '}
              {routeSpec.fixed_bioavailability_reason}
            </p>
          )}
        </div>
      )}

      {!route && !serviceDown && (
        <p className="rpk__prompt">
          Select an administration route. The route determines which model runs,
          which inputs apply, and which parameter sets are compatible — so
          nothing further is shown until it is chosen.
        </p>
      )}

      {route && plan === null && !serviceDown && <SkeletonBlock lines={4} />}

      {/* --------------------------------------------------- blocked state */}
      {plan && !plan.runnable && (
        <div data-testid="pk-blocked">
        <Alert tone="warn" title={plan.suitability || 'Cannot run'}>
          <ul className="rpk__blocked">
            {plan.blocking_reasons.map((r) => <li key={r}>{r}</li>)}
          </ul>
          {plan.missing_inputs.length > 0 && (
            <p>
              <strong>Missing:</strong>{' '}
              <span className="mono">{plan.missing_inputs.join(', ')}</span>
            </p>
          )}
          <p data-testid="pk-blocked-statement">
            {blockedExplanation(therapeutic, route, plan)}
          </p>
          <p className="rpk__nodefault">
            No values have been substituted, and none have been copied from
            another therapeutic, formulation, route or population. The study can
            still be saved as incomplete.
          </p>
          {isIntravenous(route) && (
            <p className="rpk__nodefault" data-testid="pk-no-legacy-fallback">
              The legacy depot model is <strong>not</strong> offered as a
              fallback: it places the dose in an absorption compartment that an
              intravenous dose never occupies.
            </p>
          )}
        </Alert>
        </div>
      )}

      {/* -------------------------------------------- the four categories */}
      {plan && (
        <div className="rpk__categories" data-testid="pk-categories">
          {SOURCE_CATEGORIES.map((category) => {
            const items = plan.inputs.filter(
              (i) => (category.sources as readonly string[]).includes(i.source));
            return (
              <section key={category.id} className="rpk__category"
                       data-testid={`pk-category-${category.id}`}>
                <h4>
                  <Icon name={category.icon as never} size={16} />
                  {category.title}
                </h4>
                <p className="rpk__catdesc">{category.description}</p>

                {items.length === 0 ? (
                  <p className="rpk__empty">
                    No inputs in this category for the selected route and model.
                  </p>
                ) : (
                  <ul className="rpk__inputs">
                    {items.map((i) => (
                      <li key={i.name} data-testid={`pk-input-${i.name}`}>
                        <span className="rpk__name">{i.label}</span>
                        <span className="rpk__value mono">
                          {i.value === null ? '—' : String(i.value)} {i.unit}
                        </span>
                        <Badge tone={toneForSource(i.source)}>
                          {i.source_label || fallbackSourceLabel(i.source)}
                        </Badge>
                        {!i.editable && (
                          <span className="rpk__locked">
                            <Icon name="shield" size={13} /> not editable
                          </span>
                        )}
                        {i.formula && (
                          <details className="rpk__working">
                            <summary>Show the calculation</summary>
                            <p className="mono">{i.formula}</p>
                            <dl>
                              {Object.entries(i.source_values ?? {}).map(
                                ([k, v]) => (
                                  <div key={k}>
                                    <dt>{k}</dt><dd className="mono">{v}</dd>
                                  </div>
                                ))}
                            </dl>
                          </details>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}

      {/* ------------------------------------------------ model provenance */}
      {plan?.parameter_set && (
        <details className="rpk__provenance" open={showWorking}
                 onToggle={(e) => setShowWorking(e.currentTarget.open)}
                 data-testid="pk-provenance">
          <summary>Model and parameter provenance</summary>
          <dl className="rpk__meta">
            <div><dt>Model</dt><dd>{plan.model_label}</dd></div>
            <div><dt>Engine version</dt>
                 <dd className="mono">{plan.engine_version}</dd></div>
            <div><dt>Parameter set</dt>
                 <dd className="mono">
                   {plan.parameter_set.id}@{plan.parameter_set.version}
                 </dd></div>
            <div><dt>Library version</dt>
                 <dd className="mono">{plan.library_version}</dd></div>
            <div><dt>Population</dt><dd>{plan.parameter_set.population}</dd></div>
            <div><dt>Source</dt>
                 <dd>{plan.parameter_set.source_citation}</dd></div>
            <div><dt>Validation status</dt>
                 <dd>{plan.parameter_set.validation_status}</dd></div>
            <div><dt>Reviewed</dt><dd>{plan.parameter_set.date_reviewed}</dd></div>
          </dl>
          {plan.not_represented.length > 0 && (
            <>
              <h5>Known PK features this model does not represent</h5>
              <ul>
                {plan.not_represented.map((n) => <li key={n}>{n}</li>)}
              </ul>
            </>
          )}
        </details>
      )}

      {plan && plan.warnings.length > 0 && (
        <Alert tone="info" title="Limitations of this configuration">
          <ul className="rpk__warnings">
            {plan.warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </Alert>
      )}

      {/* ------------------------------------------ pre-run confirmation */}
      {plan?.runnable && (
        <div className="rpk__confirm" data-testid="pk-confirm">
          <label>
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              data-testid="confirm-provenance"
            />
            I have reviewed the input sources, the parameter set and its
            limitations above, and confirm this configuration.
          </label>
          <Button disabled={!confirmed} data-testid="run-routed-simulation"
                  iconLeft={<Icon name="play" size={15} />}>
            Run simulation
          </Button>
        </div>
      )}
    </Card>
  );
}
