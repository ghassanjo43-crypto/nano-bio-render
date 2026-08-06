/**
 * Session-expiry handling.
 *
 * These exist because of a real report: a signed-in user left a tab open past
 * the 30-minute idle timeout, and the application went on presenting them as
 * signed in while every request returned 401. They saw "Sign in to continue."
 * inside a page they appeared to be authenticated on, with no route out but a
 * manual reload.
 *
 * The initial `/auth/me` check runs once at mount, so nothing else can notice
 * an expiry — a 401 from a data endpoint has to drive it.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from './AuthContext';
import { listScenarios, setUnauthorizedHandler } from '../api/client';
import type { UserProfile } from '../api/auth';

const USER: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

/** The exact 401 envelope FastAPI produces for an expired session. */
const EXPIRED = {
  detail: { error: 'not_authenticated', message: 'Sign in to continue.' },
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  setUnauthorizedHandler(null);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('the client notifies on 401', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => json(EXPIRED, 401)));
  });

  it('invokes the registered handler', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    await listScenarios();
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not invoke it for a non-401 failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      json({ error: 'server_error', message: 'boom' }, 500)));
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    await listScenarios();
    expect(handler).not.toHaveBeenCalled();
  });

  it('stops notifying once the handler is cleared', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    setUnauthorizedHandler(null);
    await listScenarios();
    expect(handler).not.toHaveBeenCalled();
  });
});

describe('an expired session signs the user out', () => {
  /**
   * Authenticated at mount, then every data request 401s — exactly what an
   * idle-timeout looks like to the browser.
   */
  function installExpiringFetch() {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) return json({ status: 'healthy' });
      if (url.endsWith('/api/v1/auth/me')) return json(USER);
      return json(EXPIRED, 401);
    }));
  }

  function renderAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider><App /></AuthProvider>
      </MemoryRouter>,
    );
  }

  it('lands on the login page instead of stranding the user', async () => {
    installExpiringFetch();
    renderAt('/demo');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('explains the sign-out rather than looking like a random logout', async () => {
    installExpiringFetch();
    renderAt('/demo');

    const notice = await screen.findByTestId('session-expired', {}, { timeout: 5000 });
    expect(notice.textContent).toMatch(/did not accept your session/i);
    expect(notice.textContent).toMatch(/Nothing was lost/i);
  });

  it('does not assert a cause the client cannot actually determine', async () => {
    // A 401 may be an idle timeout, an absolute expiry, a revoked session or a
    // cookie the browser declined to send. Claiming one specific cause would be
    // a statement the client has no evidence for.
    installExpiringFetch();
    renderAt('/demo');

    const notice = await screen.findByTestId('session-expired', {}, { timeout: 5000 });
    expect(notice.textContent).not.toMatch(/because the session had been idle/i);
  });

  it('does not strand the user on a page claiming they are signed in', async () => {
    installExpiringFetch();
    renderAt('/demo');

    await screen.findByTestId('session-expired', {}, { timeout: 5000 });
    // The shell, with its username chip and scenario cards, must be gone.
    expect(screen.queryByTestId('scenario-cards')).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: /Main navigation/i }))
      .not.toBeInTheDocument();
  });

  it('shows no expiry notice when simply arriving logged out', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) return json({ status: 'healthy' });
      return json(EXPIRED, 401);
    }));
    renderAt('/login');

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
    }, { timeout: 5000 });
    expect(screen.queryByTestId('session-expired')).not.toBeInTheDocument();
  });
});
