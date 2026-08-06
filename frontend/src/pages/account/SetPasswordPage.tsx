/**
 * Setting a password from a one-time link — activation and reset.
 *
 * One component for both, because the two differ in wording and in almost
 * nothing else, and two near-identical files would drift: the fix applied to
 * one link-expiry message and not the other is exactly the kind of divergence
 * this avoids.
 *
 * Two behaviours here matter more than they look
 * ----------------------------------------------
 * **A rejected password must not consume the link.** If the backend refuses
 * the password for policy reasons, the token is still live and the form stays
 * usable. Getting this wrong is quietly awful: a new colleague types something
 * too short, is told so, and finds their link now dead — with no way back
 * except asking an administrator, who will assume they did something wrong.
 * The backend checks the policy *before* claiming the token, and this screen
 * matches that by keeping the form mounted with the token intact.
 *
 * **An unusable link says one thing.** Expired, already used, replaced by a
 * newer one, and never valid all produce the same message, because
 * distinguishing them tells whoever holds the link whether it was ever real —
 * and that tells them the account exists.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import {
  activate, passwordPolicy, resetPassword, type PasswordPolicy,
} from '../../api/accountClient';
import { useAuth } from '../../auth/AuthContext';
import { Alert, Button, PasswordField } from '../../design-system/components';
import './Account.css';

type Mode = 'activate' | 'reset';

const COPY: Record<Mode, {
  title: string;
  lead: string;
  submit: string;
  done: string;
  doneDetail: string;
}> = {
  activate: {
    title: 'Activate your account',
    lead:
      'Choose a password to finish setting up your account. Nobody else — including an administrator — has seen or set a password for you.',
    submit: 'Activate account',
    done: 'Your account is active',
    doneDetail:
      'You can now sign in with your username and the password you just chose.',
  },
  reset: {
    title: 'Choose a new password',
    lead:
      'Set a new password for your account. This link works once, and any other sessions signed in as you will be ended.',
    submit: 'Set new password',
    done: 'Your password has been changed',
    doneDetail:
      'Every session that was signed in as you has been ended. Sign in again with your new password.',
  },
};

export default function SetPasswordPage({ mode }: { mode: Mode }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const copy = COPY[mode];

  // Read once, and only from the query string. Never from a redirect target,
  // never persisted.
  const token = params.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [policy, setPolicy] = useState<PasswordPolicy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [succeeded, setSucceeded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void passwordPolicy(controller.signal).then((result) => {
      if (result.status === 'ok') setPolicy(result.data);
    });
    return () => controller.abort();
  }, []);

  const submit = useCallback(async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;

    setSubmitting(true);
    setError(null);
    setErrorCode(null);

    const call = mode === 'activate' ? activate : resetPassword;
    const result = await call({ token, password, confirmation });

    if (result.status === 'ok') {
      // Clear the values from component state on success. They are gone from
      // the DOM with the form, and there is no reason for them to outlive it.
      setPassword('');
      setConfirmation('');
      setSucceeded(true);
      setSubmitting(false);
      return;
    }

    setError(result.error.message);
    setErrorCode(result.error.error);
    setSubmitting(false);
    // Deliberately NOT clearing the token or unmounting the form. A policy
    // rejection leaves the link live, and the user must be able to try again
    // on this screen.
  }, [confirmation, mode, password, submitting, token]);

  /* --- no token at all -------------------------------------------------- */
  if (!token) {
    return (
      <Shell title={copy.title}>
        <Alert tone="warn" title="This page needs a link">
          <p>
            Open the link from your {mode === 'activate' ? 'activation' : 'password reset'}{' '}
            email. If you do not have one, ask an administrator to issue a new
            link, or{' '}
            <Link to="/account/forgot">request a password reset</Link>.
          </p>
        </Alert>
      </Shell>
    );
  }

  /* --- done ------------------------------------------------------------- */
  if (succeeded) {
    return (
      <Shell title={copy.done}>
        <Alert tone="success" title={copy.done}>
          <p>{copy.doneDetail}</p>
        </Alert>
        <div className="account__actions">
          <Button
            variant="primary"
            data-testid="go-to-sign-in"
            onClick={() => navigate('/login', { replace: true })}
          >
            Go to sign in
          </Button>
        </div>
      </Shell>
    );
  }

  /* --- the link is unusable --------------------------------------------- */
  // One message for expired, used, replaced and never-valid. `invalid_token`
  // is the backend's single code for all four.
  if (errorCode === 'invalid_token') {
    return (
      <Shell title={copy.title}>
        <div data-testid="link-unusable">
        <Alert tone="danger" title="This link cannot be used">
          <p>{error}</p>
          <p>
            Links expire, work only once, and stop working when a newer one is
            issued. Nothing is wrong with your account — you just need a
            current link.
          </p>
        </Alert>
        </div>
        <div className="account__actions">
          {mode === 'reset' ? (
            <Button variant="primary" onClick={() => navigate('/account/forgot')}>
              Request a new link
            </Button>
          ) : (
            <p className="account__hint">
              Ask an administrator to reissue your activation link.
            </p>
          )}
        </div>
      </Shell>
    );
  }

  /* --- the form --------------------------------------------------------- */
  return (
    <Shell title={copy.title}>
      <p className="account__lead">{copy.lead}</p>

      {user ? (
        <Alert tone="info" title="You are already signed in">
          <p>
            Setting a password with this link will end every session, including
            this one.
          </p>
        </Alert>
      ) : null}

      {error ? (
        <div data-testid="password-rejected">
        <Alert tone="danger" title="That password was not accepted">
          <p>{error}</p>
          <p className="account__hint">
            Your link is still valid — choose a different password and try
            again.
          </p>
        </Alert>
        </div>
      ) : null}

      <form className="account__form" onSubmit={submit} noValidate>
        <PasswordField
          label="New password"
          id="new-password"
          value={password}
          autoComplete="new-password"
          required
          onChange={(event) => setPassword(event.target.value)}
          help={
            policy
              ? `At least ${policy.min_length} characters. Length matters more than symbols do.`
              : undefined
          }
        />
        <PasswordField
          label="Confirm new password"
          id="confirm-password"
          value={confirmation}
          autoComplete="new-password"
          required
          onChange={(event) => setConfirmation(event.target.value)}
        />

        {policy ? (
          <details className="account__policy">
            <summary>What makes a password acceptable</summary>
            <ul>
              {policy.rules.map((rule) => <li key={rule}>{rule}</li>)}
            </ul>
          </details>
        ) : null}

        <Button
          type="submit"
          variant="primary"
          disabled={submitting || !password || !confirmation}
          data-testid="submit-password"
        >
          {submitting ? 'Setting…' : copy.submit}
        </Button>
      </form>
    </Shell>
  );
}

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="account account--standalone">
      <div className="account__card">
        <h1 className="account__title" data-testid="account-page-title">{title}</h1>
        {children}
      </div>
    </main>
  );
}
