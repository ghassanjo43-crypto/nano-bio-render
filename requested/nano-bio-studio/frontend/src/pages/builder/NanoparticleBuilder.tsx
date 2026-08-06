/**
 * Nanoparticle 3D Builder.
 *
 * Loads the current design from the workflow session — there is no second
 * nanoparticle data model. Everything shown comes from `buildVisualModel`,
 * which attaches a provenance to every property, so the picture and the
 * parameter table can never disagree about what is known and what is drawn for
 * illustration.
 *
 * The 3D scene is a lazy chunk. Three.js and its dependencies are large, and
 * most sessions never open the builder, so they must not be in the initial
 * bundle.
 *
 * Nothing here writes to the design except an explicitly confirmed preset.
 * Choosing an illustrative architecture or payload location changes the picture
 * only; the scientific inputs to the design score and the PK model are
 * untouched.
 */

import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState }
  from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Badge, Button, Card, Dialog, SelectField, SkeletonBlock,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { useWorkflow } from '../../workflow/WorkflowContext';
import {
  ARCHITECTURES, CHARGE_BANDS, PRESETS, PROVENANCE_LABEL, PROVENANCE_TONE,
  VISUAL_DISCLAIMER, buildVisualModel, chargeBand,
  type Architecture, type PayloadLocation, type Preset, type Property,
} from './particleModel';
import InternalStructurePanel from './InternalStructurePanel';
import MolecularPopulationPanel, { ScientificLegend }
  from './MolecularPopulationPanel';
import {
  resolveBudget, seedForModel, type DetailLevel, type QualityPreset,
} from './detailLevels';
import {
  buildPopulationReport, type MolecularAssumptions,
} from './molecularPopulation';
import {
  applyTransparencyPreset, buildLayers, initialLayerStates, isolateLayer,
  type LayerId, type TransparencyPreset,
} from './layers';
import {
  DEFAULT_VIEWER_STATE, describeView, type ViewMode, type ViewerState,
} from './sceneOptions';
import './NanoparticleBuilder.css';

const ParticleScene = lazy(() => import('./ParticleScene'));

/** WebGL availability, probed once. */
function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(
      window.WebGLRenderingContext
      && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')),
    );
  } catch {
    return false;
  }
}

/**
 * Display switches that are not part of the Internal Structure group.
 * Per-layer visibility lives in the layer panel; these are global.
 */
const TOGGLES: Array<{
  key: 'showLabels' | 'showLigands' | 'showPayload'
    | 'payloadDistributionView' | 'showMeasurements' | 'autoRotate'
    | 'reducedMotion';
  label: string; hint: string;
}> = [
  { key: 'showLabels', label: 'Scientific labels',
    hint: 'Component labels in the 3D view.' },
  { key: 'showLigands', label: 'Show ligands',
    hint: 'Representative targeting-ligand markers.' },
  { key: 'showPayload', label: 'Show payload',
    hint: 'Representative encapsulated-payload markers.' },
  { key: 'payloadDistributionView', label: 'Payload distribution view',
    hint: 'Spread the payload markers so the pattern is legible.' },
  { key: 'showMeasurements', label: 'Measurement overlay',
    hint: 'Diameter and core rules, using supplied values only.' },
  { key: 'autoRotate', label: 'Auto-rotate', hint: 'Rotate continuously.' },
  { key: 'reducedMotion', label: 'Reduced motion',
    hint: 'Disable animated transitions and continuous rotation.' },
];

export default function NanoparticleBuilder() {
  const navigate = useNavigate();
  const { session, setValue, setChips } = useWorkflow();

  const [architecture, setArchitecture] = useState<Architecture | null>(null);
  const [payloadLocation, setPayloadLocation] =
    useState<PayloadLocation | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedLayer, setSelectedLayer] = useState<LayerId | null>(null);
  const [detail, setDetail] = useState<DetailLevel>('overview');
  const [quality, setQuality] = useState<QualityPreset>('balanced');
  const [visualDensity, setVisualDensity] = useState(1);
  // Molecular constants the design does not record. Empty by default: a
  // default here would silently manufacture a molecular count.
  const [assumptions, setAssumptions] = useState<MolecularAssumptions>({});
  const [pendingPreset, setPendingPreset] = useState<Preset | null>(null);
  const [captureNote, setCaptureNote] = useState<string | null>(null);
  const [webgl] = useState(webglAvailable);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const shellRef = useRef<HTMLDivElement | null>(null);

  const model = useMemo(
    () => buildVisualModel(session.values, session.chips, {
      architectureOverride: architecture,
      payloadLocationOverride: payloadLocation,
      therapeutic: session.selection.drug,
    }),
    [session.values, session.chips, architecture, payloadLocation,
     session.selection.drug]);

  // The layer list is derived from the architecture in effect, so a structure
  // the design does not record never appears as a layer.
  const layers = useMemo(() => buildLayers(model), [model]);

  const [state, setState] = useState<ViewerState>(() => ({
    ...DEFAULT_VIEWER_STATE,
    layers: initialLayerStates(buildLayers(model)),
    // Honour the operating system's reduced-motion preference at first load.
    reducedMotion: typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  }));

  // Adding or removing a layer (for example by switching architecture) must
  // not drop the states of layers that are still present.
  useEffect(() => {
    setState((prev) => {
      const fresh = initialLayerStates(layers);
      const merged = { ...fresh };
      for (const layer of layers) {
        if (prev.layers[layer.id]) merged[layer.id] = prev.layers[layer.id]!;
      }
      return { ...prev, layers: merged };
    });
  }, [layers]);

  /* --------------------------------------------- population and budget */
  const budget = useMemo(() => resolveBudget(
    detail, quality,
    Math.round(96 * visualDensity),
    Math.round(model.payloadGlyphs * visualDensity)),
    [detail, quality, visualDensity, model.payloadGlyphs]);

  const renderedCounts = useMemo(() => ({
    lipids: model.architecture.value === 'liposome' ? budget.surfaceGlyphs : 0,
    peg_chains: model.coatingLabel.value !== null ? budget.surfaceGlyphs : 0,
    ligands: Math.min(model.ligandGlyphs, budget.surfaceGlyphs),
    functional_groups: model.functionalGroups.value.length > 0
      ? Math.min(24, budget.surfaceGlyphs) : 0,
    payload_molecules: budget.payloadGlyphs,
    pore_bound_molecules: 0,
    surface_bound_drug: 0,
    coating_units: model.coatingLabel.value !== null ? budget.surfaceGlyphs : 0,
  }), [model, budget]);

  const ligandDensityPercent = useMemo(() => {
    const raw = session.values.ligand_density_percent;
    const parsed = raw === undefined || raw === '' ? null : Number(raw);
    return parsed !== null && Number.isFinite(parsed) ? parsed : null;
  }, [session.values.ligand_density_percent]);

  const populationReport = useMemo(
    () => buildPopulationReport(model, assumptions, renderedCounts,
                                ligandDensityPercent),
    [model, assumptions, renderedCounts, ligandDensityPercent]);

  const seed = useMemo(() => seedForModel(model), [model]);

  const setAssumption = useCallback(
    (key: keyof MolecularAssumptions, value: string) => {
      setAssumptions((prev) => {
        const next = { ...prev };
        if (value === '') { delete next[key]; return next; }
        if (key === 'ligandDensityDefinition') {
          next[key] = value as MolecularAssumptions['ligandDensityDefinition'];
        } else {
          const parsed = Number(value);
          if (Number.isFinite(parsed)) {
            (next[key] as number) = parsed;
          }
        }
        return next;
      });
    }, []);

  const patch = useCallback((next: Partial<ViewerState>) => {
    setState((prev) => ({ ...prev, ...next }));
  }, []);

  /**
   * Switching mode adjusts only how layers are drawn. It never changes the
   * architecture, the design, or which layers exist.
   */
  const setMode = useCallback((mode: ViewMode) => {
    setState((prev) => {
      const next: ViewerState = { ...prev, mode };
      if (mode === 'transparent' && prev.transparencyPreset === null) {
        // The transparent mode needs enclosing layers softened to mean
        // anything; it is applied as a preset so the layer panel agrees.
        next.layers = applyTransparencyPreset(layers, prev.layers, 'internal');
        next.transparencyPreset = 'internal';
      }
      if (mode === 'whole') {
        next.layers = applyTransparencyPreset(layers, prev.layers, 'opaque');
        next.transparencyPreset = 'opaque';
      }
      return next;
    });
  }, [layers]);

  const toggleLayer = useCallback((id: LayerId) => {
    setState((prev) => ({
      ...prev,
      isolated: null,
      layers: {
        ...prev.layers,
        [id]: { ...prev.layers[id]!, visible: !prev.layers[id]!.visible },
      },
    }));
  }, []);

  const setLayerOpacity = useCallback((id: LayerId, opacity: number) => {
    setState((prev) => ({
      ...prev,
      transparencyPreset: null,
      layers: { ...prev.layers, [id]: { ...prev.layers[id]!, opacity } },
    }));
  }, []);

  const isolate = useCallback((id: LayerId) => {
    setState((prev) => ({
      ...prev,
      isolated: id,
      layers: isolateLayer(layers, prev.layers, id),
    }));
    setSelectedLayer(id);
  }, [layers]);

  const restoreAll = useCallback(() => {
    setState((prev) => ({
      ...prev, isolated: null, layers: initialLayerStates(layers),
    }));
  }, [layers]);

  const applyTransparency = useCallback((preset: TransparencyPreset) => {
    setState((prev) => ({
      ...prev,
      transparencyPreset: preset,
      layers: applyTransparencyPreset(layers, prev.layers, preset),
    }));
  }, [layers]);

  const resetView = useCallback(() => {
    setState({
      ...DEFAULT_VIEWER_STATE,
      layers: initialLayerStates(layers),
      reducedMotion: state.reducedMotion,
    });
    setSelectedLayer(null);
  }, [layers, state.reducedMotion]);

  const visibleLayerLabels = layers
    .filter((l) => state.layers[l.id]?.visible)
    .map((l) => l.label);

  // A plain-language account of what the canvas is showing, so the viewer is
  // usable without seeing it. Announced politely rather than assertively.
  const viewDescription = describeView(state, visibleLayerLabels);

  /* --------------------------------------------------------- image capture */
  const capture = useCallback((scale: number, transparent: boolean) => {
    const canvas = canvasRef.current;
    if (!canvas) { setCaptureNote('The 3D view is not ready yet.'); return; }
    // The canvas already holds the rendered frame because the renderer is
    // created with preserveDrawingBuffer.
    const out = document.createElement('canvas');
    out.width = canvas.width * scale;
    out.height = canvas.height * scale;
    const ctx = out.getContext('2d');
    if (!ctx) { setCaptureNote('Image capture is not available.'); return; }
    if (!transparent) {
      ctx.fillStyle = state.background === 'light' ? '#eef2f7' : '#0b1220';
      ctx.fillRect(0, 0, out.width, out.height);
    }
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(canvas, 0, 0, out.width, out.height);

    out.toBlob((blob) => {
      if (!blob) { setCaptureNote('Image capture failed.'); return; }
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      // The view mode and the study's own name identify the export. No patient
      // information is included: the builder never receives any.
      const safeName = (session.name || 'study')
        .replace(/[^a-z0-9]+/gi, '-').toLowerCase().slice(0, 40);
      a.download = `nanoparticle-${safeName}-${state.mode}`
        + `${transparent ? '-transparent' : ''}`
        + `${scale > 1 ? `-${scale}x` : ''}.png`;
      a.click();
      URL.revokeObjectURL(url);
      setCaptureNote(`Saved ${a.download}.`);
    }, 'image/png');
  }, [state.background, state.mode, session.name]);

  const saveCameraView = useCallback(() => {
    // A camera view is a display preference, so it lives in localStorage
    // alongside other display state, never in the design record.
    localStorage.setItem('nanobio.builderView.v1', JSON.stringify({
      state, architecture, payloadLocation,
    }));
    setCaptureNote('Camera view and layer settings saved for this browser.');
  }, [state, architecture, payloadLocation]);

  /* ---------------------------------------------------------------- preset */
  function applyPreset(preset: Preset) {
    for (const [key, value] of Object.entries(preset.designValues)) {
      if (value !== undefined) setValue(key, value);
    }
    for (const [key, value] of Object.entries(preset.chips)) {
      if (value !== undefined) setChips(key, value);
    }
    setArchitecture(preset.architecture);
    setPendingPreset(null);
  }

  return (
    <>
      <Card
        title="Nanoparticle 3D Builder"
        subtitle="An interactive visual model of the design currently in this study."
        accent
        actions={
          <Button variant="secondary" onClick={() => navigate('/workflow/design')}
                  iconLeft={<Icon name="chevron-left" size={15} />}>
            Back to design parameters
          </Button>
        }
      >
        <Alert tone="warn" title="Visual representation">
          <p data-testid="visual-disclaimer">{VISUAL_DISCLAIMER}</p>
          <p data-testid="population-caveat">
            Rendered objects do not necessarily correspond one-to-one with
            physical molecules.
          </p>
          <ScientificLegend />
        </Alert>

        {model.warnings.length > 0 && (
          <div data-testid="geometry-warnings">
            <Alert tone="danger" title="Geometry cannot be drawn as entered">
              <ul>
                {model.warnings.map((w) => <li key={w.code}>{w.message}</li>)}
              </ul>
            </Alert>
          </div>
        )}

        <div className="np3d__layout">
          {/* ------------------------------------------------ the viewport */}
          <div className="np3d__viewport" ref={shellRef}
               data-testid="builder-viewport"
               role="img" aria-label={viewDescription}>
            {!webgl ? (
              <div className="np3d__fallback" data-testid="webgl-unavailable">
                <Icon name="info" size={20} />
                <p><strong>3D rendering is unavailable in this browser.</strong></p>
                <p>
                  WebGL could not be initialised, so the interactive model
                  cannot be shown. Every design value remains available in the
                  table below, and the rest of NanoBio Studio is unaffected.
                </p>
              </div>
            ) : (
              <Suspense fallback={
                <div className="np3d__loading" data-testid="scene-loading">
                  <SkeletonBlock lines={3} />
                  <p>Loading the 3D module…</p>
                </div>
              }>
                <ParticleScene
                  model={model}
                  layers={layers}
                  state={state}
                  detail={detail}
                  budget={budget}
                  seed={seed}
                  onSelect={setSelectedLayer}
                  onCanvasReady={(c) => { canvasRef.current = c; }}
                />
              </Suspense>
            )}
          </div>

          <p className="np3d__description" data-testid="view-description"
             aria-live="polite">
            {viewDescription}
          </p>

          {/* ------------------------------------------------- the controls */}
          <div className="np3d__controls">
            <h4>Structure</h4>
            <SelectField
              id="np-architecture"
              label="Architecture (illustrative)"
              value={architecture ?? ''}
              onChange={(e) => setArchitecture(
                (e.target.value || null) as Architecture | null)}
              options={[
                { value: '', label: 'Structure not specified' },
                ...ARCHITECTURES.map((a) => ({ value: a.id, label: a.label })),
              ]}
            />
            <p className="np3d__hint">
              The design schema records no architecture field. This selection
              changes the picture only — it is not stored and does not affect
              any calculation.
            </p>

            <SelectField
              id="np-payload-location"
              label="Payload location (illustrative)"
              value={payloadLocation ?? ''}
              onChange={(e) => setPayloadLocation(
                (e.target.value || null) as PayloadLocation | null)}
              options={[
                { value: '', label: 'Unspecified — assumed distribution' },
                { value: 'hydrophilic_core', label: 'Hydrophilic (interior)' },
                { value: 'hydrophobic_bilayer', label: 'Hydrophobic (bilayer)' },
                { value: 'dispersed', label: 'Dispersed through the matrix' },
              ]}
            />

            <InternalStructurePanel
              model={model}
              layers={layers}
              state={state}
              selected={selectedLayer}
              onModeChange={setMode}
              onPatch={patch}
              onLayerToggle={toggleLayer}
              onLayerOpacity={setLayerOpacity}
              onIsolate={isolate}
              onSelect={setSelectedLayer}
              onRestoreAll={restoreAll}
              onPreset={applyTransparency}
              onReset={resetView}
            />

            <MolecularPopulationPanel
              report={populationReport}
              assumptions={assumptions}
              onAssumption={setAssumption}
              detail={detail}
              onDetail={setDetail}
              quality={quality}
              onQuality={setQuality}
              budget={budget}
              visualDensity={visualDensity}
              onVisualDensity={setVisualDensity}
            />

            <h4>Display</h4>
            <ul className="np3d__toggles" data-testid="view-toggles">
              {TOGGLES.map((t) => (
                <li key={t.key}>
                  <label>
                    <input
                      type="checkbox"
                      checked={Boolean(state[t.key])}
                      onChange={() => patch({ [t.key]: !state[t.key] })}
                      data-testid={`toggle-${t.key}`}
                    />
                    <span>{t.label}</span>
                  </label>
                  <span className="np3d__hint">{t.hint}</span>
                </li>
              ))}
            </ul>

            <SelectField
              id="np-background" label="Background"
              value={state.background}
              onChange={(e) => patch({
                background: e.target.value as ViewerState['background'],
              })}
              options={[
                { value: 'dark', label: 'Dark scientific' },
                { value: 'light', label: 'Light scientific' },
                { value: 'transparent', label: 'Transparent' },
              ]}
            />

            <div className="np3d__buttons">
              <Button size="sm" variant="secondary" onClick={resetView}
                      data-testid="reset-camera">
                Reset view
              </Button>
              <Button size="sm" variant="secondary"
                      onClick={() => shellRef.current?.requestFullscreen?.()}
                      data-testid="fullscreen">
                Fullscreen
              </Button>
            </div>

            <h4>Capture</h4>
            <div className="np3d__buttons">
              <Button size="sm" variant="secondary"
                      onClick={() => capture(1, false)}
                      data-testid="capture-png">PNG</Button>
              <Button size="sm" variant="secondary"
                      onClick={() => capture(1, true)}
                      data-testid="capture-transparent">Transparent PNG</Button>
              <Button size="sm" variant="secondary"
                      onClick={() => capture(3, false)}
                      data-testid="capture-hires">High-resolution</Button>
              <Button size="sm" variant="ghost" onClick={saveCameraView}
                      data-testid="save-view">Save view</Button>
            </div>
            {captureNote && (
              <p className="np3d__hint" data-testid="capture-note">
                {captureNote}
              </p>
            )}
          </div>
        </div>
      </Card>

      {/* ------------------------------------------------------- provenance */}
      <Card title="Provenance legend"
            subtitle="What is measured, what is calculated, and what is drawn for illustration.">
        <ul className="np3d__legend" data-testid="provenance-legend">
          {(Object.keys(PROVENANCE_LABEL) as Array<keyof typeof PROVENANCE_LABEL>)
            .map((p) => (
              <li key={p}>
                <Badge tone={PROVENANCE_TONE[p]} dot>
                  {PROVENANCE_LABEL[p]}
                </Badge>
              </li>
            ))}
        </ul>

        {state.layers.charge_field?.visible && (
          <>
            <h4>Surface charge legend</h4>
            <ul className="np3d__legend" data-testid="charge-legend">
              {CHARGE_BANDS.map((b) => (
                <li key={b.label}>
                  <span className="np3d__swatch"
                        style={{ background: b.colour }} aria-hidden="true" />
                  {b.label}
                </li>
              ))}
            </ul>
            {model.chargeMv !== null && (
              <p className="np3d__hint" data-testid="charge-current">
                This design: {model.chargeMv} mV —{' '}
                {chargeBand(model.chargeMv).label}. The bands are a display
                scale for the legend, not a classification of colloidal
                stability.
              </p>
            )}
          </>
        )}

        <h4>Design properties</h4>
        <ul className="np3d__properties" data-testid="property-table">
          {model.properties.map((p: Property<unknown>) => (
            <li key={p.key} data-testid={`property-${p.key}`}
                className={selected === p.key ? 'is-selected' : ''}>
              <button type="button" onClick={() => setSelected(p.key)}>
                <span className="np3d__pname">{p.label}</span>
                <span className="np3d__pvalue mono">
                  {p.value === null || (Array.isArray(p.value)
                                        && p.value.length === 0)
                    ? '—'
                    : Array.isArray(p.value) ? p.value.join(', ')
                    : String(p.value)}
                  {p.unit ? ` ${p.unit}` : ''}
                </span>
                <Badge tone={PROVENANCE_TONE[p.provenance]}>
                  {PROVENANCE_LABEL[p.provenance]}
                </Badge>
              </button>
              {selected === p.key && (p.origin || p.formula) && (
                <p className="np3d__origin" data-testid={`origin-${p.key}`}>
                  {p.formula ?? p.origin}
                </p>
              )}
            </li>
          ))}
        </ul>

        {model.missing.length > 0 && (
          <Alert tone="info" title="Structural properties not recorded">
            <p data-testid="missing-list">
              The design does not record: {model.missing.join(', ')}. Anything
              drawn for these is an illustrative assumption and is labelled as
              such.
            </p>
            <Button size="sm" variant="secondary"
                    onClick={() => navigate('/workflow/design')}
                    data-testid="complete-design">
              Return and complete the design
            </Button>
          </Alert>
        )}

        {model.assumptions.length > 0 && (
          <>
            <h4>Illustrative assumptions in this image</h4>
            <ul className="np3d__assumptions" data-testid="assumption-list">
              {model.assumptions.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </>
        )}
      </Card>

      {/* ----------------------------------------------------------- presets */}
      <Card title="Starting templates"
            subtitle="Conventional configurations, not measured formulations.">
        <ul className="np3d__presets" data-testid="preset-list">
          {PRESETS.map((preset) => (
            <li key={preset.id}>
              <div>
                <strong>{preset.label}</strong>
                <p className="np3d__hint">{preset.description}</p>
              </div>
              <Button size="sm" variant="secondary"
                      onClick={() => setPendingPreset(preset)}
                      data-testid={`preset-${preset.id}`}>
                Apply template
              </Button>
            </li>
          ))}
        </ul>
      </Card>

      <Dialog
        open={pendingPreset !== null}
        onClose={() => setPendingPreset(null)}
        title="Apply this starting template?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingPreset(null)}>
              Cancel
            </Button>
            <Button onClick={() => pendingPreset && applyPreset(pendingPreset)}
                    data-testid="confirm-preset">
              Overwrite design values
            </Button>
          </>
        }
      >
        <p>
          <strong>{pendingPreset?.label}</strong> will overwrite these stored
          design parameters:
        </p>
        <ul className="mono" data-testid="preset-changes">
          {Object.entries(pendingPreset?.designValues ?? {}).map(([k, v]) => (
            <li key={k}>{k} = {v}</li>
          ))}
          {Object.entries(pendingPreset?.chips ?? {}).map(([k, v]) => (
            <li key={k}>{k} = {(v ?? []).join(', ')}</li>
          ))}
        </ul>
        <p>
          These are conventional illustrative values, not measurements of your
          formulation. They change the inputs the scientific engines will
          receive, so nothing is applied until you confirm.
        </p>
      </Dialog>
    </>
  );
}
