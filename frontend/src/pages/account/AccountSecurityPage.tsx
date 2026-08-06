/**
 * The signed-in user's own security screen.
 *
 * Three things, in the order somebody worried about their account needs them:
 * change the password, see where the account is signed in, and read what has
 * recently happened to it.
 *
 * The session list is the reason this page exists at all. "Am I signed in
 * somewhere I should not be?" is unanswerable without it, and until it is
 * answerable the honest advice to a worried user is to change their password
 * and hope. With it, they can look, recognise or fail to recognise a session,
 * and end that one specifically.
 *
 * Current-session identification is not decoration
 * -----------------------------------------------
 * The row for *this* session is marked, and its individual revoke control is
 * replaced by sign-out. Without that, the obvious way to end a suspicious
 * session is to revoke rows until the list looks right, and the row somebody
 * revokes by accident is their own — which logs them out mid-investigation and
 * teaches them the feature is dangerous.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  changePassword, listSessions, revokeAllSessions, revokeSession,
  securityActivity, type SecurityEvent, type SessionSummary,
} from '../../api/accountClient';
import { useAuth } from '../../auth/AuthContext';
import {
  Alert, Badge, Button, Card, PasswordField, SectionHeading,
} from '../../design-system/components';
import { ConfirmAction } from '../organization/ConfirmAction';
import './Account.css';

/** Security events, in words a user can act on rather than event codes. */
/**
 * Security events in words the account holder can act on.
 *
 * Keyed on the lowercase **wire** values of `AuthEvent`, not its Python member
 * names. Keying on the member names produced a table that never matched
 * anything, so every row fell through to the raw code — the exact opposite of
 * what this exists for, and invisible unless somebody looked at a real trail.
 *
 * Unlisted events fall through to a tidied form of their own name rather than
 * being hidden. A security trail that silently drops events it does not
 * recognise is worse than one that shows an ugly label.
 */
const EVENT_LABELS: Record<string, string> = {
  login_success: 'Signed in',
  login_failure: 'Failed sign-in attempt',
  logout: 'Signed out',
  logout_all: 'Signed out of all other sessions',
  session_expired: 'Session expired',
  session_revoked: 'Session ended',
  session_rotated: 'Session renewed at sign-in',
  rate_limited: 'Too many failed attempts — sign-in temporarily blocked',
  admin_created: 'Account created by an administrator',
  activation_issued: 'Activation link issued',
  activation_completed: 'Account activated',
  activation_revoked: 'Activation link withdrawn',
  password_reset_requested: 'Password reset link requested',
  password_reset_completed: 'Password reset completed',
  password_changed: 'Password changed',
  password_rehashed: 'Password re-secured with a stronger algorithm',
  account_state_changed: 'Account status changed',
  account_suspended: 'Account suspended',
  account_restored: 'Account access restored',
};

function describeEvent(event: string): string {
  return EVENT_LABELS[event]
    ?? event.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

function formatWhen(value: string | null): string {
  if (!value) return '—';
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return '—';
  return at.toLocaleString();
}

/**
 * Turn a user-agent string into something recognisable.
 *
 * Shown so a user can tell their own devices apart. Deliberately coarse: the
 * question being answered is "is one of these not me?", and a full UA string
 * is both unreadable and more fingerprint than the answer needs.
 */
function describeClient(userAgent: string | null): string {
  if (!userAgent) return 'Unknown device';
  const ua = userAgent.toLowerCase();
  const browser =
    ua.includes('edg/') ? 'Edge'
      : ua.includes('chrome/') && !ua.includes('chromium') ? 'Chrome'
        : ua.includes('firefox/') ? 'Firefox'
          : ua.includes('safari/') ? 'Safari'
            : 'Browser';
  const platform =
    ua.includes('windows') ? 'Windows'
      : ua.includes('mac os') ? 'macOS'
        : ua.includes('android') ? 'Android'
          : ua.includes('iphone') || ua.includes('ipad') ? 'iOS'
            : ua.includes('linux') ? 'Linux'
              : 'Unknown platform';
  return `${browser} on ${platform}`;
}

export default function AccountSecurityPage() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [events, setEvents] = useState<SecurityEvent[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [changing, setChanging] = useState(false);
  const [changeError, setChangeError] = useState<string | null>(null);
  const [changeNotice, setChangeNotice] = useState<string | null>(null);

  const [busyHandle, setBusyHandle] = useState<string | null>(null);
  // Which destructive action is awaiting confirmation, if any.
  const [confirming, setConfirming] = useState<
    { kind: 'all' } | { kind: 'one'; handle: string; client: string } | null
  >(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    const [sessionResult, activityResult] = await Promise.all([
      listSessions(signal),
      securityActivity(signal),
    ]);
    if (signal?.aborted) return;

    if (sessionResult.status === 'ok') setSessions(sessionResult.data.sessions);
    else setLoadError(sessionResult.error.message);

    if (activityResult.status === 'ok') setEvents(activityResult.data.events);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  /* --- password change -------------------------------------------------- */
  const submitPasswordChange = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();
    if (changing) return;

    setChanging(true);
    setChangeError(null);
    setChangeNotice(null);

    const result = await changePassword({
      current_password: current,
      password,
      confirmation,
    });
    setChanging(false);

    if (result.status !== 'ok') {
      setChangeError(result.error.message);
      return;
    }

    setCurrent('');
    setPassword('');
    setConfirmation('');
    const ended = result.data.other_sessions_ended;
    setChangeNotice(
      ended > 0
        ? `Your password has been changed. ${ended} other ${ended === 1 ? 'session was' : 'sessions were'} signed out. You are still signed in here.`
        : 'Your password has been changed. You are still signed in here.',
    );
    // The list changed underneath us.
    void load();
  }, [changing, confirmation, current, load, password]);

  /* --- session actions -------------------------------------------------- */
  const endSession = useCallback(async (handle: string) => {
    setBusyHandle(handle);
    setActionError(null);
    setActionNotice(null);

    const result = await revokeSession(handle);
    setBusyHandle(null);

    if (result.status !== 'ok') {
      setActionError(result.error.message);
      return;
    }
    setConfirming(null);
    setActionNotice('That session has been signed out.');
    void load();
  }, [load]);

  const endEverywhereElse = useCallback(async () => {
    setBusyHandle('all');
    setActionError(null);
    setActionNotice(null);

    const result = await revokeAllSessions();
    setBusyHandle(null);

    if (result.status !== 'ok') {
      setActionError(result.error.message);
      return;
    }
    const ended = result.data.sessions_ended;
    setActionNotice(
      ended > 0
        ? `${ended} other ${ended === 1 ? 'session was' : 'sessions were'} signed out. You are still signed in here.`
        : 'There were no other sessions to sign out.',
    );
    setConfirming(null);
    void load();
  }, [load]);

  const others = (sessions ?? []).filter((s) => !s.is_current);

  return (
    <main className="account" aria-labelledby="account-security-heading">
      <h1 id="account-security-heading" className="account__title">
        Account security
      </h1>
      <p className="account__lead">
        Signed in as <strong>{user?.username}</strong>.
      </p>

      {/* ---------------------------------------------------------------- */}
      <Card>
        <SectionHeading title="Change your password" />
        <p className="account__hint">
          Changing your password signs out every other session and keeps this
          one, so you are not logged out of the change you just made.
        </p>

        {changeNotice ? (
          <div data-testid="password-change-notice">
            <Alert tone="success" title="Password changed">
              <p>{changeNotice}</p>
            </Alert>
          </div>
        ) : null}
        {changeError ? (
          <div data-testid="password-change-error">
            <Alert tone="danger" title="Password not changed">
              <p>{changeError}</p>
            </Alert>
          </div>
        ) : null}

        <form className="account__form" onSubmit={submitPasswordChange} noValidate>
          <PasswordField
            label="Current password"
            id="current-password"
            value={current}
            autoComplete="current-password"
            required
            onChange={(event) => setCurrent(event.target.value)}
          />
          <PasswordField
            label="New password"
            id="change-new-password"
            value={password}
            autoComplete="new-password"
            required
            onChange={(event) => setPassword(event.target.value)}
          />
          <PasswordField
            label="Confirm new password"
            id="change-confirm-password"
            value={confirmation}
            autoComplete="new-password"
            required
            onChange={(event) => setConfirmation(event.target.value)}
          />
          <Button
            type="submit"
            variant="primary"
            disabled={changing || !current || !password || !confirmation}
            data-testid="submit-password-change"
          >
            {changing ? 'Changing…' : 'Change password'}
          </Button>
        </form>
      </Card>

      {/* ---------------------------------------------------------------- */}
      <Card>
        <SectionHeading
          title="Where you are signed in"
          actions={
            others.length > 0 ? (
              <Button
                variant="secondary"
                data-testid="sign-out-everywhere"
                onClick={() => setConfirming({ kind: 'all' })}
              >
                Sign out everywhere else
              </Button>
            ) : null
          }
        />

        {actionNotice ? (
          <div data-testid="session-action-notice">
            <Alert tone="success" title="Done"><p>{actionNotice}</p></Alert>
          </div>
        ) : null}
        {actionError ? (
          <Alert tone="danger" title="Could not complete that">
            <p>{actionError}</p>
          </Alert>
        ) : null}
        {loadError ? (
          <Alert tone="danger" title="Could not load your sessions">
            <p>{loadError}</p>
          </Alert>
        ) : null}

        {sessions === null ? (
          <p className="account__hint">Loading sessions…</p>
        ) : sessions.length === 0 ? (
          <p className="account__hint">No active sessions.</p>
        ) : (
          <ul className="account__sessions" data-testid="session-list">
            {sessions.map((session) => (
              <li
                key={session.handle}
                className={`account__session${session.is_current ? ' account__session--current' : ''}`}
                data-testid={session.is_current ? 'session-current' : 'session-other'}
                data-handle={session.handle}
              >
                <div className="account__session-main">
                  <span className="account__session-client">
                    {describeClient(session.user_agent)}
                  </span>
                  {session.is_current ? (
                    <span data-testid="current-session-badge">
                      <Badge tone="accent" dot>This device</Badge>
                    </span>
                  ) : null}
                </div>
                <dl className="account__session-meta">
                  <div>
                    <dt>Signed in</dt>
                    <dd>{formatWhen(session.created_at)}</dd>
                  </div>
                  <div>
                    <dt>Last active</dt>
                    <dd>{formatWhen(session.last_activity_at)}</dd>
                  </div>
                  <div>
                    <dt>Address</dt>
                    <dd>{session.ip_address ?? 'Unknown'}</dd>
                  </div>
                </dl>

                {session.is_current ? (
                  <Button
                    variant="secondary"
                    data-testid="sign-out-this-session"
                    onClick={() => {
                      void signOut().then(() => navigate('/login'));
                    }}
                  >
                    Sign out of this device
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    data-testid="revoke-session"
                    data-handle={session.handle}
                    loading={busyHandle === session.handle}
                    onClick={() => setConfirming({
                      kind: 'one', handle: session.handle,
                      client: describeClient(session.user_agent),
                    })}
                  >
                    Sign out
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ---------------------------------------------------------------- */}
      <Card>
        <SectionHeading title="Recent security activity" />
        <p className="account__hint">
          Sign-ins, failed attempts and password changes on your account.
          Failed attempts you do not recognise are worth a password change.
        </p>

        {events === null ? (
          <p className="account__hint">Loading activity…</p>
        ) : events.length === 0 ? (
          <p className="account__hint">Nothing recorded yet.</p>
        ) : (
          <table className="account__activity" data-testid="security-activity">
            <caption className="visually-hidden">
              Recent security events on your account
            </caption>
            <thead>
              <tr>
                <th scope="col">Event</th>
                <th scope="col">When</th>
                <th scope="col">Address</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, index) => (
                <tr key={event.id ?? `${event.created_at}-${index}`}>
                  <td>{describeEvent(event.event)}</td>
                  <td>{formatWhen(event.created_at)}</td>
                  <td>{event.ip_address ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Both destructive session actions go through the same typed
          confirmation the organization screens use. Signing somebody out is
          felt immediately by whoever is using that session, and the rows look
          alike — so the confirmation asks the reader to name what they are
          ending rather than to click "yes". */}
      <ConfirmAction
        open={confirming !== null}
        title={
          confirming?.kind === 'all'
            ? 'Sign out every other session?'
            : 'Sign out this session?'
        }
        description={
          confirming?.kind === 'all'
            ? `This ends ${others.length} other ${others.length === 1 ? 'session' : 'sessions'}. You stay signed in on this device.`
            : `This ends the session on ${confirming?.kind === 'one' ? confirming.client : ''}. Whoever is using it will have to sign in again.`
        }
        consequence={
          confirming?.kind === 'one'
            ? 'If you do not recognise this session, change your password as well — ending it does not stop somebody who knows your password from signing in again.'
            : undefined
        }
        confirmPhrase={user?.username ?? ''}
        confirmLabel={
          confirming?.kind === 'all' ? 'Sign out everywhere else' : 'Sign out'
        }
        busy={busyHandle !== null}
        error={actionError}
        askForReason={false}
        testId="session-confirm"
        onCancel={() => setConfirming(null)}
        onConfirm={() => {
          if (confirming?.kind === 'all') void endEverywhereElse();
          else if (confirming?.kind === 'one') void endSession(confirming.handle);
        }}
      />
    </main>
  );
}
