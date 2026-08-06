/**
 * Molecular Population panel.
 *
 * Shows, for every repeated component, the estimated physical population and
 * the rendered population as **two separate numbers**, plus the ratio between
 * them when — and only when — the physical count is known.
 *
 * The common case is that it is not known, and the panel says so with the
 * missing inputs named. That is the honest state for a design that records a
 * diameter and a percentage but no molecular constants.
 */

import { Badge, SelectField } from '../../design-system/components';
import {
  ASSUMPTION_FIELDS, POPULATION_DISCLAIMER, formatCount,
  type MolecularAssumptions, type PopulationEstimate,
} from './molecularPopulation';
import {
  DETAIL_LEVELS, MOLECULAR_PATCH_NOTE, QUALITY_PRESETS,
  type DetailLevel, type QualityPreset, type RenderBudget,
} from './detailLevels';

export interface MolecularPopulationPanelProps {
  report: PopulationEstimate[];
  assumptions: MolecularAssumptions;
  onAssumption: (key: keyof MolecularAssumptions, value: string) => void;
  detail: DetailLevel;
  onDetail: (level: DetailLevel) => void;
  quality: QualityPreset;
  onQuality: (quality: QualityPreset) => void;
  budget: RenderBudget;
  visualDensity: number;
  onVisualDensity: (value: number) => void;
}

const BLOCK_TONE = {
  missing_inputs: 'neutral',
  ambiguous_definition: 'warn',
  not_applicable: 'neutral',
} as const;

export default function MolecularPopulationPanel({
  report, assumptions, onAssumption, detail, onDetail, quality, onQuality,
  budget, visualDensity, onVisualDensity,
}: MolecularPopulationPanelProps) {
  return (
    <section className="np3d__population" aria-labelledby="np3d-population"
             data-testid="population-panel">
      <h4 id="np3d-population">Molecular population</h4>

      <p className="np3d__assumed" data-testid="population-disclaimer">
        {POPULATION_DISCLAIMER}
      </p>

      {/* ------------------------------------------------- detail level */}
      <SelectField
        id="np3d-detail" label="Detail level" value={detail}
        onChange={(e) => onDetail(e.target.value as DetailLevel)}
        options={DETAIL_LEVELS.map((d) => ({ value: d.id, label: d.label }))}
      />
      <p className="np3d__hint" data-testid="detail-description">
        {DETAIL_LEVELS.find((d) => d.id === detail)!.description}
      </p>
      {detail === 'molecular' && (
        <p className="np3d__assumed" data-testid="molecular-patch-note">
          {MOLECULAR_PATCH_NOTE}
        </p>
      )}

      <SelectField
        id="np3d-quality" label="Rendering quality" value={quality}
        onChange={(e) => onQuality(e.target.value as QualityPreset)}
        options={(Object.keys(QUALITY_PRESETS) as QualityPreset[])
          .map((q) => ({ value: q, label: QUALITY_PRESETS[q].label }))}
      />

      <label htmlFor="np3d-density">
        Visual density: {Math.round(visualDensity * 100)}%
      </label>
      <input
        id="np3d-density" type="range" min={0.1} max={1} step={0.05}
        value={visualDensity}
        onChange={(e) => onVisualDensity(Number(e.target.value))}
        data-testid="visual-density"
      />
      <p className="np3d__hint">
        Visual density changes how many representative objects are drawn. It
        changes no scientific input and no estimated population.
      </p>

      {budget.capped && (
        <p className="np3d__assumed" data-testid="performance-capped">
          Fewer objects are drawn than the current settings requested, because a
          performance cap applies. The estimated physical populations below are
          unaffected — only the sample size on screen changed.
        </p>
      )}

      {/* --------------------------------------------------- the report */}
      {report.length === 0 ? (
        <p className="np3d__hint">
          This design has no repeated molecular components to report.
        </p>
      ) : (
        <ul className="np3d__populations" data-testid="population-list">
          {report.map((e) => (
            <li key={e.component} data-testid={`population-${e.component}`}>
              <div className="np3d__poprow">
                <strong>{e.label}</strong>
                {e.physicalCount === null ? (
                  <Badge tone={BLOCK_TONE[e.blockReason ?? 'missing_inputs']}>
                    Not calculated from current data
                  </Badge>
                ) : (
                  <Badge tone="accent">
                    {e.provenance === 'researcher_supplied'
                      ? 'Researcher-supplied inputs' : 'Calculated value'}
                  </Badge>
                )}
              </div>

              <dl className="np3d__popfacts">
                <div>
                  <dt>Estimated physical population</dt>
                  <dd className="mono" data-testid={`physical-${e.component}`}>
                    {e.physicalCount === null
                      ? 'Cannot calculate from current inputs'
                      : formatCount(e.physicalCount)}
                    {e.physicalRange && (
                      <span className="np3d__range">
                        {' '}(range {formatCount(e.physicalRange[0])}–
                        {formatCount(e.physicalRange[1])})
                      </span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Rendered representative objects</dt>
                  <dd className="mono" data-testid={`rendered-${e.component}`}>
                    {e.renderedCount}
                  </dd>
                </div>
                <div>
                  <dt>Representation ratio</dt>
                  <dd className="mono" data-testid={`ratio-${e.component}`}>
                    {e.representationRatio === null
                      ? 'Unknown — the physical population is not calculated'
                      : `1 rendered object ≈ `
                        + `${formatCount(Math.round(e.representationRatio))} `
                        + 'units'}
                  </dd>
                </div>
              </dl>

              {/* The reason is shown WITHOUT expanding: an ambiguous
                  definition is a different problem from missing data, and a
                  capacity bound is not a loading. Both need to be read at a
                  glance, not discovered. */}
              <p className="np3d__assumed" data-testid={`note-${e.component}`}>
                {e.note}
              </p>

              <details className="np3d__popmethod">
                <summary>Method, inputs and formula</summary>
                <p><strong>Method:</strong> {e.method}</p>
                {e.formula && <p className="mono">{e.formula}</p>}
                {Object.keys(e.usedInputs).length > 0 && (
                  <>
                    <p><strong>Inputs used:</strong></p>
                    <ul>
                      {Object.entries(e.usedInputs).map(([k, v]) => (
                        <li key={k}><span className="mono">{k} = {v}</span></li>
                      ))}
                    </ul>
                  </>
                )}
                {e.missingInputs.length > 0 && (
                  <>
                    <p><strong>Missing required inputs:</strong></p>
                    <ul data-testid={`missing-${e.component}`}>
                      {e.missingInputs.map((m) => <li key={m}>{m}</li>)}
                    </ul>
                  </>
                )}
              </details>
            </li>
          ))}
        </ul>
      )}

      {/* ------------------------------------------- researcher inputs */}
      <details className="np3d__assumptions" data-testid="molecular-assumptions">
        <summary>Supply molecular constants (expert)</summary>
        <p className="np3d__hint">
          The design schema records none of these. Anything you enter here is
          <strong> your own research input</strong>, is labelled as such in
          every estimate it feeds, and changes no design value or simulation
          input. Blank means “not supplied” — no default is applied.
        </p>
        <ul className="np3d__assumptionfields">
          {ASSUMPTION_FIELDS.map((f) => (
            <li key={f.key}>
              <label htmlFor={`np3d-${f.key}`}>
                {f.label} <span className="np3d__unit">({f.unit})</span>
              </label>
              <input
                id={`np3d-${f.key}`} type="number" step="any"
                value={(assumptions[f.key] as number | undefined) ?? ''}
                onChange={(e) => onAssumption(f.key, e.target.value)}
                placeholder="not supplied"
                data-testid={`assumption-${f.key}`}
              />
              <span className="np3d__hint">{f.help}</span>
            </li>
          ))}
          <li>
            <label htmlFor="np3d-density-definition">
              Definition of the percentage ligand density
            </label>
            <select
              id="np3d-density-definition"
              value={assumptions.ligandDensityDefinition ?? ''}
              onChange={(e) => onAssumption('ligandDensityDefinition',
                                            e.target.value)}
              data-testid="assumption-ligandDensityDefinition"
            >
              <option value="">Not recorded — treated as ambiguous</option>
              <option value="surface_coverage_fraction">
                Fractional surface coverage
              </option>
              <option value="molar_percent">Molar percent</option>
              <option value="mass_percent">Mass percent</option>
              <option value="per_area">Molecules per unit area</option>
            </select>
            <span className="np3d__hint">
              Until this is recorded, a percentage cannot be converted into a
              count: the four meanings give different answers.
            </span>
          </li>
        </ul>
      </details>
    </section>
  );
}

/** The legend replacing the old single-line disclaimer. */
export function ScientificLegend() {
  const entries: Array<[string, string]> = [
    ['Scientific dimensions',
     'Drawn to the supplied or calculated dimension.'],
    ['Geometry enlarged for visibility',
     'Drawn larger than scale so it can be seen; the numeric value is exact.'],
    ['Estimated physical population',
     'A molecule count computed from stated inputs and a stated formula.'],
    ['Representative rendered population',
     'The objects actually drawn. Not a molecule count.'],
    ['Illustrative component',
     'Drawn so something could be shown. Not a recorded property.'],
    ['Structure unavailable',
     'No molecular structure exists for this component in the platform.'],
    ['Not calculated from current data',
     'The inputs a calculation would require are absent or ambiguous.'],
  ];
  return (
    <ul className="np3d__scilegend" data-testid="scientific-legend">
      {entries.map(([term, meaning]) => (
        <li key={term}>
          <strong>{term}</strong>
          <span>{meaning}</span>
        </li>
      ))}
    </ul>
  );
}
