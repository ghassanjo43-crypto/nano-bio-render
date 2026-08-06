/**
 * Demo Workspace — ready-made scenarios for exercising the connected engines.
 *
 * The scientific contract of this page:
 *
 *  • Scenarios supply **synthetic inputs only**. The API type they arrive in has
 *    no field capable of carrying a score, a profile or an assessment, so a
 *    stored result cannot be rendered here even by mistake.
 *  • Loading a scenario populates the ordinary workflow and **runs nothing**.
 *    Calculation still requires the deliberate "Run Simulation" action on Step 3,
 *    and the ordinary validation still applies.
 *  • Every scenario carries a "Synthetic demonstration data" badge, on the card
 *    and again in the preview, so the classification cannot be lost between the
 *    listing and the run.
 *  • A loaded scenario becomes an isolated working copy. Editing it never
 *    changes the template, and the template can always be reloaded.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getScenario, listScenarios, resetDemoData,
} from '../../api/client';
import type {
  DemoScenarioDetail, DemoScenarioSummary, WorkspaceErrorResponse,
} from '../../api/types';
import {
  Alert, Badge, Button, Card, DataTable, Dialog, EmptyState, SkeletonBlock,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { useWorkflow } from '../../workflow/WorkflowContext';
import './DemoWorkspace.css';

/** Human labels for the design fields a scenario can carry. */
const DESIGN_LABELS: Record<string, string> = {
  size_nm: 'Particle size (nm)',
  charge_mv: 'Surface charge (mV)',
  encapsulation_percent: 'Encapsulation efficiency (%)',
  pdi: 'Polydispersity index',
  hydrodynamic_size_nm: 'Hydrodynamic size (nm)',
  surface_coating: 'Surface coating',
  coating_thickness_nm: 'Coating thickness (nm)',
  surface_area_nm2: 'Surface area (nm²)',
  hydrophobicity_logp: 'Hydrophobicity (LogP)',
  crystallinity_index: 'Crystallinity index (%)',
  functional_groups: 'Functional groups',
  ligand: 'Targeting ligand',
  ligand_density_percent: 'Ligand density (%)',
  receptor_binding_kd_nm: 'Receptor binding Kd (nM)',
  stability_percent: 'Stability (%)',
  degradation_time_days: 'Degradation time (days)',
  release_predictability_percent: 'Release predictability (%)',
};

const PK_LABELS: Record<string, string> = {
  dose_mg_kg: 'Dose (mg/kg)',
  kabs_per_h: 'k_abs (h⁻¹)',
  kel_per_h: 'k_el (h⁻¹)',
  k12_per_h: 'k_12 (h⁻¹)',
  k21_per_h: 'k_21 (h⁻¹)',
  duration_h: 'Simulation duration (h)',
  time_step_h: 'Integration step (h)',
};

function renderValue(value: unknown): string {
  if (Array.isArray(value)) return value.length ? value.join(', ') : '(none)';
  if (value === null || value === undefined) return 'not supplied';
  return String(value);
}

export default function DemoWorkspace() {
  const navigate = useNavigate();
  const { loadScenario } = useWorkflow();

  const [scenarios, setScenarios] = useState<DemoScenarioSummary[] | null>(null);
  const [notice, setNotice] = useState('');
  const [fixtureVersion, setFixtureVersion] = useState('');
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);

  const [preview, setPreview] = useState<DemoScenarioDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [resetOpen, setResetOpen] = useState(false);
  const [resetScope, setResetScope] = useState<string | null>(null);
  const [resetBusy, setResetBusy] = useState(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const result = await listScenarios(signal);
    if (result.status === 'error') {
      setError(result.error);
      setScenarios([]);
      return;
    }
    setError(null);
    setScenarios(result.data.scenarios);
    setNotice(result.data.notice);
    setFixtureVersion(result.data.fixture_version);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  async function openPreview(slug: string) {
    setPreviewLoading(true);
    const result = await getScenario(slug);
    setPreviewLoading(false);
    if (result.status === 'error') {
      setError(result.error);
      return;
    }
    setPreview(result.data);
  }

  /**
   * Load into an isolated working copy and go to Step 1.
   *
   * Nothing is calculated: the user reviews Steps 1–3 and must press Run.
   */
  function handleLoad(detail: DemoScenarioDetail) {
    loadScenario(detail);
    setPreview(null);
    navigate('/workflow/disease');
  }

  async function openReset() {
    setResetBusy(true);
    const result = await resetDemoData({ confirm: false });
    setResetBusy(false);
    setResetScope(result.status === 'ok'
      ? result.data.message
      : `Could not determine the scope: ${result.error.message}`);
    setResetOpen(true);
  }

  async function confirmReset() {
    setResetBusy(true);
    const result = await resetDemoData({ confirm: true });
    setResetBusy(false);
    setResetOpen(false);
    setResetScope(null);
    if (result.status === 'error') setError(result.error);
  }

  return (
    <>
      <Card
        title="Demo Workspace"
        subtitle="Ready-made scenarios for exercising the genuinely connected engines end to end."
        accent
        actions={
          <Button variant="secondary" onClick={openReset} disabled={resetBusy}
                  iconLeft={<Icon name="refresh" size={15} />}>
            Reset demo data
          </Button>
        }
      >
        <Alert tone="warn" title="Synthetic demonstration data" role="note">
          <p data-testid="demo-notice">{notice || (
            'Synthetic demonstration inputs. Not patient data, not clinical '
            + 'data, not validated experimental data, not treatment '
            + 'recommendations, and not known-successful formulations.'
          )}</p>
        </Alert>

        <p className="dw__lead">
          Each scenario supplies a complete set of <strong>inputs</strong> so you
          can exercise a full workflow without typing every field. No scenario
          contains a stored result: every score, profile and chart you see is
          calculated at run time by the same engines the ordinary workflow uses.
          Loading a scenario populates Steps 1–3 and stops — you review the values
          and choose when to run.
        </p>

        {error && (
          <Alert tone="danger" title="Scenarios unavailable">
            <p>{error.message}</p>
            {error.detail && <p className="mono dw__detail">{error.detail}</p>}
          </Alert>
        )}

        {scenarios === null && <SkeletonBlock lines={4} />}

        {scenarios !== null && scenarios.length === 0 && !error && (
          <EmptyState
            title="No scenarios installed"
            testId="no-scenarios"
          >
            Run the seeding command to install the demonstration templates:
            <code className="dw__cmd">
              python nanobio_studio_backend\scripts\demo_data.py seed
            </code>
          </EmptyState>
        )}

        {scenarios !== null && scenarios.length > 0 && (
          <>
            <div className="dw__grid" data-testid="scenario-cards">
              {scenarios.map((s) => (
                <article className={`dw__card ${s.technical ? 'dw__card--tech' : ''}`}
                         key={s.slug} data-testid={`scenario-${s.slug}`}>
                  <header className="dw__cardhead">
                    <Badge tone={s.technical ? 'info' : 'accent'}>
                      {s.technical ? 'Technical scenario' : s.disease}
                    </Badge>
                    <Badge tone="warn" dot>{s.data_classification}</Badge>
                  </header>

                  <h3 className="dw__cardtitle">{s.name}</h3>

                  <dl className="dw__meta">
                    <div><dt>Indication</dt><dd>{s.disease}</dd></div>
                    <div><dt>Subtype</dt><dd>{s.subtype}</dd></div>
                    <div><dt>Therapeutic</dt><dd>{s.drug}</dd></div>
                  </dl>

                  <p className="dw__purpose">{s.purpose}</p>

                  <ul className="dw__engines">
                    <li className={s.score_runnable ? 'is-on' : 'is-off'}>
                      <Icon name={s.score_runnable ? 'check' : 'close'} size={13} />
                      Design impact score
                      {!s.score_runnable && <span> — inputs incomplete</span>}
                    </li>
                    <li className={s.pk_runnable ? 'is-on' : 'is-off'}>
                      <Icon name={s.pk_runnable ? 'check' : 'close'} size={13} />
                      PK simulation
                      {!s.pk_runnable && <span> — inputs incomplete</span>}
                    </li>
                    <li className="is-off">
                      <Icon name="close" size={13} />
                      {s.engine_count_not_running} engine
                      {s.engine_count_not_running === 1 ? '' : 's'} will not run
                    </li>
                  </ul>

                  <div className="dw__cardactions">
                    <Button variant="secondary" onClick={() => openPreview(s.slug)}
                            disabled={previewLoading}
                            iconLeft={<Icon name="document" size={15} />}>
                      Preview
                    </Button>
                    <Button onClick={() => openPreview(s.slug)}
                            iconRight={<Icon name="arrow-right" size={15} />}>
                      Load scenario
                    </Button>
                  </div>
                </article>
              ))}
            </div>

            <p className="dw__version">
              Fixture set <code>{fixtureVersion}</code>. Every run started from a
              scenario records this version, so a stored result stays traceable
              to the exact inputs it came from.
            </p>
          </>
        )}
      </Card>

      {/* ------------------------------------------------------ preview */}
      <Dialog
        open={preview !== null}
        onClose={() => setPreview(null)}
        wide
        title={preview ? `Preview — ${preview.name}` : ''}
        footer={preview && (
          <>
            <Button variant="ghost" onClick={() => setPreview(null)}>Cancel</Button>
            <Button onClick={() => handleLoad(preview)}
                    data-testid="confirm-load"
                    iconRight={<Icon name="arrow-right" size={15} />}>
              Load into workflow
            </Button>
          </>
        )}
      >
        {preview && (
          <div className="dw__preview" data-testid="scenario-preview">
            <Alert tone="warn" title={preview.data_classification} role="note">
              These are synthetic inputs for demonstration. They are not patient
              data, not clinical data, not validated experimental data, not a
              treatment recommendation, and not a known-successful formulation.
            </Alert>

            <section>
              <h4 className="dw__subhead">Purpose</h4>
              <p className="dw__body">{preview.purpose}</p>
            </section>

            <section>
              <h4 className="dw__subhead">Therapeutic context</h4>
              <dl className="dw__meta dw__meta--wide">
                <div><dt>Indication</dt><dd>{preview.disease}</dd></div>
                <div><dt>Subtype</dt><dd>{preview.subtype}</dd></div>
                <div><dt>Therapeutic agent</dt><dd>{preview.drug}</dd></div>
              </dl>
              <p className="dw__note">
                Recorded for traceability. Neither connected engine takes a
                disease as input, so this selection does not change any
                calculated value.
              </p>
            </section>

            <section>
              <h4 className="dw__subhead">
                Nanoparticle design inputs
                {preview.missing_required_design_inputs.length > 0 && (
                  <Badge tone="danger" className="dw__hbadge">
                    {preview.missing_required_design_inputs.length} required missing
                  </Badge>
                )}
              </h4>
              <DataTable dense caption="Design inputs"
                         head={[{ key: 'p', label: 'Parameter' },
                                { key: 'v', label: 'Value', numeric: true }]}>
                {Object.entries(preview.design_inputs).map(([k, v]) => (
                  <tr key={k}>
                    <th scope="row">{DESIGN_LABELS[k] ?? k}</th>
                    <td className="is-numeric">{renderValue(v)}</td>
                  </tr>
                ))}
                {preview.missing_required_design_inputs.map((k) => (
                  <tr key={k} className="dw__missing">
                    <th scope="row">{DESIGN_LABELS[k] ?? k}</th>
                    <td className="is-numeric">deliberately not supplied</td>
                  </tr>
                ))}
              </DataTable>
            </section>

            <section>
              <h4 className="dw__subhead">
                Pharmacokinetic inputs
                {preview.missing_required_pk_inputs.length > 0 && (
                  <Badge tone="danger" className="dw__hbadge">
                    {preview.missing_required_pk_inputs.length} required missing
                  </Badge>
                )}
              </h4>
              <DataTable dense caption="PK inputs"
                         head={[{ key: 'p', label: 'Parameter' },
                                { key: 'v', label: 'Value', numeric: true }]}>
                {Object.entries(preview.pk_inputs).map(([k, v]) => (
                  <tr key={k}>
                    <th scope="row">{PK_LABELS[k] ?? k}</th>
                    <td className="is-numeric">{renderValue(v)}</td>
                  </tr>
                ))}
                {preview.missing_required_pk_inputs.map((k) => (
                  <tr key={k} className="dw__missing">
                    <th scope="row">{PK_LABELS[k] ?? k}</th>
                    <td className="is-numeric">deliberately not supplied</td>
                  </tr>
                ))}
              </DataTable>
            </section>

            <section>
              <h4 className="dw__subhead">Engines that will run</h4>
              {preview.engines_expected_to_run.length === 0 ? (
                <p className="dw__body" data-testid="no-engines">
                  <strong>None.</strong> This scenario is deliberately incomplete,
                  so no engine will be called and no result will be produced.
                </p>
              ) : (
                <ul className="dw__list">
                  {preview.engines_expected_to_run.map((e) => (
                    <li key={e}><Icon name="check" size={14} />{e}</li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <h4 className="dw__subhead">Engines that will not run</h4>
              <ul className="dw__notlist" data-testid="engines-not-run">
                {preview.engines_that_will_not_run.map((e) => (
                  <li key={e.engine}>
                    <span className="dw__notname">{e.engine}</span>
                    <span className="dw__notreason">{e.reason}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h4 className="dw__subhead">Assumptions</h4>
              <ul className="dw__list">
                {preview.assumptions.map((a) => (
                  <li key={a}><Icon name="info" size={14} />{a}</li>
                ))}
              </ul>
            </section>

            <section>
              <h4 className="dw__subhead">Warnings you should expect</h4>
              <p className="dw__note">
                Anticipated for teaching purposes. The authoritative warning list
                is always the one the engine returns on the results page.
              </p>
              <ul className="dw__list">
                {preview.expected_warnings.map((w) => (
                  <li key={w}><Icon name="info" size={14} />{w}</li>
                ))}
              </ul>
            </section>

            <section>
              <h4 className="dw__subhead">Provenance</h4>
              <ul className="dw__list">
                {preview.provenance.map((p) => (
                  <li key={p}><Icon name="document" size={14} />{p}</li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </Dialog>

      {/* -------------------------------------------------------- reset */}
      <Dialog
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        title="Reset demonstration data"
        footer={
          <>
            <Button variant="ghost" onClick={() => setResetOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmReset} disabled={resetBusy}
                    data-testid="confirm-reset">
              Delete demo records
            </Button>
          </>
        }
      >
        <Alert tone="warn" title="Scope of this action">
          <p data-testid="reset-scope">{resetScope}</p>
        </Alert>
        <p className="dw__body">
          Only records created from a demonstration scenario are removed. Your own
          designs, runs and projects are counted above as proof of scope and are
          never deleted by this action. Scenario templates are left installed and
          can be loaded again immediately.
        </p>
      </Dialog>
    </>
  );
}
