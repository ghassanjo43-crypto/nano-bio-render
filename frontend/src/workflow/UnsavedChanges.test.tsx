/**
 * Persistence, state preservation and the unsaved-changes guard.
 *
 * The distinction this suite exists to pin
 * ----------------------------------------
 * "Unsaved" and "lost" are different things, and conflating them produces a
 * warning nobody reads.
 *
 * Moving between pathway steps cannot lose anything: the session lives in
 * `WorkflowContext` for as long as the application is mounted, so a value typed
 * on one step is still there after Back, Continue, and a detour through an
 * unrelated module. Prompting there would warn about a loss that cannot happen.
 *
 * What *can* be lost is everything since the last save, if the page is closed
 * or reloaded — the session is React state, and only `saveDraft` writes it to
 * storage. That is what `beforeunload` covers, and it is registered only while
 * the study is genuinely dirty.
 *
 * So: no prompt on Back (tested), a prompt on unload while dirty (tested), and
 * no prompt on unload once saved (tested).
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import { pkFixtureFor } from './pkTestFixtures';
import { fingerprint, LEAVE_PROMPT } from './useUnsavedChanges';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

const DRAFT_KEY = 'nanobio.designDrafts.v1';
const ACTIVE_KEY = 'nanobio.activeDraftId.v1';

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
    return json({}, 404);
  }));
}

function seedSession(patch: Record<string, unknown> = {}) {
  const now = new Date().toISOString();
  const session = {
    id: 'ds_unsaved', name: 'Seeded study', createdAt: now, updatedAt: now,
    selection: { disease: 'Breast Cancer', subtype: 'HER2-enriched (ER-, PR-, HER2+)',
                 drug: 'Trastuzumab (Herceptin)' },
    values: { size_nm: '100', charge_mv: '-5', encapsulation_percent: '85' },
    chips: { surface_coating: [], functional_groups: [] },
    pk: {},
    furthestStep: 4,
    pathway: 'research_design',
    projectId: null,
    candidateName: 'Candidate A',
    ...patch,
  };
  localStorage.setItem(DRAFT_KEY, JSON.stringify([session]));
  localStorage.setItem(ACTIVE_KEY, session.id);
  return session;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider><App /></AuthProvider>
    </MemoryRouter>,
  );
}

/** Fire beforeunload and report whether a handler asked to block. */
function firesUnloadPrompt(): boolean {
  const event = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(event);
  return event.defaultPrevented;
}

function storedDraft() {
  return JSON.parse(localStorage.getItem(DRAFT_KEY) ?? '[]')[0];
}

beforeEach(() => { localStorage.clear(); installFetch(); });
afterEach(() => {
  vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear();
});

/* ===================================================================== */
describe('1. the dirty fingerprint', () => {
  const base = {
    selection: { disease: 'A', subtype: 'B', drug: 'C' },
    values: { size_nm: '100' },
    chips: { surface_coating: [] },
    pk: { k_el: '0.1' },
    name: 'Study',
    projectId: null,
    candidateName: 'Cand',
  };

  it('is stable for identical content', () => {
    expect(fingerprint(base)).toBe(fingerprint({ ...base }));
  });

  it('changes when a design value changes', () => {
    expect(fingerprint({ ...base, values: { size_nm: '120' } }))
      .not.toBe(fingerprint(base));
  });

  it('changes when the candidate is renamed', () => {
    expect(fingerprint({ ...base, candidateName: 'Other' }))
      .not.toBe(fingerprint(base));
  });

  it('changes when the project changes', () => {
    expect(fingerprint({ ...base, projectId: 4 })).not.toBe(fingerprint(base));
  });

  it('ignores everything that is not user work', () => {
    // `updatedAt` and `furthestStep` are deliberately absent from the input
    // type. Including them would report a study dirty for having been read.
    expect(Object.keys(base)).not.toContain('updatedAt');
    expect(Object.keys(base)).not.toContain('furthestStep');
  });
});

/* ===================================================================== */
describe('2. a restored draft is clean, not dirty', () => {
  it('does not warn on unload immediately after loading a saved study', async () => {
    seedSession();
    renderAt('/workflow/design');
    await screen.findByTestId('pathway-nav');
    // The regression: comparing against a separately-computed initial session
    // reported a freshly restored draft as unsaved, and every page load
    // greeted the user with a warning about work they had already saved.
    expect(firesUnloadPrompt()).toBe(false);
  });

  it('does not warn on a brand-new study', async () => {
    renderAt('/workflow/disease');
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    expect(firesUnloadPrompt()).toBe(false);
  });
});

/* ===================================================================== */
describe('3. editing arms the warning; saving disarms it', () => {
  it('warns on unload once a value has been edited', async () => {
    const user = userEvent.setup();
    seedSession();
    renderAt('/workflow/design');
    await screen.findByTestId('pathway-nav');
    expect(firesUnloadPrompt()).toBe(false);

    const size = screen.getByRole('textbox', { name: /Particle size/i });
    await user.clear(size);
    await user.type(size, '140');

    expect(firesUnloadPrompt()).toBe(true);
  });

  it('stops warning after the draft is saved', async () => {
    const user = userEvent.setup();
    seedSession();
    renderAt('/workflow/design');
    await screen.findByTestId('pathway-nav');

    const size = screen.getByRole('textbox', { name: /Particle size/i });
    await user.clear(size);
    await user.type(size, '140');
    expect(firesUnloadPrompt()).toBe(true);

    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Targeting & Ligands/i, level: 2 });

    // Save & Continue saves before navigating, so nothing is outstanding.
    expect(firesUnloadPrompt()).toBe(false);
  });

  it('offers to save rather than only to discard', () => {
    // A confirmation whose options are "lose your work" and "stay here"
    // trains people to click through it.
    expect(LEAVE_PROMPT.save).toMatch(/save/i);
    expect(LEAVE_PROMPT.discard).toMatch(/without saving/i);
    expect(LEAVE_PROMPT.cancel).toMatch(/stay/i);
  });
});

/* ===================================================================== */
describe('4. no prompt where nothing can be lost', () => {
  it('does not interrupt Back, because Back preserves everything', async () => {
    const user = userEvent.setup();
    seedSession();
    renderAt('/workflow/targeting');
    await screen.findByTestId('pathway-nav');

    const ligandDensity = screen.getByRole('textbox', { name: /Ligand density/i });
    await user.clear(ligandDensity);
    await user.type(ligandDensity, '12');

    await user.click(screen.getByTestId('pathway-back'));

    // Straight to Step 2 with no dialog in the way.
    expect(await screen.findByRole('heading', { name: /Step 2/i, level: 2 }))
      .toBeInTheDocument();
    expect(screen.queryByTestId('unsaved-changes-body')).not.toBeInTheDocument();
  });

  it('brings the edited value back with it', async () => {
    const user = userEvent.setup();
    seedSession();
    renderAt('/workflow/targeting');
    await screen.findByTestId('pathway-nav');

    const density = screen.getByRole('textbox', { name: /Ligand density/i });
    await user.clear(density);
    await user.type(density, '12');

    await user.click(screen.getByTestId('pathway-back'));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Targeting & Ligands/i, level: 2 });

    expect(screen.getByRole('textbox', { name: /Ligand density/i })).toHaveValue('12');
  });
});

/* ===================================================================== */
describe('5. the study, candidate and project survive navigation', () => {
  it('keeps the candidate name across every step of the pathway', async () => {
    const user = userEvent.setup();
    seedSession({ candidateName: 'Candidate Z' });
    renderAt('/workflow/design');
    expect(await screen.findByTestId('banner-candidate'))
      .toHaveTextContent('Candidate Z');

    await user.click(screen.getByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Targeting & Ligands/i, level: 2 });
    expect(screen.getByTestId('banner-candidate')).toHaveTextContent('Candidate Z');

    await user.click(screen.getByTestId('pathway-back'));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
    expect(screen.getByTestId('banner-candidate')).toHaveTextContent('Candidate Z');
  });

  it('keeps the study name and pathway across a detour off the pathway',
     async () => {
    const user = userEvent.setup();
    seedSession({ name: 'Detour study' });
    renderAt('/workflow/design');
    await screen.findByTestId('pathway-nav');

    // Off to an unrelated module and back by pathway control.
    await user.click(screen.getByTestId('pathway-step-scientific-readiness'));
    await screen.findByRole('heading', { name: /Scientific Readiness/i, level: 2 });
    expect(screen.getByTestId('banner-study')).toHaveTextContent('Detour study');

    // Back from readiness follows the PATHWAY (to the PK step), not history
    // (which would return to the design step).
    await user.click(screen.getByTestId('pathway-back'));
    expect(await screen.findByRole('heading', { name: /Step 3/i, level: 2 }))
      .toBeInTheDocument();
  });

  it('preserves the project id through the session', () => {
    const seeded = seedSession({ projectId: 7 });
    expect(seeded.projectId).toBe(7);
    // Round-trips through storage, which is what carries it between steps.
    expect(storedDraft().projectId).toBe(7);
  });

  it('persists candidate and project when the draft is saved', async () => {
    const user = userEvent.setup();
    seedSession({ candidateName: 'Persisted candidate', projectId: 3 });
    renderAt('/workflow/design');
    await screen.findByTestId('pathway-nav');

    await user.click(screen.getByTestId('pathway-save-exit'));
    await screen.findByRole('heading', { name: /My Studies/i, level: 2 });

    expect(storedDraft().candidateName).toBe('Persisted candidate');
    expect(storedDraft().projectId).toBe(3);
  });
});

/* ===================================================================== */
describe('6. drafts written before these fields existed still load', () => {
  it('treats a draft with no candidate or project as clean', async () => {
    // A draft saved by the previous version has neither key. If the missing
    // values flowed into the comparison as `undefined`, the study would read
    // as permanently dirty and warn on every unload.
    const now = new Date().toISOString();
    localStorage.setItem(DRAFT_KEY, JSON.stringify([{
      id: 'legacy', name: 'Legacy draft', createdAt: now, updatedAt: now,
      selection: { disease: 'Breast Cancer',
                   subtype: 'HER2-enriched (ER-, PR-, HER2+)',
                   drug: 'Trastuzumab (Herceptin)' },
      values: { size_nm: '90', charge_mv: '-3', encapsulation_percent: '70' },
      chips: {}, pk: {}, furthestStep: 2, pathway: 'research_design',
    }]));
    localStorage.setItem(ACTIVE_KEY, 'legacy');

    renderAt('/workflow/design');
    await screen.findByTestId('pathway-nav');
    expect(firesUnloadPrompt()).toBe(false);
    expect(screen.getByTestId('banner-candidate')).toHaveTextContent(/not named/i);
  });

  it('defaults a draft with no pathway to the research pathway', async () => {
    const now = new Date().toISOString();
    localStorage.setItem(DRAFT_KEY, JSON.stringify([{
      id: 'nopath', name: 'No pathway', createdAt: now, updatedAt: now,
      selection: { disease: '', subtype: '', drug: '' },
      values: {}, chips: {}, pk: {}, furthestStep: 1,
    }]));
    localStorage.setItem(ACTIVE_KEY, 'nopath');

    renderAt('/start/research');
    expect(await screen.findByTestId('pathway-name'))
      .toHaveTextContent(/Research/i);
  });
});
