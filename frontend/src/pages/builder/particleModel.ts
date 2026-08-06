/**
 * Translate the stored nanoparticle design into a visual model specification.
 *
 * The rule this module exists to enforce
 * --------------------------------------
 * A picture is a claim. Drawing a gold core, a PEG brush and forty ligands for a
 * design that records only size, charge and encapsulation efficiency would state
 * three structural facts the platform does not have. So every property carries
 * its **provenance**, and anything the design does not supply is marked
 * `illustrative_assumption` and is labelled as such wherever it is shown.
 *
 * This module performs no rendering and imports nothing from three.js. It is the
 * single place where a design becomes a visual specification, so the scene, the
 * legend, the parameter table and the tests all read the same object.
 *
 * It never writes back to the design. Choosing an illustrative architecture
 * changes the picture and nothing else — the scientific inputs to the design
 * score and the pharmacokinetic model are untouched.
 */

import type { ChipValues, FormValues } from '../design/schema';

/* ========================================================================= */
/* Provenance                                                                */
/* ========================================================================= */

export type Provenance =
  /** The user entered it on the design form. */
  | 'supplied'
  /** A documented engine default, with its origin named. */
  | 'engine_default'
  /** Computed from supplied values; the formula is recorded. */
  | 'calculated'
  /** Chosen so something could be drawn. Not a scientific claim. */
  | 'illustrative_assumption'
  /** Not supplied and not assumed. Nothing is drawn for it. */
  | 'unavailable';

export const PROVENANCE_LABEL: Record<Provenance, string> = {
  supplied: 'Supplied design value',
  engine_default: 'Engine default',
  calculated: 'Calculated value',
  illustrative_assumption: 'Illustrative assumption',
  unavailable: 'Unavailable information',
};

export const PROVENANCE_TONE: Record<Provenance,
  'success' | 'accent' | 'info' | 'warn' | 'neutral'> = {
  supplied: 'success',
  engine_default: 'info',
  calculated: 'accent',
  illustrative_assumption: 'warn',
  unavailable: 'neutral',
};

export const VISUAL_DISCLAIMER =
  'Visual representation — geometry and molecular population may be '
  + 'simplified. This model is not experimental microscopy or proof of '
  + 'biological behavior.';

export interface Property<T> {
  key: string;
  label: string;
  value: T;
  unit: string;
  provenance: Provenance;
  /** Where a default or assumption came from. Required for both. */
  origin?: string;
  /** The formula, for calculated values. */
  formula?: string;
}

function supplied<T>(key: string, label: string, value: T,
                     unit: string): Property<T> {
  return { key, label, value, unit, provenance: 'supplied' };
}

function assumed<T>(key: string, label: string, value: T, unit: string,
                    origin: string): Property<T> {
  return { key, label, value, unit,
           provenance: 'illustrative_assumption', origin };
}

function unavailable(key: string, label: string, unit = ''): Property<null> {
  return { key, label, value: null, unit, provenance: 'unavailable' };
}

/* ========================================================================= */
/* Architecture                                                              */
/* ========================================================================= */

export type Architecture =
  | 'solid'
  | 'core_shell'
  | 'liposome'
  | 'polymeric'
  | 'metallic'
  | 'silica'
  | 'hybrid';

export interface ArchitectureSpec {
  id: Architecture;
  label: string;
  description: string;
  /** Whether the representation has a distinct interior compartment. */
  hasAqueousInterior: boolean;
  /** Whether it draws a discrete shell layer around a core. */
  hasShell: boolean;
}

export const ARCHITECTURES: readonly ArchitectureSpec[] = [
  { id: 'solid', label: 'Solid nanoparticle',
    description: 'A single homogeneous body with no distinct internal layers.',
    hasAqueousInterior: false, hasShell: false },
  { id: 'core_shell', label: 'Core–shell nanoparticle',
    description: 'A distinct core enclosed by a shell of different material.',
    hasAqueousInterior: false, hasShell: true },
  { id: 'liposome', label: 'Liposome',
    description: 'A lipid bilayer enclosing an aqueous interior.',
    hasAqueousInterior: true, hasShell: true },
  { id: 'polymeric', label: 'Polymeric nanoparticle',
    description: 'A polymer matrix with payload dispersed through it.',
    hasAqueousInterior: false, hasShell: false },
  { id: 'metallic', label: 'Metallic nanoparticle',
    description: 'A dense metallic core, optionally stabilised by a coating.',
    hasAqueousInterior: false, hasShell: true },
  { id: 'silica', label: 'Silica nanoparticle',
    description: 'A silica framework, often mesoporous, optionally coated.',
    hasAqueousInterior: false, hasShell: true },
  { id: 'hybrid', label: 'Hybrid nanoparticle',
    description: 'Combined organic and inorganic components.',
    hasAqueousInterior: false, hasShell: true },
];

export function architectureSpec(id: Architecture): ArchitectureSpec {
  const spec = ARCHITECTURES.find((a) => a.id === id);
  if (!spec) throw new Error(`unknown architecture: ${id}`);
  return spec;
}

/** Payload location. Not recorded by the design; always an assumption. */
export type PayloadLocation = 'hydrophilic_core' | 'hydrophobic_bilayer'
  | 'dispersed';

/* ========================================================================= */
/* Geometry                                                                  */
/* ========================================================================= */

export interface GeometryWarning {
  code: string;
  message: string;
}

export interface Geometry {
  /** Total outer diameter in nanometres, as supplied. */
  outerDiameterNm: number | null;
  /** Coating thickness in nanometres, when supplied. */
  coatingThicknessNm: number | null;
  /** Core diameter, derived as outer − 2 × thickness. */
  coreDiameterNm: number | null;
  /** Radii in scene units, after scaling for visibility. */
  outerRadius: number;
  coreRadius: number;
  /** Scene units per nanometre. Display-only; never a scientific quantity. */
  sceneUnitsPerNm: number;
  warnings: GeometryWarning[];
}

/** The scene is normalised so any particle fills a comparable volume. */
const TARGET_OUTER_RADIUS = 1.0;
/** Below this fraction the core is invisible; the shell is capped instead. */
const MIN_CORE_FRACTION = 0.12;

/**
 * Resolve geometry, refusing impossible combinations rather than drawing them.
 *
 * A coating thicker than the particle's radius would give a negative core
 * diameter. Clamping silently would draw a plausible picture of an impossible
 * particle, so the clamp is applied *and reported*.
 */
export function resolveGeometry(
  outerDiameterNm: number | null,
  coatingThicknessNm: number | null,
): Geometry {
  const warnings: GeometryWarning[] = [];
  const outerRadius = TARGET_OUTER_RADIUS;
  const sceneUnitsPerNm = outerDiameterNm
    ? (2 * TARGET_OUTER_RADIUS) / outerDiameterNm : 0;

  if (outerDiameterNm === null) {
    return { outerDiameterNm: null, coatingThicknessNm, coreDiameterNm: null,
             outerRadius, coreRadius: outerRadius * 0.7, sceneUnitsPerNm,
             warnings };
  }

  if (coatingThicknessNm === null) {
    return { outerDiameterNm, coatingThicknessNm: null, coreDiameterNm: null,
             outerRadius, coreRadius: outerRadius * 0.78, sceneUnitsPerNm,
             warnings };
  }

  const coreDiameter = outerDiameterNm - 2 * coatingThicknessNm;

  if (coreDiameter <= 0) {
    warnings.push({
      code: 'coating_exceeds_radius',
      message:
        `A coating thickness of ${coatingThicknessNm} nm on both sides `
        + `consumes ${2 * coatingThicknessNm} nm, which is at least the total `
        + `diameter of ${outerDiameterNm} nm. No core would remain. The shell `
        + 'is drawn at the maximum thickness that leaves a visible core; the '
        + 'geometry as entered is not physically possible.',
    });
    return { outerDiameterNm, coatingThicknessNm, coreDiameterNm: null,
             outerRadius, coreRadius: outerRadius * MIN_CORE_FRACTION,
             sceneUnitsPerNm, warnings };
  }

  const fraction = coreDiameter / outerDiameterNm;
  if (fraction < MIN_CORE_FRACTION) {
    warnings.push({
      code: 'core_barely_visible',
      message:
        `The core is ${coreDiameter.toFixed(1)} nm within a `
        + `${outerDiameterNm} nm particle (${(fraction * 100).toFixed(1)}% of `
        + 'the diameter). It is enlarged in the image so it can be seen; the '
        + 'numeric dimensions above are the supplied values.',
    });
  }

  return {
    outerDiameterNm,
    coatingThicknessNm,
    coreDiameterNm: coreDiameter,
    outerRadius,
    coreRadius: outerRadius * Math.max(fraction, MIN_CORE_FRACTION),
    sceneUnitsPerNm,
    warnings,
  };
}

/* ========================================================================= */
/* Deterministic surface placement                                           */
/* ========================================================================= */

/**
 * Fibonacci sphere: evenly distributed points, fully determined by `count`.
 *
 * Deterministic on purpose. A random arrangement would make the same design
 * look different on every render, which would imply the arrangement carried
 * information. It does not: it is a representative population, not a molecular
 * coordinate set.
 */
export function fibonacciSphere(count: number, radius = 1):
    Array<[number, number, number]> {
  if (count <= 0) return [];
  const points: Array<[number, number, number]> = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i += 1) {
    const y = count === 1 ? 0 : 1 - (i / (count - 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = golden * i;
    points.push([
      Math.cos(theta) * r * radius,
      y * radius,
      Math.sin(theta) * r * radius,
    ]);
  }
  return points;
}

/** Deterministic interior points, for dispersed payload. */
export function interiorPoints(count: number, radius: number):
    Array<[number, number, number]> {
  const shell = fibonacciSphere(count, 1);
  return shell.map(([x, y, z], i) => {
    // Vary the radius by index so points do not all sit on one sphere.
    const t = ((i * 0.6180339887) % 1) * 0.75 + 0.15;
    return [x * radius * t, y * radius * t, z * radius * t];
  });
}

/** Ligand count from density. Representative, never a molecule count. */
export const MAX_LIGAND_GLYPHS = 64;
export const MAX_PAYLOAD_GLYPHS = 48;

export function ligandGlyphCount(densityPercent: number | null): number {
  if (densityPercent === null) return 0;
  const clamped = Math.max(0, Math.min(100, densityPercent));
  return Math.round((clamped / 100) * MAX_LIGAND_GLYPHS);
}

export function payloadGlyphCount(encapsulationPercent: number | null): number {
  if (encapsulationPercent === null) return 0;
  const clamped = Math.max(0, Math.min(100, encapsulationPercent));
  // Floor of 6 so a low-but-nonzero efficiency is still visible as "some".
  return Math.max(6, Math.round((clamped / 100) * MAX_PAYLOAD_GLYPHS));
}

/* ========================================================================= */
/* The visual model                                                          */
/* ========================================================================= */

export interface VisualModel {
  architecture: Property<Architecture>;
  geometry: Geometry;
  properties: Property<unknown>[];
  /** Surface charge in mV, when supplied. Drives the charge overlay. */
  chargeMv: number | null;
  ligandGlyphs: number;
  payloadGlyphs: number;
  payloadLocation: Property<PayloadLocation>;
  coreMaterial: Property<string | null>;
  coatingLabel: Property<string | null>;
  functionalGroups: Property<string[]>;
  /** Every property the design did not supply. */
  missing: string[];
  /** Assumptions introduced so something could be drawn. */
  assumptions: string[];
  warnings: GeometryWarning[];
}

function num(values: FormValues, key: string): number | null {
  const raw = values[key];
  if (raw === undefined || raw === null || String(raw).trim() === '') return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function text(values: FormValues, key: string): string | null {
  const raw = values[key];
  const trimmed = raw === undefined || raw === null ? '' : String(raw).trim();
  return trimmed === '' ? null : trimmed;
}

/**
 * Build the visual model.
 *
 * `architectureOverride` is the user's illustrative choice. It changes only the
 * picture; it is never written back to the design.
 */
export function buildVisualModel(
  values: FormValues,
  chips: ChipValues,
  options: {
    architectureOverride?: Architecture | null;
    payloadLocationOverride?: PayloadLocation | null;
    /** The therapeutic from Step 1, shown as the payload's identity. */
    therapeutic?: string | null;
  } = {},
): VisualModel {
  const missing: string[] = [];
  const assumptions: string[] = [];
  const properties: Property<unknown>[] = [];

  /* --- architecture: never recorded by the design schema ---------------- */
  const chosen = options.architectureOverride ?? null;
  const architecture: Property<Architecture> = chosen
    ? assumed('architecture', 'Particle architecture', chosen, '',
              'Selected by you for illustration. The design schema records no '
              + 'architecture field, so this is not a stored property of the '
              + 'formulation and does not affect any calculation.')
    : assumed('architecture', 'Particle architecture', 'solid', '',
              'Structure not specified. A solid particle is drawn as the '
              + 'neutral default so the geometry can be rendered at all. It '
              + 'is a drawing choice and does not affect any calculation.');
  if (!chosen) {
    missing.push('Particle architecture');
    assumptions.push(
      'Structure not specified — drawn as a solid particle for illustration.');
  } else {
    assumptions.push(
      `Architecture shown as ${architectureSpec(chosen).label.toLowerCase()} `
      + 'by your selection, for illustration only.');
  }
  properties.push(architecture);

  /* --- dimensions -------------------------------------------------------- */
  const sizeNm = num(values, 'size_nm');
  const hydroNm = num(values, 'hydrodynamic_size_nm');
  const coatingNm = num(values, 'coating_thickness_nm');

  if (sizeNm !== null) {
    properties.push(supplied('size_nm', 'Particle size', sizeNm, 'nm'));
  } else {
    properties.push(unavailable('size_nm', 'Particle size', 'nm'));
    missing.push('Particle size');
  }

  if (hydroNm !== null) {
    properties.push(supplied('hydrodynamic_size_nm', 'Hydrodynamic size',
                             hydroNm, 'nm'));
  } else {
    properties.push(unavailable('hydrodynamic_size_nm', 'Hydrodynamic size',
                                'nm'));
    missing.push('Hydrodynamic size');
  }

  if (coatingNm !== null) {
    properties.push(supplied('coating_thickness_nm', 'Coating thickness',
                             coatingNm, 'nm'));
  } else {
    properties.push(unavailable('coating_thickness_nm', 'Coating thickness',
                                'nm'));
    missing.push('Coating thickness');
  }

  const geometry = resolveGeometry(sizeNm, coatingNm);
  if (geometry.coreDiameterNm !== null) {
    properties.push({
      key: 'core_diameter_nm', label: 'Core diameter',
      value: geometry.coreDiameterNm, unit: 'nm', provenance: 'calculated',
      formula: 'core diameter = particle size − 2 × coating thickness',
    });
  }

  /* --- charge ------------------------------------------------------------ */
  const chargeMv = num(values, 'charge_mv');
  if (chargeMv !== null) {
    properties.push(supplied('charge_mv', 'Surface charge (zeta potential)',
                             chargeMv, 'mV'));
  } else {
    properties.push(unavailable('charge_mv', 'Surface charge', 'mV'));
    missing.push('Surface charge');
  }

  /* --- encapsulation and payload ---------------------------------------- */
  const encapsulation = num(values, 'encapsulation_percent');
  if (encapsulation !== null) {
    properties.push(supplied('encapsulation_percent',
                             'Encapsulation efficiency', encapsulation, '%'));
  } else {
    properties.push(unavailable('encapsulation_percent',
                                'Encapsulation efficiency', '%'));
    missing.push('Encapsulation efficiency');
  }

  const payloadGlyphs = payloadGlyphCount(encapsulation);
  if (payloadGlyphs > 0) {
    assumptions.push(
      `Payload shown as ${payloadGlyphs} representative markers scaled from `
      + 'the encapsulation efficiency. This is not a molecule count — the '
      + 'molecular mass and loading data required to compute one are not '
      + 'recorded.');
  }

  const payloadLocation: Property<PayloadLocation> =
    options.payloadLocationOverride
      ? assumed('payload_location', 'Payload location',
                options.payloadLocationOverride, '',
                'Selected by you for illustration. The design records no '
                + 'payload hydrophilicity, so this is an assumption.')
      : assumed('payload_location', 'Payload location', 'dispersed', '',
                'Payload hydrophilicity not specified. An illustrative '
                + 'dispersed distribution is shown.');
  if (!options.payloadLocationOverride) {
    missing.push('Payload hydrophilicity / location');
    assumptions.push(
      'Payload distribution is illustrative and assumed, not specified.');
  }
  properties.push(payloadLocation);

  const therapeutic = options.therapeutic?.trim() || null;
  properties.push(therapeutic
    ? { key: 'payload', label: 'Payload / therapeutic', value: therapeutic,
        unit: '', provenance: 'supplied' }
    : unavailable('payload', 'Payload / therapeutic'));
  if (!therapeutic) missing.push('Payload / therapeutic agent');

  /* --- materials and coating -------------------------------------------- */
  // The schema has no core-material field. Recorded as unavailable rather than
  // inferred from the architecture, which would be circular.
  const coreMaterial = unavailable('core_material', 'Core material');
  missing.push('Core material');
  properties.push(coreMaterial);

  const coatingChips = chips.surface_coating ?? [];
  const coatingLabel: Property<string | null> = coatingChips.length > 0
    ? supplied('surface_coating', 'Surface coating',
               coatingChips.join(', '), '')
    : unavailable('surface_coating', 'Surface coating');
  if (coatingChips.length === 0) missing.push('Surface coating');
  properties.push(coatingLabel);

  /* --- targeting --------------------------------------------------------- */
  const ligand = text(values, 'ligand');
  const ligandDensity = num(values, 'ligand_density_percent');
  properties.push(ligand
    ? supplied('ligand', 'Targeting ligand', ligand, '')
    : unavailable('ligand', 'Targeting ligand'));
  if (!ligand) missing.push('Targeting ligand');

  properties.push(ligandDensity !== null
    ? supplied('ligand_density_percent', 'Ligand density', ligandDensity, '%')
    : unavailable('ligand_density_percent', 'Ligand density', '%'));
  if (ligandDensity === null) missing.push('Ligand density');

  const ligandGlyphs = ligandGlyphCount(ligandDensity);
  if (ligandGlyphs > 0) {
    assumptions.push(
      `Ligands shown as ${ligandGlyphs} representative surface markers scaled `
      + 'from the ligand density. One marker does not correspond to one '
      + 'molecule.');
  }

  const groups = chips.functional_groups ?? [];
  const functionalGroups: Property<string[]> = groups.length > 0
    ? supplied('functional_groups', 'Functional groups', groups, '')
    : { ...unavailable('functional_groups', 'Functional groups'),
        value: [] as string[] };
  if (groups.length === 0) missing.push('Functional groups');
  properties.push(functionalGroups as Property<unknown>);

  /* --- other recorded values, shown numerically -------------------------- */
  const pdi = num(values, 'pdi');
  properties.push(pdi !== null
    ? supplied('pdi', 'Polydispersity index', pdi, '')
    : unavailable('pdi', 'Polydispersity index'));
  if (pdi === null) missing.push('Polydispersity index');

  // Shape is not in the schema at all; a sphere is drawn.
  properties.push(assumed('shape', 'Shape', 'spherical', '',
    'The design schema records no shape field. A sphere is drawn as the '
    + 'conventional default for a nanoparticle illustration.'));
  missing.push('Shape');
  assumptions.push('Shape not specified — drawn as a sphere.');

  return {
    architecture,
    geometry,
    properties,
    chargeMv,
    ligandGlyphs,
    payloadGlyphs,
    payloadLocation,
    coreMaterial,
    coatingLabel,
    functionalGroups,
    missing,
    assumptions,
    warnings: geometry.warnings,
  };
}

/* ========================================================================= */
/* Presets                                                                   */
/* ========================================================================= */

export interface Preset {
  id: string;
  label: string;
  description: string;
  architecture: Architecture;
  /** Design values a preset would write, if confirmed. */
  designValues: Partial<Record<string, string>>;
  chips: Partial<Record<string, string[]>>;
}

/**
 * Starting templates. Applying one CHANGES STORED DESIGN PARAMETERS, so the
 * interface must confirm before doing it. They are conventional illustrative
 * configurations, not measured formulations.
 */
export const PRESETS: readonly Preset[] = [
  {
    id: 'liposome', label: 'Liposome',
    description:
      'Conventional PEGylated liposome geometry. A starting template, not a '
      + 'measured formulation.',
    architecture: 'liposome',
    designValues: { size_nm: '100', coating_thickness_nm: '5' },
    chips: { surface_coating: ['PEG (Stealth)'] },
  },
  {
    id: 'pegylated_polymeric', label: 'PEGylated polymeric nanoparticle',
    description:
      'Polymer matrix with a PEG surface layer. A starting template, not a '
      + 'measured formulation.',
    architecture: 'polymeric',
    designValues: { size_nm: '120', coating_thickness_nm: '8' },
    chips: { surface_coating: ['PEG (Stealth)'] },
  },
  {
    id: 'gold', label: 'Gold nanoparticle',
    description:
      'Dense metallic core with a thin stabilising layer. A starting '
      + 'template, not a measured formulation.',
    architecture: 'metallic',
    designValues: { size_nm: '50', coating_thickness_nm: '3' },
    chips: {},
  },
  {
    id: 'silica_core_shell', label: 'Silica core–shell nanoparticle',
    description:
      'Silica framework with a distinct outer shell. A starting template, '
      + 'not a measured formulation.',
    architecture: 'silica',
    designValues: { size_nm: '80', coating_thickness_nm: '10' },
    chips: {},
  },
];

/* ========================================================================= */
/* Charge overlay                                                            */
/* ========================================================================= */

export interface ChargeBand {
  label: string;
  colour: string;
  test: (mv: number) => boolean;
}

/**
 * Bands for the charge overlay legend.
 *
 * These are **display bands for a colour scale**, not a scientific
 * classification of colloidal stability. The boundaries are round numbers
 * chosen so the legend is readable.
 */
export const CHARGE_BANDS: readonly ChargeBand[] = [
  { label: 'Strongly negative (≤ −30 mV)', colour: '#2563eb',
    test: (mv) => mv <= -30 },
  { label: 'Negative (−30 to −10 mV)', colour: '#38bdf8',
    test: (mv) => mv <= -10 },
  { label: 'Near neutral (−10 to +10 mV)', colour: '#94a3b8',
    test: (mv) => mv < 10 },
  { label: 'Positive (+10 to +30 mV)', colour: '#fbbf24',
    test: (mv) => mv < 30 },
  { label: 'Strongly positive (≥ +30 mV)', colour: '#ef4444',
    test: () => true },
];

export function chargeBand(mv: number): ChargeBand {
  return CHARGE_BANDS.find((b) => b.test(mv)) ?? CHARGE_BANDS[
    CHARGE_BANDS.length - 1]!;
}
