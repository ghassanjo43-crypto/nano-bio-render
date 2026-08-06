/**
 * Which structural layers exist for a design, and what each one is made of.
 *
 * Why this is derived, not fixed
 * ------------------------------
 * A layer list is a structural claim. Showing "Lipid bilayer" for a design with
 * no recorded architecture would assert a structure the platform does not know.
 * So the list is derived from the architecture actually in effect, and every
 * layer carries the provenance of the fact that put it there — supplied,
 * calculated, or illustrative.
 *
 * A metallic particle deliberately has **no payload layer**: the specification
 * requires that internal drug encapsulation is not implied for a metallic core
 * unless it is supported. A silica particle gets no porosity layer, because
 * porosity is never recorded.
 *
 * This module imports nothing from three.js. The scene reads the result.
 */

import type { Provenance, VisualModel } from './particleModel';

/** Stable identifiers, used by the scene, the panel and the tests alike. */
export type LayerId =
  | 'core'
  | 'internal_compartment'
  | 'shell'
  | 'lipid_bilayer'
  | 'coating'
  | 'peg'
  | 'ligands'
  | 'functional_groups'
  | 'payload'
  | 'charge_field';

export interface LayerSpec {
  id: LayerId;
  label: string;
  /** Radial order, innermost first. Drives the exploded view's ordering. */
  order: number;
  /** What this layer represents. */
  description: string;
  /** Where the fact that this layer exists came from. */
  provenance: Provenance;
  /** Required for an assumption or default. */
  origin?: string;
  /** The design field this layer corresponds to, when there is one. */
  designKey?: string;
  /** Default opacity, 0-1. */
  defaultOpacity: number;
  /** Whether the layer's drawn thickness had to be enlarged to be visible. */
  enlargedForVisibility?: boolean;
}

const ILLUSTRATIVE_STRUCTURE =
  'The design records no particle architecture, so this layer is part of an '
  + 'illustrative representation rather than a recorded structure.';

/**
 * Build the layer list for a model.
 *
 * Only layers with a genuine basis appear. A coating layer exists when a
 * surface coating was recorded; ligand markers exist when a ligand density was
 * recorded; the charge overlay exists when a zeta potential was supplied.
 */
export function buildLayers(model: VisualModel): LayerSpec[] {
  const arch = model.architecture.value;
  const architectureIsAssumed =
    model.architecture.provenance === 'illustrative_assumption';
  const structureProvenance: Provenance = architectureIsAssumed
    ? 'illustrative_assumption' : 'supplied';
  const structureOrigin = architectureIsAssumed
    ? (model.architecture.origin ?? ILLUSTRATIVE_STRUCTURE) : undefined;

  const layers: LayerSpec[] = [];

  /* --- interior ---------------------------------------------------------- */
  if (arch === 'liposome') {
    layers.push({
      id: 'internal_compartment', label: 'Aqueous interior', order: 0,
      description:
        'The water-filled compartment enclosed by the lipid bilayer.',
      provenance: structureProvenance, origin: structureOrigin,
      defaultOpacity: 0.18,
    });
    layers.push({
      id: 'lipid_bilayer', label: 'Lipid bilayer', order: 1,
      description:
        'The two-leaflet lipid membrane. Drawn as two closely spaced '
        + 'surfaces; the real leaflet spacing is not recorded.',
      provenance: structureProvenance, origin: structureOrigin,
      defaultOpacity: 0.55, enlargedForVisibility: true,
    });
  } else {
    layers.push({
      id: 'core', label: arch === 'polymeric' ? 'Polymer matrix' : 'Core',
      order: 0,
      description: arch === 'polymeric'
        ? 'The polymer body of the particle, through which payload disperses.'
        : arch === 'metallic'
          ? 'The dense metallic body of the particle.'
          : 'The interior body of the particle.',
      provenance: structureProvenance, origin: structureOrigin,
      designKey: model.geometry.coreDiameterNm !== null
        ? 'core_diameter_nm' : undefined,
      defaultOpacity: 1,
    });
  }

  /* --- shell ------------------------------------------------------------- */
  // A distinct shell is only drawn when the architecture has one AND a coating
  // thickness was recorded — otherwise its dimension would be invented.
  if (arch === 'core_shell' || arch === 'silica' || arch === 'hybrid'
      || arch === 'metallic') {
    const thicknessSupplied = model.geometry.coatingThicknessNm !== null;
    layers.push({
      id: 'shell', label: 'Shell', order: 2,
      description: thicknessSupplied
        ? 'The outer shell enclosing the core. Its thickness is the recorded '
          + 'coating thickness.'
        : 'The outer shell enclosing the core. No thickness was recorded, so '
          + 'the drawn thickness is illustrative.',
      provenance: thicknessSupplied ? 'supplied' : 'illustrative_assumption',
      origin: thicknessSupplied ? undefined
        : 'No coating thickness is recorded, so the shell is drawn at a '
          + 'nominal thickness chosen for visibility. It is not a measurement.',
      designKey: 'coating_thickness_nm',
      defaultOpacity: 0.5,
      enlargedForVisibility: !thicknessSupplied,
    });
  }

  /* --- coating and PEG --------------------------------------------------- */
  if (model.coatingLabel.value !== null) {
    const isPeg = String(model.coatingLabel.value).toUpperCase().includes('PEG');
    layers.push({
      id: isPeg ? 'peg' : 'coating',
      label: isPeg ? 'PEG chains' : 'Surface coating', order: 3,
      description: isPeg
        ? 'Poly(ethylene glycol) chains, drawn as a representative brush. The '
          + 'number of chains drawn is not a molecular count.'
        : `Recorded surface coating: ${model.coatingLabel.value}.`,
      provenance: 'supplied', designKey: 'surface_coating',
      defaultOpacity: 0.8,
    });
  }

  /* --- surface structures ------------------------------------------------ */
  if (model.ligandGlyphs > 0) {
    layers.push({
      id: 'ligands', label: 'Targeting ligands', order: 4,
      description:
        `${model.ligandGlyphs} representative surface markers, scaled from the `
        + 'recorded ligand density. One marker is not one molecule.',
      provenance: 'calculated', designKey: 'ligand_density_percent',
      defaultOpacity: 1,
    });
  }

  if (model.functionalGroups.value.length > 0) {
    layers.push({
      id: 'functional_groups', label: 'Functional groups', order: 5,
      description:
        `Recorded groups: ${model.functionalGroups.value.join(', ')}. Drawn as `
        + 'simplified surface markers at representative positions.',
      provenance: 'supplied', designKey: 'functional_groups',
      defaultOpacity: 1,
    });
  }

  /* --- payload ----------------------------------------------------------- */
  // Deliberately absent for a metallic particle: the specification forbids
  // implying internal drug encapsulation for a metallic core unless supported,
  // and nothing in the design supports it.
  if (model.payloadGlyphs > 0 && arch !== 'metallic') {
    layers.push({
      id: 'payload', label: 'Encapsulated payload', order: 1.5,
      description:
        `${model.payloadGlyphs} representative markers, scaled from the `
        + 'recorded encapsulation efficiency. This is an illustrative density, '
        + 'not a molecule count.',
      provenance: 'calculated', designKey: 'encapsulation_percent',
      defaultOpacity: 1,
    });
  }

  /* --- charge overlay ---------------------------------------------------- */
  if (model.chargeMv !== null) {
    layers.push({
      id: 'charge_field', label: 'Surface charge field', order: 6,
      description:
        'Colour overlay for the recorded zeta potential. A display scale, not '
        + 'a modelled electrostatic field.',
      provenance: 'supplied', designKey: 'charge_mv',
      defaultOpacity: 0.16,
    });
  }

  return layers.sort((a, b) => a.order - b.order);
}

/** Why a metallic particle shows no payload layer. Surfaced in the panel. */
export const METALLIC_NO_PAYLOAD_NOTE =
  'No payload layer is drawn for a metallic architecture. Internal drug '
  + 'encapsulation is not implied for a metallic core unless the design '
  + 'records something that supports it, and it does not.';

/** Shown whenever the architecture itself is an assumption. */
export const UNSPECIFIED_STRUCTURE_NOTE =
  'Internal structure not specified — illustrative representation.';

export const EXPLODED_SPACING_NOTE =
  'Layer spacing in the exploded view is illustrative. It is chosen so each '
  + 'layer can be seen and does not represent any physical separation.';

export const ENLARGED_LAYER_NOTE =
  'Layer enlarged for visibility — displayed thickness is not to scale.';

/* ========================================================================= */
/* Per-layer viewer state                                                    */
/* ========================================================================= */

export interface LayerState {
  visible: boolean;
  opacity: number;
}

export type LayerStates = Record<string, LayerState>;

export function initialLayerStates(layers: LayerSpec[]): LayerStates {
  const states: LayerStates = {};
  for (const layer of layers) {
    states[layer.id] = {
      // The charge overlay is off by default; everything structural is on.
      visible: layer.id !== 'charge_field',
      opacity: layer.defaultOpacity,
    };
  }
  return states;
}

/** Opacity presets. Viewing aids only — none of these touches a design value. */
export type TransparencyPreset = 'opaque' | 'semi' | 'internal' | 'xray';

export const TRANSPARENCY_PRESETS: Record<TransparencyPreset, {
  label: string; description: string; opacity: Partial<Record<LayerId, number>>;
}> = {
  opaque: {
    label: 'Opaque',
    description: 'Every layer fully solid. The interior is hidden.',
    opacity: { core: 1, shell: 1, coating: 1, peg: 1, lipid_bilayer: 1,
               internal_compartment: 0.9, payload: 1 },
  },
  semi: {
    label: 'Semi-transparent',
    description: 'Outer layers softened so the interior is suggested.',
    opacity: { core: 0.75, shell: 0.45, coating: 0.7, peg: 0.7,
               lipid_bilayer: 0.5, internal_compartment: 0.25, payload: 1 },
  },
  internal: {
    label: 'Internal inspection',
    description: 'Outer layers faint so internal components read clearly.',
    opacity: { core: 0.35, shell: 0.2, coating: 0.35, peg: 0.35,
               lipid_bilayer: 0.28, internal_compartment: 0.12, payload: 1 },
  },
  xray: {
    label: 'X-ray view',
    description:
      'All enclosing layers nearly invisible. A viewing aid — it is not an '
      + 'imaging modality and shows nothing that was not already drawn.',
    opacity: { core: 0.12, shell: 0.08, coating: 0.12, peg: 0.12,
               lipid_bilayer: 0.1, internal_compartment: 0.05, payload: 1 },
  },
};

export function applyTransparencyPreset(
  layers: LayerSpec[], states: LayerStates, preset: TransparencyPreset,
): LayerStates {
  const next: LayerStates = { ...states };
  const table = TRANSPARENCY_PRESETS[preset].opacity;
  for (const layer of layers) {
    const value = table[layer.id];
    if (value !== undefined) {
      next[layer.id] = { ...next[layer.id]!, opacity: value };
    }
  }
  return next;
}

/** Isolate one layer: it stays visible, everything else hides. */
export function isolateLayer(layers: LayerSpec[], states: LayerStates,
                             id: LayerId): LayerStates {
  const next: LayerStates = {};
  for (const layer of layers) {
    next[layer.id] = {
      ...states[layer.id]!,
      visible: layer.id === id,
      // An isolated layer is always fully readable.
      opacity: layer.id === id ? 1 : states[layer.id]!.opacity,
    };
  }
  return next;
}
