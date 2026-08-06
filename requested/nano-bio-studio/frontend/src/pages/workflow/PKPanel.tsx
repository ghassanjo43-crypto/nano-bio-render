/**
 * Pharmacokinetic simulation presentation.
 *
 * Every number rendered here comes from the API response. Nothing is derived,
 * converted, rounded for effect, or supplied as a placeholder. In particular:
 *
 *  • the chart is drawn from the returned arrays alone;
 *  • the exact returned values are listed alongside it, so the chart is never
 *    the only way to read a number;
 *  • a null half-life is displayed as "not determined", never as an estimate;
 *  • quantities the engine does not produce — clearance above all — are named
 *    explicitly rather than omitted silently or filled in;
 *  • no clinical interpretation is offered. The legacy Streamlit page rendered
 *    prose such as "excellent targeting efficacy"; none of it is reproduced,
 *    because the model does not support those conclusions.
 */

import { useState } from 'react';
import { ConcentrationTimeChart } from '../../charts/ConcentrationTimeChart';
import type { PKSimulationResponse } from '../../api/types';
import { Alert, Badge, DataTable, Tabs } from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import './PKPanel.css';

/** Rows of the derived-parameter table, in the engine's own terms. */
const PARAMETER_ROWS = [
  {
    key: 'peak_concentration_central',
    label: 'Peak amount, central (plasma)',
    unitFrom: 'concentration',
    note: 'C_max of the central compartment.',
  },
  {
    key: 'time_to_peak_central_h',
    label: 'Time to peak, central',
    unitFrom: 'time',
    note: 'T_max of the central compartment.',
  },
  {
    key: 'peak_concentration_peripheral',
    label: 'Peak amount, peripheral (tissue)',
    unitFrom: 'concentration',
    note: 'C_max of the peripheral compartment.',
  },
  {
    key: 'time_to_peak_peripheral_h',
    label: 'Time to peak, peripheral',
    unitFrom: 'time',
    note: 'T_max of the peripheral compartment.',
  },
  {
    key: 'auc_central',
    label: 'AUC, central',
    unitFrom: 'auc',
    note: 'Trapezoidal integral over the simulated window. Not AUC(0–∞).',
  },
  {
    key: 'auc_peripheral',
    label: 'AUC, peripheral',
    unitFrom: 'auc',
    note: 'Trapezoidal integral over the simulated window. Not AUC(0–∞).',
  },
  {
    key: 'half_life_central_h',
    label: 'Terminal half-life, central',
    unitFrom: 'time',
    note: 'First time after the peak at which the curve falls to half its peak.',
  },
  {
    key: 'tissue_accumulation_ratio',
    label: 'Tissue accumulation ratio',
    unitFrom: 'ratio',
    note: 'AUC peripheral divided by AUC central.',
  },
  {
    key: 'vss_ratio',
    label: 'Peak ratio (peripheral / central)',
    unitFrom: 'ratio',
    note: 'Peak peripheral amount divided by peak central amount.',
  },
] as const;

const INPUT_LABELS: Record<string, string> = {
  dose: 'Dose (mg/kg)',
  kabs: 'k_abs (h⁻¹)',
  kel: 'k_el (h⁻¹)',
  k12: 'k_12 (h⁻¹)',
  k21: 'k_21 (h⁻¹)',
  duration: 'Simulated duration (h)',
  dt: 'Integration step (h)',
};

/** Full precision. The chart is the approximation; this is the record. */
function exact(value: number): string {
  return String(value);
}

export function PKPanel({ data }: { data: PKSimulationResponse }) {
  // Tab ids are namespaced: the design-score panel renders its own tab set on
  // the same page, and `Tabs` derives DOM ids from them. Unprefixed ids would
  // collide (two `#panel-profile`) and break the ARIA relationships.
  const [tab, setTab] = useState('pk-profile');
  const series = data.concentration_time;
  const p = data.pk_parameters;

  /**
   * The returned series as table rows.
   *
   * A point is emitted only when all three arrays carry a value at that index.
   * The API client already rejects a response whose arrays disagree, so this
   * drops nothing in practice — but it means a malformed profile can never be
   * padded out with a substituted zero.
   */
  const dataRows = series.time_h.flatMap((t, i) => {
    const central = series.central_plasma[i];
    const peripheral = series.peripheral_tissue[i];
    return central === undefined || peripheral === undefined
      ? []
      : [{ t, central, peripheral }];
  });

  const units: Record<string, string> = {
    concentration: series.concentration_unit,
    time: series.time_unit,
    auc: `${series.concentration_unit} · ${series.time_unit}`,
    ratio: 'ratio',
  };

  return (
    <div className="pk" data-testid="pk-panel">
      <p className="pk__caption">
        Calculated by the migrated two-compartment model. This is a{' '}
        <strong>separate calculation from the design impact score</strong> — it
        takes different inputs, uses a different model and carries its own
        version. The two are not combined into a single figure.
      </p>

      {/* -------------------------------------------------- headline values */}
      <dl className="pk__headline" data-testid="pk-headline">
        <div>
          <dt>Peak amount (central)</dt>
          <dd data-testid="pk-cmax">{exact(p.peak_concentration_central)}</dd>
          <span>{series.concentration_unit}</span>
        </div>
        <div>
          <dt>AUC (central)</dt>
          <dd data-testid="pk-auc">{exact(p.auc_central)}</dd>
          <span>{series.concentration_unit} · {series.time_unit}</span>
        </div>
        <div>
          <dt>Terminal half-life</dt>
          <dd data-testid="pk-half-life">
            {p.half_life_central_h === null
              ? <span className="pk__null">not determined</span>
              : exact(p.half_life_central_h)}
          </dd>
          <span>
            {p.half_life_central_h === null
              ? 'never halved within the window'
              : series.time_unit}
          </span>
        </div>
        <div>
          <dt>Clearance</dt>
          <dd data-testid="pk-clearance">
            <span className="pk__null">not produced</span>
          </dd>
          <span>the model has no volume term</span>
        </div>
      </dl>

      {/* ------------------------------------------------------------ tabs */}
      <div className="pk__tabs">
        <Tabs
          ariaLabel="Pharmacokinetic detail"
          active={tab}
          onChange={setTab}
          tabs={[
            { id: 'pk-profile', label: 'Profile' },
            { id: 'pk-parameters', label: 'Parameters' },
            { id: 'pk-data', label: `Data (${series.point_count})` },
            { id: 'pk-inputs', label: 'Inputs' },
            { id: 'pk-assumptions', label: 'Assumptions' },
            {
              id: 'pk-warnings',
              label: 'Warnings',
              badge: data.warnings.length
                ? <Badge tone="warn" className="pk__tabbadge">{data.warnings.length}</Badge>
                : undefined,
            },
          ]}
        />
      </div>

      {tab === 'pk-profile' && (
        <div role="tabpanel" id="panel-pk-profile" aria-labelledby="tab-pk-profile"
             className="pk__panel">
          <ConcentrationTimeChart
            time={series.time_h}
            timeUnit={series.time_unit}
            concentrationUnit={series.concentration_unit}
            series={[
              { key: 'central', label: 'Central compartment (plasma)',
                values: series.central_plasma },
              { key: 'peripheral', label: 'Peripheral compartment (tissue)',
                values: series.peripheral_tissue },
            ]}
            markers={[
              { key: 'peak-central', label: 'Peak, central',
                t: p.time_to_peak_central_h, value: p.peak_concentration_central },
              { key: 'peak-peripheral', label: 'Peak, peripheral',
                t: p.time_to_peak_peripheral_h,
                value: p.peak_concentration_peripheral },
            ]}
          />
          <p className="pk__hint">
            The vertical axis is a dose-scaled amount in arbitrary units, not a
            mass-per-volume concentration: the model carries no compartment
            volume. Select <strong>Data</strong> for every calculated point.
          </p>
        </div>
      )}

      {tab === 'pk-parameters' && (
        <div role="tabpanel" id="panel-pk-parameters" aria-labelledby="tab-pk-parameters"
             className="pk__panel">
          <DataTable
            caption="Derived pharmacokinetic parameters"
            head={[
              { key: 'p', label: 'Parameter' },
              { key: 'v', label: 'Value', numeric: true },
              { key: 'u', label: 'Unit' },
              { key: 'n', label: 'Definition' },
            ]}
          >
            {PARAMETER_ROWS.map((row) => {
              const value = p[row.key];
              return (
                <tr key={row.key}>
                  <th scope="row">{row.label}</th>
                  <td className="is-numeric" data-testid={`pk-param-${row.key}`}>
                    {value === null
                      ? <span className="pk__null">not determined</span>
                      : exact(value)}
                  </td>
                  <td>{value === null ? '—' : units[row.unitFrom]}</td>
                  <td className="pk__note">{row.note}</td>
                </tr>
              );
            })}
          </DataTable>

          <section className="pk__notproduced" data-testid="pk-not-produced">
            <h4 className="pk__subhead">Not produced by this model</h4>
            <p className="pk__hint">
              These are absent because the migrated engine does not calculate
              them. Deriving one here would be a new scientific claim, so none
              is shown.
            </p>
            <ul className="pk__notlist">
              {data.quantities_not_produced.map((q) => (
                <li key={q.quantity}>
                  <span className="pk__notname">{q.quantity.replace(/_/g, ' ')}</span>
                  <span className="pk__notreason">{q.reason}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}

      {tab === 'pk-data' && (
        <div role="tabpanel" id="panel-pk-data" aria-labelledby="tab-pk-data"
             className="pk__panel">
          <p className="pk__hint">
            Every point the engine returned, at full precision — the exact
            values behind the chart. {dataRows.length} points across{' '}
            {dataRows[dataRows.length - 1]?.t} {series.time_unit}.
          </p>
          <div className="pk__datascroll">
            <DataTable
              dense
              caption="Calculated concentration–time data"
              head={[
                { key: 't', label: `Time (${series.time_unit})`, numeric: true },
                { key: 'c', label: 'Central (plasma)', numeric: true },
                { key: 'p', label: 'Peripheral (tissue)', numeric: true },
              ]}
            >
              {dataRows.map((row) => (
                <tr key={row.t}>
                  <td className="is-numeric">{exact(row.t)}</td>
                  <td className="is-numeric">{exact(row.central)}</td>
                  <td className="is-numeric">{exact(row.peripheral)}</td>
                </tr>
              ))}
            </DataTable>
          </div>
        </div>
      )}

      {tab === 'pk-inputs' && (
        <div role="tabpanel" id="panel-pk-inputs" aria-labelledby="tab-pk-inputs"
             className="pk__panel">
          <p className="pk__hint">
            The effective values the engine used. The dose and the four rate
            constants are yours; the window settings fall back to the engine’s
            documented defaults when left blank. These make the run reproducible.
          </p>
          <DataTable
            caption="Normalised pharmacokinetic inputs"
            dense
            head={[
              { key: 'p', label: 'Input' },
              { key: 'v', label: 'Value', numeric: true },
            ]}
          >
            {Object.entries(data.normalized_inputs).map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{INPUT_LABELS[k] ?? k}</th>
                <td className="is-numeric">{exact(v)}</td>
              </tr>
            ))}
          </DataTable>
        </div>
      )}

      {tab === 'pk-assumptions' && (
        <div role="tabpanel" id="panel-pk-assumptions" aria-labelledby="tab-pk-assumptions"
             className="pk__panel">
          <ul className="pk__list" data-testid="pk-assumptions">
            {data.assumptions.map((a) => (
              <li key={a}><Icon name="info" size={15} /><span>{a}</span></li>
            ))}
          </ul>
        </div>
      )}

      {tab === 'pk-warnings' && (
        <div role="tabpanel" id="panel-pk-warnings" aria-labelledby="tab-pk-warnings"
             className="pk__panel">
          {data.warnings.length === 0 ? (
            <Alert tone="success" title="No warnings">
              The engine reported no interpretation notes for this run.
            </Alert>
          ) : (
            <ul className="pk__list" data-testid="pk-warnings">
              {data.warnings.map((w) => (
                <li key={w}><Icon name="info" size={15} /><span>{w}</span></li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* ---------------------------------------------------- provenance */}
      <section className="pk__provenance" aria-labelledby="pk-prov-head">
        <h4 id="pk-prov-head" className="pk__subhead">Provenance &amp; validation</h4>
        <dl className="pk__prov">
          <div>
            <dt>Calculation version</dt>
            <dd data-testid="pk-version"><code>{data.calculation_version}</code></dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd><code>{data.model_name}</code></dd>
          </div>
          <div>
            <dt>Scientific source</dt>
            <dd><code>{data.scientific_source}</code></dd>
          </div>
          <div>
            <dt>Prediction basis</dt>
            <dd><Badge tone="info">{data.prediction_basis}</Badge></dd>
          </div>
          <div>
            <dt>Evidence level</dt>
            <dd><Badge tone="warn">{data.evidence_level}</Badge></dd>
          </div>
          <div>
            <dt>Validation status</dt>
            <dd data-testid="pk-validation">
              <Badge tone="danger" dot>{data.validation_status}</Badge>
            </dd>
          </div>
        </dl>
      </section>

      <section className="pk__limits" aria-labelledby="pk-lim-head">
        <h4 id="pk-lim-head" className="pk__subhead">Limitations</h4>
        <ul className="pk__limitlist" data-testid="pk-limitations">
          {data.limitations.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </section>
    </div>
  );
}
