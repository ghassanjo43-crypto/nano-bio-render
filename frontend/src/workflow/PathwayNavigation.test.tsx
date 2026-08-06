/**
 * Pathway-aware workflow navigation.
 *
 * Four properties dominate these tests:
 *
 * 1. **Back follows the pathway, not history.** After a detour to an unrelated
 *    module, Back still returns to the previous *scientific* step. This is the
 *    whole reason the sequences live in data rather than in `history.back()`.
 * 2. **The three pathways are genuinely distinct.** Same routes, different
 *    orders, different first and last steps — otherwise "pathway" would be a
 *    label rather than a behaviour.
 * 3. **Nothing is lost by moving.** Back and Continue preserve the study, the
 *    candidate and every entered value.
 * 4. **The pathway guides but does not lock.** Every menu entry stays
 *    reachable, and an off-pathway page renders normally instead of
 *    redirecting.
 *
 * The pure ordering functions are tested directly. Rendering is used only where
 * the question is genuinely about the DOM.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import { pkFixtureFor } from './pkTestFixtures';
import {
  PATHWAY_CAVEAT, PATHWAY_LABEL, PATHWAY_STEPS, allPathwayPaths, nextStep,
  previousStep, progressFor, stepIndexFor, stepsFor,
} from './pathways';
import type { StudyPathway } from '../shell/navigation';
import { NAV_ITEMS } from '../shell/navigation';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

const ALL_PATHWAYS: StudyPathway[] = [
  'patient_assessment', 'research_design', 'demo_scenario',
];

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
    if (url.includes('/api/v1/runs')) return json({ runs: [], total: 0 });
    if (url.includes('/api/v1/projects')) return json({ projects: [], total: 0 });
    if (url.includes('/readiness')) {
      return json({ areas: [], rules_engine_version: 'readiness-rules-1.1.0',
                    dictionary_version: 'data-dictionary-1.0.0',
                    evaluated_at: '2026-08-03T10:00:00Z', notice: 'x',
                    study_id: 1, record_count: 0 });
    }
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

/** Put a study on a pathway into storage, then render. */
function seedSession(patch: Record<string, unknown>) {
  const now = new Date().toISOString();
  const session = {
    id: 'ds_test', name: 'Seeded study', createdAt: now, updatedAt: now,
    selection: { disease: 'Breast Cancer', subtype: 'HER2-enriched (ER-, PR-, HER2+)',
                 drug: 'Trastuzumab (Herceptin)' },
    values: { size_nm: '100', charge_mv: '-5', encapsulation_percent: '85' },
    chips: { surface_coating: [], functional_groups: [] },
    pk: {},
    furthestStep: 4,
    pathway: 'research_design',
    projectId: null,
    candidateName: '',
    ...patch,
  };
  localStorage.setItem('nanobio.designDrafts.v1', JSON.stringify([session]));
  localStorage.setItem('nanobio.activeDraftId.v1', session.id);
}

beforeEach(() => { localStorage.clear(); installFetch(); });
afterEach(() => {
  vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear();
});

/* ===================================================================== */
describe('1. the three pathways are distinct sequences', () => {
  it('defines a sequence for each pathway', () => {
    for (const pathway of ALL_PATHWAYS) {
      expect(stepsFor(pathway).length).toBeGreaterThan(3);
    }
  });

  it('gives each pathway its own first step', () => {
    const firsts = ALL_PATHWAYS.map((p) => stepsFor(p)[0]!.path);
    expect(new Set(firsts).size).toBe(3);
    expect(stepsFor('patient_assessment')[0]!.path).toBe('/report');
    expect(stepsFor('research_design')[0]!.path).toBe('/start/research');
    expect(stepsFor('demo_scenario')[0]!.path).toBe('/demo');
  });

  it('orders the patient pathway exactly as specified', () => {
    expect(stepsFor('patient_assessment').map((s) => s.path)).toEqual([
      '/report', '/workflow/disease', '/start/research', '/workflow/design',
      '/workflow/targeting', '/workflow/review', '/scientific-readiness',
      // Phase 2 Milestone 1 inserts the Validation Registry after readiness:
      // an experiment is recorded once the study knows what its data supports.
      '/validation',
      '/protocol', '/experimental-planning', '/evidence', '/compare',
      '/reports',
    ]);
  });

  it('orders the research pathway exactly as specified', () => {
    expect(stepsFor('research_design').map((s) => s.path)).toEqual([
      '/start/research', '/workflow/disease', '/workflow/design',
      '/workflow/targeting', '/workflow/review', '/scientific-readiness',
      '/validation',
      '/protocol', '/experimental-planning', '/evidence', '/compare',
      '/reports',
    ]);
  });

  it('ends the demo pathway on a comparison and a report', () => {
    const demo = stepsFor('demo_scenario');
    expect(demo[0]!.path).toBe('/demo');
    expect(demo[demo.length - 2]!.label).toMatch(/comparison/i);
    expect(demo[demo.length - 1]!.label).toMatch(/report/i);
  });

  it('puts the same scientific step in a different position per pathway', () => {
    // Disease & Biomarker is step 2 on both study pathways but for different
    // reasons: after the report on one, after the research question on the
    // other. Same stop, different journey — which is the point.
    const patient = stepsFor('patient_assessment');
    const research = stepsFor('research_design');
    const design = '/workflow/design';
    expect(patient.findIndex((s) => s.path === design))
      .not.toBe(research.findIndex((s) => s.path === design));
  });

  it('never lists the same route twice within one pathway', () => {
    for (const pathway of ALL_PATHWAYS) {
      const paths = stepsFor(pathway).map((s) => s.path);
      expect(new Set(paths).size).toBe(paths.length);
    }
  });

  it('gives Targeting & Ligands a route of its own', () => {
    // It shared /workflow/design with Nanoparticle Design, which made two
    // consecutive steps resolve to one URL and Continue a no-op.
    const design = NAV_ITEMS.find((i) => i.key === 'nanoparticle-design')!;
    const targeting = NAV_ITEMS.find((i) => i.key === 'targeting-ligands')!;
    expect(targeting.path).not.toBe(design.path);
    expect(targeting.path).toBe('/workflow/targeting');
  });
});

/* ===================================================================== */
describe('2. back and next follow the pathway', () => {
  it('returns the previous scientific step, not the previous page visited', () => {
    expect(previousStep('research_design', '/workflow/review')?.path)
      .toBe('/workflow/targeting');
    expect(previousStep('research_design', '/workflow/targeting')?.path)
      .toBe('/workflow/design');
  });

  it('gives the same route a different Back per pathway', () => {
    // /workflow/disease is reached from the report on one pathway and from the
    // research question on the other. History would answer "whatever you last
    // looked at"; the pathway answers correctly.
    expect(previousStep('patient_assessment', '/workflow/disease')?.path)
      .toBe('/report');
    expect(previousStep('research_design', '/workflow/disease')?.path)
      .toBe('/start/research');
  });

  it('has no previous step at the start of a pathway', () => {
    for (const pathway of ALL_PATHWAYS) {
      const first = stepsFor(pathway)[0]!;
      expect(previousStep(pathway, first.path)).toBeUndefined();
    }
  });

  it('has no next step at the end of a pathway', () => {
    for (const pathway of ALL_PATHWAYS) {
      const steps = stepsFor(pathway);
      expect(nextStep(pathway, steps[steps.length - 1]!.path)).toBeUndefined();
    }
  });

  it('walks the whole pathway forwards and back to the same sequence', () => {
    for (const pathway of ALL_PATHWAYS) {
      const steps = stepsFor(pathway);
      const forwards: string[] = [steps[0]!.path];
      let cursor = nextStep(pathway, steps[0]!.path);
      while (cursor) {
        forwards.push(cursor.path);
        cursor = nextStep(pathway, cursor.path);
      }
      const backwards: string[] = [];
      let back = steps[steps.length - 1]!;
      backwards.unshift(back.path);
      let prev = previousStep(pathway, back.path);
      while (prev) {
        backwards.unshift(prev.path);
        back = prev;
        prev = previousStep(pathway, prev.path);
      }
      expect(forwards).toEqual(steps.map((s) => s.path));
      expect(backwards).toEqual(forwards);
    }
  });

  it('treats an off-pathway page as off-pathway rather than as step zero', () => {
    // The builder is a legitimate detour. Reporting it as position 0 of the
    // pathway would make Back mean "the step before the first one".
    expect(stepIndexFor('research_design', '/builder')).toBe(-1);
    expect(previousStep('research_design', '/builder')).toBeUndefined();
    expect(nextStep('research_design', '/builder')).toBeUndefined();
    expect(progressFor('research_design', '/builder').onPathway).toBe(false);
  });
});

/* ===================================================================== */
describe('3. progress and the next recommended step', () => {
  it('reports position and total', () => {
    const p = progressFor('research_design', '/workflow/design');
    expect(p.position).toBe(3);
    expect(p.total).toBe(stepsFor('research_design').length);
    expect(p.onPathway).toBe(true);
  });

  it('reaches 100% only on the final step', () => {
    const steps = stepsFor('research_design');
    expect(progressFor('research_design', steps[steps.length - 1]!.path).percent)
      .toBe(100);
    expect(progressFor('research_design', steps[0]!.path).percent)
      .toBeLessThan(100);
  });

  it('reports zero progress off the pathway rather than guessing', () => {
    const p = progressFor('research_design', '/projects');
    expect(p.percent).toBe(0);
    expect(p.position).toBe(0);
    expect(p.onPathway).toBe(false);
  });

  it('names the next recommended step on the page', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    const next = await screen.findByTestId('pathway-next');
    expect(next).toHaveTextContent(/Targeting & Ligands/i);
  });

  it('says so on the last step instead of inventing a next one', () => {
    const steps = stepsFor('research_design');
    expect(nextStep('research_design', steps[steps.length - 1]!.path))
      .toBeUndefined();
  });

  it('separates position from scientific completeness in words', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    const progress = await screen.findByTestId('pathway-progress');
    expect(progress).toHaveTextContent(/not a measure of scientific completeness/i);
  });
});

/* ===================================================================== */
describe('4. the controls appear and behave', () => {
  it('renders Back, Save & Continue and Save & Exit', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    await screen.findByTestId('pathway-nav');
    expect(screen.getByTestId('pathway-back')).toBeInTheDocument();
    expect(screen.getByTestId('pathway-continue')).toBeInTheDocument();
    expect(screen.getByTestId('pathway-save-exit')).toBeInTheDocument();
  });

  it('labels Back with the step it returns to', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    expect(await screen.findByTestId('pathway-back'))
      .toHaveTextContent(/Disease/i);
  });

  it('disables Back on the first step and says why', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/start/research');
    expect(await screen.findByTestId('pathway-back')).toBeDisabled();
    expect(screen.getByTestId('pathway-back-hint'))
      .toHaveTextContent(/first step/i);
  });

  it('moves back along the pathway when Back is pressed', async () => {
    const user = userEvent.setup();
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/targeting');
    await user.click(await screen.findByTestId('pathway-back'));
    expect(await screen.findByRole('heading', { name: /Step 2/i, level: 2 }))
      .toBeInTheDocument();
  });

  it('moves forward along the pathway when Continue is pressed', async () => {
    const user = userEvent.setup();
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    await user.click(await screen.findByTestId('pathway-continue'));
    expect(await screen.findByRole('heading',
      { name: /Targeting & Ligands/i, level: 2 })).toBeInTheDocument();
  });

  it('Save & Exit returns to My Studies', async () => {
    const user = userEvent.setup();
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    await user.click(await screen.findByTestId('pathway-save-exit'));
    expect(await screen.findByRole('heading',
      { name: /My Studies/i, level: 2 })).toBeInTheDocument();
  });

  it('Save & Exit writes the draft before leaving', async () => {
    const user = userEvent.setup();
    seedSession({ pathway: 'research_design', name: 'Before exit' });
    renderAt('/workflow/design');
    await user.click(await screen.findByTestId('pathway-save-exit'));
    await screen.findByRole('heading', { name: /My Studies/i, level: 2 });
    const raw = localStorage.getItem('nanobio.designDrafts.v1') ?? '[]';
    expect(JSON.parse(raw)[0].name).toBe('Before exit');
  });

  it('shows no controls on a page outside the pathway', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/projects');
    await screen.findByRole('heading', { name: /Projects/i, level: 2 });
    expect(screen.queryByTestId('pathway-nav')).not.toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('5. context is shown on every scientific page', () => {
  it('names the pathway, the study and the candidate', async () => {
    seedSession({
      pathway: 'research_design', name: 'HER2 liposome',
      candidateName: 'Candidate B',
    });
    renderAt('/workflow/design');
    await screen.findByTestId('pathway-banner');
    expect(screen.getByTestId('pathway-name'))
      .toHaveTextContent(PATHWAY_LABEL.research_design);
    expect(screen.getByTestId('banner-study')).toHaveTextContent('HER2 liposome');
    expect(screen.getByTestId('banner-candidate')).toHaveTextContent('Candidate B');
  });

  it('says a candidate is not named rather than inventing one', async () => {
    seedSession({ pathway: 'research_design', candidateName: '' });
    renderAt('/workflow/design');
    expect(await screen.findByTestId('banner-candidate'))
      .toHaveTextContent(/not named/i);
  });

  it('shows the step position in the banner', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    expect(await screen.findByTestId('banner-step')).toHaveTextContent(/3 of/);
  });

  it('appears on a scientific tool reached as a pathway step', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/scientific-readiness');
    expect(await screen.findByTestId('pathway-banner')).toBeInTheDocument();
    expect(screen.getByTestId('pathway-nav')).toBeInTheDocument();
  });

  it('states plainly when the page is off the pathway', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/results');
    expect(await screen.findByTestId('banner-offpathway'))
      .toHaveTextContent(/not part of the/i);
  });
});

/* ===================================================================== */
describe('6. demonstration and patient labelling', () => {
  it('labels the demonstration pathway as synthetic and illustrative', async () => {
    seedSession({ pathway: 'demo_scenario' });
    renderAt('/workflow/design');
    const caveat = await screen.findByTestId('pathway-caveat');
    expect(caveat).toHaveTextContent(/synthetic/i);
    expect(caveat).toHaveTextContent(/illustrative/i);
    expect(caveat).toHaveTextContent(/describes no real material/i);
  });

  it('labels the patient pathway as a limited prototype', async () => {
    seedSession({ pathway: 'patient_assessment' });
    renderAt('/workflow/design');
    const caveat = await screen.findByTestId('pathway-caveat');
    expect(caveat).toHaveTextContent(/limited prototype/i);
    expect(caveat).toHaveTextContent(/not been validated/i);
  });

  it('gives the research pathway no such caveat', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    await screen.findByTestId('pathway-banner');
    expect(screen.queryByTestId('pathway-caveat')).not.toBeInTheDocument();
  });

  it('keeps the two caveats distinct', () => {
    // Synthetic inputs and an unvalidated extractor are different problems.
    // One generic "research use only" would blur both.
    expect(PATHWAY_CAVEAT.demo_scenario)
      .not.toBe(PATHWAY_CAVEAT.patient_assessment);
    expect(PATHWAY_CAVEAT.research_design).toBeUndefined();
  });

  it('marks a step whose engine is not connected', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/protocol');
    expect(await screen.findByTestId('pathway-availability-note'))
      .toHaveTextContent(/not connected/i);
  });
});

/* ===================================================================== */
describe('7. the pathway guides without locking', () => {
  it('leaves every menu group reachable while a study is open', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    const nav = await screen.findByRole('navigation', { name: 'Main navigation' });
    // A representative entry from each group, none of which is on the pathway.
    for (const label of [/Projects/i, /Simulation History/i, /My Studies/i]) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('renders an off-pathway module normally instead of redirecting', async () => {
    seedSession({ pathway: 'research_design' });
    renderAt('/projects');
    expect(await screen.findByRole('heading',
      { name: /Projects/i, level: 2 })).toBeInTheDocument();
  });

  it('lets the progress rail jump to any step, including later ones', async () => {
    const user = userEvent.setup();
    seedSession({ pathway: 'research_design' });
    renderAt('/workflow/design');
    await user.click(await screen.findByTestId('pathway-step-scientific-readiness'));
    expect(await screen.findByRole('heading',
      { name: /Scientific Readiness/i, level: 2 })).toBeInTheDocument();
  });

  it('every pathway route is a real route in the application', () => {
    // A step pointing at a path the router does not serve would send the user
    // to the not-found page from a control that looks official.
    const known = new Set(NAV_ITEMS.map((i) => i.path));
    const extra = new Set([
      '/report', '/start/research', '/workflow/disease', '/workflow/design',
      '/workflow/targeting', '/workflow/review', '/compare', '/reports',
      '/demo', '/protocol', '/experimental-planning', '/evidence',
      '/scientific-readiness', '/validation',
    ]);
    for (const path of allPathwayPaths()) {
      expect(known.has(path) || extra.has(path)).toBe(true);
    }
  });
});

/* ===================================================================== */
describe('8. every declared step is well formed', () => {
  it('gives each step a label, a short label and a summary', () => {
    for (const pathway of ALL_PATHWAYS) {
      for (const step of PATHWAY_STEPS[pathway]) {
        expect(step.label.length).toBeGreaterThan(3);
        // 'PK' is two characters and is the clearest label for that step.
        expect(step.shortLabel.length).toBeGreaterThanOrEqual(2);
        expect(step.summary.length).toBeGreaterThan(15);
        expect(step.path.startsWith('/')).toBe(true);
      }
    }
  });

  it('declares availability honestly for the unconnected modules', () => {
    const byId = new Map(
      stepsFor('research_design').map((s) => [s.id, s]));
    expect(byId.get('protocol')!.availability).toBe('not_connected');
    expect(byId.get('experimental-planning')!.availability).toBe('not_connected');
    expect(byId.get('nanoparticle-design')!.availability).toBe('operational');
  });

  it('names each pathway for a human', () => {
    for (const pathway of ALL_PATHWAYS) {
      expect(PATHWAY_LABEL[pathway].length).toBeGreaterThan(10);
    }
  });
});
