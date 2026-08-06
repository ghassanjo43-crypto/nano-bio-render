/**
 * Detail levels, seeded placement and architecture-specific geometry.
 *
 * Three levels, not one
 * ---------------------
 * A whole nanoparticle cannot be drawn at molecular detail — a 100 nm liposome
 * holds on the order of 10⁵ lipids, and instantiating them would make the
 * browser unusable. So detail is scoped:
 *
 *   overview   — optimised whole particle, representative populations;
 *   structural — layers, cutaways, denser surface and payload sampling;
 *   molecular  — ONE LOCAL PATCH at recognisable molecular detail.
 *
 * The molecular level never applies to the whole particle. That is a deliberate
 * limit, stated in the interface, not an omission.
 *
 * Determinism
 * -----------
 * All variation comes from a seeded PRNG keyed on the design, so the same
 * design always produces the same arrangement. Variation is cosmetic: it makes
 * chains look like chains rather than identical spikes. It carries no
 * information and must not be read as conformational data.
 */

import type { Architecture, VisualModel } from './particleModel';

/* ========================================================================= */
/* Detail levels                                                             */
/* ========================================================================= */

export type DetailLevel = 'overview' | 'structural' | 'molecular';

export interface DetailLevelSpec {
  id: DetailLevel;
  label: string;
  description: string;
  /** Sphere tessellation for enclosing layers. */
  sphereSegments: number;
  /** Upper bound on rendered surface glyphs. */
  maxSurfaceGlyphs: number;
  /** Upper bound on rendered payload glyphs. */
  maxPayloadGlyphs: number;
  /** Segments per flexible chain. 1 = a single rigid capsule. */
  chainSegments: number;
}

export const DETAIL_LEVELS: readonly DetailLevelSpec[] = [
  {
    id: 'overview', label: 'A — Particle overview',
    description:
      'The whole particle, optimised for rotation and comparison. Surface and '
      + 'payload are drawn as representative samples, not populations.',
    sphereSegments: 64, maxSurfaceGlyphs: 96, maxPayloadGlyphs: 48,
    chainSegments: 1,
  },
  {
    id: 'structural', label: 'B — Structural detail',
    description:
      'Core, shell, bilayer and coating with denser surface and payload '
      + 'sampling. Cutaway, cross-section and exploded views apply here.',
    sphereSegments: 96, maxSurfaceGlyphs: 260, maxPayloadGlyphs: 160,
    chainSegments: 4,
  },
  {
    id: 'molecular', label: 'C — Molecular close-up',
    description:
      'One local patch of the surface at recognisable molecular detail: lipid '
      + 'heads and tails, flexible PEG, anchored ligands. The rest of the '
      + 'particle is not drawn at this detail and never is.',
    sphereSegments: 128, maxSurfaceGlyphs: 420, maxPayloadGlyphs: 90,
    chainSegments: 7,
  },
];

export function detailSpec(level: DetailLevel): DetailLevelSpec {
  return DETAIL_LEVELS.find((d) => d.id === level)!;
}

/** Quality presets, applied on top of the detail level. */
export type QualityPreset = 'low' | 'balanced' | 'high';

export const QUALITY_PRESETS: Record<QualityPreset, {
  label: string; glyphScale: number; segmentScale: number; description: string;
}> = {
  low: { label: 'Low (fastest)', glyphScale: 0.4, segmentScale: 0.5,
         description: 'Fewer objects and coarser meshes, for slow hardware.' },
  balanced: { label: 'Balanced', glyphScale: 1, segmentScale: 1,
              description: 'The default.' },
  high: { label: 'High', glyphScale: 1.6, segmentScale: 1.35,
          description: 'More objects and finer meshes. Needs a capable GPU.' },
};

/** Hard ceiling on instances, regardless of level or quality. */
export const ABSOLUTE_GLYPH_CAP = 900;

export interface RenderBudget {
  surfaceGlyphs: number;
  payloadGlyphs: number;
  sphereSegments: number;
  chainSegments: number;
  /** True when a cap reduced what would otherwise have been drawn. */
  capped: boolean;
}

export function resolveBudget(
  level: DetailLevel, quality: QualityPreset,
  requestedSurface: number, requestedPayload: number,
): RenderBudget {
  const spec = detailSpec(level);
  const q = QUALITY_PRESETS[quality];

  const surfaceLimit = Math.round(spec.maxSurfaceGlyphs * q.glyphScale);
  const payloadLimit = Math.round(spec.maxPayloadGlyphs * q.glyphScale);

  const surfaceGlyphs = Math.min(requestedSurface, surfaceLimit,
                                 ABSOLUTE_GLYPH_CAP);
  const payloadGlyphs = Math.min(requestedPayload, payloadLimit,
                                 ABSOLUTE_GLYPH_CAP);

  return {
    surfaceGlyphs,
    payloadGlyphs,
    sphereSegments: Math.max(16,
      Math.round(spec.sphereSegments * q.segmentScale)),
    chainSegments: Math.max(1, Math.round(spec.chainSegments * q.segmentScale)),
    capped: surfaceGlyphs < requestedSurface || payloadGlyphs < requestedPayload,
  };
}

/* ========================================================================= */
/* Seeded determinism                                                        */
/* ========================================================================= */

/** FNV-1a, so a design string maps to a stable 32-bit seed. */
export function seedFrom(input: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

/** Mulberry32. Small, fast, and identical across runs for a given seed. */
export function makeRng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A seed derived from the design, so the same design looks the same. */
export function seedForModel(model: VisualModel): number {
  return seedFrom([
    model.architecture.value,
    model.geometry.outerDiameterNm ?? 'na',
    model.geometry.coatingThicknessNm ?? 'na',
    model.ligandGlyphs,
    model.payloadGlyphs,
    model.chargeMv ?? 'na',
  ].join('|'));
}

/* ========================================================================= */
/* Surface chains                                                            */
/* ========================================================================= */

export type Vec3 = [number, number, number];

export interface ChainConformation {
  /** Anchor point on the surface. */
  anchor: Vec3;
  /** Successive joint positions, ending at the free tip. */
  joints: Vec3[];
  /** Terminal group position, for a ligand on a linker. */
  tip: Vec3;
}

/**
 * Build flexible chain conformations anchored to the surface.
 *
 * Each chain leaves along the local surface normal and wanders by a seeded
 * amount, so no two look identical. The wander is cosmetic — it represents
 * "these are flexible polymers", not any measured conformation.
 */
export function buildChains(
  anchors: Vec3[], length: number, segments: number, seed: number,
  wander = 0.42,
): ChainConformation[] {
  const rng = makeRng(seed);
  return anchors.map((anchor) => {
    const norm = Math.hypot(anchor[0], anchor[1], anchor[2]) || 1;
    let dir: Vec3 = [anchor[0] / norm, anchor[1] / norm, anchor[2] / norm];
    let point: Vec3 = [...anchor] as Vec3;
    const joints: Vec3[] = [];
    const step = length / Math.max(1, segments);

    for (let s = 0; s < segments; s += 1) {
      // Perturb the direction, then renormalise, so the chain bends smoothly.
      const jitter: Vec3 = [
        (rng() - 0.5) * wander,
        (rng() - 0.5) * wander,
        (rng() - 0.5) * wander,
      ];
      const nx = dir[0] + jitter[0];
      const ny = dir[1] + jitter[1];
      const nz = dir[2] + jitter[2];
      const len = Math.hypot(nx, ny, nz) || 1;
      // Bias back outward so a chain never tunnels into the particle.
      dir = [
        (nx / len) * 0.75 + (anchor[0] / norm) * 0.25,
        (ny / len) * 0.75 + (anchor[1] / norm) * 0.25,
        (nz / len) * 0.75 + (anchor[2] / norm) * 0.25,
      ];
      const dl = Math.hypot(dir[0], dir[1], dir[2]) || 1;
      dir = [dir[0] / dl, dir[1] / dl, dir[2] / dl];

      point = [point[0] + dir[0] * step,
               point[1] + dir[1] * step,
               point[2] + dir[2] * step];
      joints.push([...point] as Vec3);
    }

    return { anchor, joints, tip: joints[joints.length - 1] ?? anchor };
  });
}

/**
 * Drop anchors that sit closer than `minSeparation`, so glyphs do not visibly
 * interpenetrate. A crude steric check: it prevents obvious overlap and makes
 * no claim about real packing.
 */
export function applyStericSpacing(points: Vec3[],
                                   minSeparation: number): Vec3[] {
  const kept: Vec3[] = [];
  const min2 = minSeparation * minSeparation;
  for (const p of points) {
    let ok = true;
    for (const q of kept) {
      const dx = p[0] - q[0], dy = p[1] - q[1], dz = p[2] - q[2];
      if (dx * dx + dy * dy + dz * dz < min2) { ok = false; break; }
    }
    if (ok) kept.push(p);
  }
  return kept;
}

/* ========================================================================= */
/* Architecture-specific surface morphology                                  */
/* ========================================================================= */

export interface SurfaceMorphology {
  /** Displacement applied per-vertex, as a fraction of the radius. */
  roughness: number;
  /** Facet count for a crystalline body. 0 means smooth. */
  facets: number;
  /** Material character, consumed by the scene's material choice. */
  finish: 'metallic' | 'glassy' | 'soft' | 'matte';
  note: string;
}

/**
 * Morphology per architecture.
 *
 * These are appearance choices, not measurements. The design records no
 * surface roughness or crystal habit, so each carries a note saying so.
 */
export function morphologyFor(architecture: Architecture): SurfaceMorphology {
  switch (architecture) {
    case 'metallic':
      return {
        roughness: 0.035, facets: 1, finish: 'metallic',
        note: 'Drawn with a mildly faceted, crystalline-looking surface. The '
          + 'design records no crystal habit, so the faceting is illustrative.',
      };
    case 'silica':
      return {
        roughness: 0.02, facets: 0, finish: 'glassy',
        note: 'Drawn with a smooth glassy finish. Porosity is shown only when '
          + 'it is explicitly supplied or selected as illustrative.',
      };
    case 'polymeric':
      return {
        roughness: 0.045, facets: 0, finish: 'soft',
        note: 'Drawn with a soft irregular surface suggesting an entangled '
          + 'polymer matrix. The irregularity is illustrative.',
      };
    case 'liposome':
      return {
        roughness: 0.015, facets: 0, finish: 'soft',
        note: 'Drawn with gentle membrane undulation. Real curvature '
          + 'fluctuations are not recorded and are not modelled.',
      };
    default:
      return {
        roughness: 0.01, facets: 0, finish: 'matte',
        note: 'Drawn as a smooth sphere. The design records no shape or '
          + 'surface morphology, so the form is illustrative.',
      };
  }
}

/**
 * Whether a mesoporous representation may be drawn.
 *
 * Never inferred from the architecture alone: silica is often mesoporous, but
 * "often" is not "this one". Porosity is drawn only when the researcher
 * supplies a pore volume or explicitly asks for an illustrative porous view.
 */
export function poresMayBeDrawn(architecture: Architecture,
                                poreVolumeNm3: number | undefined,
                                illustrativePorosity: boolean): boolean {
  if (architecture !== 'silica') return false;
  return Boolean(poreVolumeNm3) || illustrativePorosity;
}

export const POROSITY_NOT_SPECIFIED_NOTE =
  'Porosity is not recorded for this design, so the particle is drawn solid. '
  + 'Select the illustrative porous view to see a pore structure — it will be '
  + 'labelled as illustrative and no pore dimension will be claimed.';

export const MOLECULAR_PATCH_NOTE =
  'Molecular detail is drawn for one local patch only. A whole nanoparticle '
  + 'holds far more molecules than a browser can render, so no view here shows '
  + 'the complete molecular population.';

export const NO_ATOMIC_STRUCTURE_NOTE =
  'No atomic structure is available for this payload. Molecules are drawn as '
  + 'schematic shapes. A structure is never generated from a compound name.';
