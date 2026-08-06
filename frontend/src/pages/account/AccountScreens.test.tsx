/**
 * The account security screens, tested against the behaviours that matter.
 *
 * These are not "does it render" tests. Each one pins a decision that would be
 * a real defect if it were reversed — a link consumed by a rejected password,
 * an enumeration oracle on the forgotten-password form, a revoke control on
 * the user's own session row, or a password appearing anywhere an
 * administrator can reach it.
 *
 * Every denial has a positive control beside it, so a screen that renders
 * nothing at all cannot pass by refusing everything.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AccountSecurityPage from './AccountSecurityPage';
import ForgotPasswordPage from './ForgotPasswordPage';
import SetPasswordPage from './SetPasswordPage';
import { AccountsPanel } from '../organization/AccountsPanel';
import type { Member } from '../../api/organizationClient';

/* ------------------------------------------------------------------------ */
/* Harness                                                                   */
/* ------------------------------------------------------------------------ */

const authState = {
  user: { id: 1, username: 'r.chen', role: 'researcher', email: null, full_name: null },
  signOut: vi.fn(async () => {}),
};

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => authState,
}));

/** Captures every fetch so tests can assert on what was *not* sent, too. */
let requests: Array<{ url: string; method: string; body: unknown }> = [];
let responder: (url: string, method: string, body: unknown) =>
  { status: number; body: unknown };

beforeEach(() => {
  requests = [];
  responder = () => ({ status: 200, body: {} });

  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();
    const method = (init?.method ?? 'GET').toUpperCase();
    const body = init?.body ? JSON.parse(init.body as string) : null;
    requests.push({ url, method, body });

    const result = responder(url, method, body);
    return new Response(JSON.stringify(result.body), {
      status: result.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

const POLICY = {
  min_length: 12,
  max_length: 1024,
  rules: ['At least 12 characters', 'Not a commonly used password'],
};

function renderAt(path: string, element: React.ReactElement, route: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={route} element={element} />
        <Route path="/login" element={<p>Sign in page</p>} />
        <Route path="/account/forgot" element={<p>Forgot page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

/* ======================================================================== */
/* 1. Activation                                                             */
/* ======================================================================== */

describe('activation through a one-time link', () => {

  it('sends the token from the query string and nothing else', async () => {
    responder = (url) => url.includes('password-policy')
      ? { status: 200, body: POLICY }
      : { status: 200, body: { username: 'r.chen' } };

    renderAt('/account/activate?token=live-activation-token',
             <SetPasswordPage mode="activate" />, '/account/activate');

    await userEvent.type(screen.getByLabelText(/^New password/i),
                         'tumour-margin-assay-14');
    await userEvent.type(screen.getByLabelText(/Confirm new password/i),
                         'tumour-margin-assay-14');
    await userEvent.click(screen.getByTestId('submit-password'));

    // Appears as both the page heading and the alert title, so match the
    // heading specifically rather than asserting there is exactly one.
    await screen.findByTestId('account-page-title');
    expect(screen.getByTestId('account-page-title'))
      .toHaveTextContent(/Your account is active/i);

    // The body as it goes ON THE WIRE. Asserting the client's own argument
    // shape here would have passed against a backend that rejects every field
    // name it sends — which is exactly what happened.
    const call = requests.find((r) => r.url.includes('/account/activate'));
    expect(call?.body).toEqual({
      token: 'live-activation-token',
      password: 'tumour-margin-assay-14',
      confirm_password: 'tumour-margin-assay-14',
    });
  });

  it('keeps the form usable when the password is rejected, so the link is not spent',
     async () => {
    // The defect this guards: a user types something too short, is told so,
    // and finds their link dead — with no way back except asking an
    // administrator who will assume they did something wrong.
    responder = (url) => url.includes('password-policy')
      ? { status: 200, body: POLICY }
      : {
          status: 400,
          body: { detail: { error: 'password_too_short',
                            message: 'Use at least 12 characters.' } },
        };

    renderAt('/account/activate?token=still-live',
             <SetPasswordPage mode="activate" />, '/account/activate');

    await userEvent.type(screen.getByLabelText(/^New password/i), 'short');
    await userEvent.type(screen.getByLabelText(/Confirm new password/i), 'short');
    await userEvent.click(screen.getByTestId('submit-password'));

    await screen.findByTestId('password-rejected');

    // The form is still there, with the token intact, and says so.
    expect(screen.getByTestId('submit-password')).toBeInTheDocument();
    expect(screen.getByLabelText(/^New password/i)).toBeInTheDocument();
    expect(screen.getByTestId('password-rejected'))
      .toHaveTextContent(/link is still valid/i);
    // And it is NOT presented as a dead link.
    expect(screen.queryByTestId('link-unusable')).not.toBeInTheDocument();
  });

  it('gives one message for expired, used, replaced and never-valid links',
     async () => {
    // Distinguishing them would tell whoever holds the link that it was once
    // real, which tells them the account exists.
    for (const scenario of ['expired', 'already used', 'superseded', 'forged']) {
      responder = (url) => url.includes('password-policy')
        ? { status: 200, body: POLICY }
        : {
            status: 400,
            body: { detail: { error: 'invalid_token',
                              message: 'This link cannot be used.' } },
          };

      const { unmount } = renderAt(
        `/account/activate?token=${scenario}`,
        <SetPasswordPage mode="activate" />, '/account/activate');

      await userEvent.type(screen.getByLabelText(/^New password/i),
                           'tumour-margin-assay-14');
      await userEvent.type(screen.getByLabelText(/Confirm new password/i),
                           'tumour-margin-assay-14');
      await userEvent.click(screen.getByTestId('submit-password'));

      const notice = await screen.findByTestId('link-unusable');
      expect(notice).toHaveTextContent(/cannot be used/i);
      // No hint about which of the four it was.
      expect(notice).not.toHaveTextContent(/no such account|does not exist|never/i);
      unmount();
    }
  });

  it('asks for a link rather than failing obscurely when none is present', () => {
    renderAt('/account/activate', <SetPasswordPage mode="activate" />,
             '/account/activate');
    expect(screen.getByText(/This page needs a link/i)).toBeInTheDocument();
    expect(screen.queryByTestId('submit-password')).not.toBeInTheDocument();
  });

  it('warns a signed-in user that the link ends their session', async () => {
    responder = () => ({ status: 200, body: POLICY });
    renderAt('/account/reset?token=t', <SetPasswordPage mode="reset" />,
             '/account/reset');
    expect(await screen.findByText(/already signed in/i)).toBeInTheDocument();
  });
});

/* ======================================================================== */
/* 2. Forgotten password                                                     */
/* ======================================================================== */

describe('forgotten-password request', () => {

  it('shows the same confirmation whether or not the account exists', async () => {
    const notice =
      'If an account exists for that username, a reset link has been sent.';
    responder = () => ({ status: 200,
                         body: { requested: true, message: notice } });

    for (const username of ['r.chen', 'definitely-not-a-user']) {
      const { unmount } = renderAt('/account/forgot', <ForgotPasswordPage />,
                                   '/account/forgot');
      await userEvent.type(screen.getByLabelText(/Username/i), username);
      await userEvent.click(screen.getByTestId('request-reset'));

      const confirmation = await screen.findByTestId('forgot-confirmation');
      expect(confirmation).toHaveTextContent(notice);
      expect(confirmation).not.toHaveTextContent(/not found|no such|unknown/i);
      unmount();
    }
  });

  it('renders the backend notice verbatim rather than composing its own',
     async () => {
    // A screen that wrote its own confirmation could drift into revealing
    // something the backend deliberately does not say.
    responder = () => ({
      status: 200,
      body: { requested: true,
              message: 'A distinctive server-authored sentence.' },
    });

    renderAt('/account/forgot', <ForgotPasswordPage />, '/account/forgot');
    await userEvent.type(screen.getByLabelText(/Username/i), 'anyone');
    await userEvent.click(screen.getByTestId('request-reset'));

    expect(await screen.findByTestId('forgot-confirmation'))
      .toHaveTextContent('A distinctive server-authored sentence.');
  });
});

/* ======================================================================== */
/* 3. Sessions                                                               */
/* ======================================================================== */

const SESSIONS = {
  sessions: [
    {
      handle: 'this-one', is_current: true,
      created_at: '2026-08-01T09:00:00Z',
      last_activity_at: '2026-08-01T11:00:00Z',
      expires_at: null, ip_address: '10.0.0.1',
      user_agent: 'Mozilla/5.0 (Windows NT 10.0) Chrome/126',
    },
    {
      handle: 'other-one', is_current: false,
      created_at: '2026-07-30T09:00:00Z',
      last_activity_at: '2026-07-30T10:00:00Z',
      expires_at: null, ip_address: '203.0.113.9',
      user_agent: 'Mozilla/5.0 (iPhone) Safari/604',
    },
  ],
};

function sessionResponder(url: string, method: string) {
  if (url.includes('/account/sessions') && method === 'GET') {
    return { status: 200, body: SESSIONS };
  }
  if (url.includes('/security-activity')) {
    return {
      status: 200,
      body: { events: [
        { id: 1, event: 'login_success', created_at: '2026-08-01T09:00:00Z',
          ip_address: '10.0.0.1', user_agent: null, detail: null },
        { id: 2, event: 'login_failure', created_at: '2026-07-31T22:14:00Z',
          ip_address: '203.0.113.9', user_agent: null, detail: null },
      ] },
    };
  }
  if (url.includes('/sessions/revoke-all')) {
    return { status: 200, body: { sessions_ended: 1 } };
  }
  if (url.includes('/sessions/revoke')) {
    return { status: 200, body: { revoked: true } };
  }
  if (url.includes('/account/password')) {
    return { status: 200, body: { changed: true, other_sessions_ended: 1 } };
  }
  return { status: 200, body: {} };
}

describe('active sessions', () => {

  beforeEach(() => { responder = sessionResponder; });

  it('marks the current session and offers no revoke control for it', async () => {
    render(<MemoryRouter><AccountSecurityPage /></MemoryRouter>);

    const current = await screen.findByTestId('session-current');
    expect(within(current).getByTestId('current-session-badge'))
      .toHaveTextContent(/this device/i);

    // The row for this session offers sign-out, never "revoke" — revoking
    // rows until the list looks right is how somebody ends their own session
    // by accident, mid-investigation.
    expect(within(current).getByTestId('sign-out-this-session')).toBeInTheDocument();
    expect(within(current).queryByTestId('revoke-session')).not.toBeInTheDocument();

    // Positive control: the *other* row does have one.
    const other = screen.getByTestId('session-other');
    expect(within(other).getByTestId('revoke-session')).toBeInTheDocument();
  });

  it('describes each session well enough to recognise it', async () => {
    render(<MemoryRouter><AccountSecurityPage /></MemoryRouter>);

    const other = await screen.findByTestId('session-other');
    expect(other).toHaveTextContent(/Safari on iOS/i);
    expect(other).toHaveTextContent('203.0.113.9');
  });

  it('requires a typed confirmation before revoking another session', async () => {
    render(<MemoryRouter><AccountSecurityPage /></MemoryRouter>);

    const other = await screen.findByTestId('session-other');
    await userEvent.click(within(other).getByTestId('revoke-session'));

    // Nothing is sent on the click alone.
    expect(requests.some((r) => r.url.includes('/sessions/revoke'))).toBe(false);

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent(/change your password as well/i);

    await userEvent.type(within(dialog).getByRole('textbox'), 'r.chen');
    await userEvent.click(within(dialog).getByRole('button', { name: /sign out/i }));

    await waitFor(() => {
      const call = requests.find((r) =>
        r.url.includes('/sessions/revoke') && r.method === 'POST');
      expect(call?.body).toEqual({ handle: 'other-one' });
    });
  });

  it('signs out everywhere else and says the current session survived',
     async () => {
    render(<MemoryRouter><AccountSecurityPage /></MemoryRouter>);

    await screen.findByTestId('session-list');
    await userEvent.click(screen.getByTestId('sign-out-everywhere'));

    const dialog = await screen.findByRole('dialog');
    await userEvent.type(within(dialog).getByRole('textbox'), 'r.chen');
    await userEvent.click(
      within(dialog).getByRole('button', { name: /sign out everywhere else/i }));

    const notice = await screen.findByTestId('session-action-notice');
    expect(notice).toHaveTextContent(/still signed in here/i);
    expect(requests.some((r) => r.url.includes('/sessions/revoke-all'))).toBe(true);
  });

  it('renders recent security activity in words, not event codes', async () => {
    render(<MemoryRouter><AccountSecurityPage /></MemoryRouter>);

    const table = await screen.findByTestId('security-activity');
    expect(table).toHaveTextContent(/Signed in/);
    expect(table).toHaveTextContent(/Failed sign-in attempt/);
    expect(table).not.toHaveTextContent('login_success');
  });
});

/* ======================================================================== */
/* 4. Password change                                                        */
/* ======================================================================== */

describe('changing your own password', () => {

  beforeEach(() => { responder = sessionResponder; });

  it('states that this session survives and the others did not', async () => {
    render(<MemoryRouter><AccountSecurityPage /></MemoryRouter>);
    await screen.findByTestId('session-list');

    await userEvent.type(screen.getByLabelText(/Current password/i), 'old-passphrase-here');
    await userEvent.type(screen.getByLabelText(/^New password/i), 'tumour-margin-assay-14');
    await userEvent.type(screen.getByLabelText(/Confirm new password/i), 'tumour-margin-assay-14');
    await userEvent.click(screen.getByTestId('submit-password-change'));

    const notice = await screen.findByTestId('password-change-notice');
    expect(notice).toHaveTextContent(/1 other session was signed out/i);
    expect(notice).toHaveTextContent(/still signed in here/i);
  });

  it('never sends the password anywhere but the change endpoint', async () => {
    render(<MemoryRouter><AccountSecurityPage /></MemoryRouter>);
    await screen.findByTestId('session-list');

    await userEvent.type(screen.getByLabelText(/Current password/i), 'old-passphrase-here');
    await userEvent.type(screen.getByLabelText(/^New password/i), 'tumour-margin-assay-14');
    await userEvent.type(screen.getByLabelText(/Confirm new password/i), 'tumour-margin-assay-14');
    await userEvent.click(screen.getByTestId('submit-password-change'));

    await screen.findByTestId('password-change-notice');

    const leaked = requests.filter(
      (r) => !r.url.includes('/account/password')
        && JSON.stringify(r.body ?? '').includes('tumour-margin-assay-14'));
    expect(leaked).toEqual([]);
  });
});

/* ======================================================================== */
/* 5. Administrative screens                                                 */
/* ======================================================================== */

const MEMBER: Member = {
  id: 1, user_id: 42, username: 'new.colleague', role: 'RESEARCHER',
  is_administrative: false, scope: 'INTERNAL', status: 'ACTIVE',
  is_active: true, starts_at: null, expires_at: null,
  external_organization: null, is_external: false,
  may_download_attachments: true, created_at: '2026-07-01T00:00:00Z',
  ended_at: null, end_reason: null, revision: 1, assignable_study_roles: [],
};

function adminResponder(state: string) {
  return (url: string, method: string) => {
    if (method === 'GET') {
      return {
        status: 200,
        body: {
          user_id: 42, username: 'new.colleague',
          email: 'new.colleague@example.test', state,
          state_reason: null, must_set_password: state === 'pending_activation',
          last_login_at: null, password_algorithm: 'argon2id',
          activation: { state: state === 'pending_activation' ? 'recorded' : 'accepted' },
          password_reset: { state: 'none' },
          notice: 'There is no way to view or set this account password.',
        },
      };
    }
    if (url.includes('/activation') || url.includes('/reset')) {
      // The real field names. The API names the link by purpose —
      // `activation_link` / `reset_link` — and a fixture that invented a
      // single `link` key was what let a mismatched client pass this test
      // while rendering an empty code block against a live server.
      return {
        status: 200,
        body: {
          delivery_status: 'recorded', delivery_provider: 'recorded',
          expires_at: '2026-08-10T00:00:00Z', link_shown_once: true,
          activation_link:
            'https://studio.example.test/account/activate?token=one-time-value',
          reset_link:
            'https://studio.example.test/account/reset?token=one-time-value',
        },
      };
    }
    return { status: 200, body: { user_id: 42, state: 'suspended', sessions_ended: 2 } };
  };
}

function renderPanel() {
  return render(
    <MemoryRouter>
      <AccountsPanel organizationId={7} members={[MEMBER]} canAdminister
                     onChanged={() => {}} />
    </MemoryRouter>,
  );
}

describe('administrative account screens', () => {

  it('offers no way to see, set or copy a password', async () => {
    responder = adminResponder('active');
    const { container } = renderPanel();

    await userEvent.click(screen.getByTestId('open-account'));
    await screen.findByTestId('account-state');

    const text = container.textContent ?? '';
    expect(text).toMatch(/cannot see, set,\s*recover or copy/i);
    expect(screen.queryByText(/show password/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^set password/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('no-password-control'))
      .toHaveTextContent(/no way to view or set this account password/i);
  });

  it('shows a newly issued link once, with a warning that it cannot be recovered',
     async () => {
    responder = adminResponder('pending_activation');
    renderPanel();

    await userEvent.click(screen.getByTestId('open-account'));
    await userEvent.click(await screen.findByTestId('reissue-activation'));

    const issued = await screen.findByTestId('issued-link');
    expect(issued).toHaveTextContent(/only time\s*it will be displayed/i);
    expect(issued).toHaveTextContent(/no way to retrieve it/i);
    expect(screen.getByTestId('one-time-link'))
      .toHaveTextContent('token=one-time-value');
  });

  it('distinguishes account state from membership state', async () => {
    // The confusion that locks a collaborator out of their own institution:
    // an administrator suspends the *account* to remove somebody from one
    // organization's work.
    responder = adminResponder('active');
    renderPanel();

    await userEvent.click(screen.getByTestId('open-account'));
    await screen.findByTestId('account-state');

    expect(screen.getByTestId('membership-status')).toHaveTextContent(/Active/);
    await userEvent.click(screen.getByTestId('suspend-account'));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent(/whole account, not just this organization/i);
    expect(dialog).toHaveTextContent(/end their membership instead/i);
  });

  it('says that suspension preserves scientific attribution', async () => {
    responder = adminResponder('active');
    renderPanel();

    await userEvent.click(screen.getByTestId('open-account'));
    await screen.findByTestId('account-state');
    await userEvent.click(screen.getByTestId('disable-account'));

    expect(await screen.findByRole('dialog'))
      .toHaveTextContent(/every experiment, review and approval — is kept/i);
  });

  it('describes every one of the six account states', async () => {
    // The wire values, lowercase. Typing these in uppercase is exactly the
    // mistake that made the panel crash for every account.
    const states = ['pending_activation', 'active', 'suspended', 'disabled',
                    'deletion_pending', 'deleted'] as const;

    for (const state of states) {
      responder = adminResponder(state);
      const { unmount } = renderPanel();

      await userEvent.click(screen.getByTestId('open-account'));
      const meaning = await screen.findByTestId('account-state-meaning');
      expect(meaning.textContent ?? '').not.toBe('');
      expect(screen.getByTestId('account-state').textContent ?? '')
        .not.toBe(state);   // a label, not the raw enum name
      unmount();
    }
  });

  it('shows only the actions that make sense for the state', async () => {
    responder = adminResponder('pending_activation');
    const { unmount } = renderPanel();
    await userEvent.click(screen.getByTestId('open-account'));
    await screen.findByTestId('account-state');

    // Nothing to reset — there is no password yet.
    expect(screen.getByTestId('reissue-activation')).toBeInTheDocument();
    expect(screen.queryByTestId('initiate-reset')).not.toBeInTheDocument();
    unmount();

    responder = adminResponder('suspended');
    renderPanel();
    await userEvent.click(screen.getByTestId('open-account'));
    await screen.findByTestId('account-state');

    expect(screen.getByTestId('restore-account')).toBeInTheDocument();
    expect(screen.queryByTestId('suspend-account')).not.toBeInTheDocument();
  });

  it('hides administrative controls from a non-administrator', () => {
    render(
      <MemoryRouter>
        <AccountsPanel organizationId={7} members={[MEMBER]}
                       canAdminister={false} onChanged={() => {}} />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('open-account')).not.toBeInTheDocument();
    expect(screen.getByText(/managed by this organization's/i)).toBeInTheDocument();
  });
});
