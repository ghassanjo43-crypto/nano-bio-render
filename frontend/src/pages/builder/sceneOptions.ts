/**
 * Viewer state for the nanoparticle builder.
 *
 * Deliberately a separate module from `ParticleScene.tsx`: the builder page
 * needs these values at runtime, and importing them from the scene file would
 * pull three.js, @react-three/fiber and drei into the initial bundle, defeating
 * the lazy load. Types erase at compile time; values do not.
 *
 * **Everything here is a viewing preference.** No field affects a design value,
 * a simulation input or any calculation. Changing a view mode, a cutaway depth
 * or a layer opacity leaves the stored study byte-identical.
 */

import type { LayerStates, TransparencyPreset } from './layers';

/** The Internal Structure modes. Mutually exclusive. */
export type ViewMode =
  | 'whole'
  | 'transparent'
  | 'cutaway'
  | 'cross_section'
  | 'exploded';

export interface ViewModeSpec {
  id: ViewMode;
  label: string;
  description: string;
}

export const VIEW_MODES: readonly ViewModeSpec[] = [
  { id: 'whole', label: 'Whole particle',
    description:
      'The complete exterior: outer surface, coating, ligands, functional '
      + 'groups and the charge overlay when enabled.' },
  { id: 'transparent', label: 'Transparent shell',
    description:
      'Enclosing layers softened so interior components are visible through '
      + 'them. No geometry is removed.' },
  { id: 'cutaway', label: 'Cutaway',
    description:
      'A wedge of the outer structure is geometrically removed, exposing the '
      + 'interior. The remaining shell keeps its thickness and stays solid.' },
  { id: 'cross_section', label: 'Cross-section',
    description:
      'A single plane cuts the particle, showing one clean face through every '
      + 'layer. The plane can be moved and re-oriented.' },
  { id: 'exploded', label: 'Exploded layers',
    description:
      'Layers separated along an axis in their radial order, so each can be '
      + 'seen. The spacing is illustrative.' },
];

export type SectionAxis = 'sagittal' | 'transverse' | 'coronal';

export const SECTION_AXES: ReadonlyArray<{
  id: SectionAxis; label: string; normal: [number, number, number];
}> = [
  { id: 'sagittal', label: 'Sagittal (vertical, left–right)', normal: [1, 0, 0] },
  { id: 'transverse', label: 'Transverse (horizontal)', normal: [0, 1, 0] },
  { id: 'coronal', label: 'Coronal (vertical, front–back)', normal: [0, 0, 1] },
];

/**
 * Cutaway depths, as the fraction of the particle removed.
 *
 * Only these three are expressible with plane clipping: an arbitrary angle
 * would need a non-convex kept region. Intermediate slider values snap to the
 * nearest of these, and the interface reports the depth actually applied.
 */
export const CUTAWAY_FRACTIONS = [0.25, 0.5, 0.75] as const;

export function snapCutawayFraction(fraction: number): number {
  if (fraction <= 0.375) return 0.25;
  if (fraction <= 0.625) return 0.5;
  return 0.75;
}

export interface ViewerState {
  mode: ViewMode;

  /** Fraction of the outer structure removed in cutaway mode, 0–1. */
  cutawayFraction: number;

  /** Cross-section plane. */
  sectionAxis: SectionAxis;
  /** Plane offset in scene units, −1 to 1 (particle radius is 1). */
  sectionPosition: number;
  /** Which half is kept. */
  sectionSide: 'front' | 'back';
  showMeasurements: boolean;

  /** Separation between layers in exploded mode, in scene units. */
  explosionDistance: number;

  /** Per-layer visibility and opacity. */
  layers: LayerStates;
  /** The isolated layer, when one is isolated. */
  isolated: string | null;
  transparencyPreset: TransparencyPreset | null;

  showLabels: boolean;
  showLigands: boolean;
  showPayload: boolean;
  payloadDistributionView: boolean;
  autoRotate: boolean;
  reducedMotion: boolean;
  background: 'dark' | 'light' | 'transparent';
}

export const DEFAULT_VIEWER_STATE: Omit<ViewerState, 'layers'> = {
  mode: 'whole',
  cutawayFraction: 0.5,
  sectionAxis: 'sagittal',
  sectionPosition: 0,
  sectionSide: 'front',
  showMeasurements: false,
  explosionDistance: 0.9,
  isolated: null,
  transparencyPreset: null,
  showLabels: true,
  showLigands: true,
  showPayload: true,
  payloadDistributionView: false,
  autoRotate: false,
  reducedMotion: false,
  background: 'dark',
};

/** True when the mode removes geometry rather than only softening it. */
export function modeRemovesGeometry(mode: ViewMode): boolean {
  return mode === 'cutaway' || mode === 'cross_section';
}

/**
 * A plain-language description of what is currently on screen.
 *
 * Exists for the accessibility requirement: a user who cannot see the canvas
 * must still be able to learn what the viewer is showing.
 */
export function describeView(state: ViewerState,
                             layerLabels: string[]): string {
  const mode = VIEW_MODES.find((m) => m.id === state.mode)!;
  const parts = [`${mode.label}: ${mode.description}`];

  if (state.mode === 'cutaway') {
    parts.push(
      `${Math.round(state.cutawayFraction * 100)}% of the outer structure is `
      + 'removed.');
  }
  if (state.mode === 'cross_section') {
    const axis = SECTION_AXES.find((a) => a.id === state.sectionAxis)!;
    parts.push(
      `${axis.label} plane at offset ${state.sectionPosition.toFixed(2)} of the `
      + `particle radius, showing the ${state.sectionSide} half.`);
  }
  if (state.mode === 'exploded') {
    parts.push(
      `Layers separated by ${state.explosionDistance.toFixed(2)} scene units. `
      + 'The spacing is illustrative.');
  }
  if (state.isolated) {
    parts.push(`Only the ${state.isolated} layer is shown.`);
  }

  parts.push(layerLabels.length
    ? `Visible layers: ${layerLabels.join(', ')}.`
    : 'No layers are currently visible.');

  return parts.join(' ');
}
