/**
 * Step 3 — Review & Run Simulation.
 *
 * Mirrors the legacy `pages/2_Run_Simulation.py` position in the sequence:
 * confirm the complete session, then execute.
 *
 * What "Run" actually does, stated plainly on the page:
 *   • the **design impact score** is calculated by the migrated, verified
 *     scoring engine;
 *   • the **pharmacokinetic simulation** is calculated by the migrated
 *     two-compartment engine — but ONLY when every scientifically required
 *     input is present and valid. Otherwise it does not run, and the page says
 *     so instead of producing a curve from assumed kinetics;
 *   • the assessment engines still do not run, and nothing is fabricated for
 *     them.
 *
 * The PK inputs are collected here rather than in Step 2 because they are
 * simulation inputs, not formulation properties — the same division the legacy
 * simulation page made. Step 2 is unchanged by this slice.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { scoreDesign, simulatePk } from '../../api/client';
import { Alert, Badge, Button, Card, DataTable, TextField }
  from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { useWorkflow } from '../../workflow/WorkflowContext';
import { STEPS as FIELD_SECTIONS, buildRequest, reviewRows } from '../design/schema';
import {
  PK_FIELDS, buildPkRequest, pkReviewRows, validatePkField,
} from './pkSchema';
import RoutedPKPanel from './RoutedPKPanel';
import {
  isIntravenous, mayCallLegacyEngine, shouldRequestRateConstants,
} from './pkPathway';
import { StepActions } from './WorkflowLayout';
import PathwayNav, { PathwayProgress } from '../../workflow/PathwayNav';
import PathwayBanner from '../../workflow/PathwayBanner';
import './Step3Review.css';

export default function Step3Review() {
  const navigate = useNavigate();
  const {
    session, setPkValue, setResult, setPkResult, reachStep, saveDraft,
    pkInputsReady, pkPathway, setPkPathway,
  } = useWorkflow();
  const [running, setRunning] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const rows = reviewRows(session.values, session.chips);
  const supplied = rows.filter((r) => r.supplied).length;
  const { disease, subtype, drug } = session.selection;

  const pkRows = pkReviewRows(session.pk);
  const pkSupplied = pkRows.filter((r) => r.supplied).length;

  function pkError(name: string): string | undefined {
    if (!touched[name]) return undefined;
    const def = PK_FIELDS.find((f) => (f.name as string) === name)!;
    return validatePkField(def, session.pk[name] ?? '');
  }

  /**
   * Run the migrated engines.
   *
   * The two calls are independent and their outcomes are stored separately.
   * A failure of one never suppresses or substitutes for the other, and the PK
   * model is not called at all unless its inputs are complete and valid.
   */
  // Resolved once per render and shared by every branch below, so the badge,
  // the field list, the warning and the run action cannot disagree.
  const legacyApplies = shouldRequestRateConstants(pkPathway);

  async function handleRun() {
    setRunning(true);
    setResult(null);
    setPkResult(null);
    try {
      const outcome = await scoreDesign(buildRequest(session.values, session.chips));
      setResult(outcome);

      // The legacy depot engine is called ONLY where it is scientifically
      // compatible: a route with a genuine first-order absorption phase. For an
      // intravenous study it is never called, whatever is typed into the
      // rate-constant boxes, because the depot compartment does not exist.
      if (mayCallLegacyEngine(pkPathway) && pkInputsReady) {
        setPkResult(await simulatePk(buildPkRequest(session.pk)));
      }

      reachStep(4);
      navigate('/workflow/results');
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <PathwayBanner />
      <PathwayProgress />
      <Card
        title="Step 3 — Review & Run Simulation"
        subtitle="Confirm the complete session before execution. Nothing is sent until you choose to run."
        accent
      >
        {/* ---------------------------------------- therapeutic context */}
        <section className="s3__block" aria-labelledby="s3-context">
          <h3 className="s3__head" id="s3-context">Therapeutic context</h3>
          <dl className="s3__context">
            <div><dt>Indication</dt><dd>{disease}</dd></div>
            <div><dt>Subtype</dt><dd>{subtype}</dd></div>
            <div><dt>Therapeutic agent</dt><dd>{drug}</dd></div>
          </dl>
          <p className="s3__note">
            Recorded for traceability. Neither migrated engine takes a disease
            as input, so this selection does not affect the design impact score
            or the pharmacokinetic profile.
          </p>
        </section>

        {/* ------------------------------------------ formulation table */}
        <section className="s3__block" aria-labelledby="s3-formulation">
          <div className="s3__headrow">
            <h3 className="s3__head" id="s3-formulation">Nanoparticle configuration</h3>
            <div className="s3__headactions">
              <Badge tone="accent">{supplied} of {rows.length} supplied</Badge>
              {/* Deliberately inside this section and OUTSIDE every
                  pharmacokinetic condition: the builder visualises the
                  formulation, so it must remain available when the PK model is
                  blocked, unconfigured or unavailable. */}
              <Button variant="secondary" size="sm"
                      onClick={() => navigate('/scientific-readiness')}
                      iconLeft={<Icon name="flask" size={15} />}
                      data-testid="step3-to-readiness">
                Scientific readiness
              </Button>
              <Button variant="primary" size="sm"
                      onClick={() => navigate('/builder')}
                      iconLeft={<Icon name="atom" size={15} />}
                      data-testid="view-in-3d">
                View in 3D
              </Button>
            </div>
          </div>
          <p className="s3__note">
            Parameters marked <em>default</em> are not sent. The scientific engine
            applies its own documented value — the interface never invents one.
            <br />
            <strong>View in 3D</strong> opens an interactive visual model of
            this formulation. It is a visualisation only: it changes no input,
            runs no engine and predicts nothing.
          </p>

          {FIELD_SECTIONS.filter((s) => s.id !== 'review').map((sec) => (
            <div className="s3__section" key={sec.id}>
              <p className="eyebrow">{sec.title}</p>
              <DataTable
                dense
                caption={`${sec.title} parameters`}
                head={[
                  { key: 'p', label: 'Parameter' },
                  { key: 'v', label: 'Value', numeric: true },
                ]}
              >
                {rows.filter((r) => r.step === sec.id).map((r) => (
                  <tr key={r.key} className={r.supplied ? undefined : 's3__row--default'}>
                    <th scope="row">
                      {r.label}
                      {r.unit && <span className="s3__unit"> ({r.unit})</span>}
                      {r.required && <span className="s3__req">required</span>}
                    </th>
                    <td className="is-numeric">{r.value}</td>
                  </tr>
                ))}
              </DataTable>
            </div>
          ))}
        </section>

        {/* ----------------------------------------- pharmacokinetics */}
        <section className="s3__block" aria-labelledby="s3-pk" data-testid="pk-inputs">
          <div className="s3__headrow">
            <h3 className="s3__head" id="s3-pk">Pharmacokinetic simulation inputs</h3>
            <Badge
              tone={legacyApplies && pkInputsReady ? 'success' : 'warn'} dot
            >
              {!legacyApplies
                ? 'Route-aware model'
                : pkInputsReady
                  ? 'Ready to run'
                  : `${pkSupplied} of ${pkRows.length} supplied`}
            </Badge>
          </div>
          <p className="s3__note">
            Inputs are determined by the administration route. Select it below;
            the route decides which model applies, which inputs exist, and
            whether a reviewed parameter set is available.
          </p>

          {/* The depot engine below has no concept of administration route: it
              places the whole dose in a depot and absorbs it first-order, which
              is wrong for any intravenous therapeutic. The route-aware panel
              states which model actually applies and where each input comes
              from. It is shown first so the distinction is unmissable. */}
          <RoutedPKPanel therapeutic={drug || ''}
                         initial={pkPathway}
                         onPathwayChange={setPkPathway} />

          {legacyApplies && (
          <details className="s3__legacy" data-testid="legacy-depot-inputs">
            <summary>
              Direct rate-constant entry (depot model, no route awareness)
            </summary>
            <p className="s3__note">
              These fields drive the original depot model, which places the
              entire dose in an absorption compartment. They are retained so
              existing studies stay reproducible. <strong>They are not
              appropriate for an intravenous therapeutic</strong>, and the
              values are not derived from any parameter set or medical report.
            </p>
            <p className="s3__note">
              <strong>Nothing here is pre-filled.</strong> These values
              determine the kinetics being reported, so the simulation runs only
              once you supply them. The model does not infer them from the
              formulation above.
            </p>

          <div className="s3__pkgrid">
            {PK_FIELDS.map((def) => {
              const name = def.name as string;
              return (
                <TextField
                  key={name}
                  id={`pk-${name}`}
                  label={def.label}
                  unit={def.unit}
                  required={def.required}
                  type="number"
                  inputMode="decimal"
                  step="any"
                  value={session.pk[name] ?? ''}
                  onChange={(e) => setPkValue(name, e.target.value)}
                  onBlur={() => setTouched((t) => ({ ...t, [name]: true }))}
                  error={pkError(name)}
                  placeholder={def.required ? 'required' : `default: ${def.defaultNote}`}
                  help={
                    <>
                      <span className="s3__pksym">{def.symbol}</span>
                      {def.definition}
                      {def.choices
                        ? ` Accepted values: ${def.choices.join(', ')}.`
                        : ` Range ${def.min}–${def.max} ${def.unit}.`}
                    </>
                  }
                />
              );
            })}
          </div>
          </details>
          )}

          {isIntravenous(pkPathway.route) && (
            <Alert tone="info" title="Depot rate constants do not apply"
                   role="note">
              <p data-testid="legacy-not-applicable">
                The four first-order rate constants belong to the depot
                absorption model. They are not requested for an intravenous
                route, and this study will not be sent to that engine.
              </p>
            </Alert>
          )}

          {legacyApplies && !pkInputsReady && (
            <Alert tone="info" title="The simulation will not run yet" role="note">
              <p data-testid="pk-incomplete-note">
                One or more required pharmacokinetic inputs is missing or out of
                range. Running now calculates the design impact score only —
                no concentration–time profile, half-life or AUC will be produced,
                and none will be shown.
              </p>
            </Alert>
          )}
        </section>

        {/* -------------------------------------- what will actually run */}
        <section className="s3__block" aria-labelledby="s3-run">
          <h3 className="s3__head" id="s3-run">What will run</h3>
          <ul className="s3__runlist">
            <li className="is-on">
              <span className="s3__runicon" aria-hidden="true"><Icon name="check" size={14} /></span>
              <div>
                <p className="s3__runtitle">
                  Design impact score <Badge tone="success" dot>Operational</Badge>
                </p>
                <p className="s3__runbody">
                  Delivery, toxicity and cost, computed by the canonical scientific
                  engine and returned with its model version, evidence level and
                  limitations.
                </p>
              </div>
            </li>
            <li className={pkInputsReady ? 'is-on' : 'is-off'}>
              <span className="s3__runicon" aria-hidden="true">
                {pkInputsReady ? <Icon name="check" size={14} /> : '—'}
              </span>
              <div>
                <p className="s3__runtitle">
                  Pharmacokinetic simulation{' '}
                  {pkInputsReady
                    ? <Badge tone="success" dot>Operational</Badge>
                    : <Badge tone="warn" dot>Inputs incomplete</Badge>}
                </p>
                <p className="s3__runbody" data-testid="pk-run-status">
                  {pkInputsReady ? (
                    <>
                      The migrated two-compartment model will run on the inputs
                      above and return a concentration–time profile with the
                      parameters it genuinely produces. It does not produce a
                      clearance, and none will be shown. This is a separate
                      calculation from the design impact score.
                    </>
                  ) : (
                    <>
                      Will not run: the required inputs are incomplete. No
                      concentration–time profile, half-life or AUC will be
                      produced, and none will be shown.
                    </>
                  )}
                </p>
              </div>
            </li>
            <li className="is-off">
              <span className="s3__runicon" aria-hidden="true">—</span>
              <div>
                <p className="s3__runtitle">
                  Scientific assessments <Badge tone="info" dot>Calibration required</Badge>
                </p>
                <p className="s3__runbody">
                  The mechanistic, safety, disease-fit, manufacturability and
                  regulatory engines are not migrated. No disease-specific
                  assessment will be produced for the selection above.
                </p>
              </div>
            </li>
          </ul>
        </section>

        {/* Running is this step's scientific action and is kept as its own
            control: it executes engines and opens the results view, which is
            not the same thing as advancing along the pathway. */}
        <StepActions
          onSaveDraft={saveDraft}
          onContinue={handleRun}
          continueLabel={running ? 'Running…' : 'Run Simulation'}
          continueLoading={running}
          primaryIcon={<Icon name="play" size={15} />}
        />

        {/* Pathway movement: back to targeting, on to Scientific Readiness.
            Disabled while a run is in flight so the user cannot navigate out
            from under a calculation. */}
        <PathwayNav continueDisabled={running} />
      </Card>

      <Alert tone="warn" title="Partial execution" role="note">
        Two migrated engines run here: the design impact score, and — when its
        inputs are complete — the two-compartment pharmacokinetic model. They are
        separate calculations and are reported separately. The assessment engines
        are still not migrated, so this session will not produce disease-specific
        assessments, and the results page will say so rather than filling the gap
        with placeholder figures.
      </Alert>
    </>
  );
}
