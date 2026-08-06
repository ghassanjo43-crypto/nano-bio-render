/**
 * Nanoparticle 3D Builder.
 *
 * The property under test throughout: **a picture is a claim**. The builder
 * must draw something for a design that records only size, charge and
 * encapsulation efficiency — but every structural detail it invents to do so
 * must be labelled an illustrative assumption, and none of it may reach the
 * stored design or any scientific calculation.
 *
 * The 3D scene itself is not rendered here: jsdom has no WebGL. The builder's
 * WebGL probe therefore takes the fallback path, which is exactly the case
 * requirement 14 describes — and the parameter table, provenance legend and
 * assumption list must all still be present.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import {
  ARCHITECTURES, CHARGE_BANDS, PRESETS, PROVENANCE_LABEL, VISUAL_DISCLAIMER,
  buildVisualModel, chargeBand, fibonacciSphere, interiorPoints,
  ligandGlyphCount, payloadGlyphCount, resolveGeometry,
} from '../pages/builder/particleModel';
import { pkFixtureFor } from './pkTestFixtures';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

/** The manual verification case from the specification. */
const MINIMAL_VALUES: Record<string, string> = {
  size_nm: '100', charge_mv: '-5', encapsulation_percent: '85',
};
const NO_CHIPS: Record<string, string[]> = {
  surface_coating: [], functional_groups: [],
};

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

function seedDraft(values = MINIMAL_VALUES) {
  localStorage.setItem('nanobio.designDrafts.v1', JSON.stringify([{
    id: 'ds_builder', name: 'Builder draft',
    createdAt: '2026-08-02T09:00:00.000Z', updatedAt: '2026-08-02T09:00:00.000Z',
    selection: { disease: 'Breast Cancer',
                 subtype: 'HER2-enriched (ER-, PR-, HER2+)',
                 drug: 'Trastuzumab (Herceptin)' },
    values, chips: NO_CHIPS, pk: {}, furthestStep: 3,
  }]));
  localStorage.setItem('nanobio.activeDraftId.v1', 'ds_builder');
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
describe('mapping of supplied values', () => {
  const model = () => buildVisualModel(MINIMAL_VALUES, NO_CHIPS, {});

  it('marks the three supplied values as supplied', () => {
    const props = model().properties;
    for (const key of ['size_nm', 'charge_mv', 'encapsulation_percent']) {
      const p = props.find((x) => x.key === key)!;
      expect(p.provenance).toBe('supplied');
    }
  });

  it('carries the supplied numbers through unchanged', () => {
    const props = model().properties;
    expect(props.find((p) => p.key === 'size_nm')!.value).toBe(100);
    expect(props.find((p) => p.key === 'charge_mv')!.value).toBe(-5);
    expect(props.find((p) => p.key === 'encapsulation_percent')!.value).toBe(85);
    expect(model().chargeMv).toBe(-5);
  });

  it('uses particle size as the primary diameter', () => {
    expect(model().geometry.outerDiameterNm).toBe(100);
  });

  it('keeps scene scale separate from real dimensions', () => {
    const g = model().geometry;
    // The sphere is normalised to a fixed scene radius so any particle is
    // visible; the nanometre value is reported separately and unchanged.
    expect(g.outerRadius).toBe(1);
    expect(g.outerDiameterNm).toBe(100);
    expect(g.sceneUnitsPerNm).toBeCloseTo(0.02);
  });

  it('reads the therapeutic as the payload identity when supplied', () => {
    const m = buildVisualModel(MINIMAL_VALUES, NO_CHIPS,
                               { therapeutic: 'Trastuzumab (Herceptin)' });
    const payload = m.properties.find((p) => p.key === 'payload')!;
    expect(payload.provenance).toBe('supplied');
    expect(payload.value).toBe('Trastuzumab (Herceptin)');
  });
});

/* ===================================================================== */
describe('missing-value provenance', () => {
  const model = () => buildVisualModel(MINIMAL_VALUES, NO_CHIPS, {});

  it('names every unrecorded structural property', () => {
    const missing = model().missing;
    for (const expected of ['Particle architecture', 'Core material', 'Shape',
                            'Surface coating', 'Targeting ligand',
                            'Ligand density', 'Coating thickness',
                            'Hydrodynamic size', 'Functional groups']) {
      expect(missing).toContain(expected);
    }
  });

  it('marks architecture and shape as illustrative assumptions', () => {
    const props = model().properties;
    for (const key of ['architecture', 'shape', 'payload_location']) {
      expect(props.find((p) => p.key === key)!.provenance)
        .toBe('illustrative_assumption');
    }
  });

  it('gives every assumption a stated origin', () => {
    for (const p of model().properties) {
      if (p.provenance === 'illustrative_assumption') {
        expect(p.origin, `${p.key} has no origin`).toBeTruthy();
      }
    }
  });

  it('never marks an unrecorded property as supplied', () => {
    const props = model().properties;
    for (const key of ['core_material', 'ligand', 'surface_coating',
                       'coating_thickness_nm']) {
      expect(props.find((p) => p.key === key)!.provenance)
        .not.toBe('supplied');
    }
  });

  it('does not invent a core material from the architecture', () => {
    // Choosing "metallic" for the picture must not become a claim that the
    // core IS metal — the design records no material.
    const m = buildVisualModel(MINIMAL_VALUES, NO_CHIPS,
                               { architectureOverride: 'metallic' });
    expect(m.coreMaterial.provenance).toBe('unavailable');
    expect(m.coreMaterial.value).toBeNull();
  });

  it('states the structure is unspecified when none is chosen', () => {
    expect(model().assumptions.join(' ')).toMatch(/Structure not specified/i);
  });

  it('exposes the five provenance categories', () => {
    expect(Object.keys(PROVENANCE_LABEL)).toEqual([
      'supplied', 'engine_default', 'calculated',
      'illustrative_assumption', 'unavailable',
    ]);
  });
});

/* ===================================================================== */
describe('deterministic placement', () => {
  it('produces identical ligand positions for the same count', () => {
    expect(fibonacciSphere(24, 1)).toEqual(fibonacciSphere(24, 1));
  });

  it('produces identical interior positions for the same inputs', () => {
    expect(interiorPoints(18, 0.8)).toEqual(interiorPoints(18, 0.8));
  });

  it('places points on the requested sphere radius', () => {
    for (const [x, y, z] of fibonacciSphere(40, 2)) {
      expect(Math.sqrt(x * x + y * y + z * z)).toBeCloseTo(2, 5);
    }
  });

  it('scales ligand glyphs from density without one-per-molecule', () => {
    expect(ligandGlyphCount(null)).toBe(0);
    expect(ligandGlyphCount(0)).toBe(0);
    expect(ligandGlyphCount(100)).toBe(64);
    expect(ligandGlyphCount(50)).toBe(32);
    // Capped: a real particle carries orders of magnitude more molecules.
    expect(ligandGlyphCount(100)).toBeLessThan(1000);
  });

  it('scales payload glyphs from encapsulation efficiency', () => {
    expect(payloadGlyphCount(null)).toBe(0);
    expect(payloadGlyphCount(85)).toBe(41);
    // A low but nonzero efficiency still shows "some" payload.
    expect(payloadGlyphCount(1)).toBeGreaterThan(0);
    expect(payloadGlyphCount(100)).toBeLessThan(1000);
  });

  it('states that glyph counts are representative, not molecule counts', () => {
    const m = buildVisualModel(MINIMAL_VALUES, NO_CHIPS, {});
    expect(m.assumptions.join(' ')).toMatch(/not a molecule count/i);
  });
});

/* ===================================================================== */
describe('impossible coating geometry', () => {
  it('accepts a valid coating and derives the core diameter', () => {
    const g = resolveGeometry(100, 10);
    expect(g.coreDiameterNm).toBe(80);
    expect(g.warnings).toHaveLength(0);
  });

  it('refuses a coating that consumes the whole particle', () => {
    const g = resolveGeometry(100, 50);
    expect(g.coreDiameterNm).toBeNull();
    expect(g.warnings[0]!.code).toBe('coating_exceeds_radius');
    expect(g.warnings[0]!.message).toMatch(/not physically possible/i);
  });

  it('refuses a coating thicker than the radius', () => {
    const g = resolveGeometry(100, 80);
    expect(g.warnings.map((w) => w.code)).toContain('coating_exceeds_radius');
  });

  it('warns but still draws a very thin core', () => {
    const g = resolveGeometry(100, 45);
    expect(g.coreDiameterNm).toBe(10);
    expect(g.warnings[0]!.code).toBe('core_barely_visible');
    // Enlarged so it is visible, with the true dimension still reported.
    expect(g.coreRadius).toBeGreaterThan(0.1 * g.outerRadius);
  });

  it('records the core diameter as calculated, with its formula', () => {
    const m = buildVisualModel({ ...MINIMAL_VALUES, coating_thickness_nm: '10' },
                               NO_CHIPS, {});
    const core = m.properties.find((p) => p.key === 'core_diameter_nm')!;
    expect(core.provenance).toBe('calculated');
    expect(core.formula).toBe(
      'core diameter = particle size − 2 × coating thickness');
    expect(core.value).toBe(80);
  });
});

/* ===================================================================== */
describe('architecture switching', () => {
  it('offers all seven first-release structures', () => {
    expect(ARCHITECTURES.map((a) => a.id)).toEqual([
      'solid', 'core_shell', 'liposome', 'polymeric', 'metallic', 'silica',
      'hybrid',
    ]);
  });

  it('only the liposome has a distinct aqueous interior', () => {
    const withInterior = ARCHITECTURES.filter((a) => a.hasAqueousInterior);
    expect(withInterior.map((a) => a.id)).toEqual(['liposome']);
  });

  it('switching architecture never changes a supplied value', () => {
    const before = buildVisualModel(MINIMAL_VALUES, NO_CHIPS, {});
    const after = buildVisualModel(MINIMAL_VALUES, NO_CHIPS,
                                   { architectureOverride: 'liposome' });
    for (const key of ['size_nm', 'charge_mv', 'encapsulation_percent']) {
      expect(after.properties.find((p) => p.key === key)!.value)
        .toBe(before.properties.find((p) => p.key === key)!.value);
    }
  });

  it('records a chosen architecture as an assumption, never as supplied', () => {
    const m = buildVisualModel(MINIMAL_VALUES, NO_CHIPS,
                               { architectureOverride: 'liposome' });
    expect(m.architecture.provenance).toBe('illustrative_assumption');
    expect(m.architecture.origin).toMatch(/does not affect any calculation/i);
  });
});

/* ===================================================================== */
describe('charge legend', () => {
  it('bands the supplied charge', () => {
    expect(chargeBand(-5).label).toMatch(/Near neutral/);
    expect(chargeBand(-40).label).toMatch(/Strongly negative/);
    expect(chargeBand(-15).label).toMatch(/^Negative/);
    expect(chargeBand(20).label).toMatch(/^Positive/);
    expect(chargeBand(45).label).toMatch(/Strongly positive/);
  });

  it('covers every value with exactly one band', () => {
    for (const mv of [-100, -30, -10, 0, 10, 30, 100]) {
      expect(chargeBand(mv)).toBeDefined();
    }
    expect(CHARGE_BANDS).toHaveLength(5);
  });
});

/* ===================================================================== */
describe('presets', () => {
  it('offers the four required templates', () => {
    expect(PRESETS.map((p) => p.id)).toEqual([
      'liposome', 'pegylated_polymeric', 'gold', 'silica_core_shell',
    ]);
  });

  it('labels every preset as a starting template', () => {
    for (const preset of PRESETS) {
      expect(preset.description).toMatch(/starting template/i);
      expect(preset.description).toMatch(/not a measured formulation/i);
    }
  });

  it('every preset produces valid geometry', () => {
    for (const preset of PRESETS) {
      const g = resolveGeometry(Number(preset.designValues.size_nm),
                                Number(preset.designValues.coating_thickness_nm));
      expect(g.warnings.filter((w) => w.code === 'coating_exceeds_radius'))
        .toHaveLength(0);
    }
  });
});

/* ===================================================================== */
describe('the builder page', () => {
  it('opens from Step 3 via View in 3D', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/workflow/review');
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });
    await user.click(await screen.findByTestId('view-in-3d'));
    // The title appears in the shell header and on the card; the viewport is
    // the unambiguous signal that the builder itself rendered.
    expect(await screen.findByTestId('builder-viewport')).toBeInTheDocument();
    expect(screen.getByTestId('property-table')).toBeInTheDocument();
  });

  it('loads the current design automatically', async () => {
    seedDraft();
    renderAt('/builder');
    const table = await screen.findByTestId('property-table');
    expect(within(table).getByTestId('property-size_nm'))
      .toHaveTextContent('100 nm');
    expect(within(table).getByTestId('property-charge_mv'))
      .toHaveTextContent('-5 mV');
    expect(within(table).getByTestId('property-encapsulation_percent'))
      .toHaveTextContent('85 %');
  });

  it('shows the required visual disclaimer', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('visual-disclaimer'))
      .toHaveTextContent(VISUAL_DISCLAIMER);
  });

  it('shows the provenance legend', async () => {
    seedDraft();
    renderAt('/builder');
    const legend = await screen.findByTestId('provenance-legend');
    for (const label of Object.values(PROVENANCE_LABEL)) {
      expect(legend).toHaveTextContent(label);
    }
  });

  it('lists the unrecorded structural properties', async () => {
    seedDraft();
    renderAt('/builder');
    const missing = await screen.findByTestId('missing-list');
    expect(missing).toHaveTextContent(/Particle architecture/);
    expect(missing).toHaveTextContent(/Core material/);
    expect(missing).toHaveTextContent(/illustrative assumption/i);
  });

  it('offers a route back to complete the design', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('complete-design')).toBeInTheDocument();
  });

  it('falls back cleanly when WebGL is unavailable', async () => {
    // jsdom provides no WebGL context, which is exactly the fallback case.
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('webgl-unavailable'))
      .toHaveTextContent(/3D rendering is unavailable/i);
    // The parameter table must survive the fallback.
    expect(screen.getByTestId('property-table')).toBeInTheDocument();
  });

  it('keeps the rest of the application working after the fallback', async () => {
    seedDraft();
    renderAt('/builder');
    await screen.findByTestId('webgl-unavailable');
    const nav = screen.getByRole('navigation', { name: /Main navigation/i });
    expect(within(nav).getByText('My Studies')).toBeInTheDocument();
  });

  it('exposes every viewer control as keyboard-reachable', async () => {
    seedDraft();
    renderAt('/builder');
    // Display switches.
    const toggles = await screen.findByTestId('view-toggles');
    const boxes = within(toggles).getAllByRole('checkbox');
    expect(boxes.length).toBeGreaterThanOrEqual(6);
    for (const box of boxes) expect(box).not.toBeDisabled();
    // Internal Structure modes, as a radio group.
    const modes = screen.getByTestId('view-modes');
    const radios = within(modes).getAllByRole('radio');
    expect(radios.length).toBe(5);
    for (const radio of radios) expect(radio).not.toBeDisabled();
  });

  it('changes the view without touching a design value', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const before = localStorage.getItem('nanobio.designDrafts.v1');
    await user.click(await screen.findByTestId('toggle-showLigands'));
    await user.click(screen.getByTestId('mode-cutaway'));
    expect(screen.getByTestId('mode-cutaway')).toHaveAttribute(
      'aria-checked', 'true');
    expect(localStorage.getItem('nanobio.designDrafts.v1')).toBe(before);
  });

  it('shows the charge legend only when the overlay layer is on', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await screen.findByTestId('property-table');
    expect(screen.queryByTestId('charge-legend')).not.toBeInTheDocument();

    // The charge overlay is now a layer, toggled in the layer panel.
    await user.click(screen.getByTestId('layer-visible-charge_field'));
    expect(await screen.findByTestId('charge-legend')).toBeInTheDocument();
    expect(screen.getByTestId('charge-current')).toHaveTextContent(/-5 mV/);
  });

  it('reveals a property origin when it is selected', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const row = await screen.findByTestId('property-architecture');
    await user.click(within(row).getByRole('button'));
    const origin = await screen.findByTestId('origin-architecture');
    // No architecture was chosen, so the default origin is shown — and it must
    // still say the choice carries no scientific weight.
    expect(origin).toHaveTextContent(/Structure not specified/i);
    expect(origin).toHaveTextContent(/does not affect any calculation/i);
  });

  it('states a chosen architecture is illustrative only', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.selectOptions(
      await screen.findByLabelText(/Architecture \(illustrative\)/i),
      'liposome');
    await user.click(
      within(screen.getByTestId('property-architecture')).getByRole('button'));
    expect(await screen.findByTestId('origin-architecture'))
      .toHaveTextContent(/does not affect any calculation/i);
  });

  it('warns about impossible coating geometry on the page', async () => {
    seedDraft({ ...MINIMAL_VALUES, coating_thickness_nm: '60' });
    renderAt('/builder');
    expect(await screen.findByTestId('geometry-warnings'))
      .toHaveTextContent(/not physically possible/i);
  });
});

/* ===================================================================== */
describe('presets require confirmation', () => {
  it('does not change the design until confirmed', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const before = (await screen.findByTestId('property-size_nm')).textContent;

    await user.click(screen.getByTestId('preset-gold'));
    // The dialog lists exactly what would change.
    expect(await screen.findByTestId('preset-changes'))
      .toHaveTextContent('size_nm = 50');
    // Nothing has changed yet.
    expect(screen.getByTestId('property-size_nm').textContent).toBe(before);
  });

  it('applies the template only after confirmation', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await screen.findByTestId('property-size_nm');

    await user.click(screen.getByTestId('preset-gold'));
    await user.click(await screen.findByTestId('confirm-preset'));

    expect(await screen.findByTestId('property-size_nm'))
      .toHaveTextContent('50 nm');
  });

  it('can be cancelled with no change', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const before = (await screen.findByTestId('property-size_nm')).textContent;

    await user.click(screen.getByTestId('preset-liposome'));
    await user.click(await screen.findByRole('button', { name: /^Cancel$/i }));

    expect(screen.getByTestId('property-size_nm').textContent).toBe(before);
  });
});

/* ===================================================================== */
describe('the original scientific inputs are preserved', () => {
  it('opening the builder does not modify the stored draft', async () => {
    seedDraft();
    const before = localStorage.getItem('nanobio.designDrafts.v1');
    renderAt('/builder');
    await screen.findByTestId('property-table');
    expect(localStorage.getItem('nanobio.designDrafts.v1')).toBe(before);
  });

  it('choosing an illustrative architecture does not modify the draft',
     async () => {
       seedDraft();
       const user = userEvent.setup();
       renderAt('/builder');
       await screen.findByTestId('property-table');
       const before = localStorage.getItem('nanobio.designDrafts.v1');

       await user.selectOptions(
         screen.getByLabelText(/Architecture \(illustrative\)/i), 'liposome');

       expect(localStorage.getItem('nanobio.designDrafts.v1')).toBe(before);
     });

  it('the builder writes nothing to the PK inputs', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await screen.findByTestId('property-table');
    await user.click(screen.getByTestId('preset-gold'));
    await user.click(await screen.findByTestId('confirm-preset'));

    const draft = JSON.parse(
      localStorage.getItem('nanobio.designDrafts.v1') ?? '[]')[0];
    // A preset may change design values; it must never touch pharmacokinetics.
    expect(draft.pk).toEqual({});
  });
});

/* ===================================================================== */
describe('the View in 3D entry point is findable', () => {
  /**
   * The defect: the button existed but sat BETWEEN the nanoparticle
   * configuration section and the pharmacokinetics section, so it read as
   * belonging to neither — and Step 3 is itself unreachable until Steps 1 and
   * 2 are complete. It is now inside the configuration section header.
   */
  it('sits inside the Nanoparticle configuration section', async () => {
    seedDraft();
    renderAt('/workflow/review');
    const button = await screen.findByTestId('view-in-3d');
    const section = button.closest('section');
    expect(section).not.toBeNull();
    expect(within(section!).getByRole('heading', { level: 3 }))
      .toHaveTextContent(/Nanoparticle configuration/i);
  });

  it('is not inside the pharmacokinetics section', async () => {
    seedDraft();
    renderAt('/workflow/review');
    const button = await screen.findByTestId('view-in-3d');
    const pk = screen.getByTestId('pk-inputs');
    expect(pk.contains(button)).toBe(false);
  });

  it('is present on the design step as well', async () => {
    seedDraft();
    renderAt('/workflow/design');
    expect(await screen.findByTestId('view-in-3d-step2')).toBeInTheDocument();
  });

  it('remains available when no PK route has been chosen', async () => {
    // The builder visualises the formulation. It must not depend on the
    // pharmacokinetic model being configured, let alone runnable.
    seedDraft();
    renderAt('/workflow/review');
    expect(await screen.findByTestId('view-in-3d')).toBeInTheDocument();
    expect(screen.queryByTestId('legacy-depot-inputs')).not.toBeInTheDocument();
  });

  it('remains available when the PK simulation is blocked', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/workflow/review');
    await screen.findByTestId('view-in-3d');

    await user.selectOptions(
      await screen.findByLabelText(/Administration route/i), 'iv_infusion');
    await screen.findByTestId('pk-blocked');

    expect(screen.getByTestId('view-in-3d')).toBeInTheDocument();
  });

  it('opens the builder when pressed', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/workflow/review');
    await user.click(await screen.findByTestId('view-in-3d'));
    expect(await screen.findByTestId('builder-viewport')).toBeInTheDocument();
  });

  it('is listed in the sidebar under its own name', async () => {
    seedDraft();
    renderAt('/builder');
    const nav = await screen.findByRole('navigation',
                                        { name: /Main navigation/i });
    expect(within(nav).getByText('Nanoparticle 3D Builder'))
      .toBeInTheDocument();
    // The old placeholder label must be gone, or two entries would compete.
    expect(within(nav).queryByText('Molecular Visualization'))
      .not.toBeInTheDocument();
  });

  it('marks the sidebar entry active on /builder', async () => {
    seedDraft();
    renderAt('/builder');
    const nav = await screen.findByRole('navigation',
                                        { name: /Main navigation/i });
    expect(within(nav).getByRole('link', { current: 'page' }))
      .toHaveTextContent(/Nanoparticle 3D Builder/);
  });
});
