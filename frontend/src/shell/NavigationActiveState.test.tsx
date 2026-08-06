/**
 * Sidebar active-state and breadcrumb regression tests.
 *
 * The original defect: `NavLink`'s `isActive` matches the exact path, so the
 * workflow entry lost its indicator the moment the user pressed "Start" and
 * moved to `/workflow/disease` — in the middle of that very journey. Active
 * state is now resolved once, centrally, by `activeNavKeyForPath`.
 *
 * The second, subtler rule tested here: `/workflow/*` is shared by all three
 * pathways, so the route alone cannot decide which sidebar entry owns it. The
 * study's own pathway does. Without that, a patient assessment mid-workflow
 * would highlight "Research Designs" — which would simply be untrue.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import type { DesignScoreResponse } from '../api/types';
import {
  activeNavKeyForPath, isStudyWorkflowActive, navKeyForPathway,
} from './navigation';
import { crumbsForPath } from './StudyContextBar';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

const SCORE: DesignScoreResponse = {
  design_impact_score: { delivery: 87.52475247524752, toxicity: 0.8, cost: 80.75 },
  score_version: 'design-impact-adapter-0.1.0',
  component_scores: {
    delivery: { value: 87.52475247524752, scale: '0-100', meaning: 'delivery' },
    toxicity: { value: 0.8, scale: '0-10', meaning: 'toxicity' },
    cost: { value: 80.75, scale: '0-100', meaning: 'cost' },
  },
  normalized_inputs: { Size: 100 },
  warnings: [],
  prediction_basis: 'rule_based_physicochemical_heuristic',
  evidence_level: 'literature_informed_unvalidated',
  validation_status: 'not_experimentally_validated',
  limitations: ['Computational research-planning result only.'],
  scientific_source: 'core.scoring.compute_impact',
};

const STORED_RUN = {
  id: 7, name: 'Stored study', origin: 'user',
  pathway: 'research_design', research_purpose: null,
  inputs_are_synthetic: false, report_assessment_id: null,
  demo_scenario_slug: null,
  disease: 'Liver Cancer (HCC)', subtype: 'AFP-high HCC', drug: 'Sorafenib',
  status: 'complete', engines_run: ['Design impact score'],
  has_design_result: true, has_pk_result: false,
  design_score_version: 'design-impact-adapter-0.1.0',
  pk_calculation_version: null, project_id: null,
  created_at: '2026-08-01T10:00:00.000Z',
  design_inputs: { size_nm: 100, charge_mv: -5, encapsulation_percent: 85 },
  pk_inputs: null, design_result: SCORE, pk_result: null,
  engines_not_run: [], demo_fixture_version: null,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

function installFetch() {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    if (url.endsWith('/api/v1/design/score')) return json(SCORE);
    if (url.endsWith('/api/v1/demo/scenarios')) {
      return json({ fixture_version: 'demo-scenarios-1.0.0', scenarios: [],
                    notice: 'Synthetic demonstration inputs.' });
    }
    if (url.includes('/api/v1/reports/synthetic')) {
      return json({ reports: [], fixture_version: 'x', notice: 'y' });
    }
    if (/\/api\/v1\/runs\/\d+$/.test(url)) return json(STORED_RUN);
    if (url.includes('/api/v1/runs')) {
      return json({ runs: [STORED_RUN], total: 1 });
    }
    if (url.includes('/api/v1/projects')) return json({ projects: [], total: 0 });
    return json({}, 404);
  }));
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider><App /></AuthProvider>
    </MemoryRouter>,
  );
}

/** The nav row currently marked active, by its accessible label text. */
async function activeNavLabel(): Promise<string | null> {
  const nav = await screen.findByRole('navigation', { name: /Main navigation/i });
  const active = within(nav).queryAllByRole('link', { current: 'page' });
  if (active.length === 0) return null;
  if (active.length > 1) {
    throw new Error(
      `expected one active nav item, found ${active.length}: `
      + active.map((a) => a.textContent).join(' | '));
  }
  return active[0]!.textContent?.replace(/\s*\(current page\)\s*/, '').trim()
    ?? null;
}

/** Complete Step 1, which is what makes a session genuinely in progress. */
async function completeStep1(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                           'Liver Cancer (HCC)');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Disease subtype' }),
                           'AFP-high HCC');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Therapeutic agent' }),
                           'Sorafenib');
}

beforeEach(() => {
  localStorage.clear();
  installFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

/* ===================================================================== */
describe('route-family resolution (pure)', () => {
  it.each([
    ['/home', 'home'],
    ['/dashboard', 'home'],
    ['/start', 'start-study'],
    ['/start/research', 'start-study'],
    ['/studies', 'studies'],
    ['/studies/7', 'studies'],
    ['/patient-assessments', 'patient-assessments'],
    ['/research-designs', 'research-designs'],
    ['/history', 'history'],
    ['/history/7', 'history'],
    ['/demo', 'demo'],
    ['/compare', 'compare'],
    ['/projects', 'projects'],
    ['/reports', 'reports'],
    ['/evidence', 'evidence'],
    ['/settings', 'settings'],
  ])('%s resolves to %s', (path, expected) => {
    expect(activeNavKeyForPath(path)).toBe(expected);
  });

  it('distinguishes /report from /reports', () => {
    // A bare string prefix would collapse these two modules into one.
    expect(activeNavKeyForPath('/report')).toBe('patient-assessments');
    expect(activeNavKeyForPath('/reports')).toBe('reports');
  });

  it('returns undefined for a route outside the menu', () => {
    expect(activeNavKeyForPath('/nope')).toBeUndefined();
  });

  it('exposes a direct workflow predicate', () => {
    expect(isStudyWorkflowActive('/start')).toBe(true);
    expect(isStudyWorkflowActive('/workflow/results')).toBe(true);
    expect(isStudyWorkflowActive('/studies/7')).toBe(false);
  });
});

/* ===================================================================== */
describe('the shared workflow belongs to the study pathway', () => {
  it.each([
    ['patient_assessment', 'patient-assessments'],
    ['research_design', 'research-designs'],
    ['demo_scenario', 'demo'],
  ] as const)('a %s study highlights %s', (pathway, expected) => {
    expect(navKeyForPathway(pathway)).toBe(expected);
    for (const step of ['/workflow/disease', '/workflow/design',
                        '/workflow/review', '/workflow/results']) {
      expect(activeNavKeyForPath(step, { pathway })).toBe(expected);
    }
  });

  it('falls back to research design when no pathway is known', () => {
    // An old draft carries no pathway. Research design is what such a study
    // actually was, so this restates rather than guesses.
    expect(activeNavKeyForPath('/workflow/disease')).toBe('research-designs');
  });

  it('never lets the route override the pathway', () => {
    // The same route, three different owners. This is the whole point.
    const keys = (['patient_assessment', 'research_design', 'demo_scenario'] as const)
      .map((pathway) => activeNavKeyForPath('/workflow/review', { pathway }));
    expect(new Set(keys).size).toBe(3);
  });
});

/* ===================================================================== */
describe('breadcrumbs', () => {
  it('starts at Home and ends at the current page', () => {
    const crumbs = crumbsForPath('/history');
    expect(crumbs[0]).toEqual({ label: 'Home', to: '/home' });
    expect(crumbs[crumbs.length - 1]!.label).toBe('Simulation History');
    expect(crumbs[crumbs.length - 1]!.to).toBeUndefined();
  });

  it('shows the workflow stage as the leaf', () => {
    const crumbs = crumbsForPath('/workflow/design',
                                 { pathway: 'research_design' });
    expect(crumbs.map((c) => c.label)).toEqual(
      ['Home', 'Workspace', 'Research Designs', 'Nanoparticle Parameters']);
  });

  it('routes the trail through the pathway that owns the study', () => {
    const crumbs = crumbsForPath('/workflow/design',
                                 { pathway: 'patient_assessment' });
    expect(crumbs.map((c) => c.label)).toContain('Patient Assessments');
    expect(crumbs.map((c) => c.label)).not.toContain('Research Designs');
  });

  it('never contains the study name', () => {
    // A breadcrumb is announced by screen readers and reflected in navigation
    // history. The name is user-supplied and could hold an identifier.
    const crumbs = crumbsForPath('/workflow/review', {
      pathway: 'patient_assessment',
      name: 'Jane Doe MRN 12345',
      disease: 'Breast Cancer',
    });
    for (const crumb of crumbs) {
      expect(crumb.label).not.toMatch(/Jane|Doe|12345/);
    }
  });
});

/* ===================================================================== */
describe('1. start pathway chooser', () => {
  it('marks Start New Study active on /start', async () => {
    renderAt('/start');
    expect(await activeNavLabel()).toMatch(/Start New Study/);
  });

  it('keeps it active on the research purpose step', async () => {
    renderAt('/start/research');
    expect(await activeNavLabel()).toMatch(/Start New Study/);
  });

  it('asks how the user would like to begin', async () => {
    renderAt('/start');
    expect(await screen.findByRole('heading',
      { name: /How would you like to begin\?/i })).toBeInTheDocument();
  });

  it('offers exactly the three pathways', async () => {
    renderAt('/start');
    expect(await screen.findByTestId('pathway-patient')).toBeInTheDocument();
    expect(screen.getByTestId('pathway-research')).toBeInTheDocument();
    expect(screen.getByTestId('pathway-demo')).toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('2-4. every workflow route keeps an indicator', () => {
  it.each([
    ['/workflow/disease'],
    ['/workflow/design'],
    ['/workflow/review'],
    ['/workflow/results'],
  ])('%s keeps exactly one item active', async (path) => {
    renderAt(path);
    // Defaults to a research design, the pathway an unmarked draft had.
    expect(await activeNavLabel()).toMatch(/Research Designs/);
  });

  it('keeps the indicator after starting a research study', async () => {
    // The original defect: the indicator vanished on leaving the start page.
    const user = userEvent.setup();
    renderAt('/start');
    await user.click(await screen.findByTestId('start-research'));
    await user.click(await screen.findByTestId('choose-disease_specific_design'));
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    expect(await activeNavLabel()).toMatch(/Research Designs/);
  });

  it('keeps the indicator across the whole journey to results', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    expect(await activeNavLabel()).toMatch(/Research Designs/);

    await completeStep1(user);
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
    expect(await activeNavLabel()).toMatch(/Research Designs/);

    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });
    expect(await activeNavLabel()).toMatch(/Research Designs/);

    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');
    expect(await activeNavLabel()).toMatch(/Research Designs/);
  });
});

/* ===================================================================== */
describe('5. resumed saved study', () => {
  it('keeps an indicator when a draft is reopened', async () => {
    localStorage.setItem('nanobio.designDrafts.v1', JSON.stringify([{
      id: 'ds_saved', name: 'Saved design',
      createdAt: '2026-08-01T09:00:00.000Z', updatedAt: '2026-08-01T09:00:00.000Z',
      selection: { disease: 'Liver Cancer (HCC)', subtype: 'AFP-high HCC',
                   drug: 'Sorafenib' },
      values: { size_nm: '118', charge_mv: '-5', encapsulation_percent: '85' },
      chips: { surface_coating: [], functional_groups: [] },
      pk: {}, furthestStep: 3,
    }]));

    const user = userEvent.setup();
    renderAt('/start');
    // "Resume Saved Draft" opens the drafts gate, where the localStorage
    // drafts genuinely live; the draft itself is opened from there.
    await user.click(await screen.findByTestId('resume-research'));
    const saved = await screen.findByTestId('saved-designs');
    await user.click(within(saved).getAllByRole('button', { name: /Open/i })[0]!);

    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    expect(await activeNavLabel()).toMatch(/Research Designs/);
  });
});

/* ===================================================================== */
describe('6. the workspace lists own their study details', () => {
  it('marks My Studies active on the list', async () => {
    renderAt('/studies');
    expect(await activeNavLabel()).toMatch(/My Studies/);
  });

  it('keeps My Studies active on a stored study, not the workflow', async () => {
    renderAt('/studies/7');
    const active = await activeNavLabel();
    expect(active).toMatch(/My Studies/);
    expect(active).not.toMatch(/Research Designs/);
  });

  it('marks History active on its own list', async () => {
    renderAt('/history');
    expect(await activeNavLabel()).toMatch(/Simulation History/);
  });

  it('marks Patient Assessments active on its list', async () => {
    renderAt('/patient-assessments');
    expect(await activeNavLabel()).toMatch(/Patient Assessments/);
  });

  it('marks Research Designs active on its list', async () => {
    renderAt('/research-designs');
    expect(await activeNavLabel()).toMatch(/Research Designs/);
  });
});

/* ===================================================================== */
describe('7. Demo Workspace before and after loading', () => {
  it('marks Demo Workspace active while choosing a scenario', async () => {
    renderAt('/demo');
    expect(await activeNavLabel()).toMatch(/Demo Workspace/);
  });

  it('keeps Demo Workspace active once a demonstration is loaded', async () => {
    // A demonstration study stays a demonstration through every workflow step.
    expect(activeNavKeyForPath('/workflow/design', { pathway: 'demo_scenario' }))
      .toBe('demo');
  });
});

/* ===================================================================== */
describe('8. browser refresh on an internal workflow URL', () => {
  it.each(['/workflow/design', '/workflow/review', '/workflow/results'])(
    'a fresh load of %s marks exactly one item active', async (path) => {
      // A fresh render is exactly what a refresh produces: no prior navigation.
      renderAt(path);
      expect(await activeNavLabel()).toBeTruthy();
    });
});

/* ===================================================================== */
describe('exclusivity and accessibility', () => {
  it.each(['/start', '/workflow/design', '/studies/7', '/demo', '/projects',
           '/evidence', '/patient-assessments', '/research-designs'])(
    'exactly one item is active on %s', async (path) => {
      renderAt(path);
      // activeNavLabel throws if more than one row is marked current.
      expect(await activeNavLabel()).toBeTruthy();
    });

  it('marks the active item with aria-current="page"', async () => {
    renderAt('/workflow/review');
    const nav = await screen.findByRole('navigation', { name: /Main navigation/i });
    const active = within(nav).getByRole('link', { current: 'page' });
    expect(active).toHaveAttribute('aria-current', 'page');
  });

  it('does not signal active state by colour alone', async () => {
    renderAt('/workflow/design');
    const nav = await screen.findByRole('navigation', { name: /Main navigation/i });
    const active = within(nav).getByRole('link', { current: 'page' });
    // A text affordance and the ARIA state both exist independently of styling.
    expect(active.textContent).toMatch(/current page/i);
    expect(active).toHaveAttribute('aria-current', 'page');
  });

  it('keeps the active class that draws the vertical indicator', async () => {
    renderAt('/workflow/results');
    const nav = await screen.findByRole('navigation', { name: /Main navigation/i });
    expect(within(nav).getByRole('link', { current: 'page' }))
      .toHaveClass('is-active');
  });

  it('marks nothing active on a route outside the menu', async () => {
    renderAt('/unauthorized');
    expect(await activeNavLabel()).toBeNull();
  });

  it('reaches every sidebar entry by keyboard', async () => {
    renderAt('/home');
    const nav = await screen.findByRole('navigation', { name: /Main navigation/i });
    const links = within(nav).getAllByRole('link');
    expect(links.length).toBeGreaterThan(10);
    // Anchors with an href are in the tab order; none may be removed from it.
    for (const link of links) {
      expect(link).toHaveAttribute('href');
      expect(link).not.toHaveAttribute('tabindex', '-1');
    }
  });

  it('groups the menu into the five declared sections', async () => {
    renderAt('/home');
    const nav = await screen.findByRole('navigation', { name: /Main navigation/i });
    for (const label of ['Start', 'Workspace', 'Scientific Tools',
                         'Intelligence', 'System']) {
      expect(within(nav).getByText(label)).toBeInTheDocument();
    }
  });
});
