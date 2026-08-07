/**
 * Single source of truth for the application menu, module status and which menu
 * entry owns a given route.
 *
 * `status` governs what the UI is permitted to claim about a module. Only
 * `operational` and `limited_prototype` modules may render calculated output.
 * Everything else renders an honest placeholder: no scores, charts, projects,
 * activity or AI output.
 *
 * **Navigation access does not imply scientific availability.** A module can be
 * reachable from the menu and still say, on its own page, that its engine is not
 * connected. That is deliberate: hiding an unbuilt module would make the gap
 * invisible rather than honest.
 */

import type { UserRole } from '../api/auth';

export type ModuleStatus =
  | 'operational'
  | 'limited_prototype'
  | 'calibration_required'
  | 'migration_in_progress'
  | 'not_operational';

/**
 * The three ways a study can begin. Recorded on every study so a patient
 * assessment, a research design and a demonstration stay distinguishable
 * wherever studies are listed.
 */
export type StudyPathway =
  | 'patient_assessment'
  | 'research_design'
  | 'demo_scenario';

export interface NavItem {
  key: string;
  label: string;
  path: string;
  icon: string;
  status: ModuleStatus;
  /** One-line statement of what the module provides. */
  summary: string;
  /** Ordered outline of the workflow the module will offer. */
  workflow?: readonly string[];
  /** Key of an operational module a user can use instead. */
  relatedKey?: string;
  roles?: readonly UserRole[];
}

export interface NavGroup {
  id: string;
  label: string;
  items: readonly NavItem[];
}

export const STATUS_META: Record<ModuleStatus, {
  label: string; tone: 'success' | 'accent' | 'warn' | 'info' | 'neutral';
}> = {
  operational: { label: 'Operational', tone: 'success' },
  limited_prototype: { label: 'Limited prototype', tone: 'accent' },
  calibration_required: { label: 'Calibration required', tone: 'info' },
  migration_in_progress: { label: 'Migration in progress', tone: 'warn' },
  not_operational: { label: 'Not yet operational', tone: 'neutral' },
};

export const NAV_GROUPS: readonly NavGroup[] = [
  /* ------------------------------------------------------------- START */
  {
    id: 'start',
    label: 'Start',
    items: [
      {
        key: 'home',
        label: 'Home',
        path: '/home',
        icon: 'grid',
        status: 'operational',
        summary: 'Platform status, module availability and validation status.',
      },
      {
        key: 'start-study',
        label: 'Start New Study',
        path: '/start',
        icon: 'hexagon',
        status: 'operational',
        summary:
          'Begin a study by one of three pathways: from a de-identified '
          + 'medical report, from a research question, or from a synthetic '
          + 'demonstration scenario.',
      },
      {
        key: 'demo',
        label: 'Demo Workspace',
        path: '/demo',
        icon: 'flask',
        status: 'operational',
        summary:
          'Ready-made scenarios with synthetic inputs. Scenarios supply inputs '
          + 'only — every result is calculated at run time by the genuine '
          + 'engines.',
      },
    ],
  },

  /* --------------------------------------------------------- WORKSPACE */
  {
    id: 'workspace',
    label: 'Workspace',
    items: [
      {
        key: 'studies',
        label: 'My Studies',
        path: '/studies',
        icon: 'list',
        status: 'operational',
        summary:
          'Every study you have saved, across all three pathways, with its '
          + 'origin, status and the engines that ran.',
      },
      {
        key: 'patient-assessments',
        label: 'Patient Assessments',
        path: '/patient-assessments',
        icon: 'document',
        status: 'limited_prototype',
        summary:
          'Studies begun from a de-identified medical report. Upload, '
          + 'extraction, review and confirmation are operational; the '
          + 'extractor itself is rule-based and unvalidated.',
        relatedKey: 'start-study',
      },
      {
        key: 'research-designs',
        label: 'Research Designs',
        path: '/research-designs',
        icon: 'hexagon',
        status: 'operational',
        summary:
          'Studies begun from a research question rather than an individual '
          + 'report.',
        relatedKey: 'start-study',
      },
      {
        key: 'history',
        label: 'Simulation History',
        path: '/history',
        icon: 'clock',
        status: 'operational',
        summary:
          'Server-stored record of past runs, including the exact inputs, the '
          + 'engine versions used, and which engines did not run.',
      },
      {
        key: 'compare',
        label: 'Compare Results',
        path: '/compare',
        icon: 'compare',
        status: 'operational',
        summary:
          'Side-by-side comparison of genuine stored studies, aligned field by '
          + 'field. No combined ranking is produced: no approved formula exists '
          + 'for merging these measures.',
        relatedKey: 'history',
      },
      {
        key: 'projects',
        label: 'Projects',
        path: '/projects',
        icon: 'folder',
        status: 'operational',
        summary:
          'Server-stored groupings of studies. Deleting a project never deletes '
          + 'its calculated studies.',
      },
      {
        key: 'reports',
        label: 'Reports',
        path: '/reports',
        icon: 'document',
        status: 'limited_prototype',
        summary:
          'Downloadable reports generated from a stored study, listing inputs, '
          + 'engines run and not run, model versions, warnings and limitations. '
          + 'Plain text only — typeset PDF export is not built.',
        relatedKey: 'history',
      },
    ],
  },

  /* -------------------------------------------------- SCIENTIFIC TOOLS */
  {
    id: 'tools',
    label: 'Scientific Tools',
    items: [
      {
        key: 'disease-biomarker',
        label: 'Disease & Biomarker Assessment',
        path: '/workflow/disease',
        icon: 'flask',
        status: 'limited_prototype',
        summary:
          'Disease and therapeutic selection is operational and drives the '
          + 'study context. Biomarker-driven assessment is NOT: the assessment '
          + 'engines have disease profiles for only two indications and are not '
          + 'connected.',
        workflow: [
          'Select indication, subtype and therapeutic agent',
          'Record biomarker findings from a report, where available',
          'Biomarker-driven assessment — not connected',
        ],
        relatedKey: 'start-study',
      },
      {
        key: 'nanoparticle-design',
        label: 'Nanoparticle Design',
        path: '/workflow/design',
        icon: 'hexagon',
        status: 'operational',
        summary:
          'Formulation parameters feeding the canonical design impact score '
          + '(delivery, toxicity, cost).',
      },
      {
        key: 'targeting-ligands',
        label: 'Targeting & Ligands',
        // Its own route. Previously this pointed at /workflow/design, which
        // made Targeting & Ligands and Nanoparticle Design indistinguishable
        // to anything resolving a route to a menu entry — and impossible to
        // sequence as two steps of a pathway.
        path: '/workflow/targeting',
        icon: 'atom',
        status: 'limited_prototype',
        summary:
          'Ligand, ligand density and receptor-binding inputs feed the '
          + 'targeting component of the design score. A dedicated '
          + 'ligand-assessment engine is not connected, and the passive '
          + 'targeting baseline is an uncalibrated constant.',
        relatedKey: 'nanoparticle-design',
      },
      {
        key: 'pk-simulation',
        label: 'Pharmacokinetic Simulation',
        path: '/workflow/review',
        icon: 'play',
        status: 'operational',
        summary:
          'The migrated two-compartment model. Produces concentration–time '
          + 'profiles, AUC, peak amount and a nullable half-life. Produces no '
          + 'clearance: the model has no volume term.',
      },
      {
        key: 'visualisation',
        label: 'Nanoparticle 3D Builder',
        path: '/builder',
        icon: 'atom',
        status: 'limited_prototype',
        summary:
          'Interactive three-dimensional model of the current formulation. '
          + 'Renders the supplied design values and labels every unrecorded '
          + 'structural property as an illustrative assumption. It is a '
          + 'visualisation, not microscopy, and predicts nothing.',
        relatedKey: 'nanoparticle-design',
      },
      {
        key: 'protocol',
        label: 'Protocol Generator',
        path: '/protocol',
        icon: 'document',
        status: 'migration_in_progress',
        summary:
          'Ten-section wet-lab synthesis and characterisation protocol. The '
          + 'legacy generator exists and is deterministic, but is not migrated '
          + 'and needs formulation fields this workflow does not yet collect.',
        workflow: [
          'Load a formulation',
          'Select protocol scope',
          'Generate the synthesis and characterisation sections',
          'Export for laboratory use',
        ],
        relatedKey: 'nanoparticle-design',
      },
      {
        key: 'experimental-planning',
        label: 'Experimental Planning',
        path: '/experimental-planning',
        icon: 'list',
        status: 'not_operational',
        summary:
          'Plan wet-lab experiments against a design, with success criteria '
          + 'linked to calculated predictions.',
        relatedKey: 'protocol',
      },
    ],
  },

  /* ------------------------------------------------------ INTELLIGENCE */
  {
    id: 'intelligence',
    label: 'Intelligence',
    items: [
      {
        key: 'ai-co-designer',
        label: 'AI Co-Designer',
        path: '/ai-co-designer',
        icon: 'sparkle',
        status: 'not_operational',
        summary:
          'Multi-objective optimisation of formulation parameters. The '
          + 'optimiser is genuine but currently optimises a placeholder '
          + 'objective function, so no candidate it produces is traceable to a '
          + 'real calculation.',
        workflow: [
          'Define objectives, weights and constraints',
          'Run a real optimisation with a recorded seed',
          'Review the candidate set and trade-off front',
          'Inspect why each candidate was proposed',
        ],
        relatedKey: 'nanoparticle-design',
      },
      {
        key: 'ml-training',
        label: 'ML Training',
        path: '/ml-training',
        icon: 'grid',
        status: 'limited_prototype',
        summary:
          'Genuine trained toxicity models exist with recorded metrics. No '
          + 'uptake or particle-size model exists, and the legacy code silently '
          + 'substituted heuristics — so no ML prediction is served.',
        relatedKey: 'evidence',
      },
      {
        key: 'scientific-readiness',
        label: 'Scientific Readiness',
        path: '/scientific-readiness',
        icon: 'flask',
        status: 'operational',
        summary:
          'Per-study assessment of whether the recorded data is sufficient '
          + 'and self-consistent for structural, formulation, targeting, '
          + 'pharmacokinetic, safety and animation work. Six areas, assessed '
          + 'independently — there is no combined score.',
        relatedKey: 'evidence',
      },
      {
        key: 'validation-registry',
        label: 'Validation Registry',
        path: '/validation',
        icon: 'flask',
        status: 'operational',
        summary:
          'In-vitro experiments recorded against an exact candidate version, '
          + 'reviewed and approved independently. The only path by which a '
          + 'scientific purpose reaches E3 — and only that purpose, on that '
          + 'candidate version.',
      },
      {
        key: 'evidence',
        label: 'Evidence & Validation',
        path: '/evidence',
        icon: 'shield',
        status: 'operational',
        summary:
          'The verified status, evidence level and known blockers of every '
          + 'module, in one place.',
      },
    ],
  },

  /* ------------------------------------------------------------ SYSTEM */
  {
    id: 'system',
    label: 'System',
    items: [
      {
        key: 'organization',
        label: 'Organization',
        path: '/organization',
        icon: 'shield',
        status: 'operational',
        summary:
          'Members, organization roles, invitations, external collaborators '
          + 'and the access history for the organization you are working in. '
          + 'Organization authority is shown separately from scientific '
          + 'assignment, because holding one never grants the other.',
        workflow: [
          'Review the organization profile and confirm a migrated organization',
          'Add, suspend, reinstate and remove members',
          'Invite people and external collaborators with an expiry date',
          'Appoint scientific reviewers and approvers per study',
          'Read the append-only access history',
        ],
      },
      {
        key: 'admin',
        label: 'Administration',
        path: '/admin',
        icon: 'shield',
        status: 'migration_in_progress',
        summary: 'User accounts, roles and authentication audit review.',
        workflow: [
          'Review user accounts and roles',
          'Create and deactivate accounts',
          'Inspect the authentication audit trail',
          'Manage platform configuration',
        ],
        roles: ['admin'],
      },
      {
        key: 'settings',
        label: 'Settings',
        path: '/settings',
        icon: 'gear',
        status: 'migration_in_progress',
        summary:
          'Account preferences and display options. Scoring-weight overrides '
          + 'are deliberately excluded: changing them changes results, which is '
          + 'a scientific decision rather than a preference.',
      },
      {
        key: 'help',
        label: 'Help & Tutorial',
        path: '/help',
        icon: 'info',
        status: 'operational',
        summary:
          'Platform guidance, workflow orientation, security help and links '
          + 'to the operational documentation available to every signed-in role.',
      },
    ],
  },
];

export const NAV_ITEMS: readonly NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export function visibleGroups(role: UserRole | undefined): NavGroup[] {
  if (!role) return [];
  return NAV_GROUPS
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.roles || i.roles.includes(role)) }))
    .filter((g) => g.items.length > 0);
}

export function visibleNavItems(role: UserRole | undefined): NavItem[] {
  return visibleGroups(role).flatMap((g) => g.items);
}

export function findNavItem(key: string): NavItem {
  const item = NAV_ITEMS.find((i) => i.key === key);
  if (!item) throw new Error(`unknown nav item: ${key}`);
  return item;
}

/* ========================================================================= */
/* Route families                                                            */
/* ========================================================================= */
/**
 * A menu entry that owns more than one route.
 *
 * Declared once, here. The sidebar, header title and breadcrumbs all resolve
 * through `activeNavKeyForPath`, so the rule cannot drift between them.
 *
 * `prefixes` match on a path SEGMENT boundary, never a bare string prefix:
 * `/report` and `/reports` are two different modules, and a naive
 * `startsWith('/report')` would light up the wrong one.
 */
const ROUTE_FAMILIES: ReadonlyArray<{
  key: string;
  exact?: readonly string[];
  prefixes?: readonly string[];
}> = [
  { key: 'start-study', exact: ['/start'], prefixes: ['/start'] },
  { key: 'demo', prefixes: ['/demo'] },
  { key: 'patient-assessments', prefixes: ['/report', '/patient-assessments'] },
  { key: 'research-designs', prefixes: ['/research-designs'] },
  { key: 'studies', prefixes: ['/studies'] },
  { key: 'history', prefixes: ['/history'] },
  { key: 'compare', prefixes: ['/compare'] },
  { key: 'projects', prefixes: ['/projects'] },
  { key: 'scientific-readiness', prefixes: ['/scientific-readiness'] },
  { key: 'validation-registry', prefixes: ['/validation'] },
  { key: 'visualisation', prefixes: ['/builder', '/visualisation'] },
  { key: 'organization', prefixes: ['/organization'] },
  { key: 'home', prefixes: ['/home', '/dashboard'] },
];

/** True when `path` is `base` or a child segment of it. */
function isWithin(path: string, base: string): boolean {
  return path === base || path.startsWith(`${base}/`);
}

/**
 * Which menu entry owns the active workflow, given the study's pathway.
 *
 * The `/workflow/*` routes are shared by all three pathways — the same four
 * steps run whether the study began from a report, a research question or a
 * demonstration. So the route alone cannot decide the active entry; the study's
 * own pathway does. Without this, a patient assessment mid-workflow would
 * highlight "Research Designs", which would be simply untrue.
 */
export function navKeyForPathway(pathway: StudyPathway | undefined): string {
  switch (pathway) {
    case 'patient_assessment':
      return 'patient-assessments';
    case 'demo_scenario':
      return 'demo';
    case 'research_design':
    default:
      return 'research-designs';
  }
}

export interface NavContext {
  /** Pathway of the study currently open, when one is. */
  pathway?: StudyPathway;
}

/**
 * The single source of truth for which menu entry a route belongs to.
 *
 * Returns the nav key, or `undefined` for a route outside the menu.
 */
export function activeNavKeyForPath(path: string,
                                    context: NavContext = {}): string | undefined {
  // The shared workflow belongs to whichever pathway opened it.
  if (isWithin(path, '/workflow')) return navKeyForPathway(context.pathway);

  // An exact nav path wins, so `/reports` resolves to Reports even though
  // `/report` is a declared prefix of another family.
  const exact = NAV_ITEMS.find((i) => i.path === path);
  if (exact) return exact.key;

  for (const family of ROUTE_FAMILIES) {
    if (family.exact?.includes(path)) return family.key;
    if (family.prefixes?.some((base) => isWithin(path, base))) return family.key;
  }
  return undefined;
}

/** True when `path` belongs to a study workflow of any pathway. */
export function isStudyWorkflowActive(path: string): boolean {
  return isWithin(path, '/workflow') || path === '/start'
    || isWithin(path, '/start');
}

export function navItemByPath(path: string,
                              context: NavContext = {}): NavItem | undefined {
  const key = activeNavKeyForPath(path, context);
  return key ? NAV_ITEMS.find((i) => i.key === key) : undefined;
}

/* ========================================================================= */
/* Titles                                                                    */
/* ========================================================================= */

const STATIC_TITLES: Record<string, string> = {
  '/home': 'Home',
  '/start': 'Start New Study',
  '/start/research': 'Research Purpose',
  '/demo': 'Demo Workspace',
  '/report': 'Patient Assessment',
  '/patient-assessments': 'Patient Assessments',
  '/research-designs': 'Research Designs',
  '/studies': 'My Studies',
  '/history': 'Simulation History',
  '/compare': 'Compare Results',
  '/projects': 'Projects',
  '/reports': 'Reports',
  '/evidence': 'Evidence & Validation',
  '/builder': 'Nanoparticle 3D Builder',
  '/scientific-readiness': 'Scientific Readiness',
  '/validation': 'Validation Registry',
  '/validation/new': 'New In-Vitro Experiment',
  '/organization': 'Organization',
  '/invitations/accept': 'Accept an Invitation',
  '/workflow/disease': 'Disease & Therapeutic Context',
  '/workflow/design': 'Nanoparticle Parameters',
  '/workflow/targeting': 'Targeting & Ligands',
  '/workflow/review': 'Review & Run',
  '/workflow/results': 'Results',
};

/** Human-readable page title. Never contains study or patient detail. */
export function pageTitleForPath(path: string): string {
  if (STATIC_TITLES[path]) return STATIC_TITLES[path]!;
  if (path.startsWith('/history/')) return 'Stored Study';
  if (path.startsWith('/studies/')) return 'Study';
  return navItemByPath(path)?.label ?? 'NanoBio Studio';
}

/** The workflow stage label, for the breadcrumb trail. */
export function workflowStageForPath(path: string): string | undefined {
  return STATIC_TITLES[path] && path.startsWith('/workflow/')
    ? STATIC_TITLES[path]
    : undefined;
}

export function groupLabelFor(key: string): string | undefined {
  return NAV_GROUPS.find((g) => g.items.some((i) => i.key === key))?.label;
}
