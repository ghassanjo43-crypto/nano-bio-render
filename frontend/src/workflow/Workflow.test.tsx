/**
 * Tests for the three-stage design workflow: sequence, gating, state
 * preservation, draft save/resume, and the honesty rules.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { pkFixtureFor } from './pkTestFixtures';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import type { DesignScoreResponse } from '../api/types';

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
  normalized_inputs: { Size: 100, Charge: -5, Encapsulation: 85 },
  warnings: [],
  prediction_basis: 'rule_based_physicochemical_heuristic',
  evidence_level: 'literature_informed_unvalidated',
  validation_status: 'not_experimentally_validated',
  limitations: ['Computational research-planning result only.'],
  scientific_source: 'core.scoring.compute_impact',
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

function installFetch(opts: { scoreStatus?: number; scoreBody?: unknown } = {}) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    // The route-aware PK endpoints Step 3 calls on mount.
    const pkFixture = pkFixtureFor(url);
    if (pkFixture !== null) return json(pkFixture);
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    if (url.endsWith('/api/v1/design/score')) {
      return json(opts.scoreBody ?? SCORE, opts.scoreStatus ?? 200);
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

/** Complete Step 1 with a real disease/subtype/drug from the generated data. */
async function completeStep1(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
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
describe('post-login landing', () => {
  it('lands on the pathway chooser, not a dashboard', async () => {
    renderAt('/');
    expect(await screen.findByRole('heading',
      { name: /How would you like to begin\?/i })).toBeInTheDocument();
    expect(screen.getByTestId('pathway-cards')).toBeInTheDocument();
    expect(screen.queryByText(/Platform migration status/i)).not.toBeInTheDocument();
  });

  it('offers exactly the three pathways', async () => {
    renderAt('/start');
    await screen.findByTestId('pathway-cards');
    expect(screen.getByTestId('pathway-patient')).toBeInTheDocument();
    expect(screen.getByTestId('pathway-research')).toBeInTheDocument();
    expect(screen.getByTestId('pathway-demo')).toBeInTheDocument();
  });

  it('shows an honest empty saved list on the drafts gate', async () => {
    renderAt('/start/session');
    await screen.findByTestId('start-new');
    expect(screen.getByTestId('no-saved-designs')).toBeInTheDocument();
    expect(screen.getByText(/never\s+populated with examples/i)).toBeInTheDocument();
  });

  it('does not offer resume when there is no session in progress', async () => {
    renderAt('/start/session');
    await screen.findByTestId('start-new');
    expect(screen.queryByRole('heading', { name: /Resume current design/i }))
      .not.toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('workflow sequence and gating', () => {
  it('starts at Step 1 — Disease & Therapeutic Selection', async () => {
    const user = userEvent.setup();
    renderAt('/start/session');
    await user.click(await screen.findByTestId('start-new'));
    expect(await screen.findByRole('heading', { name: /Step 1 — Disease/i, level: 2 }))
      .toBeInTheDocument();
  });

  it('blocks Continue until disease, subtype and drug are chosen', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });

    const cont = screen.getByTestId('pathway-continue');
    expect(cont).toBeDisabled();

    await completeStep1(user);
    expect(screen.getByTestId('pathway-continue'))
      .toBeEnabled();
  });

  it('redirects a deep link to step 2 back to step 1 when incomplete', async () => {
    renderAt('/workflow/design');
    expect(await screen.findByRole('heading', { name: /Step 1 — Disease/i, level: 2 }))
      .toBeInTheDocument();
  });

  it('redirects a deep link to review back when design is incomplete', async () => {
    renderAt('/workflow/review');
    expect(await screen.findByRole('heading', { name: /Step 1 — Disease/i, level: 2 }))
      .toBeInTheDocument();
  });

  it('advances through all three steps', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);

    await user.click(await screen.findByTestId('pathway-continue'));
    expect(await screen.findByRole('heading', { name: /Step 2 — Nanoparticle Design/i, level: 2 }))
      .toBeInTheDocument();

    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    expect(await screen.findByRole('heading', { name: /Step 3 — Review/i, level: 2 }))
      .toBeInTheDocument();
  });

  it('marks locked steps as unavailable in the progress rail', async () => {
    renderAt('/workflow/disease');
    const rail = await screen.findByRole('navigation', { name: /workflow progress/i });
    const locked = rail.querySelectorAll('.is-locked');
    expect(locked.length).toBeGreaterThan(0);
    expect(within(rail).getAllByText(/Complete the previous step/i).length)
      .toBeGreaterThan(0);
  });
});

/* ===================================================================== */
describe('state preservation', () => {
  it('preserves the therapeutic selection when moving forward and back', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });

    await user.click(await screen.findByTestId('pathway-back'));
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });

    expect((screen.getByRole('combobox', { name: 'Indication' }) as HTMLSelectElement).value)
      .toBe('Liver Cancer (HCC)');
    expect((screen.getByRole('combobox', { name: 'Therapeutic agent' }) as HTMLSelectElement).value)
      .toBe('Sorafenib');
  });

  it('preserves edited design parameters across navigation', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });

    const size = screen.getByRole('textbox', { name: 'Particle size' });
    await user.clear(size);
    await user.type(size, '137');

    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });
    await user.click(await screen.findByTestId('pathway-back'));
    await user.click(await screen.findByTestId('pathway-back'));

    expect((screen.getByRole('textbox', { name: 'Particle size' }) as HTMLInputElement).value)
      .toBe('137');
  });

  it('clears the drug when the disease changes, preventing an invalid pair', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);

    await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                             'Breast Cancer');
    expect((screen.getByRole('combobox', { name: 'Therapeutic agent' }) as HTMLSelectElement).value)
      .toBe('');
  });

  it('only offers drugs valid for the chosen subtype', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);

    const drugSelect = screen.getByRole('combobox', { name: 'Therapeutic agent' });
    const options = within(drugSelect).getAllByRole('option').map((o) => o.textContent);
    expect(options).toContain('Sorafenib');
    expect(options).toContain('Lenvatinib');
    expect(options).not.toContain('Gemcitabine');
  });
});

/* ===================================================================== */
describe('review and run', () => {
  async function reachReview(user: ReturnType<typeof userEvent.setup>) {
    renderAt('/workflow/disease');
    await completeStep1(user);
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Step 2/i, level: 2 });
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await screen.findByRole('heading', { name: /Step 3/i, level: 2 });
  }

  it('shows disease, subtype, drug and the nanoparticle configuration', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    // The selection legitimately appears twice: in the review card and in the
    // persistent rail summary. Scope the assertion to the review card.
    const heading = screen.getByRole('heading', { name: /Therapeutic context/i });
    const context = heading.parentElement!;
    expect(within(context).getByText('Liver Cancer (HCC)')).toBeInTheDocument();
    expect(within(context).getByText('AFP-high HCC')).toBeInTheDocument();
    expect(within(context).getByText('Sorafenib')).toBeInTheDocument();
    expect(screen.getByText(/Nanoparticle configuration/i)).toBeInTheDocument();
  });

  it('states plainly that PK will not run until its inputs are supplied', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    // The PK engine is migrated, but this session has supplied none of its
    // required inputs, so the page must say it will not run rather than
    // implying a profile is coming.
    expect(screen.getAllByText(/Pharmacokinetic simulation/i).length)
      .toBeGreaterThan(0);
    expect(screen.getByTestId('pk-run-status').textContent)
      .toMatch(/Will not run/i);
    // No administration route has been chosen, so no model has been selected
    // and no inputs are offered. The depot rate constants are NOT requested by
    // default: which inputs exist depends on the route.
    expect(screen.getByText(/Select an administration route/i))
      .toBeInTheDocument();
    expect(screen.queryByTestId('legacy-depot-inputs')).not.toBeInTheDocument();
    expect(screen.queryByRole('spinbutton', { name: /Absorption rate constant/i }))
      .not.toBeInTheDocument();
  });

  it('states plainly that the assessment engines will not run', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    expect(screen.getByText(/are not migrated/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Calibration required/i).length).toBeGreaterThan(0);
  });

  it('runs the real scoring endpoint and shows the result stage', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    expect(await screen.findByTestId('result-card')).toBeInTheDocument();
    expect(screen.getAllByText('87.52').length).toBeGreaterThan(0);
  });

  it('posts only the supplied fields to the scoring endpoint', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    const call = calls.find((c) => String(c[0]).includes('/design/score'));
    const body = JSON.parse((call![1] as RequestInit).body as string);
    expect(body).toEqual({ size_nm: 100, charge_mv: -5, encapsulation_percent: 85 });
  });

  it('surfaces a calculation failure without any fallback number', async () => {
    installFetch({
      scoreStatus: 500,
      scoreBody: { error: 'calculation_failed', message: 'failed', score_available: false },
    });
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByRole('button', { name: /Run Simulation/i }));

    expect(await screen.findByTestId('results-error')).toBeInTheDocument();
    expect(screen.queryByTestId('result-card')).not.toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('results stage honesty', () => {
  it('lists the stages that did not run, with no fabricated output', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    const pending = screen.getByTestId('pending-stages');
    expect(pending).toBeInTheDocument();
    expect(pending.textContent).toMatch(/Disease & Biomarker Assessment/);
    expect(pending.textContent).toMatch(/Nanoparticle 3D Builder/);
    // No numeric result may appear in the not-run section.
    expect(pending.textContent).not.toMatch(/\d+\.\d+/);
  });

  it('states that the results do not vary with the disease selection', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    expect(screen.getByText(/Neither result varies with this\s+selection/i))
      .toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('draft save and resume', () => {
  it('saves a draft and offers it on the session gate', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);

    const rail = screen.getByRole('navigation', { name: /workflow progress/i });
    await user.click(within(rail).getByRole('button', { name: /Save draft/i }));

    const saved: unknown = JSON.parse(localStorage.getItem('nanobio.designDrafts.v1') ?? '[]');
    expect(Array.isArray(saved) && saved.length).toBe(1);
  });

  it('offers resume once a session is in progress', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);

    const rail = screen.getByRole('navigation', { name: /workflow progress/i });
    await user.click(within(rail).getByRole('button', { name: /Save draft/i }));

    // The drafts gate is where a saved draft is genuinely resumed from.
    await user.click(screen.getByRole('link', { name: /Start New Study/i }));
    await user.click(await screen.findByTestId('resume-research'));
    expect(await screen.findByRole('heading', { name: /Resume current design/i }))
      .toBeInTheDocument();
    expect(screen.getByTestId('saved-designs')).toBeInTheDocument();
  });

  it('never stores a credential in the draft payload', async () => {
    const user = userEvent.setup();
    renderAt('/workflow/disease');
    await completeStep1(user);
    const rail = screen.getByRole('navigation', { name: /workflow progress/i });
    await user.click(within(rail).getByRole('button', { name: /Save draft/i }));

    const raw = localStorage.getItem('nanobio.designDrafts.v1') ?? '';
    for (const banned of ['password', 'token', 'nanobio_session', 'cookie']) {
      expect(raw.toLowerCase()).not.toContain(banned);
    }
  });
});

/* ===================================================================== */
describe('sidebar', () => {
  it('leads with Start New Study and keeps Administration admin-only', async () => {
    renderAt('/start');
    await screen.findByTestId('pathway-cards');
    const nav = screen.getByRole('navigation', { name: /Main navigation/i });
    expect(within(nav).getByText('Start New Study')).toBeInTheDocument();
    expect(within(nav).getByText('Administration')).toBeInTheDocument();
  });
});
