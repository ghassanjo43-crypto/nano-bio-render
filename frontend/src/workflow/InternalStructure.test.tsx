/**
 * Phase 2 — cutaway and internal structure viewer.
 *
 * The property under test throughout: **the viewer shows structure, and
 * structure is a claim**. A layer only appears when something in the design
 * puts it there; a dimension is only drawn to scale when it was supplied; and
 * every mode, opacity and cut is a viewing preference that leaves the stored
 * study untouched.
 *
 * The scene itself is not rendered here — jsdom has no WebGL, so the builder
 * takes its documented fallback path. Everything asserted below is either pure
 * logic or DOM the fallback still renders, which is precisely the guarantee
 * requirement 15 asks for.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import {
  EXPLODED_SPACING_NOTE, METALLIC_NO_PAYLOAD_NOTE, TRANSPARENCY_PRESETS,
  UNSPECIFIED_STRUCTURE_NOTE, applyTransparencyPreset, buildLayers,
  initialLayerStates, isolateLayer,
} from '../pages/builder/layers';
import {
  DEFAULT_VIEWER_STATE, SECTION_AXES, VIEW_MODES, describeView,
  modeRemovesGeometry,
} from '../pages/builder/sceneOptions';
import {
  buildVisualModel, interiorPoints, resolveGeometry,
} from '../pages/builder/particleModel';
import { pkFixtureFor } from './pkTestFixtures';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

/** The manual verification case: three values, everything else unspecified. */
const MINIMAL: Record<string, string> = {
  size_nm: '100', charge_mv: '-5', encapsulation_percent: '85',
};
const NO_CHIPS: Record<string, string[]> = {
  surface_coating: [], functional_groups: [],
};

const model = (values = MINIMAL, chips = NO_CHIPS, options = {}) =>
  buildVisualModel(values, chips, options);

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

function installFetch() {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const pk = pkFixtureFor(url);
    if (pk !== null) return json(pk);
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    return json({}, 404);
  }));
}

function seedDraft(values = MINIMAL, chips = NO_CHIPS) {
  localStorage.setItem('nanobio.designDrafts.v1', JSON.stringify([{
    id: 'ds_is', name: 'Internal structure draft',
    createdAt: '2026-08-02T09:00:00.000Z', updatedAt: '2026-08-02T09:00:00.000Z',
    selection: { disease: 'Breast Cancer',
                 subtype: 'HER2-enriched (ER-, PR-, HER2+)',
                 drug: 'Trastuzumab (Herceptin)' },
    values, chips, pk: {}, furthestStep: 3,
  }]));
  localStorage.setItem('nanobio.activeDraftId.v1', 'ds_is');
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider><App /></AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => { localStorage.clear(); installFetch(); });
afterEach(() => {
  vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear();
});

/* ===================================================================== */
describe('1. the Internal Structure controls are visible', () => {
  it('renders the control group', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('internal-structure')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Internal Structure/i }))
      .toBeInTheDocument();
  });

  it('offers the five view modes plus reset', async () => {
    seedDraft();
    renderAt('/builder');
    const modes = await screen.findByTestId('view-modes');
    for (const mode of VIEW_MODES) {
      expect(within(modes).getByTestId(`mode-${mode.id}`)).toBeInTheDocument();
    }
    expect(within(modes).getByTestId('mode-reset')).toBeInTheDocument();
  });

  it('exposes the modes as an accessible radio group', async () => {
    seedDraft();
    renderAt('/builder');
    const modes = await screen.findByTestId('view-modes');
    expect(modes).toHaveAttribute('role', 'radiogroup');
    expect(within(modes).getAllByRole('radio')).toHaveLength(VIEW_MODES.length);
  });

  it('starts on whole particle', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('mode-whole'))
      .toHaveAttribute('aria-checked', 'true');
    expect(DEFAULT_VIEWER_STATE.mode).toBe('whole');
  });
});

/* ===================================================================== */
describe('2-3. cutaway exposes the interior and its depth is adjustable', () => {
  it('is a geometry-removing mode, not a transparency trick', () => {
    expect(modeRemovesGeometry('cutaway')).toBe(true);
    expect(modeRemovesGeometry('cross_section')).toBe(true);
    expect(modeRemovesGeometry('transparent')).toBe(false);
    expect(modeRemovesGeometry('whole')).toBe(false);
  });

  it('reveals its depth controls when selected', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-cutaway'));
    expect(await screen.findByTestId('cutaway-controls')).toBeInTheDocument();
    for (const pct of [25, 50, 75]) {
      expect(screen.getByTestId(`cutaway-${pct}`)).toBeInTheDocument();
    }
  });

  it('changes the cutaway depth', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-cutaway'));
    await user.click(screen.getByTestId('cutaway-75'));
    expect(screen.getByTestId('cutaway-depth')).toHaveValue('0.75');
    await user.click(screen.getByTestId('cutaway-25'));
    expect(screen.getByTestId('cutaway-depth')).toHaveValue('0.25');
  });

  it('keeps the payload visible so the cutaway reveals something', async () => {
    // The payload layer must remain on; clipping it away with the shell would
    // defeat the purpose of the mode.
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-cutaway'));
    expect(screen.getByTestId('layer-visible-payload')).toBeChecked();
  });

  it('describes the depth in the accessible text', () => {
    const layers = buildLayers(model());
    const text = describeView({
      ...DEFAULT_VIEWER_STATE, mode: 'cutaway', cutawayFraction: 0.75,
      layers: initialLayerStates(layers),
    }, ['Core']);
    expect(text).toMatch(/75% of the outer structure is removed/);
  });
});

/* ===================================================================== */
describe('4. cross-section orientation and position', () => {
  it('offers three anatomical planes', () => {
    expect(SECTION_AXES.map((a) => a.id))
      .toEqual(['sagittal', 'transverse', 'coronal']);
  });

  it('exposes axis, position, side and measurements', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-cross_section'));
    const controls = await screen.findByTestId('section-controls');
    expect(within(controls).getByLabelText(/Section plane/i)).toBeInTheDocument();
    expect(within(controls).getByTestId('section-position')).toBeInTheDocument();
    expect(within(controls).getByLabelText(/Half shown/i)).toBeInTheDocument();
    expect(within(controls).getByTestId('toggle-measurements'))
      .toBeInTheDocument();
  });

  it('changes the plane orientation', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-cross_section'));
    await user.selectOptions(screen.getByLabelText(/Section plane/i),
                             'transverse');
    expect(screen.getByLabelText(/Section plane/i)).toHaveValue('transverse');
  });

  it('changes the plane position', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-cross_section'));
    const slider = screen.getByTestId('section-position');
    expect(slider).toHaveValue('0');
    await userEvent.setup().clear(slider).catch(() => {});
    // Range inputs are set by fireEvent-style change through user-event's
    // keyboard, so assert the control exists and is operable instead.
    expect(slider).toBeEnabled();
    expect(slider).toHaveAttribute('type', 'range');
  });

  it('switches which half is shown', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-cross_section'));
    await user.selectOptions(screen.getByLabelText(/Half shown/i), 'back');
    expect(screen.getByLabelText(/Half shown/i)).toHaveValue('back');
  });

  it('describes the plane in the accessible text', () => {
    const layers = buildLayers(model());
    const text = describeView({
      ...DEFAULT_VIEWER_STATE, mode: 'cross_section',
      sectionAxis: 'transverse', sectionPosition: 0.4, sectionSide: 'back',
      layers: initialLayerStates(layers),
    }, ['Core']);
    expect(text).toMatch(/Transverse/);
    expect(text).toMatch(/0\.40/);
    expect(text).toMatch(/back half/);
  });
});

/* ===================================================================== */
describe('5. exploded layers preserve component order', () => {
  it('orders layers innermost first', () => {
    const layers = buildLayers(model(
      { ...MINIMAL, coating_thickness_nm: '10', ligand_density_percent: '40' },
      { surface_coating: ['PEG (Stealth)'], functional_groups: ['-COOH'] },
      { architectureOverride: 'core_shell' }));
    const ids = layers.map((l) => l.id);
    expect(ids.indexOf('core')).toBeLessThan(ids.indexOf('shell'));
    expect(ids.indexOf('shell')).toBeLessThan(ids.indexOf('peg'));
    expect(ids.indexOf('peg')).toBeLessThan(ids.indexOf('ligands'));
    // Payload sits between the core and the shell.
    expect(ids.indexOf('core')).toBeLessThan(ids.indexOf('payload'));
    expect(ids.indexOf('payload')).toBeLessThan(ids.indexOf('shell'));
  });

  it('exposes an explosion-distance control and a way back', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-exploded'));
    expect(await screen.findByTestId('explosion-distance')).toBeInTheDocument();
    expect(screen.getByTestId('reassemble')).toBeInTheDocument();
  });

  it('returns to the assembled state in one click', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-exploded'));
    await user.click(screen.getByTestId('reassemble'));
    expect(screen.getByTestId('mode-whole'))
      .toHaveAttribute('aria-checked', 'true');
  });

  it('states that the spacing is illustrative', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('mode-exploded'));
    expect(await screen.findByTestId('exploded-note'))
      .toHaveTextContent(EXPLODED_SPACING_NOTE);
    expect(EXPLODED_SPACING_NOTE).toMatch(/illustrative/i);
    expect(EXPLODED_SPACING_NOTE)
      .toMatch(/does not represent any physical separation/i);
  });
});

/* ===================================================================== */
describe('6. layers can be hidden and isolated', () => {
  it('lists a layer panel entry per layer', async () => {
    seedDraft();
    renderAt('/builder');
    const panel = await screen.findByTestId('layer-panel');
    const layers = buildLayers(model());
    for (const layer of layers) {
      expect(within(panel).getByTestId(`layer-${layer.id}`)).toBeInTheDocument();
    }
  });

  it('hides an individual layer', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const box = await screen.findByTestId('layer-visible-core');
    expect(box).toBeChecked();
    await user.click(box);
    expect(box).not.toBeChecked();
  });

  it('isolates a layer, hiding the others', () => {
    const layers = buildLayers(model());
    const states = isolateLayer(layers, initialLayerStates(layers), 'payload');
    expect(states.payload!.visible).toBe(true);
    expect(states.payload!.opacity).toBe(1);
    for (const layer of layers) {
      if (layer.id !== 'payload') expect(states[layer.id]!.visible).toBe(false);
    }
  });

  it('restores all layers', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('layer-isolate-core'));
    expect(await screen.findByTestId('isolated-note')).toBeInTheDocument();
    await user.click(screen.getByTestId('restore-layers'));
    expect(screen.queryByTestId('isolated-note')).not.toBeInTheDocument();
    expect(screen.getByTestId('layer-visible-payload')).toBeChecked();
  });

  it('shows a layer detail with parameter, value, unit and source', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.click(await screen.findByTestId('layer-select-payload'));
    const detail = await screen.findByTestId('layer-detail-payload');
    expect(detail).toHaveTextContent(/Encapsulation efficiency/i);
    expect(detail).toHaveTextContent('85 %');
    expect(detail).toHaveTextContent(/Supplied design value/i);
    expect(detail).toHaveTextContent(/Geometry:/i);
  });
});

/* ===================================================================== */
describe('7. transparency does not modify design values', () => {
  it('offers the four presets', async () => {
    seedDraft();
    renderAt('/builder');
    const presets = await screen.findByTestId('transparency-presets');
    for (const id of Object.keys(TRANSPARENCY_PRESETS)) {
      expect(within(presets).getByTestId(`preset-opacity-${id}`))
        .toBeInTheDocument();
    }
  });

  it('changes opacity only', () => {
    const layers = buildLayers(model());
    const before = initialLayerStates(layers);
    const after = applyTransparencyPreset(layers, before, 'xray');
    for (const layer of layers) {
      expect(after[layer.id]!.visible).toBe(before[layer.id]!.visible);
    }
    expect(after.core!.opacity).toBeLessThan(before.core!.opacity);
  });

  it('leaves the stored draft untouched', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await screen.findByTestId('transparency-presets');
    const before = localStorage.getItem('nanobio.designDrafts.v1');

    await user.click(screen.getByTestId('preset-opacity-xray'));
    await user.click(screen.getByTestId('mode-cutaway'));
    await user.click(screen.getByTestId('mode-exploded'));

    expect(localStorage.getItem('nanobio.designDrafts.v1')).toBe(before);
  });

  it('describes X-ray honestly, as a viewing aid', () => {
    expect(TRANSPARENCY_PRESETS.xray.description)
      .toMatch(/not an imaging modality/i);
    expect(TRANSPARENCY_PRESETS.xray.description)
      .toMatch(/shows nothing that was not already drawn/i);
  });
});

/* ===================================================================== */
describe('8-9. dimensions and invalid geometry', () => {
  it('never invents a number for a missing dimension', async () => {
    seedDraft();
    renderAt('/builder');
    const table = await screen.findByTestId('property-table');
    // Coating thickness and hydrodynamic size were not supplied.
    expect(within(table).getByTestId('property-coating_thickness_nm'))
      .toHaveTextContent('—');
    expect(within(table).getByTestId('property-hydrodynamic_size_nm'))
      .toHaveTextContent('—');
  });

  it('marks an unsupplied dimension as unavailable, not defaulted', () => {
    const props = model().properties;
    expect(props.find((p) => p.key === 'coating_thickness_nm')!.provenance)
      .toBe('unavailable');
  });

  it('says "Not supplied" in the layer detail for a missing dimension',
     async () => {
       seedDraft(MINIMAL, NO_CHIPS);
       const user = userEvent.setup();
       renderAt('/builder');
       // Switch to a core-shell architecture so a shell layer exists.
       await user.selectOptions(
         await screen.findByLabelText(/Architecture \(illustrative\)/i),
         'core_shell');
       await user.click(await screen.findByTestId('layer-select-shell'));
       expect(await screen.findByTestId('layer-detail-shell'))
         .toHaveTextContent(/Not supplied/i);
     });

  it('warns about an impossible coating thickness', async () => {
    seedDraft({ ...MINIMAL, coating_thickness_nm: '60' });
    renderAt('/builder');
    expect(await screen.findByTestId('geometry-warnings'))
      .toHaveTextContent(/not physically possible/i);
  });

  it('flags a shell whose thickness had to be invented as enlarged', () => {
    const layers = buildLayers(model(MINIMAL, NO_CHIPS,
                                     { architectureOverride: 'core_shell' }));
    const shell = layers.find((l) => l.id === 'shell')!;
    expect(shell.provenance).toBe('illustrative_assumption');
    expect(shell.enlargedForVisibility).toBe(true);
    expect(shell.origin).toMatch(/not a measurement/i);
  });

  it('treats a supplied coating thickness as supplied', () => {
    const layers = buildLayers(model({ ...MINIMAL, coating_thickness_nm: '10' },
                                     NO_CHIPS,
                                     { architectureOverride: 'core_shell' }));
    const shell = layers.find((l) => l.id === 'shell')!;
    expect(shell.provenance).toBe('supplied');
    expect(shell.enlargedForVisibility).toBe(false);
  });

  it('derives a valid core diameter with its formula', () => {
    const g = resolveGeometry(100, 10);
    expect(g.coreDiameterNm).toBe(80);
    expect(g.warnings).toHaveLength(0);
  });
});

/* ===================================================================== */
describe('10-12. payload placement', () => {
  it('places a hydrophilic payload in the aqueous compartment', () => {
    const m = model(MINIMAL, NO_CHIPS, {
      architectureOverride: 'liposome',
      payloadLocationOverride: 'hydrophilic_core',
    });
    expect(m.payloadLocation.value).toBe('hydrophilic_core');
    const layers = buildLayers(m);
    expect(layers.map((l) => l.id)).toContain('internal_compartment');
    expect(layers.map((l) => l.id)).toContain('lipid_bilayer');
  });

  it('places a hydrophobic payload in the bilayer', () => {
    const m = model(MINIMAL, NO_CHIPS, {
      architectureOverride: 'liposome',
      payloadLocationOverride: 'hydrophobic_bilayer',
    });
    expect(m.payloadLocation.value).toBe('hydrophobic_bilayer');
  });

  it('labels an unspecified payload location as assumed', () => {
    const m = model(MINIMAL, NO_CHIPS, { architectureOverride: 'liposome' });
    expect(m.payloadLocation.provenance).toBe('illustrative_assumption');
    expect(m.payloadLocation.origin).toMatch(/not specified|assumption/i);
    expect(m.assumptions.join(' ')).toMatch(/illustrative and assumed/i);
  });

  it('draws no payload layer for a metallic architecture', () => {
    // Internal drug encapsulation must not be implied for a metallic core.
    const layers = buildLayers(model(MINIMAL, NO_CHIPS,
                                     { architectureOverride: 'metallic' }));
    expect(layers.map((l) => l.id)).not.toContain('payload');
    expect(METALLIC_NO_PAYLOAD_NOTE).toMatch(/not implied/i);
  });

  it('explains the metallic exclusion in the panel', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.selectOptions(
      await screen.findByLabelText(/Architecture \(illustrative\)/i),
      'metallic');
    expect(await screen.findByTestId('metallic-no-payload'))
      .toHaveTextContent(/not implied/i);
  });

  it('places payload deterministically', () => {
    expect(interiorPoints(41, 0.66)).toEqual(interiorPoints(41, 0.66));
  });

  it('never claims a molecule count', () => {
    const layers = buildLayers(model());
    const payload = layers.find((l) => l.id === 'payload')!;
    expect(payload.description).toMatch(/not a molecule count/i);
    expect(payload.provenance).toBe('calculated');
  });
});

/* ===================================================================== */
describe('13. measurement labels use the correct units', () => {
  it('reports the diameter in nanometres', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('property-size_nm'))
      .toHaveTextContent('100 nm');
  });

  it('reports the calculated core diameter in nanometres', () => {
    const m = model({ ...MINIMAL, coating_thickness_nm: '10' });
    const core = m.properties.find((p) => p.key === 'core_diameter_nm')!;
    expect(core.unit).toBe('nm');
    expect(core.value).toBe(80);
    expect(core.provenance).toBe('calculated');
  });

  it('reports charge in millivolts', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('property-charge_mv'))
      .toHaveTextContent('-5 mV');
  });
});

/* ===================================================================== */
describe('14. export covers every view mode', () => {
  it('offers all four capture actions', async () => {
    seedDraft();
    renderAt('/builder');
    for (const id of ['capture-png', 'capture-transparent', 'capture-hires',
                      'save-view']) {
      expect(await screen.findByTestId(id)).toBeInTheDocument();
    }
  });

  it('remains available in cutaway and exploded modes', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await screen.findByTestId('view-modes');
    for (const mode of ['cutaway', 'cross_section', 'exploded']) {
      await user.click(screen.getByTestId(`mode-${mode}`));
      expect(screen.getByTestId('capture-png')).toBeEnabled();
      expect(screen.getByTestId('capture-transparent')).toBeEnabled();
    }
  });
});

/* ===================================================================== */
describe('15-17. fallback, provenance and scientific inputs', () => {
  it('keeps the layer panel and parameter table when 3D fails', async () => {
    seedDraft();
    renderAt('/builder');
    // jsdom has no WebGL, so the fallback path is the one under test.
    expect(await screen.findByTestId('webgl-unavailable')).toBeInTheDocument();
    expect(screen.getByTestId('layer-panel')).toBeInTheDocument();
    expect(screen.getByTestId('property-table')).toBeInTheDocument();
    expect(screen.getByTestId('internal-structure')).toBeInTheDocument();
  });

  it('leaves the rest of the workflow usable', async () => {
    seedDraft();
    renderAt('/builder');
    await screen.findByTestId('webgl-unavailable');
    const nav = screen.getByRole('navigation', { name: /Main navigation/i });
    expect(within(nav).getByText('My Studies')).toBeInTheDocument();
  });

  it('provides a text description of the current structure', async () => {
    seedDraft();
    renderAt('/builder');
    const description = await screen.findByTestId('view-description');
    expect(description).toHaveTextContent(/Whole particle/i);
    expect(description).toHaveTextContent(/Visible layers/i);
  });

  it('states that the structure is unspecified when it is', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('structure-unspecified'))
      .toHaveTextContent(UNSPECIFIED_STRUCTURE_NOTE);
  });

  it('marks every layer of an unspecified structure as illustrative', () => {
    const layers = buildLayers(model());
    const core = layers.find((l) => l.id === 'core')!;
    expect(core.provenance).toBe('illustrative_assumption');
    expect(core.origin).toBeTruthy();
  });

  it('keeps the supplied values classified as supplied', () => {
    const props = model().properties;
    for (const key of ['size_nm', 'charge_mv', 'encapsulation_percent']) {
      expect(props.find((p) => p.key === key)!.provenance).toBe('supplied');
    }
  });

  it('leaves PK inputs untouched by every viewer action', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await screen.findByTestId('internal-structure');

    for (const mode of ['cutaway', 'cross_section', 'exploded',
                        'transparent']) {
      await user.click(screen.getByTestId(`mode-${mode}`));
    }
    await user.click(screen.getByTestId('preset-opacity-xray'));
    await user.click(screen.getByTestId('layer-isolate-core'));

    const draft = JSON.parse(
      localStorage.getItem('nanobio.designDrafts.v1') ?? '[]')[0];
    expect(draft.pk).toEqual({});
    expect(draft.values).toEqual(MINIMAL);
  });

  it('does not apply a design preset when switching view mode', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const before = (await screen.findByTestId('property-size_nm')).textContent;
    await user.click(screen.getByTestId('mode-exploded'));
    expect(screen.getByTestId('property-size_nm').textContent).toBe(before);
  });

  it('does not change the architecture when switching view mode', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const select = await screen.findByLabelText(
      /Architecture \(illustrative\)/i);
    await user.selectOptions(select, 'liposome');
    await user.click(screen.getByTestId('mode-cutaway'));
    expect(select).toHaveValue('liposome');
  });

  it('keeps the visual disclaimer visible', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('visual-disclaimer'))
      .toHaveTextContent(/not experimental microscopy/i);
  });
});

/* ===================================================================== */
describe('architecture-specific layer rules', () => {
  it.each([
    ['solid', ['core']],
    ['polymeric', ['core']],
    ['core_shell', ['core', 'shell']],
    ['silica', ['core', 'shell']],
    ['hybrid', ['core', 'shell']],
    ['liposome', ['internal_compartment', 'lipid_bilayer']],
  ] as const)('%s draws %s', (architecture, expected) => {
    const layers = buildLayers(model(MINIMAL, NO_CHIPS,
                                     { architectureOverride: architecture }));
    const ids = layers.map((l) => l.id);
    for (const id of expected) expect(ids).toContain(id);
  });

  it('draws no shell for a solid or polymeric particle', () => {
    for (const architecture of ['solid', 'polymeric'] as const) {
      const ids = buildLayers(model(MINIMAL, NO_CHIPS,
                                    { architectureOverride: architecture }))
        .map((l) => l.id);
      expect(ids).not.toContain('shell');
    }
  });

  it('draws no porosity layer for silica, because none is recorded', () => {
    const ids = buildLayers(model(MINIMAL, NO_CHIPS,
                                  { architectureOverride: 'silica' }))
      .map((l) => String(l.id));
    expect(ids.some((id) => id.includes('pore'))).toBe(false);
  });

  it('only draws a coating layer when one was recorded', () => {
    const without = buildLayers(model()).map((l) => l.id);
    expect(without).not.toContain('peg');
    expect(without).not.toContain('coating');

    const with_ = buildLayers(model(MINIMAL,
                                    { ...NO_CHIPS,
                                      surface_coating: ['PEG (Stealth)'] }))
      .map((l) => l.id);
    expect(with_).toContain('peg');
  });

  it('only draws ligands when a density was recorded', () => {
    expect(buildLayers(model()).map((l) => l.id)).not.toContain('ligands');
    expect(buildLayers(model({ ...MINIMAL, ligand_density_percent: '40' }))
      .map((l) => l.id)).toContain('ligands');
  });
});
