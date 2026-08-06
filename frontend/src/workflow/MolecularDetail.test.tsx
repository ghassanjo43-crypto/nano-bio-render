/**
 * Phase 3 — detail levels and molecular population.
 *
 * The property under test: **a rendered object is not a molecule**. The viewer
 * may draw 96 chains; that is a sample, not a population. A population is only
 * stated when a formula, its inputs and its units are all present — and when
 * they are not, the viewer says "cannot calculate" and names what is missing.
 *
 * The second property: a percentage "ligand density" is ambiguous. Surface
 * coverage, molar percent, mass percent and per-area density give different
 * counts, so the estimator refuses until the definition is recorded.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import { buildVisualModel } from '../pages/builder/particleModel';
import {
  ABSOLUTE_GLYPH_CAP, DETAIL_LEVELS, MOLECULAR_PATCH_NOTE,
  NO_ATOMIC_STRUCTURE_NOTE, POROSITY_NOT_SPECIFIED_NOTE, QUALITY_PRESETS,
  applyStericSpacing, buildChains, makeRng, morphologyFor, poresMayBeDrawn,
  resolveBudget, seedForModel, seedFrom,
} from '../pages/builder/detailLevels';
import {
  AVOGADRO, POPULATION_DISCLAIMER, buildPopulationReport, estimateLipids,
  estimatePayload, estimatePoreBound, estimateSurfaceGrafted, formatCount,
  type MolecularAssumptions,
} from '../pages/builder/molecularPopulation';
import { pkFixtureFor } from './pkTestFixtures';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

const MINIMAL: Record<string, string> = {
  size_nm: '100', charge_mv: '-5', encapsulation_percent: '85',
};
const NO_CHIPS: Record<string, string[]> = {
  surface_coating: [], functional_groups: [],
};

const model = (values = MINIMAL, chips = NO_CHIPS, options = {}) =>
  buildVisualModel(values, chips, options);

const NO_RENDER = {
  lipids: 0, peg_chains: 0, ligands: 0, functional_groups: 0,
  payload_molecules: 0, pore_bound_molecules: 0, surface_bound_drug: 0,
  coating_units: 0,
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

function seedDraft(values = MINIMAL, chips = NO_CHIPS) {
  localStorage.setItem('nanobio.designDrafts.v1', JSON.stringify([{
    id: 'ds_mol', name: 'Molecular draft',
    createdAt: '2026-08-02T09:00:00.000Z', updatedAt: '2026-08-02T09:00:00.000Z',
    selection: { disease: 'Breast Cancer',
                 subtype: 'HER2-enriched (ER-, PR-, HER2+)',
                 drug: 'Trastuzumab (Herceptin)' },
    values, chips, pk: {}, furthestStep: 3,
  }]));
  localStorage.setItem('nanobio.activeDraftId.v1', 'ds_mol');
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
describe('detail levels', () => {
  it('defines exactly three', () => {
    expect(DETAIL_LEVELS.map((d) => d.id))
      .toEqual(['overview', 'structural', 'molecular']);
  });

  it('increases tessellation and sampling with detail', () => {
    const [a, b, c] = DETAIL_LEVELS;
    expect(a!.sphereSegments).toBeLessThan(b!.sphereSegments);
    expect(b!.sphereSegments).toBeLessThan(c!.sphereSegments);
    expect(a!.maxSurfaceGlyphs).toBeLessThan(b!.maxSurfaceGlyphs);
    expect(a!.chainSegments).toBeLessThan(c!.chainSegments);
  });

  it('states that molecular detail is a local patch only', () => {
    expect(DETAIL_LEVELS[2]!.description).toMatch(/local patch/i);
    expect(MOLECULAR_PATCH_NOTE).toMatch(/one local patch only/i);
    expect(MOLECULAR_PATCH_NOTE)
      .toMatch(/no view here shows the complete molecular population/i);
  });

  it('switches detail level in the interface', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const select = await screen.findByLabelText(/Detail level/i);
    await user.selectOptions(select, 'molecular');
    expect(select).toHaveValue('molecular');
    expect(await screen.findByTestId('molecular-patch-note'))
      .toHaveTextContent(/local patch only/i);
  });
});

/* ===================================================================== */
describe('performance budget', () => {
  it('caps instances at every level', () => {
    const b = resolveBudget('overview', 'balanced', 100000, 100000);
    expect(b.surfaceGlyphs).toBeLessThanOrEqual(ABSOLUTE_GLYPH_CAP);
    expect(b.payloadGlyphs).toBeLessThanOrEqual(ABSOLUTE_GLYPH_CAP);
    expect(b.capped).toBe(true);
  });

  it('never instantiates a physical population', () => {
    // A 100 nm liposome holds ~1e5 lipids. The cap is three orders below that.
    const b = resolveBudget('molecular', 'high', 100000, 100000);
    expect(b.surfaceGlyphs).toBeLessThanOrEqual(ABSOLUTE_GLYPH_CAP);
    expect(ABSOLUTE_GLYPH_CAP).toBeLessThan(5000);
  });

  it('reports when a cap reduced the sample', () => {
    expect(resolveBudget('overview', 'low', 500, 500).capped).toBe(true);
    expect(resolveBudget('overview', 'balanced', 5, 5).capped).toBe(false);
  });

  it('quality presets scale the budget', () => {
    const low = resolveBudget('structural', 'low', 1000, 1000);
    const high = resolveBudget('structural', 'high', 1000, 1000);
    expect(low.surfaceGlyphs).toBeLessThan(high.surfaceGlyphs);
    expect(low.sphereSegments).toBeLessThan(high.sphereSegments);
    expect(Object.keys(QUALITY_PRESETS)).toEqual(['low', 'balanced', 'high']);
  });

  it('offers a quality control in the interface', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    const select = await screen.findByLabelText(/Rendering quality/i);
    await user.selectOptions(select, 'low');
    expect(select).toHaveValue('low');
  });
});

/* ===================================================================== */
describe('deterministic placement', () => {
  it('produces the same seed for the same design', () => {
    expect(seedForModel(model())).toBe(seedForModel(model()));
    expect(seedFrom('abc')).toBe(seedFrom('abc'));
    expect(seedFrom('abc')).not.toBe(seedFrom('abd'));
  });

  it('produces identical chain conformations for the same seed', () => {
    const anchors: Array<[number, number, number]> = [[1, 0, 0], [0, 1, 0]];
    expect(buildChains(anchors, 0.3, 5, 42))
      .toEqual(buildChains(anchors, 0.3, 5, 42));
  });

  it('produces different conformations for different seeds', () => {
    const anchors: Array<[number, number, number]> = [[1, 0, 0]];
    expect(buildChains(anchors, 0.3, 5, 1))
      .not.toEqual(buildChains(anchors, 0.3, 5, 2));
  });

  it('keeps chains outside the particle surface', () => {
    const anchors: Array<[number, number, number]> = [[1, 0, 0], [0, 0, 1]];
    for (const chain of buildChains(anchors, 0.4, 6, 7)) {
      const anchorR = Math.hypot(...chain.anchor);
      const tipR = Math.hypot(...chain.tip);
      // A chain must extend outward, never tunnel inward.
      expect(tipR).toBeGreaterThan(anchorR);
    }
  });

  it('has a deterministic PRNG', () => {
    const a = makeRng(99); const b = makeRng(99);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it('applies steric spacing without randomness', () => {
    const pts: Array<[number, number, number]> = [
      [0, 0, 0], [0.001, 0, 0], [1, 0, 0],
    ];
    const kept = applyStericSpacing(pts, 0.1);
    expect(kept).toEqual(applyStericSpacing(pts, 0.1));
    expect(kept).toHaveLength(2);   // the near-duplicate is dropped
  });
});

/* ===================================================================== */
describe('physical count is separate from rendered count', () => {
  it('reports both numbers independently', () => {
    const a: MolecularAssumptions = {
      areaPerLipidNm2: 0.65, bilayerThicknessNm: 4,
    };
    const e = estimateLipids(model(MINIMAL, NO_CHIPS,
                                   { architectureOverride: 'liposome' }),
                             a, 120);
    expect(e.renderedCount).toBe(120);
    expect(e.physicalCount).toBeGreaterThan(10000);
    expect(e.physicalCount).not.toBe(e.renderedCount);
  });

  it('states the representation ratio', () => {
    const e = estimateLipids(model(MINIMAL, NO_CHIPS,
                                   { architectureOverride: 'liposome' }),
                             { areaPerLipidNm2: 0.65, bilayerThicknessNm: 4 },
                             100);
    expect(e.representationRatio).toBeCloseTo(e.physicalCount! / 100, 6);
  });

  it('gives no ratio when the physical count is unknown', () => {
    const e = estimateLipids(model(MINIMAL, NO_CHIPS,
                                   { architectureOverride: 'liposome' }),
                             {}, 100);
    expect(e.physicalCount).toBeNull();
    expect(e.representationRatio).toBeNull();
  });

  it('carries the disclaimer that objects are not molecules', () => {
    expect(POPULATION_DISCLAIMER)
      .toMatch(/do not necessarily correspond one-to-one/i);
  });
});

/* ===================================================================== */
describe('population formulas and units', () => {
  it('computes lipids from both leaflet areas', () => {
    // d = 100 nm, t = 4 nm, a = 0.65 nm^2
    // A_out = 4*pi*50^2 = 31415.93 ; A_in = 4*pi*46^2 = 26590.44
    // N = (31415.93 + 26590.44) / 0.65 = 89241
    const e = estimateLipids(model(MINIMAL, NO_CHIPS,
                                   { architectureOverride: 'liposome' }),
                             { areaPerLipidNm2: 0.65, bilayerThicknessNm: 4 },
                             100);
    expect(e.physicalCount).toBe(89241);
    expect(e.formula).toBe('N = [4π(d/2)² + 4π((d/2) − t)²] / a_lipid');
  });

  it('carries an uncertainty range for the lipid estimate', () => {
    const e = estimateLipids(model(MINIMAL, NO_CHIPS,
                                   { architectureOverride: 'liposome' }),
                             { areaPerLipidNm2: 0.65, bilayerThicknessNm: 4 },
                             100);
    expect(e.physicalRange![0]).toBeLessThan(e.physicalCount!);
    expect(e.physicalRange![1]).toBeGreaterThan(e.physicalCount!);
  });

  it('refuses a bilayer that cannot fit inside the vesicle', () => {
    const e = estimateLipids(model(MINIMAL, NO_CHIPS,
                                   { architectureOverride: 'liposome' }),
                             { areaPerLipidNm2: 0.65, bilayerThicknessNm: 60 },
                             100);
    expect(e.physicalCount).toBeNull();
    expect(e.note).toMatch(/does not fit/i);
  });

  it('computes surface grafting from a per-area density', () => {
    // A = 4*pi*50^2 = 31415.9 nm^2 ; sigma = 0.05 /nm^2 -> 1571
    const e = estimateSurfaceGrafted('ligands', model(), { ligandsPerNm2: 0.05 },
                                     40, null);
    expect(e.physicalCount).toBe(1571);
    expect(e.formula).toBe('N = 4π(d/2)² × σ');
    expect(e.usedInputs['Surface density (σ)']).toBe('0.05 nm⁻²');
  });

  it('computes payload molecules from mass and molar mass', () => {
    // 1 ag = 1e-18 g ; M = 500 g/mol -> (1e-18/500)*6.022e23 = 1204
    const e = estimatePayload(model(), {
      payloadMassPerParticleAg: 1, payloadMolarMassGPerMol: 500,
    }, 40);
    expect(e.physicalCount).toBe(Math.round((1e-18 / 500) * AVOGADRO));
    expect(e.formula).toBe('N = (m_particle / M) × N_A');
  });

  it('computes a pore capacity bound and labels it as a bound', () => {
    const e = estimatePoreBound(
      model(MINIMAL, NO_CHIPS, { architectureOverride: 'silica' }),
      { poreVolumeNm3: 1000, payloadMolecularVolumeNm3: 0.5 }, 20);
    expect(e.physicalCount).toBe(2000);
    expect(e.note).toMatch(/CAPACITY bound/i);
    expect(e.note).toMatch(/not a measured or predicted loading/i);
  });

  it('formats large counts without false precision', () => {
    // A non-breaking space keeps the number and its magnitude word together
    // when the panel wraps, so the assertions use   deliberately.
    expect(formatCount(500)).toBe('500');
    expect(formatCount(89241)).toBe('89.2 thousand');
    expect(formatCount(1.2e7)).toBe('12.0 million');
    expect(formatCount(89241)).not.toContain(' ');
  });
});

/* ===================================================================== */
describe('ambiguous ligand density is refused', () => {
  it('refuses a percentage with no recorded definition', () => {
    const e = estimateSurfaceGrafted('ligands', model(), {}, 40, 40);
    expect(e.physicalCount).toBeNull();
    expect(e.blockReason).toBe('ambiguous_definition');
    expect(e.note).toMatch(/ambiguous/i);
    expect(e.note).toMatch(/surface coverage/i);
    expect(e.note).toMatch(/molar percent/i);
    expect(e.note).toMatch(/mass percent/i);
  });

  it('accepts the percentage once its definition is recorded', () => {
    const e = estimateSurfaceGrafted('ligands', model(), {
      molecularFootprintNm2: 0.5,
      ligandDensityDefinition: 'surface_coverage_fraction',
    }, 40, 40);
    expect(e.physicalCount).not.toBeNull();
    expect(e.usedInputs.Coverage).toMatch(/defined as surface coverage/i);
  });

  it('names the missing definition among the missing inputs', () => {
    const e = estimateSurfaceGrafted('ligands', model(), {}, 40, 40);
    expect(e.missingInputs).toContain('Definition of the percentage');
  });
});

/* ===================================================================== */
describe('missing molecular data is refused, never defaulted', () => {
  it('refuses a payload count without a molar mass', () => {
    const e = estimatePayload(model(), { payloadMassPerParticleAg: 1 }, 40);
    expect(e.physicalCount).toBeNull();
    expect(e.missingInputs).toContain('Payload molar mass');
  });

  it('refuses a payload count without a mass per particle', () => {
    const e = estimatePayload(model(), { payloadMolarMassGPerMol: 500 }, 40);
    expect(e.physicalCount).toBeNull();
    expect(e.missingInputs).toContain('Payload mass per particle');
  });

  it('explains why encapsulation efficiency is not enough', () => {
    const e = estimatePayload(model(), {}, 40);
    expect(e.note).toMatch(/fraction of offered drug/i);
    expect(e.note).toMatch(/does not give the mass carried by one particle/i);
  });

  it('refuses lipids without an area per lipid', () => {
    const e = estimateLipids(model(MINIMAL, NO_CHIPS,
                                   { architectureOverride: 'liposome' }),
                             { bilayerThicknessNm: 4 }, 100);
    expect(e.physicalCount).toBeNull();
    expect(e.missingInputs).toContain('Area per lipid');
  });

  it('refuses pore loading when porosity is not recorded', () => {
    const e = estimatePoreBound(
      model(MINIMAL, NO_CHIPS, { architectureOverride: 'silica' }), {}, 0);
    expect(e.physicalCount).toBeNull();
    expect(e.note).toMatch(/Porosity is not recorded/i);
  });

  it('marks a component not applicable rather than zero', () => {
    const e = estimateLipids(model(), {}, 0);
    expect(e.blockReason).toBe('not_applicable');
    expect(e.physicalCount).toBeNull();
  });

  it('for the minimal design, calculates nothing at all', () => {
    const report = buildPopulationReport(model(), {},
                                         { ...NO_RENDER, payload_molecules: 40 },
                                         null);
    expect(report.length).toBeGreaterThan(0);
    for (const e of report) expect(e.physicalCount).toBeNull();
  });
});

/* ===================================================================== */
describe('architecture-specific geometry', () => {
  it('gives each architecture its own morphology', () => {
    expect(morphologyFor('metallic').finish).toBe('metallic');
    expect(morphologyFor('metallic').facets).toBeGreaterThan(0);
    expect(morphologyFor('silica').finish).toBe('glassy');
    expect(morphologyFor('polymeric').finish).toBe('soft');
    expect(morphologyFor('polymeric').roughness)
      .toBeGreaterThan(morphologyFor('silica').roughness);
  });

  it('labels every morphology as illustrative', () => {
    for (const a of ['metallic', 'silica', 'polymeric', 'liposome',
                     'solid'] as const) {
      expect(morphologyFor(a).note).toMatch(/illustrative|not recorded|not modelled/i);
    }
  });

  it('never draws pores unless porosity is supplied or chosen', () => {
    expect(poresMayBeDrawn('silica', undefined, false)).toBe(false);
    expect(poresMayBeDrawn('silica', 1000, false)).toBe(true);
    expect(poresMayBeDrawn('silica', undefined, true)).toBe(true);
    // Never for a non-silica architecture.
    expect(poresMayBeDrawn('metallic', 1000, true)).toBe(false);
  });

  it('explains why a silica particle is drawn solid by default', () => {
    expect(POROSITY_NOT_SPECIFIED_NOTE).toMatch(/not recorded/i);
    expect(POROSITY_NOT_SPECIFIED_NOTE).toMatch(/labelled as illustrative/i);
  });
});

/* ===================================================================== */
describe('no false atomic structure', () => {
  it('states that structures are never generated from a name', () => {
    expect(NO_ATOMIC_STRUCTURE_NOTE)
      .toMatch(/never generated from a compound name/i);
  });

  it('offers no atomic structure for the payload', () => {
    // The platform holds no structure files. Payload is schematic, and the
    // model says so rather than implying atomic detail.
    const m = model();
    const payload = m.properties.find((p) => p.key === 'payload')!;
    expect(payload.provenance).toBe('unavailable');
  });
});

/* ===================================================================== */
describe('the population panel', () => {
  it('renders with the disclaimer and legend', async () => {
    seedDraft();
    renderAt('/builder');
    expect(await screen.findByTestId('population-panel')).toBeInTheDocument();
    expect(screen.getByTestId('population-disclaimer'))
      .toHaveTextContent(/do not necessarily correspond one-to-one/i);
    expect(screen.getByTestId('scientific-legend')).toBeInTheDocument();
  });

  it('lists the seven legend terms', async () => {
    seedDraft();
    renderAt('/builder');
    const legend = await screen.findByTestId('scientific-legend');
    for (const term of ['Scientific dimensions',
                        'Geometry enlarged for visibility',
                        'Estimated physical population',
                        'Representative rendered population',
                        'Illustrative component', 'Structure unavailable',
                        'Not calculated from current data']) {
      expect(legend).toHaveTextContent(term);
    }
  });

  it('shows "cannot calculate" for the minimal design', async () => {
    seedDraft();
    renderAt('/builder');
    const payload = await screen.findByTestId('population-payload_molecules');
    expect(within(payload).getByTestId('physical-payload_molecules'))
      .toHaveTextContent(/Cannot calculate from current inputs/i);
    expect(within(payload).getByTestId('ratio-payload_molecules'))
      .toHaveTextContent(/Unknown/i);
  });

  it('shows the rendered count even when the physical count is unknown',
     async () => {
       seedDraft();
       renderAt('/builder');
       const rendered = await screen.findByTestId(
         'rendered-payload_molecules');
       expect(Number(rendered.textContent)).toBeGreaterThan(0);
     });

  it('offers researcher inputs with no defaults', async () => {
    seedDraft();
    renderAt('/builder');
    const fields = await screen.findByTestId('molecular-assumptions');
    const input = within(fields).getByTestId('assumption-areaPerLipidNm2');
    expect(input).toHaveValue(null);
    expect(input).toHaveAttribute('placeholder', 'not supplied');
  });

  it('calculates once a researcher supplies the constants', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await user.selectOptions(
      await screen.findByLabelText(/Architecture \(illustrative\)/i),
      'liposome');
    await user.type(screen.getByTestId('assumption-areaPerLipidNm2'), '0.65');
    await user.type(screen.getByTestId('assumption-bilayerThicknessNm'), '4');

    const lipids = await screen.findByTestId('population-lipids');
    expect(within(lipids).getByTestId('physical-lipids'))
      .toHaveTextContent(/thousand/);
    expect(lipids).toHaveTextContent(/Researcher-supplied inputs/i);
  });
});

/* ===================================================================== */
describe('visual density does not touch scientific inputs', () => {
  it('leaves the stored draft untouched', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await screen.findByTestId('population-panel');
    const before = localStorage.getItem('nanobio.designDrafts.v1');

    await user.selectOptions(screen.getByLabelText(/Detail level/i),
                             'structural');
    await user.selectOptions(screen.getByLabelText(/Rendering quality/i),
                             'high');

    expect(localStorage.getItem('nanobio.designDrafts.v1')).toBe(before);
  });

  it('leaves PK inputs untouched', async () => {
    seedDraft();
    const user = userEvent.setup();
    renderAt('/builder');
    await screen.findByTestId('population-panel');
    await user.selectOptions(screen.getByLabelText(/Detail level/i),
                             'molecular');

    const draft = JSON.parse(
      localStorage.getItem('nanobio.designDrafts.v1') ?? '[]')[0];
    expect(draft.pk).toEqual({});
    expect(draft.values).toEqual(MINIMAL);
  });

  it('does not change an estimated population when density changes', () => {
    // The estimate depends on physical constants, never on how many objects
    // happen to be drawn.
    const a: MolecularAssumptions = {
      areaPerLipidNm2: 0.65, bilayerThicknessNm: 4,
    };
    const m = model(MINIMAL, NO_CHIPS, { architectureOverride: 'liposome' });
    expect(estimateLipids(m, a, 20).physicalCount)
      .toBe(estimateLipids(m, a, 400).physicalCount);
  });
});
