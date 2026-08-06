/**
 * The Internal Structure control group and the layer panel.
 *
 * Split out of `NanoparticleBuilder` because it is substantial and entirely
 * about viewing state. Nothing here writes to the design: every control changes
 * how the particle is drawn and nothing else.
 */

import { Badge, Button, SelectField } from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import {
  ENLARGED_LAYER_NOTE, EXPLODED_SPACING_NOTE, METALLIC_NO_PAYLOAD_NOTE,
  TRANSPARENCY_PRESETS, UNSPECIFIED_STRUCTURE_NOTE,
  type LayerId, type LayerSpec, type TransparencyPreset,
} from './layers';
import {
  CUTAWAY_FRACTIONS, SECTION_AXES, VIEW_MODES, snapCutawayFraction,
  type ViewMode, type ViewerState,
} from './sceneOptions';
import { PROVENANCE_LABEL, PROVENANCE_TONE, type VisualModel } from './particleModel';

export interface InternalStructurePanelProps {
  model: VisualModel;
  layers: LayerSpec[];
  state: ViewerState;
  selected: LayerId | null;
  onModeChange: (mode: ViewMode) => void;
  onPatch: (patch: Partial<ViewerState>) => void;
  onLayerToggle: (id: LayerId) => void;
  onLayerOpacity: (id: LayerId, opacity: number) => void;
  onIsolate: (id: LayerId) => void;
  onSelect: (id: LayerId) => void;
  onRestoreAll: () => void;
  onPreset: (preset: TransparencyPreset) => void;
  onReset: () => void;
}

export default function InternalStructurePanel({
  model, layers, state, selected, onModeChange, onPatch, onLayerToggle,
  onLayerOpacity, onIsolate, onSelect, onRestoreAll, onPreset, onReset,
}: InternalStructurePanelProps) {
  const architectureAssumed =
    model.architecture.provenance === 'illustrative_assumption';
  const selectedLayer = selected
    ? layers.find((l) => l.id === selected) : undefined;
  const selectedProperty = selectedLayer?.designKey
    ? model.properties.find((p) => p.key === selectedLayer.designKey)
    : undefined;

  return (
    <section className="np3d__internal" aria-labelledby="np3d-internal"
             data-testid="internal-structure">
      <h4 id="np3d-internal">Internal Structure</h4>

      {architectureAssumed && (
        <p className="np3d__assumed" data-testid="structure-unspecified">
          {UNSPECIFIED_STRUCTURE_NOTE}
        </p>
      )}

      {/* ------------------------------------------------------- modes */}
      <div className="np3d__modes" role="radiogroup"
           aria-label="Internal structure view mode" data-testid="view-modes">
        {VIEW_MODES.map((mode) => (
          <button
            key={mode.id}
            type="button"
            role="radio"
            aria-checked={state.mode === mode.id}
            className={`np3d__mode${state.mode === mode.id ? ' is-on' : ''}`}
            onClick={() => onModeChange(mode.id)}
            title={mode.description}
            data-testid={`mode-${mode.id}`}
          >
            {mode.label}
          </button>
        ))}
        <button type="button" className="np3d__mode"
                onClick={onReset} data-testid="mode-reset">
          Reset view
        </button>
      </div>

      <p className="np3d__hint" data-testid="mode-description">
        {VIEW_MODES.find((m) => m.id === state.mode)!.description}
      </p>

      {/* ----------------------------------------------------- cutaway */}
      {state.mode === 'cutaway' && (
        <div className="np3d__submode" data-testid="cutaway-controls">
          <label htmlFor="np3d-cutaway-depth">
            Cutaway depth:{' '}
            {Math.round(snapCutawayFraction(state.cutawayFraction) * 100)}%
            removed
          </label>
          <input
            id="np3d-cutaway-depth" type="range" min={0.1} max={0.9} step={0.05}
            value={state.cutawayFraction}
            onChange={(e) => onPatch({
              cutawayFraction: Number(e.target.value) })}
            data-testid="cutaway-depth"
          />
          <div className="np3d__buttons">
            {CUTAWAY_FRACTIONS.map((f) => (
              <Button key={f} size="sm"
                      variant={state.cutawayFraction === f
                        ? 'primary' : 'secondary'}
                      onClick={() => onPatch({ cutawayFraction: f })}
                      data-testid={`cutaway-${Math.round(f * 100)}`}>
                {Math.round(f * 100)}%
              </Button>
            ))}
          </div>
          <p className="np3d__hint">
            A wedge of the enclosing layers is geometrically removed. The
            remaining shell keeps its thickness, and the particle can still be
            rotated freely. Depth snaps to 25%, 50% or 75%: those are the cuts
            plane clipping can express exactly.
          </p>
        </div>
      )}

      {/* ----------------------------------------------- cross-section */}
      {state.mode === 'cross_section' && (
        <div className="np3d__submode" data-testid="section-controls">
          <SelectField
            id="np3d-section-axis" label="Section plane"
            value={state.sectionAxis}
            onChange={(e) => onPatch({
              sectionAxis: e.target.value as ViewerState['sectionAxis'] })}
            options={SECTION_AXES.map((a) => ({ value: a.id, label: a.label }))}
          />
          <label htmlFor="np3d-section-pos">
            Plane position: {state.sectionPosition.toFixed(2)} of the radius
          </label>
          <input
            id="np3d-section-pos" type="range" min={-0.95} max={0.95} step={0.05}
            value={state.sectionPosition}
            onChange={(e) => onPatch({
              sectionPosition: Number(e.target.value) })}
            data-testid="section-position"
          />
          <SelectField
            id="np3d-section-side" label="Half shown"
            value={state.sectionSide}
            onChange={(e) => onPatch({
              sectionSide: e.target.value as 'front' | 'back' })}
            options={[{ value: 'front', label: 'Front half' },
                      { value: 'back', label: 'Back half' }]}
          />
          <label className="np3d__check">
            <input type="checkbox" checked={state.showMeasurements}
                   onChange={() => onPatch({
                     showMeasurements: !state.showMeasurements })}
                   data-testid="toggle-measurements" />
            Measurement overlay
          </label>
        </div>
      )}

      {/* -------------------------------------------------- exploded */}
      {state.mode === 'exploded' && (
        <div className="np3d__submode" data-testid="exploded-controls">
          <label htmlFor="np3d-explosion">
            Explosion distance: {state.explosionDistance.toFixed(2)}
          </label>
          <input
            id="np3d-explosion" type="range" min={0} max={2.5} step={0.05}
            value={state.explosionDistance}
            onChange={(e) => onPatch({
              explosionDistance: Number(e.target.value) })}
            data-testid="explosion-distance"
          />
          <Button size="sm" variant="secondary"
                  onClick={() => onModeChange('whole')}
                  data-testid="reassemble">
            Return to assembled
          </Button>
          <p className="np3d__assumed" data-testid="exploded-note">
            {EXPLODED_SPACING_NOTE}
          </p>
        </div>
      )}

      {/* ------------------------------------------------ transparency */}
      <h4>Transparency</h4>
      <div className="np3d__buttons" data-testid="transparency-presets">
        {(Object.keys(TRANSPARENCY_PRESETS) as TransparencyPreset[]).map((p) => (
          <Button key={p} size="sm"
                  variant={state.transparencyPreset === p
                    ? 'primary' : 'secondary'}
                  onClick={() => onPreset(p)}
                  title={TRANSPARENCY_PRESETS[p].description}
                  data-testid={`preset-opacity-${p}`}>
            {TRANSPARENCY_PRESETS[p].label}
          </Button>
        ))}
      </div>
      <p className="np3d__hint">
        Transparency is a viewing aid. It changes nothing about the stored
        formulation and reveals nothing that was not already drawn.
      </p>

      {/* -------------------------------------------------- layer panel */}
      <h4>Layers</h4>
      {layers.length === 0 ? (
        <p className="np3d__hint">No layers are defined for this design.</p>
      ) : (
        <ul className="np3d__layers" data-testid="layer-panel">
          {layers.map((layer) => {
            const entry = state.layers[layer.id];
            const isSelected = selected === layer.id;
            return (
              <li key={layer.id} data-testid={`layer-${layer.id}`}
                  className={isSelected ? 'is-selected' : ''}>
                <div className="np3d__layerrow">
                  <label className="np3d__check">
                    <input
                      type="checkbox"
                      checked={entry?.visible ?? false}
                      onChange={() => onLayerToggle(layer.id)}
                      aria-label={`Show ${layer.label}`}
                      data-testid={`layer-visible-${layer.id}`}
                    />
                  </label>
                  <button type="button" className="np3d__layername"
                          onClick={() => onSelect(layer.id)}
                          data-testid={`layer-select-${layer.id}`}>
                    {layer.label}
                  </button>
                  <Badge tone={PROVENANCE_TONE[layer.provenance]}>
                    {PROVENANCE_LABEL[layer.provenance]}
                  </Badge>
                  <button type="button" className="np3d__isolate"
                          onClick={() => onIsolate(layer.id)}
                          aria-label={`Isolate ${layer.label}`}
                          data-testid={`layer-isolate-${layer.id}`}>
                    <Icon name="shield" size={13} /> Isolate
                  </button>
                </div>
                <input
                  type="range" min={0.05} max={1} step={0.05}
                  value={entry?.opacity ?? 1}
                  onChange={(e) => onLayerOpacity(layer.id,
                                                  Number(e.target.value))}
                  aria-label={`${layer.label} opacity`}
                  data-testid={`layer-opacity-${layer.id}`}
                />
                {isSelected && (
                  <div className="np3d__layerdetail"
                       data-testid={`layer-detail-${layer.id}`}>
                    <p>{layer.description}</p>
                    {selectedProperty && (
                      <p className="mono">
                        {selectedProperty.label}:{' '}
                        {selectedProperty.value === null
                          ? 'Not supplied'
                          : `${String(selectedProperty.value)} ${selectedProperty.unit}`}
                        {' — '}
                        {PROVENANCE_LABEL[selectedProperty.provenance]}
                      </p>
                    )}
                    {!selectedProperty && layer.designKey && (
                      <p className="mono">
                        {layer.designKey}: Not supplied
                      </p>
                    )}
                    <p className="np3d__hint">
                      Geometry: {layer.provenance === 'supplied'
                        ? 'drawn from the supplied dimension'
                        : layer.provenance === 'calculated'
                          ? 'drawn from a calculated dimension'
                          : 'illustrative'}
                      {layer.enlargedForVisibility
                        ? ` — ${ENLARGED_LAYER_NOTE}` : ''}
                    </p>
                    {layer.origin && (
                      <p className="np3d__assumed">{layer.origin}</p>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <div className="np3d__buttons">
        <Button size="sm" variant="secondary" onClick={onRestoreAll}
                data-testid="restore-layers">
          Restore all layers
        </Button>
      </div>

      {state.isolated && (
        <p className="np3d__hint" data-testid="isolated-note">
          Showing only <strong>{state.isolated}</strong>. Use “Restore all
          layers” to bring the rest back.
        </p>
      )}

      {model.architecture.value === 'metallic' && (
        <p className="np3d__assumed" data-testid="metallic-no-payload">
          {METALLIC_NO_PAYLOAD_NOTE}
        </p>
      )}
    </section>
  );
}
