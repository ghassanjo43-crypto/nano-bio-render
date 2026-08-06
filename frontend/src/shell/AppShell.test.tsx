/**
 * Tests for the application shell: authentication, routing, guards, menu and
 * the honesty rules on the dashboard and placeholders.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};
const RESEARCHER: UserProfile = { ...ADMIN, id: 2, username: 'rlee',
  full_name: 'R. Lee', role: 'researcher', email: null };

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

interface FakeServer {
  profile: UserProfile | null;
  loginResult?: { status: number; body: unknown };
}

function installFetch(server: FakeServer) {
  const calls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      if (url.endsWith('/health')) return json({ status: 'healthy' });
      if (url.endsWith('/api/v1/auth/me')) {
        return server.profile ? json(server.profile) : json({ detail: 'no' }, 401);
      }
      if (url.endsWith('/api/v1/auth/login')) {
        if (server.loginResult) {
          return json(server.loginResult.body, server.loginResult.status);
        }
        const body = JSON.parse(String(init?.body ?? '{}'));
        if (body.password === 'correct-horse-battery') {
          server.profile = ADMIN;
          return json({ user: ADMIN, session_expires_at: '2026-07-31T00:00:00Z',
                        idle_timeout_minutes: 30 });
        }
        return json({ error: 'invalid_credentials',
                      message: 'Invalid username or password.' }, 401);
      }
      if (url.endsWith('/api/v1/auth/logout')) {
        server.profile = null;
        return json({ detail: 'Signed out.' });
      }
      if (url.endsWith('/api/v1/design/score')) {
        if (!server.profile) return json({ detail: 'no' }, 401);
        return json({
          design_impact_score: { delivery: 87.52475247524752, toxicity: 0.8, cost: 80.75 },
          score_version: 'design-impact-adapter-0.1.0',
          component_scores: {
            delivery: { value: 87.52475247524752, scale: '0-100', meaning: 'd' },
            toxicity: { value: 0.8, scale: '0-10', meaning: 't' },
            cost: { value: 80.75, scale: '0-100', meaning: 'c' },
          },
          normalized_inputs: { Size: 100 },
          warnings: [],
          prediction_basis: 'rule_based_physicochemical_heuristic',
          evidence_level: 'literature_informed_unvalidated',
          validation_status: 'not_experimentally_validated',
          limitations: ['Computational research-planning result only.'],
          scientific_source: 'core.scoring.compute_impact',
        });
      }
      return json({}, 404);
    }),
  );
  return calls;
}

function renderApp(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// =========================================================================
describe('unauthenticated access', () => {
  beforeEach(() => installFetch({ profile: null }));

  it('redirects a protected route to the login page', async () => {
    renderApp('/dashboard');
    expect(await screen.findByRole('heading', { name: /Sign in/i })).toBeInTheDocument();
  });

  it('redirects the root path to login when signed out', async () => {
    renderApp('/');
    expect(await screen.findByRole('heading', { name: /Sign in/i })).toBeInTheDocument();
  });

  it('never shows default credentials on the login page', async () => {
    const { container } = renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });
    const text = container.textContent ?? '';
    expect(text).not.toMatch(/admin\s*\/\s*admin/i);
    expect(text).not.toMatch(/demo account/i);
  });

  it('shows the research-use notice and a working reset link', async () => {
    // This assertion used to require the words "coming soon". The reset
    // workflow now exists, so the placeholder it was pinning would be a
    // dead end telling users to email an administrator for something they
    // can do themselves.
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });
    expect(screen.getByText(/Computational research use only/i)).toBeInTheDocument();

    const link = screen.getByTestId('forgot-password-link');
    expect(link).toHaveAttribute('href', '/account/forgot');
    expect(screen.getByTestId('reset-note')).not.toHaveTextContent(/coming soon/i);
  });

  it('does not render the application shell', async () => {
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });
    expect(screen.queryByTestId('user-menu-button')).not.toBeInTheDocument();
  });
});

// =========================================================================
describe('login', () => {
  it('signs in successfully and lands on the pathway chooser', async () => {
    installFetch({ profile: null });
    const user = userEvent.setup();
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });

    await user.type(screen.getByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: /^Sign In$/i }));

    // The landing is the pathway chooser: the first question is which of the
    // three pathways the study begins from, not a dashboard of activity.
    expect(await screen.findByRole('heading',
      { name: /How would you like to begin\?/i })).toBeInTheDocument();
    expect(screen.getByTestId('user-name')).toHaveTextContent('Platform Administrator');
  });

  it('shows a generic message on bad credentials and stays on login', async () => {
    installFetch({ profile: null });
    const user = userEvent.setup();
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });

    await user.type(screen.getByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: /^Sign In$/i }));

    const alert = await screen.findByTestId('auth-error');
    expect(alert).toHaveTextContent(/Invalid username or password/i);
    expect(screen.getByRole('heading', { name: /Sign in/i })).toBeInTheDocument();
  });

  it('surfaces rate limiting', async () => {
    installFetch({
      profile: null,
      loginResult: {
        status: 429,
        body: { error: 'rate_limited',
                message: 'Too many failed sign-in attempts. Try again in 15 minute(s).',
                retry_after_seconds: 900 },
      },
    });
    const user = userEvent.setup();
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });

    await user.type(screen.getByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: /^Sign In$/i }));

    expect(await screen.findByTestId('auth-error')).toHaveTextContent(/Too many failed/i);
    expect(screen.getByText(/Temporarily locked/i)).toBeInTheDocument();
  });

  it('reports an unavailable API distinctly', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/api/v1/auth/me')) return json({}, 401);
      throw new TypeError('Failed to fetch');
    }));
    const user = userEvent.setup();
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });

    await user.type(screen.getByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: /^Sign In$/i }));

    expect(await screen.findByTestId('auth-error')).toHaveTextContent(
      /Cannot reach the authentication service/i);
  });

  it('validates that both fields are provided', async () => {
    installFetch({ profile: null });
    const user = userEvent.setup();
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });

    await user.click(screen.getByRole('button', { name: /^Sign In$/i }));
    expect(await screen.findByText(/Enter your username\./i)).toBeInTheDocument();
    expect(screen.getByText(/Enter your password\./i)).toBeInTheDocument();
  });

  it('toggles password visibility', async () => {
    installFetch({ profile: null });
    const user = userEvent.setup();
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });

    const pw = screen.getByLabelText('Password') as HTMLInputElement;
    expect(pw.type).toBe('password');
    await user.click(screen.getByRole('button', { name: /Show password/i }));
    expect(pw.type).toBe('text');
  });
});

// =========================================================================
describe('session restoration and expiry', () => {
  it('restores the session on refresh without re-login', async () => {
    installFetch({ profile: ADMIN });
    renderApp('/workflow/disease');
    expect(await screen.findByRole('heading', { name: /Step 1 — Disease/i, level: 2 }))
      .toBeInTheDocument();
  });

  it('sends an expired session back to login', async () => {
    installFetch({ profile: null });   // server rejects /me
    renderApp('/dashboard');
    expect(await screen.findByRole('heading', { name: /Sign in/i })).toBeInTheDocument();
  });

  it('redirects an authenticated user away from /login', async () => {
    installFetch({ profile: ADMIN });
    renderApp('/login');
    expect(await screen.findByRole('heading',
      { name: /How would you like to begin\?/i })).toBeInTheDocument();
  });
});

// =========================================================================
describe('logout', () => {
  it('signs out and returns to the login page', async () => {
    installFetch({ profile: ADMIN });
    const user = userEvent.setup();
    renderApp('/dashboard');
    await screen.findByRole('heading', { name: /Welcome/i });

    await user.click(screen.getByTestId('user-menu-button'));
    await user.click(screen.getByTestId('logout-button'));
    // The redesign adds a confirmation dialog before signing out.
    await user.click(await screen.findByTestId('confirm-logout'));

    expect(await screen.findByRole('heading', { name: /Sign in/i })).toBeInTheDocument();
  });
});

// =========================================================================
describe('navigation menu', () => {
  it('shows every menu entry for an administrator', async () => {
    installFetch({ profile: ADMIN });
    renderApp('/dashboard');
    await screen.findByRole('heading', { name: /Welcome/i });

    const nav = screen.getByRole('navigation', { name: /Main navigation/i });
    for (const label of ['Home', 'Start New Study', 'Demo Workspace',
      'My Studies', 'Patient Assessments', 'Research Designs',
      'Simulation History', 'Compare Results', 'Projects', 'Reports',
      'Nanoparticle Design', 'Pharmacokinetic Simulation',
      'Nanoparticle 3D Builder', 'Protocol Generator',
      'AI Co-Designer', 'ML Training', 'Evidence & Validation',
      'Administration', 'Settings', 'Help & Tutorial']) {
      expect(within(nav).getByText(label)).toBeInTheDocument();
    }
  });

  it('hides Administration from non-admin roles', async () => {
    installFetch({ profile: RESEARCHER });
    renderApp('/dashboard');
    await screen.findByRole('heading', { name: /Welcome/i });

    const nav = screen.getByRole('navigation', { name: /Main navigation/i });
    expect(within(nav).queryByText('Administration')).not.toBeInTheDocument();
    expect(within(nav).getByText('Start New Study')).toBeInTheDocument();
  });

  it('navigates to the pathway chooser', async () => {
    installFetch({ profile: ADMIN });
    const user = userEvent.setup();
    renderApp('/dashboard');
    await screen.findByRole('heading', { name: /Welcome/i });

    const nav = screen.getByRole('navigation', { name: /Main navigation/i });
    await user.click(within(nav).getByText('Start New Study'));

    // The menu entry opens the pathway chooser, from which every study begins.
    expect(await screen.findByTestId('pathway-cards')).toBeInTheDocument();
  });

  it('groups the menu into the five declared sections', async () => {
    installFetch({ profile: ADMIN });
    renderApp('/dashboard');
    await screen.findByRole('heading', { name: /Welcome/i });

    const nav = screen.getByRole('navigation', { name: /Main navigation/i });
    for (const label of ['Start', 'Workspace', 'Scientific Tools',
                         'Intelligence', 'System']) {
      expect(within(nav).getByText(label)).toBeInTheDocument();
    }
  });
});

// =========================================================================
describe('role-based access control', () => {
  it('allows an admin into /admin', async () => {
    installFetch({ profile: ADMIN });
    renderApp('/admin');
    // The label appears in the header title and in the module panel; assert on
    // the panel, which only renders when access was granted.
    const panel = await screen.findByTestId('module-placeholder');
    expect(within(panel).getByRole('heading', { name: /Administration/i }))
      .toBeInTheDocument();
  });

  it('blocks a researcher from /admin', async () => {
    installFetch({ profile: RESEARCHER });
    renderApp('/admin');
    expect(await screen.findByTestId('unauthorized')).toBeInTheDocument();
  });
});

// =========================================================================
describe('not found', () => {
  it('renders a not-found page for an unknown route', async () => {
    installFetch({ profile: ADMIN });
    renderApp('/no-such-page');
    expect(await screen.findByTestId('not-found')).toBeInTheDocument();
  });
});

// =========================================================================
describe('scoring workflow after login', () => {
  it('calculates a real score through the authenticated shell', async () => {
    installFetch({ profile: ADMIN });
    const user = userEvent.setup();
    renderApp('/workflow/disease');
    await screen.findByRole('heading', { name: /Step 1 — Disease/i, level: 2 });

    // Step 1 -> 2 -> 3 -> run.
    await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                             'Liver Cancer (HCC)');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Disease subtype' }),
                             'AFP-high HCC');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Therapeutic agent' }),
                             'Sorafenib');
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByRole('button', { name: /Run Simulation/i }));

    expect(await screen.findByTestId('result-card')).toBeInTheDocument();
    expect(screen.getAllByText('87.52').length).toBeGreaterThan(0);
  });
});

// =========================================================================
describe('no fabricated data', () => {
  it('dashboard shows honest empty activity, not sample rows', async () => {
    installFetch({ profile: ADMIN });
    renderApp('/dashboard');
    await screen.findByRole('heading', { name: /Welcome/i });

    const activity = screen.getByTestId('activity-empty');
    expect(activity).toHaveTextContent(/No activity recorded/i);
    expect(activity.textContent).not.toMatch(/\d{2,}/);
  });

  it('dashboard invents no counts or success rates', async () => {
    installFetch({ profile: ADMIN });
    const { container } = renderApp('/dashboard');
    await screen.findByRole('heading', { name: /Welcome/i });

    const text = container.textContent ?? '';
    expect(text).not.toMatch(/success rate/i);
    expect(text).not.toMatch(/\d+\s*(projects|simulations)\s+(completed|run)/i);
    // the only counts are module availability, which is derived from the menu
    expect(screen.getByTestId('migration-progress')).toHaveTextContent(
      /\d+ of \d+ modules available/);
  });

  it('AI Co-Designer stays unavailable with no restored candidates', async () => {
    installFetch({ profile: ADMIN });
    const { container } = renderApp('/ai-co-designer');
    await screen.findByTestId('module-placeholder');

    expect(screen.getByTestId('module-status')).toHaveTextContent(/Not yet operational/i);
    expect(screen.getByTestId('ai-notice')).toBeInTheDocument();

    const text = container.textContent ?? '';
    for (const banned of ['94.2', '91.5', '89.8', '87.3', '84.9', '387']) {
      expect(text).not.toContain(banned);
    }
  });

  it('placeholder modules show no scores or charts', async () => {
    installFetch({ profile: ADMIN });
    const { container } = renderApp('/protocol');
    await screen.findByTestId('module-placeholder');

    expect(screen.getByTestId('module-status')).toHaveTextContent(/Migration in progress/i);
    const main = container.querySelector('.shell__content');
    expect(main!.textContent).not.toMatch(/\d+\.\d+/);
    expect(main!.querySelector('table')).toBeNull();
  });
});

// =========================================================================
describe('no sensitive client-side storage', () => {
  it('stores no credential in localStorage or sessionStorage', async () => {
    installFetch({ profile: null });
    const user = userEvent.setup();
    renderApp('/login');
    await screen.findByRole('heading', { name: /Sign in/i });

    await user.type(screen.getByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: /^Sign In$/i }));
    await screen.findByRole('heading', { name: /How would you like to begin\?/i });

    // The workflow stores a non-sensitive design-draft pointer, so the
    // assertion is now about CONTENT rather than emptiness: no credential,
    // token or cookie value may ever reach client storage. Authentication
    // still relies solely on the HttpOnly cookie.
    const dump = JSON.stringify([
      Object.entries({ ...localStorage }),
      Object.entries({ ...sessionStorage }),
    ]).toLowerCase();
    for (const banned of ['password', 'token', 'nanobio_session', 'secret', 'bearer']) {
      expect(dump).not.toContain(banned);
    }
    expect(sessionStorage.length).toBe(0);
  });

  it('sends credentials with API requests so the cookie is used', async () => {
    installFetch({ profile: ADMIN });
    const user = userEvent.setup();
    renderApp('/workflow/disease');
    await screen.findByRole('heading', { name: /Step 1 — Disease/i, level: 2 });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                             'Liver Cancer (HCC)');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Disease subtype' }),
                             'AFP-high HCC');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Therapeutic agent' }),
                             'Sorafenib');
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByTestId('pathway-continue'));
    await user.click(await screen.findByRole('button', { name: /Run Simulation/i }));
    await screen.findByTestId('result-card');

    const mock = globalThis.fetch as ReturnType<typeof vi.fn>;
    const call = mock.mock.calls.find((c) => String(c[0]).includes('/design/score'));
    expect((call![1] as RequestInit).credentials).toBe('include');
  });
});
