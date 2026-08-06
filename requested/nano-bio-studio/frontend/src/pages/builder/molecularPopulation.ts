/**
 * Molecular population estimation.
 *
 * The problem this solves
 * -----------------------
 * The viewer draws 96 PEG capsules, up to 64 ligand cones and up to 48 payload
 * markers. Those numbers look like populations. They are not: the PEG count was
 * a hard-coded constant, and the others are linear rescalings of a percentage.
 * A viewer that shows objects without saying what they represent invites the
 * reader to count them.
 *
 * So every repeated component now carries an explicit estimate with two
 * separate numbers — the **estimated physical count** and the **rendered
 * count** — plus the ratio between them, the formula, the inputs used, and the
 * inputs that were missing.
 *
 * The default answer is "cannot calculate"
 * ----------------------------------------
 * The design schema records a particle diameter, a charge, an encapsulation
 * percentage and a handful of formulation fields. It records no area per lipid,
 * no molecular weight, no drug loading and no definition of what its "ligand
 * density (%)" means. Almost every population is therefore **not calculable**,
 * and this module says so rather than producing a number.
 *
 * `MolecularAssumptions` exists so a researcher can supply the missing physical
 * constants explicitly. Values entered there are the researcher's own inputs
 * and are labelled as such — they are never defaults.
 */

import type { Architecture, VisualModel } from './particleModel';

/* ========================================================================= */
/* Component vocabulary                                                      */
/* ========================================================================= */

export type PopulationComponent =
  | 'lipids'
  | 'peg_chains'
  | 'ligands'
  | 'functional_groups'
  | 'payload_molecules'
  | 'pore_bound_molecules'
  | 'surface_bound_drug'
  | 'coating_units';

export const COMPONENT_LABEL: Record<PopulationComponent, string> = {
  lipids: 'Lipid molecules',
  peg_chains: 'PEG chains',
  ligands: 'Targeting ligands',
  functional_groups: 'Functional groups',
  payload_molecules: 'Payload molecules',
  pore_bound_molecules: 'Pore-bound molecules',
  surface_bound_drug: 'Surface-bound drug',
  coating_units: 'Coating units',
};

/** Why a population could not be computed. */
export type BlockReason =
  | 'missing_inputs'
  | 'ambiguous_definition'
  | 'not_applicable';

export interface PopulationEstimate {
  component: PopulationComponent;
  label: string;

  /** The estimated number of real molecules. Null when not calculable. */
  physicalCount: number | null;
  /** Uncertainty range, when the method supports one. */
  physicalRange?: [number, number];

  /** How many objects the scene actually draws. Always known. */
  renderedCount: number;

  /**
   * How many physical units one rendered object stands for. Null whenever the
   * physical count is unknown — a ratio to an unknown quantity is meaningless.
   */
  representationRatio: number | null;

  /** Human-readable method name. */
  method: string;
  /** The formula, when one was applied. */
  formula?: string;
  /** Inputs the method requires. */
  requiredInputs: string[];
  /** Inputs that were present, with their values. */
  usedInputs: Record<string, string>;
  /** Required inputs that were absent. Empty when calculable. */
  missingInputs: string[];

  provenance: 'calculated' | 'researcher_supplied' | 'not_calculated';
  blockReason?: BlockReason;
  /** Plain statement shown to the user. */
  note: string;
}

/* ========================================================================= */
/* Researcher-supplied physical constants                                    */
/* ========================================================================= */

/**
 * Physical constants the design schema does not record.
 *
 * Every field is optional and every field is **the researcher's own input**.
 * None has a default: a default here would silently manufacture a molecular
 * count. Units are fixed and stated in the field name.
 */
export interface MolecularAssumptions {
  /** Mean area occupied by one lipid in one leaflet, in nm². */
  areaPerLipidNm2?: number;
  /** Bilayer thickness, in nm. */
  bilayerThicknessNm?: number;
  /** Cross-sectional footprint of one grafted chain or ligand, in nm². */
  molecularFootprintNm2?: number;
  /** Payload molecular weight, in g/mol. */
  payloadMolarMassGPerMol?: number;
  /** Mass of payload per particle, in attograms (1e-18 g). */
  payloadMassPerParticleAg?: number;
  /** Ligand surface density, in molecules per nm². Unambiguous. */
  ligandsPerNm2?: number;
  /**
   * What the design's percentage "ligand density" means. Until this is
   * recorded, the percentage cannot be converted to a count.
   */
  ligandDensityDefinition?: 'surface_coverage_fraction' | 'molar_percent'
    | 'mass_percent' | 'per_area';
  /** Total accessible pore volume per particle, in nm³. */
  poreVolumeNm3?: number;
  /** Molecular volume of one payload molecule, in nm³. */
  payloadMolecularVolumeNm3?: number;
}

export const ASSUMPTION_FIELDS: ReadonlyArray<{
  key: keyof MolecularAssumptions; label: string; unit: string;
  help: string;
}> = [
  { key: 'areaPerLipidNm2', label: 'Area per lipid', unit: 'nm²',
    help: 'Mean area one lipid occupies in one leaflet. Required to estimate '
      + 'a lipid population.' },
  { key: 'bilayerThicknessNm', label: 'Bilayer thickness', unit: 'nm',
    help: 'Used to derive the inner-leaflet radius.' },
  { key: 'molecularFootprintNm2', label: 'Molecular footprint', unit: 'nm²',
    help: 'Cross-sectional area of one grafted chain or ligand.' },
  { key: 'ligandsPerNm2', label: 'Ligand surface density', unit: 'nm⁻²',
    help: 'Ligands per square nanometre. Unambiguous, unlike a percentage.' },
  { key: 'payloadMolarMassGPerMol', label: 'Payload molar mass', unit: 'g/mol',
    help: 'Required to convert a payload mass into a molecule count.' },
  { key: 'payloadMassPerParticleAg', label: 'Payload mass per particle',
    unit: 'ag', help: 'Attograms of payload carried by one particle.' },
  { key: 'poreVolumeNm3', label: 'Accessible pore volume', unit: 'nm³',
    help: 'Total pore volume available per particle.' },
  { key: 'payloadMolecularVolumeNm3', label: 'Payload molecular volume',
    unit: 'nm³', help: 'Volume of one payload molecule.' },
];

export const AVOGADRO = 6.02214076e23;

/* ========================================================================= */
/* Helpers                                                                   */
/* ========================================================================= */

function sphereAreaNm2(diameterNm: number): number {
  return 4 * Math.PI * (diameterNm / 2) ** 2;
}

function notCalculated(
  component: PopulationComponent, renderedCount: number,
  method: string, requiredInputs: string[], missingInputs: string[],
  note: string, blockReason: BlockReason = 'missing_inputs',
): PopulationEstimate {
  return {
    component, label: COMPONENT_LABEL[component],
    physicalCount: null, renderedCount, representationRatio: null,
    method, requiredInputs, usedInputs: {}, missingInputs,
    provenance: 'not_calculated', blockReason, note,
  };
}

const CANNOT_CALCULATE = 'Cannot calculate from current inputs.';

/* ========================================================================= */
/* Estimators                                                                */
/* ========================================================================= */

/**
 * Lipids in a bilayer vesicle.
 *
 *   N = (A_outer + A_inner) / area_per_lipid
 *   A_outer = 4π(d/2)²
 *   A_inner = 4π((d/2) − t)²
 *
 * Both leaflets are counted, which is why the inner radius is reduced by the
 * bilayer thickness. Requires an area per lipid, which the design does not
 * record.
 */
export function estimateLipids(
  model: VisualModel, a: MolecularAssumptions, renderedCount: number,
): PopulationEstimate {
  const required = ['Particle diameter', 'Bilayer thickness',
                    'Area per lipid'];
  if (model.architecture.value !== 'liposome') {
    return notCalculated('lipids', renderedCount,
      'Bilayer leaflet area / area per lipid', required,
      [], 'A lipid population applies to a bilayer vesicle. The selected '
      + 'architecture is not one.', 'not_applicable');
  }

  const d = model.geometry.outerDiameterNm;
  const missing: string[] = [];
  if (d === null) missing.push('Particle diameter');
  if (!a.bilayerThicknessNm) missing.push('Bilayer thickness');
  if (!a.areaPerLipidNm2) missing.push('Area per lipid');
  if (missing.length > 0 || d === null) {
    return notCalculated('lipids', renderedCount,
      'Bilayer leaflet area / area per lipid', required, missing,
      CANNOT_CALCULATE + ' A lipid count needs the bilayer thickness and the '
      + 'mean area per lipid; neither is recorded by the design.');
  }

  const t = a.bilayerThicknessNm!;
  const outerR = d / 2;
  const innerR = outerR - t;
  if (innerR <= 0) {
    return notCalculated('lipids', renderedCount,
      'Bilayer leaflet area / area per lipid', required, [],
      `A bilayer ${t} nm thick does not fit inside a ${d} nm vesicle. No `
      + 'population is estimated.', 'missing_inputs');
  }

  const areaOuter = 4 * Math.PI * outerR ** 2;
  const areaInner = 4 * Math.PI * innerR ** 2;
  const n = Math.round((areaOuter + areaInner) / a.areaPerLipidNm2!);

  return {
    component: 'lipids', label: COMPONENT_LABEL.lipids,
    physicalCount: n,
    // Area per lipid is itself uncertain; +/-10% is carried through so the
    // number is not read as exact.
    physicalRange: [Math.round(n / 1.1), Math.round(n * 1.1)],
    renderedCount,
    representationRatio: renderedCount > 0 ? n / renderedCount : null,
    method: 'Sum of leaflet areas divided by the area per lipid',
    formula: 'N = [4π(d/2)² + 4π((d/2) − t)²] / a_lipid',
    requiredInputs: required,
    usedInputs: {
      'Particle diameter (d)': `${d} nm`,
      'Bilayer thickness (t)': `${t} nm`,
      'Area per lipid (a_lipid)': `${a.areaPerLipidNm2} nm²`,
    },
    missingInputs: [],
    provenance: 'researcher_supplied',
    note:
      'Estimated from geometry and the area per lipid you supplied. It assumes '
      + 'a smooth spherical bilayer with uniform packing and no pores or '
      + 'defects. The range reflects ±10% on the area per lipid alone and does '
      + 'not include shape or polydispersity effects.',
  };
}

/**
 * Grafted chains or ligands on the outer surface.
 *
 *   N = A_surface × σ         (when a per-area density is given)
 *   N = A_surface / footprint (when a footprint and full coverage are given)
 *
 * A percentage "ligand density" is deliberately refused: it could mean surface
 * coverage, molar percent, mass percent or molecules per area, and those give
 * different answers.
 */
export function estimateSurfaceGrafted(
  component: 'ligands' | 'peg_chains',
  model: VisualModel, a: MolecularAssumptions, renderedCount: number,
  densityPercent: number | null,
): PopulationEstimate {
  // `model` supplies the diameter; `a` supplies the molecular constants.
  const required = ['Particle diameter',
                    'Ligand surface density (nm⁻²) or molecular footprint '
                    + '(nm²) with a defined coverage'];
  const d = model.geometry.outerDiameterNm;

  if (d === null) {
    return notCalculated(component, renderedCount,
      'Surface area × surface density', required, ['Particle diameter'],
      CANNOT_CALCULATE);
  }
  const area = sphereAreaNm2(d);

  // Unambiguous path: molecules per nm².
  if (a.ligandsPerNm2) {
    const n = Math.round(area * a.ligandsPerNm2);
    return {
      component, label: COMPONENT_LABEL[component],
      physicalCount: n, renderedCount,
      representationRatio: renderedCount > 0 ? n / renderedCount : null,
      method: 'Accessible surface area × surface density',
      formula: 'N = 4π(d/2)² × σ',
      requiredInputs: required,
      usedInputs: {
        'Particle diameter (d)': `${d} nm`,
        'Surface area (A)': `${area.toFixed(0)} nm²`,
        'Surface density (σ)': `${a.ligandsPerNm2} nm⁻²`,
      },
      missingInputs: [],
      provenance: 'researcher_supplied',
      note:
        'Estimated from the outer surface area and the surface density you '
        + 'supplied. It assumes a smooth sphere and uniform grafting.',
    };
  }

  // Footprint path, only with an explicit coverage definition.
  if (a.molecularFootprintNm2
      && a.ligandDensityDefinition === 'surface_coverage_fraction'
      && densityPercent !== null) {
    const n = Math.round((area * (densityPercent / 100))
                         / a.molecularFootprintNm2);
    return {
      component, label: COMPONENT_LABEL[component],
      physicalCount: n, renderedCount,
      representationRatio: renderedCount > 0 ? n / renderedCount : null,
      method: 'Covered surface area / molecular footprint',
      formula: 'N = [4π(d/2)² × coverage] / footprint',
      requiredInputs: required,
      usedInputs: {
        'Particle diameter (d)': `${d} nm`,
        'Surface area (A)': `${area.toFixed(0)} nm²`,
        'Coverage': `${densityPercent}% (defined as surface coverage)`,
        'Footprint': `${a.molecularFootprintNm2} nm²`,
      },
      missingInputs: [],
      provenance: 'researcher_supplied',
      note:
        'Estimated from the covered surface area and the molecular footprint '
        + 'you supplied, using your recorded definition of the percentage as '
        + 'fractional surface coverage.',
    };
  }

  // Ambiguity is reported as ambiguity, not resolved by assumption.
  if (densityPercent !== null && !a.ligandDensityDefinition) {
    return notCalculated(component, renderedCount,
      'Surface area × surface density', required,
      ['Definition of the percentage', 'Molecular footprint or per-area density'],
      `A ligand density of ${densityPercent}% is ambiguous: it could mean `
      + 'fractional surface coverage, molar percent, mass percent, or '
      + 'molecules per unit area. These give different counts, so no '
      + 'population is estimated until the definition is recorded.',
      'ambiguous_definition');
  }

  return notCalculated(component, renderedCount,
    'Surface area × surface density', required,
    ['Ligand surface density (nm⁻²) or molecular footprint with a defined '
     + 'coverage'],
    CANNOT_CALCULATE + ' The design records no surface density in molecules '
    + 'per unit area and no molecular footprint.');
}

/**
 * Payload molecules per particle.
 *
 *   N = (mass_per_particle / M) × N_A
 *
 * Encapsulation efficiency alone cannot give this: it is the fraction of the
 * offered drug that ended up encapsulated, which says nothing about how much
 * drug was offered or what it weighs.
 */
export function estimatePayload(
  _model: VisualModel, a: MolecularAssumptions, renderedCount: number,
): PopulationEstimate {
  // The particle geometry does not enter this calculation: the molecule count
  // follows from the mass carried and the molar mass alone.
  const required = ['Payload mass per particle', 'Payload molar mass'];
  const missing: string[] = [];
  if (!a.payloadMassPerParticleAg) missing.push('Payload mass per particle');
  if (!a.payloadMolarMassGPerMol) missing.push('Payload molar mass');

  if (missing.length > 0) {
    return notCalculated('payload_molecules', renderedCount,
      'Mass per particle / molar mass × Avogadro', required, missing,
      CANNOT_CALCULATE + ' Encapsulation efficiency is the fraction of offered '
      + 'drug that was encapsulated. It does not give the mass carried by one '
      + 'particle, and without that mass and the molar mass no molecule count '
      + 'can be derived.');
  }

  // attograms -> grams
  const massG = a.payloadMassPerParticleAg! * 1e-18;
  const n = Math.round((massG / a.payloadMolarMassGPerMol!) * AVOGADRO);

  return {
    component: 'payload_molecules', label: COMPONENT_LABEL.payload_molecules,
    physicalCount: n, renderedCount,
    representationRatio: renderedCount > 0 ? n / renderedCount : null,
    method: 'Mass per particle converted to moles, then to molecules',
    formula: 'N = (m_particle / M) × N_A',
    requiredInputs: required,
    usedInputs: {
      'Mass per particle (m)': `${a.payloadMassPerParticleAg} ag`,
      'Molar mass (M)': `${a.payloadMolarMassGPerMol} g/mol`,
      'Avogadro (N_A)': `${AVOGADRO.toExponential(4)} mol⁻¹`,
    },
    missingInputs: [],
    provenance: 'researcher_supplied',
    note:
      'Estimated from the mass per particle and molar mass you supplied. It '
      + 'describes one particle of the stated size and does not account for '
      + 'polydispersity.',
  };
}

/**
 * Molecules that fit in the accessible pore volume of a mesoporous particle.
 *
 *   N_max = V_pore / v_molecule
 *
 * An upper bound on capacity, not a loading. It is reported as such.
 */
export function estimatePoreBound(
  model: VisualModel, a: MolecularAssumptions, renderedCount: number,
): PopulationEstimate {
  const required = ['Accessible pore volume', 'Payload molecular volume'];
  if (model.architecture.value !== 'silica') {
    return notCalculated('pore_bound_molecules', renderedCount,
      'Pore volume / molecular volume', required, [],
      'Pore loading applies to a mesoporous architecture. The selected '
      + 'architecture is not one.', 'not_applicable');
  }
  const missing: string[] = [];
  if (!a.poreVolumeNm3) missing.push('Accessible pore volume');
  if (!a.payloadMolecularVolumeNm3) missing.push('Payload molecular volume');
  if (missing.length > 0) {
    return notCalculated('pore_bound_molecules', renderedCount,
      'Pore volume / molecular volume', required, missing,
      CANNOT_CALCULATE + ' Porosity is not recorded by the design.');
  }

  const n = Math.floor(a.poreVolumeNm3! / a.payloadMolecularVolumeNm3!);
  return {
    component: 'pore_bound_molecules',
    label: COMPONENT_LABEL.pore_bound_molecules,
    physicalCount: n, renderedCount,
    representationRatio: renderedCount > 0 ? n / renderedCount : null,
    method: 'Accessible pore volume / molecular volume (capacity bound)',
    formula: 'N_max = V_pore / v_molecule',
    requiredInputs: required,
    usedInputs: {
      'Pore volume (V)': `${a.poreVolumeNm3} nm³`,
      'Molecular volume (v)': `${a.payloadMolecularVolumeNm3} nm³`,
    },
    missingInputs: [],
    provenance: 'researcher_supplied',
    note:
      'This is a geometric CAPACITY bound — the most that could fit if pores '
      + 'were filled completely with no packing inefficiency. It is not a '
      + 'measured or predicted loading.',
  };
}

/* ========================================================================= */
/* Assembly                                                                  */
/* ========================================================================= */

export interface RenderedCounts {
  lipids: number;
  peg_chains: number;
  ligands: number;
  functional_groups: number;
  payload_molecules: number;
  pore_bound_molecules: number;
  surface_bound_drug: number;
  coating_units: number;
}

export function buildPopulationReport(
  model: VisualModel,
  assumptions: MolecularAssumptions,
  rendered: RenderedCounts,
  ligandDensityPercent: number | null,
): PopulationEstimate[] {
  const report: PopulationEstimate[] = [];
  const arch: Architecture = model.architecture.value;

  if (arch === 'liposome') {
    report.push(estimateLipids(model, assumptions, rendered.lipids));
  }
  if (rendered.peg_chains > 0) {
    report.push(estimateSurfaceGrafted('peg_chains', model, assumptions,
                                       rendered.peg_chains, null));
  }
  if (rendered.ligands > 0 || ligandDensityPercent !== null) {
    report.push(estimateSurfaceGrafted('ligands', model, assumptions,
                                       rendered.ligands, ligandDensityPercent));
  }
  if (rendered.payload_molecules > 0) {
    report.push(estimatePayload(model, assumptions,
                                rendered.payload_molecules));
  }
  if (arch === 'silica') {
    report.push(estimatePoreBound(model, assumptions,
                                  rendered.pore_bound_molecules));
  }
  if (rendered.functional_groups > 0) {
    report.push(notCalculated('functional_groups', rendered.functional_groups,
      'Surface area × surface density',
      ['Particle diameter', 'Group surface density'],
      ['Group surface density'],
      CANNOT_CALCULATE + ' The design records which functional groups are '
      + 'present, not how many of each.'));
  }

  return report;
}

/** Format a large count readably without implying false precision. */
export function formatCount(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1e6) return `${(n / 1e3).toFixed(1)} thousand`;
  if (n < 1e9) return `${(n / 1e6).toFixed(1)} million`;
  return n.toExponential(2);
}

export const POPULATION_DISCLAIMER =
  'Visual representation — geometry and molecular population may be '
  + 'simplified. Rendered objects do not necessarily correspond one-to-one '
  + 'with physical molecules.';
