/**
 * The Three.js scene. Loaded lazily — nothing here reaches the initial bundle.
 *
 * Every dimension drawn comes from `particleModel.ts` and every layer from
 * `layers.ts`. This file decides how things look, never what they mean.
 *
 * The cutaway is a genuine geometric removal
 * ------------------------------------------
 * Two clipping planes meeting at the centre remove a real wedge of the
 * enclosing layers, so the remaining shell keeps its thickness and reads as a
 * solid three-dimensional layer with a visible cut edge. Transparency is
 * offered separately, as its own mode, and is never used as a substitute for a
 * cutaway.
 *
 * Interior components are deliberately NOT clipped: clipping the payload away
 * with the shell would remove exactly what the cutaway exists to reveal.
 *
 * Repeated objects are drawn with `<Instances>`, so a few hundred glyphs cost a
 * handful of draw calls. Geometries are memoised and disposed with the meshes.
 */

import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  Html, Instance, Instances, Line, OrbitControls,
  PerspectiveCamera,
} from '@react-three/drei';
import * as THREE from 'three';
import {
  chargeBand, fibonacciSphere, interiorPoints, type VisualModel,
} from './particleModel';
import { EXPLODED_SPACING_NOTE, type LayerId, type LayerSpec } from './layers';
import { SECTION_AXES, type ViewerState } from './sceneOptions';
import {
  applyStericSpacing, buildChains, makeRng, morphologyFor,
  type DetailLevel, type RenderBudget, type Vec3,
} from './detailLevels';

export interface ParticleSceneProps {
  model: VisualModel;
  layers: LayerSpec[];
  state: ViewerState;
  /** Which of the three detail levels to draw. */
  detail: DetailLevel;
  /** Resolved instance and tessellation caps. */
  budget: RenderBudget;
  /** Seed for deterministic conformational variation. */
  seed: number;
  onSelect?: (layerId: LayerId) => void;
  /** Exposes the canvas so the page can capture a PNG. */
  onCanvasReady?: (canvas: HTMLCanvasElement) => void;
}

const PALETTE: Record<string, string> = {
  core: '#5b7fbd',
  internal_compartment: '#7dd3fc',
  shell: '#8ec5ff',
  lipid_bilayer: '#f2c14e',
  coating: '#c4b5fd',
  peg: '#c4b5fd',
  ligands: '#34d399',
  functional_groups: '#fca5a5',
  payload: '#f472b6',
};

/* ------------------------------------------------------------- clipping */

/**
 * Clipping configuration for the current mode.
 *
 * Three.js clips with a set of planes that are either INTERSECTED (the default:
 * keep only what satisfies every plane) or UNIONED (`clipIntersection = true`:
 * keep what satisfies any plane). That choice is what makes different cutaway
 * depths expressible:
 *
 *   * a quarter removed — keep (x<0 OR z<0), a union of two half-spaces;
 *   * a half removed    — keep one half-space, a single plane;
 *   * three quarters removed — keep (x<0 AND z<0), an intersection.
 *
 * The removed wedge always faces +X+Z, which is toward the default camera, so
 * the cut faces and the exposed interior are what the viewer sees rather than
 * the intact far wall.
 *
 * Fractions between the three cases are snapped to the nearest expressible
 * one: an arbitrary angle would need a non-convex region, which plane clipping
 * cannot represent. The control reports the depth actually applied.
 */
export interface ClipConfig {
  planes: THREE.Plane[];
  intersection: boolean;
  /** The depth actually applied, after snapping. */
  appliedFraction: number;
}

const X_NEG = () => new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
const Z_NEG = () => new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);

export function resolveCutaway(fraction: number): ClipConfig {
  if (fraction <= 0.375) {
    // Union: keep x<0 OR z<0 — one quadrant is removed.
    return { planes: [X_NEG(), Z_NEG()], intersection: true,
             appliedFraction: 0.25 };
  }
  if (fraction <= 0.625) {
    // A single plane at 45 degrees, so the cut face angles toward the camera.
    const n = new THREE.Vector3(-1, 0, -1).normalize();
    return { planes: [new THREE.Plane(n, 0)], intersection: false,
             appliedFraction: 0.5 };
  }
  // Intersection: keep x<0 AND z<0 — three quadrants are removed.
  return { planes: [X_NEG(), Z_NEG()], intersection: false,
           appliedFraction: 0.75 };
}

function useClipping(state: ViewerState): ClipConfig {
  return useMemo(() => {
    if (state.mode === 'cutaway') return resolveCutaway(state.cutawayFraction);
    if (state.mode === 'cross_section') {
      const axis = SECTION_AXES.find((s) => s.id === state.sectionAxis)!;
      const normal = new THREE.Vector3(...axis.normal);
      if (state.sectionSide === 'back') normal.negate();
      return {
        planes: [new THREE.Plane(normal, state.sectionPosition)],
        intersection: false,
        appliedFraction: 0.5,
      };
    }
    return { planes: [], intersection: false, appliedFraction: 0 };
  }, [state.mode, state.cutawayFraction, state.sectionAxis,
      state.sectionPosition, state.sectionSide]);
}


function useLayer(state: ViewerState, id: LayerId) {
  const entry = state.layers[id];
  return { visible: entry?.visible ?? false, opacity: entry?.opacity ?? 1 };
}

/** Vertical offset for a layer in the exploded view, by radial order. */
function explodedOffset(state: ViewerState, layer: LayerSpec | undefined,
                        layers: LayerSpec[]): number {
  if (state.mode !== 'exploded' || !layer) return 0;
  const index = layers.findIndex((l) => l.id === layer.id);
  const centre = (layers.length - 1) / 2;
  return (index - centre) * state.explosionDistance;
}

/* ------------------------------------------------------------ animation */

function Spinner({ state, children }: {
  state: ViewerState; children: React.ReactNode;
}) {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    // Reduced motion disables continuous rotation entirely.
    if (state.autoRotate && !state.reducedMotion && ref.current) {
      ref.current.rotation.y += delta * 0.35;
    }
  });
  return <group ref={ref}>{children}</group>;
}

/** Eases a group's Y offset, so exploding is not a jump cut. */
function Animated({ targetY, reducedMotion, children }: {
  targetY: number; reducedMotion: boolean; children: React.ReactNode;
}) {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (!ref.current) return;
    if (reducedMotion) { ref.current.position.y = targetY; return; }
    const step = Math.min(1, delta * 6);
    ref.current.position.y += (targetY - ref.current.position.y) * step;
  });
  return <group ref={ref}>{children}</group>;
}

function Label({ position, text, visible, tone }: {
  position: [number, number, number]; text: string; visible: boolean;
  tone?: 'assumed';
}) {
  if (!visible) return null;
  return (
    <Html position={position} center distanceFactor={7}
          zIndexRange={[10, 0]} style={{ pointerEvents: 'none' }}>
      <span className={`np3d__label${tone === 'assumed'
        ? ' np3d__label--assumed' : ''}`}>{text}</span>
    </Html>
  );
}

/* --------------------------------------------------------------- layers */

function ShellLike({ id, radius, colour, state, layers, layerSpec, clipping,
                    onSelect, label, segments = 64, finish = 'matte' }: {
  id: LayerId; radius: number; colour: string; state: ViewerState;
  layers: LayerSpec[]; layerSpec?: LayerSpec; clipping: ClipConfig;
  onSelect?: (id: LayerId) => void; label?: string; segments?: number;
  finish?: 'metallic' | 'glassy' | 'soft' | 'matte';
}) {
  const { visible, opacity } = useLayer(state, id);
  const geometry = useMemo(
    () => new THREE.SphereGeometry(radius, segments, segments),
    [radius, segments]);
  useEffect(() => () => geometry.dispose(), [geometry]);

  if (!visible) return null;

  return (
    <Animated targetY={explodedOffset(state, layerSpec, layers)}
              reducedMotion={state.reducedMotion}>
      <mesh geometry={geometry}
            onClick={(e) => { e.stopPropagation(); onSelect?.(id); }}>
        <meshPhysicalMaterial
          color={colour}
          transparent={opacity < 1}
          opacity={opacity}
          roughness={finish === 'metallic' ? 0.18
            : finish === 'glassy' ? 0.08
            : finish === 'soft' ? 0.62 : 0.4}
          metalness={finish === 'metallic' ? 0.85 : 0.05}
          clearcoat={finish === 'glassy' ? 0.8 : 0.25}
          transmission={finish === 'glassy' ? 0.15 : 0}
          clippingPlanes={clipping.planes}
          clipIntersection={clipping.intersection}
          // Double-sided so a cut or sectioned layer shows its inner wall
          // rather than vanishing into an empty silhouette.
          side={THREE.DoubleSide}
        />
      </mesh>
      {label && (
        <Label position={[0, radius * 1.14, 0]} text={label}
               visible={state.showLabels}
               tone={layerSpec?.provenance === 'illustrative_assumption'
                 ? 'assumed' : undefined} />
      )}
    </Animated>
  );
}

/**
 * Flexible grafted chains: a run of small capsules following a seeded
 * conformation, so chains look like polymers rather than identical spikes.
 *
 * The conformations are deterministic for a given design and carry no
 * information — they are not measured or predicted conformations.
 */
function FlexibleChains({ id, anchors, colour, state, layers, layerSpec,
                          segments, length, seed, onSelect, tipColour }: {
  id: LayerId; anchors: Vec3[]; colour: string; state: ViewerState;
  layers: LayerSpec[]; layerSpec?: LayerSpec; segments: number;
  length: number; seed: number; onSelect?: (id: LayerId) => void;
  tipColour?: string;
}) {
  const { visible, opacity } = useLayer(state, id);
  const chains = useMemo(
    () => buildChains(anchors, length, segments, seed),
    [anchors, length, segments, seed]);

  if (!visible || chains.length === 0) return null;

  // One instance per segment across every chain.
  const beads: Array<{ p: Vec3; last: boolean }> = [];
  for (const chain of chains) {
    chain.joints.forEach((j, i) => {
      beads.push({ p: j, last: i === chain.joints.length - 1 });
    });
  }

  return (
    <Animated targetY={explodedOffset(state, layerSpec, layers)}
              reducedMotion={state.reducedMotion}>
      <Instances limit={beads.length}
                 onClick={(e) => { e.stopPropagation(); onSelect?.(id); }}>
        <sphereGeometry args={[0.018, 8, 8]} />
        <meshStandardMaterial color={colour} roughness={0.55}
                              transparent={opacity < 1} opacity={opacity} />
        {beads.map((b, i) => <Instance key={i} position={b.p} />)}
      </Instances>
      {tipColour && (
        <Instances limit={chains.length}>
          <icosahedronGeometry args={[0.042, 1]} />
          <meshStandardMaterial color={tipColour} roughness={0.35}
                                transparent={opacity < 1} opacity={opacity} />
          {chains.map((c, i) => <Instance key={i} position={c.tip} />)}
        </Instances>
      )}
    </Animated>
  );
}

function SurfaceGlyphs({ id, points, colour, geometry, state, layers,
                        layerSpec, onSelect, orient }: {
  id: LayerId; points: Array<[number, number, number]>; colour: string;
  geometry: React.ReactNode; state: ViewerState; layers: LayerSpec[];
  layerSpec?: LayerSpec; onSelect?: (id: LayerId) => void; orient?: boolean;
}) {
  const { visible, opacity } = useLayer(state, id);
  if (!visible || points.length === 0) return null;

  return (
    <Animated targetY={explodedOffset(state, layerSpec, layers)}
              reducedMotion={state.reducedMotion}>
      <Instances limit={points.length}
                 onClick={(e) => { e.stopPropagation(); onSelect?.(id); }}>
        {geometry}
        <meshStandardMaterial color={colour} roughness={0.4}
                              transparent={opacity < 1} opacity={opacity} />
        {points.map((p, i) => {
          if (!orient) return <Instance key={i} position={p} />;
          const dir = new THREE.Vector3(...p).normalize();
          const q = new THREE.Quaternion().setFromUnitVectors(
            new THREE.Vector3(0, 1, 0), dir);
          const e = new THREE.Euler().setFromQuaternion(q);
          return <Instance key={i} position={p} rotation={[e.x, e.y, e.z]} />;
        })}
      </Instances>
    </Animated>
  );
}

function Payload({ model, state, layers, layerSpec, onSelect }: {
  model: VisualModel; state: ViewerState; layers: LayerSpec[];
  layerSpec?: LayerSpec; onSelect?: (id: LayerId) => void;
}) {
  const { visible, opacity } = useLayer(state, 'payload');
  const arch = model.architecture.value;
  const location = model.payloadLocation.value;

  const points = useMemo(() => {
    const r = model.geometry.coreRadius;
    // Placement follows the recorded classification, when there is one.
    if (arch === 'liposome' && location === 'hydrophobic_bilayer') {
      return fibonacciSphere(model.payloadGlyphs, r * 1.03);
    }
    if (arch === 'liposome' && location === 'hydrophilic_core') {
      return interiorPoints(model.payloadGlyphs, r * 0.78);
    }
    return interiorPoints(model.payloadGlyphs, r * 0.85);
  }, [model.payloadGlyphs, model.geometry.coreRadius, arch, location]);

  if (!visible || !state.showPayload || points.length === 0) return null;
  const scale = state.payloadDistributionView ? 1.3 : 1;

  return (
    <Animated targetY={explodedOffset(state, layerSpec, layers)}
              reducedMotion={state.reducedMotion}>
      <Instances limit={points.length}
                 onClick={(e) => { e.stopPropagation(); onSelect?.('payload'); }}>
        {/* Deliberately NOT clipped: clipping the payload with the shell would
            remove exactly what the cutaway and cross-section exist to show. */}
        <icosahedronGeometry args={[0.05, 0]} />
        <meshStandardMaterial color={PALETTE.payload} roughness={0.35}
                              emissive={PALETTE.payload}
                              emissiveIntensity={0.28}
                              transparent={opacity < 1} opacity={opacity} />
        {points.map((p, i) => (
          <Instance key={i}
                    position={[p[0] * scale, p[1] * scale, p[2] * scale]} />
        ))}
      </Instances>
    </Animated>
  );
}

/**
 * A local patch of individual lipids, drawn only at molecular detail.
 *
 * Each lipid is a polar head sphere plus two hydrophobic tail capsules, on
 * both leaflets. Only a patch is drawn: a 100 nm vesicle holds on the order of
 * 10⁵ lipids, so the whole membrane at this detail is not renderable and is
 * never attempted.
 */
function LipidPatch({ model, state, budget, seed, detail, onSelect }: {
  model: VisualModel; state: ViewerState; budget: RenderBudget;
  seed: number; detail: DetailLevel; onSelect?: (id: LayerId) => void;
}) {
  const { visible, opacity } = useLayer(state, 'lipid_bilayer');
  const r = model.geometry.coreRadius;

  // Anchors confined to a cap facing the camera, so the patch reads as a
  // close-up of one region rather than a sparse global scatter.
  const lipids = useMemo(() => {
    const all = fibonacciSphere(budget.surfaceGlyphs * 3, 1) as Vec3[];
    const patch = all.filter((p) => p[2] > 0.55);
    const rng = makeRng(seed + 11);
    return patch.slice(0, budget.surfaceGlyphs).map((dir) => {
      // Slight seeded tilt, so the tails are not perfectly parallel.
      const tilt = (rng() - 0.5) * 0.16;
      return { dir, tilt };
    });
  }, [budget.surfaceGlyphs, seed]);

  if (!visible || detail !== 'molecular' || lipids.length === 0) return null;

  const headR = 0.026;
  const tailLen = 0.075;

  return (
    <group onClick={(e) => { e.stopPropagation(); onSelect?.('lipid_bilayer'); }}>
      {/* Outer leaflet: heads out, tails pointing inward. */}
      <Instances limit={lipids.length}>
        <sphereGeometry args={[headR, 10, 10]} />
        <meshStandardMaterial color="#fbbf24" roughness={0.3}
                              transparent={opacity < 1} opacity={opacity} />
        {lipids.map((l, i) => (
          <Instance key={i} position={[l.dir[0] * (r * 1.09),
                                       l.dir[1] * (r * 1.09),
                                       l.dir[2] * (r * 1.09)]} />
        ))}
      </Instances>
      {/* Inner leaflet heads, facing the aqueous compartment. */}
      <Instances limit={lipids.length}>
        <sphereGeometry args={[headR, 10, 10]} />
        <meshStandardMaterial color="#fcd34d" roughness={0.3}
                              transparent={opacity < 1} opacity={opacity} />
        {lipids.map((l, i) => (
          <Instance key={i} position={[l.dir[0] * (r * 0.9),
                                       l.dir[1] * (r * 0.9),
                                       l.dir[2] * (r * 0.9)]} />
        ))}
      </Instances>
      {/* Hydrophobic tails filling the space between the leaflets. */}
      <Instances limit={lipids.length * 2}>
        <capsuleGeometry args={[0.007, tailLen, 3, 5]} />
        <meshStandardMaterial color="#a8a29e" roughness={0.72}
                              transparent={opacity < 1} opacity={opacity} />
        {lipids.flatMap((l, i) => {
          const d = new THREE.Vector3(...l.dir).normalize();
          const q = new THREE.Quaternion().setFromUnitVectors(
            new THREE.Vector3(0, 1, 0), d);
          const e = new THREE.Euler().setFromQuaternion(q);
          // Two tails per lipid, offset laterally by the seeded tilt.
          return [r * 1.035, r * 0.965].map((rad, k) => (
            <Instance key={`${i}-${k}`}
                      position={[d.x * rad + l.tilt * (k ? 1 : -1) * 0.012,
                                 d.y * rad,
                                 d.z * rad]}
                      rotation={[e.x, e.y, e.z]} />
          ));
        })}
      </Instances>
    </group>
  );
}

/* ---------------------------------------------------------- measurement */

function MeasurementOverlay({ model, state }: {
  model: VisualModel; state: ViewerState;
}) {
  if (!state.showMeasurements) return null;
  const r = model.geometry.outerRadius;
  const cr = model.geometry.coreRadius;
  const d = model.geometry.outerDiameterNm;
  const cd = model.geometry.coreDiameterNm;

  return (
    <group>
      <Line points={[[-r, -r * 1.32, 0], [r, -r * 1.32, 0]]}
            color="#94a3b8" lineWidth={1.5} />
      <Label position={[0, -r * 1.5, 0]}
             text={d !== null ? `Diameter ${d} nm` : 'Diameter: not supplied'}
             visible tone={d === null ? 'assumed' : undefined} />
      {cd !== null && (
        <>
          <Line points={[[-cr, 0, 0], [cr, 0, 0]]}
                color="#c4b5fd" lineWidth={1.5} />
          <Label position={[0, cr * 0.22, 0]}
                 text={`Core ${cd.toFixed(1)} nm`} visible />
        </>
      )}
    </group>
  );
}

/* ---------------------------------------------------------------- scene */

function ClippingEnabler() {
  const { gl } = useThree();
  useEffect(() => { gl.localClippingEnabled = true; }, [gl]);
  return null;
}

function SceneContents({ model, layers, state, detail, budget, seed,
                        onSelect }: ParticleSceneProps) {
  const clipping = useClipping(state);
  const arch = model.architecture.value;
  const { outerRadius, coreRadius } = model.geometry;
  const byId = (id: LayerId) => layers.find((l) => l.id === id);

  const morphology = morphologyFor(arch);

  // Steric spacing drops anchors that would visibly interpenetrate. It is a
  // crude overlap check and makes no claim about real molecular packing.
  const ligandPoints = useMemo(() => applyStericSpacing(
    fibonacciSphere(Math.min(model.ligandGlyphs, budget.surfaceGlyphs),
                    outerRadius * 1.02) as Vec3[], 0.055),
    [model.ligandGlyphs, budget.surfaceGlyphs, outerRadius]);

  const pegPoints = useMemo(() => applyStericSpacing(
    fibonacciSphere(budget.surfaceGlyphs, outerRadius * 1.01) as Vec3[], 0.03),
    [budget.surfaceGlyphs, outerRadius]);

  const groupPoints = useMemo(
    () => fibonacciSphere(
      Math.min(24, model.functionalGroups.value.length * 8,
               budget.surfaceGlyphs),
      outerRadius * 1.03) as Vec3[],
    [model.functionalGroups.value.length, budget.surfaceGlyphs, outerRadius]);

  // Chain length grows with detail: a flat brush at overview, a resolvable
  // polymer at molecular detail.
  const chainLength = detail === 'molecular' ? 0.34
    : detail === 'structural' ? 0.22 : 0.16;

  return (
    <>
      <ClippingEnabler />
      <PerspectiveCamera makeDefault position={[0, 0.7, 4.4]} fov={38} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[4, 6, 4]} intensity={1.15} />
      <directionalLight position={[-5, -2, -3]} intensity={0.4} />
      <Suspense fallback={null}>
        <ambientLight intensity={0.75} />
      </Suspense>

      <Spinner state={state}>
        {/* --- interior ------------------------------------------------ */}
        {arch === 'liposome' ? (
          <>
            <ShellLike id="internal_compartment" radius={coreRadius * 0.92}
                       colour={PALETTE.internal_compartment!} state={state}
                       layers={layers} layerSpec={byId('internal_compartment')}
                       clipping={clipping} onSelect={onSelect}
                       label="Aqueous interior" />
            {state.showLabels && detail !== 'molecular' && (
              // Offset so it does not sit on top of the interior label.
              <Label position={[0, coreRadius * 1.45, 0]} text="Lipid bilayer"
                     visible />
            )}
            <ShellLike id="lipid_bilayer" radius={coreRadius}
                       colour={PALETTE.lipid_bilayer!} state={state}
                       layers={layers} layerSpec={byId('lipid_bilayer')}
                       clipping={clipping} onSelect={onSelect}
            />
            <LipidPatch model={model} state={state} budget={budget}
                        seed={seed} detail={detail} onSelect={onSelect} />
          </>
        ) : (
          <ShellLike id="core" radius={coreRadius} colour={PALETTE.core!}
                     state={state} layers={layers} layerSpec={byId('core')}
                     clipping={clipping} onSelect={onSelect}
                     segments={budget.sphereSegments}
                     finish={morphology.finish}
                     label={arch === 'polymeric' ? 'Polymer matrix' : 'Core'} />
        )}

        {/* --- payload, between interior and shell ---------------------- */}
        <Payload model={model} state={state} layers={layers}
                 layerSpec={byId('payload')} onSelect={onSelect} />

        {/* --- outer leaflet of the bilayer, drawn after the payload ---- */}
        {arch === 'liposome' && (
          <ShellLike id="lipid_bilayer" radius={coreRadius * 1.07}
                     colour={PALETTE.lipid_bilayer!} state={state}
                     layers={layers} layerSpec={byId('lipid_bilayer')}
                     clipping={clipping} onSelect={onSelect} />
        )}

        {/* --- shell ---------------------------------------------------- */}
        {byId('shell') && (
          <ShellLike id="shell" radius={outerRadius} colour={PALETTE.shell!}
                     state={state} layers={layers} layerSpec={byId('shell')}
                     clipping={clipping} onSelect={onSelect} label="Shell" />
        )}

        {/* --- surface -------------------------------------------------- */}
        {byId('peg') && (
          <FlexibleChains id="peg" anchors={pegPoints} colour={PALETTE.peg!}
                          state={state} layers={layers} layerSpec={byId('peg')}
                          segments={budget.chainSegments}
                          length={chainLength} seed={seed}
                          onSelect={onSelect} />
        )}
        {byId('coating') && (
          <FlexibleChains id="coating" anchors={pegPoints}
                          colour={PALETTE.coating!} state={state}
                          layers={layers} layerSpec={byId('coating')}
                          segments={Math.max(1, budget.chainSegments - 1)}
                          length={chainLength * 0.8} seed={seed + 1}
                          onSelect={onSelect} />
        )}
        {byId('ligands') && state.showLigands && (
          // Anchor -> linker -> terminal ligand, so the organisation is
          // visible rather than a bare spike.
          <FlexibleChains id="ligands" anchors={ligandPoints}
                          colour={PALETTE.ligands!} state={state}
                          layers={layers} layerSpec={byId('ligands')}
                          segments={Math.max(2, budget.chainSegments)}
                          length={chainLength * 1.15} seed={seed + 2}
                          tipColour="#10b981" onSelect={onSelect} />
        )}
        {byId('functional_groups') && (
          <SurfaceGlyphs id="functional_groups" points={groupPoints}
                         colour={PALETTE.functional_groups!}
                         geometry={<octahedronGeometry args={[0.045, 0]} />}
                         state={state} layers={layers}
                         layerSpec={byId('functional_groups')}
                         onSelect={onSelect} />
        )}

        {/* --- charge overlay ------------------------------------------- */}
        {byId('charge_field') && state.layers.charge_field?.visible
          && model.chargeMv !== null && (
          <mesh onClick={(e) => {
            e.stopPropagation(); onSelect?.('charge_field');
          }}>
            <sphereGeometry args={[outerRadius * 1.22, 48, 48]} />
            <meshBasicMaterial color={chargeBand(model.chargeMv).colour}
                               transparent
                               opacity={state.layers.charge_field?.opacity ?? 0.16}
                               side={THREE.BackSide} />
          </mesh>
        )}

        <MeasurementOverlay model={model} state={state} />

        {state.mode === 'exploded' && state.showLabels && (
          <Label position={[0, -outerRadius * 2.4, 0]}
                 text={EXPLODED_SPACING_NOTE} visible tone="assumed" />
        )}
      </Spinner>

      <OrbitControls makeDefault enablePan enableZoom enableRotate
                     minDistance={1.6} maxDistance={16} />
    </>
  );
}

export default function ParticleScene(props: ParticleSceneProps) {
  const { state, onCanvasReady } = props;
  const background = state.background === 'light' ? '#eef2f7'
    : state.background === 'dark' ? '#0b1220' : undefined;

  return (
    <Canvas
      dpr={[1, 2]}
      gl={{
        antialias: true,
        // Required so the canvas can be read back for a PNG export.
        preserveDrawingBuffer: true,
        alpha: state.background === 'transparent',
        localClippingEnabled: true,
      }}
      onCreated={({ gl }) => {
        gl.localClippingEnabled = true;
        onCanvasReady?.(gl.domElement);
      }}
      style={{ background: background ?? 'transparent' }}
      data-testid="particle-canvas"
    >
      <SceneContents {...props} />
    </Canvas>
  );
}
