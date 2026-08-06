/**
 * Design impact score presentation.
 *
 * Every number rendered here comes from the API response. Nothing is derived,
 * rounded for effect, or supplied as a placeholder. The visualisations encode
 * only the returned values, and each is accompanied by the numeral in text.
 *
 * The heading deliberately says "Design Impact Score" and never "Overall Score":
 * no composite score exists, and the candidate formula is documented but not
 * implemented pending scientific review.
 */

import { useState } from 'react';
import { ComponentBars, ComponentRadar, ScoreGauge, type ScoreTone }
  from '../../charts/ScoreVisuals';
import type { DesignScoreResponse } from '../../api/types';
import {
  Alert, Badge, Button, DataTable, Tabs,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';

/**
 * Component scale metadata.
 *
 * `favourable` describes the direction of improvement, which is required to
 * normalise the radar sensibly: Delivery is better high, Toxicity and Cost are
 * better low. This is presentation metadata, not a scientific transformation of
 * the values — the raw numbers are always shown alongside.
 */
const SCALES = {
  delivery: { min: 0, max: 100, favourable: 'high', label: 'Delivery',
              direction: 'higher is better' },
  toxicity: { min: 0, max: 10, favourable: 'low', label: 'Toxicity',
              direction: 'lower is better' },
  cost: { min: 0, max: 100, favourable: 'low', label: 'Cost',
          direction: 'lower is better' },
} as const;

type ComponentKey = keyof typeof SCALES;

/** Tone by position within the component's own favourable direction. */
function toneFor(key: ComponentKey, value: number): ScoreTone {
  const s = SCALES[key];
  const frac = (value - s.min) / (s.max - s.min || 1);
  const good = s.favourable === 'high' ? frac : 1 - frac;
  if (good >= 0.7) return 'good';
  if (good >= 0.4) return 'moderate';
  return 'poor';
}

function normalisedFor(key: ComponentKey, value: number): number {
  const s = SCALES[key];
  const frac = Math.min(1, Math.max(0, (value - s.min) / (s.max - s.min || 1)));
  return s.favourable === 'high' ? frac : 1 - frac;
}

export function ResultPanel({
  data, onEdit, onRecalculate,
}: {
  data: DesignScoreResponse;
  onEdit: () => void;
  onRecalculate: () => void;
}) {
  const [tab, setTab] = useState('breakdown');
  const score = data.design_impact_score;
  const keys: ComponentKey[] = ['delivery', 'toxicity', 'cost'];

  const normalisedInputs = Object.entries(data.normalized_inputs);

  return (
    <div data-testid="result-card" className="result">
      <p className="result__caption">
        Three separate canonical measures. <strong>No single composite score is
        produced</strong> — the candidate formula is documented but not
        implemented, pending scientific review.
      </p>

      {/* ------------------------------------------------------ gauges */}
      <div className="result__gauges">
        {keys.map((k) => (
          <ScoreGauge
            key={k}
            label={SCALES[k].label}
            value={score[k]}
            min={SCALES[k].min}
            max={SCALES[k].max}
            direction={SCALES[k].direction}
            tone={toneFor(k, score[k])}
          />
        ))}
      </div>

      {/* ------------------------------------------------------- tabs */}
      <div className="result__tabs">
        <Tabs
          ariaLabel="Result detail"
          active={tab}
          onChange={setTab}
          tabs={[
            { id: 'breakdown', label: 'Breakdown' },
            { id: 'profile', label: 'Profile' },
            { id: 'inputs', label: `Inputs (${normalisedInputs.length})` },
            {
              id: 'warnings',
              label: 'Warnings',
              badge: data.warnings.length
                ? <Badge tone="warn" className="result__tabbadge">{data.warnings.length}</Badge>
                : undefined,
            },
          ]}
        />
      </div>

      {tab === 'breakdown' && (
        <div role="tabpanel" id="panel-breakdown" aria-labelledby="tab-breakdown"
             className="result__panel">
          <ComponentBars
            caption="Component scores"
            data={keys.map((k) => ({
              key: k,
              label: SCALES[k].label,
              value: score[k],
              min: SCALES[k].min,
              max: SCALES[k].max,
              tone: toneFor(k, score[k]),
              scale: `${SCALES[k].min}–${SCALES[k].max} · ${SCALES[k].direction}`,
            }))}
          />
          <DataTable
            caption="Component score detail"
            head={[
              { key: 'c', label: 'Component' },
              { key: 'v', label: 'Value', numeric: true },
              { key: 'm', label: 'Meaning' },
            ]}
          >
            {Object.entries(data.component_scores).map(([name, c]) => (
              <tr key={name}>
                <th scope="row" className="result__ccell">{SCALES[name as ComponentKey]?.label ?? name}</th>
                <td className="is-numeric">{c.value.toFixed(4)}</td>
                <td>{c.meaning}<span className="result__cscale">{c.scale}</span></td>
              </tr>
            ))}
          </DataTable>
        </div>
      )}

      {tab === 'profile' && (
        <div role="tabpanel" id="panel-profile" aria-labelledby="tab-profile"
             className="result__panel result__panel--radar">
          <ComponentRadar
            caption={
              'Position of each component within its own favourable range '
              + '(outer edge = more favourable). Raw values:'
            }
            axes={keys.map((k) => ({
              key: k,
              label: SCALES[k].label,
              normalised: normalisedFor(k, score[k]),
              display: `${score[k].toFixed(2)} of ${SCALES[k].max} (${SCALES[k].direction})`,
            }))}
          />
          <ul className="result__radarkey">
            {keys.map((k) => (
              <li key={k}>
                <span className="result__radarkey-label">{SCALES[k].label}</span>
                <span className="result__radarkey-value">
                  {score[k].toFixed(2)}<span> / {SCALES[k].max}</span>
                </span>
                <span className="result__radarkey-dir">{SCALES[k].direction}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {tab === 'inputs' && (
        <div role="tabpanel" id="panel-inputs" aria-labelledby="tab-inputs"
             className="result__panel">
          <p className="result__hint">
            The effective values used by the engine, after its own documented
            defaults were applied. These make the result reproducible.
          </p>
          <DataTable
            caption="Normalised inputs"
            dense
            head={[
              { key: 'p', label: 'Parameter' },
              { key: 'v', label: 'Value', numeric: true },
            ]}
          >
            {normalisedInputs.map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{k}</th>
                <td className="is-numeric">
                  {Array.isArray(v) ? v.join(', ') : String(v)}
                </td>
              </tr>
            ))}
          </DataTable>
        </div>
      )}

      {tab === 'warnings' && (
        <div role="tabpanel" id="panel-warnings" aria-labelledby="tab-warnings"
             className="result__panel">
          {data.warnings.length === 0 ? (
            <Alert tone="success" title="No warnings">
              The engine reported no interpretation notes for this calculation.
            </Alert>
          ) : (
            <ul className="result__warnings" data-testid="warnings">
              {data.warnings.map((w) => (
                <li key={w}>
                  <Icon name="info" size={15} />
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* -------------------------------------------------- provenance */}
      <section className="result__provenance" aria-labelledby="prov-head">
        <h3 id="prov-head" className="result__subhead">Provenance &amp; validation</h3>
        <dl className="result__prov">
          <div>
            <dt>Model / formula version</dt>
            <dd data-testid="score-version"><code>{data.score_version}</code></dd>
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
            <dd><Badge tone="danger" dot>{data.validation_status}</Badge></dd>
          </div>
        </dl>
      </section>

      <section className="result__limits" aria-labelledby="lim-head">
        <h3 id="lim-head" className="result__subhead">Limitations</h3>
        <ul className="result__limitlist">
          {data.limitations.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </section>

      <div className="result__actions">
        <Button variant="secondary" onClick={onEdit} iconLeft={<Icon name="edit" size={15} />}>
          Edit this design
        </Button>
        <Button variant="ghost" onClick={onRecalculate} iconLeft={<Icon name="refresh" size={15} />}>
          Recalculate
        </Button>
      </div>
    </div>
  );
}
