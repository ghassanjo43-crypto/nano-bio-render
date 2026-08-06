/**
 * Requesting a password reset link.
 *
 * The one thing this screen must not do
 * -------------------------------------
 * It must not reveal whether the account exists. The backend answers
 * identically either way, and this screen renders that answer verbatim — no
 * "we found your account", no different styling for the two cases, and no
 * branch anywhere in this file on whether a user was matched.
 *
 * That matters because the form is unauthenticated and public. A screen that
 * said "no such user" would turn this into an account-enumeration oracle:
 * anybody could work out who has an account here, which for a clinical
 * research platform is a list of who collaborates with whom.
 *
 * The confirmation is deliberately worded as a conditional — "if an account
 * exists" — so a user whose account genuinely does not exist is not left
 * waiting for an email that will never arrive without any hint why.
 */

import { useCallback, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { forgotPassword } from '../../api/accountClient';
import { Alert, Button, TextField } from '../../design-system/components';
import './Account.css';

export default function ForgotPasswordPage() {
  const [username, setUsername] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async (event: FormEvent) => {
    event.preventDefault();
    if (submitting || !username.trim()) return;

    setSubmitting(true);
    setError(null);

    const result = await forgotPassword({ username: username.trim() });
    setSubmitting(false);

    if (result.status === 'ok') {
      // Rendered as given. There is no branch here on whether an account was
      // found, because this component is never told.
      setNotice(result.data.message);
      return;
    }

    // Only genuine transport or throttling failures reach here — an unknown
    // username is a success as far as this screen is concerned.
    setError(result.error.message);
  }, [submitting, username]);

  if (notice) {
    return (
      <main className="account account--standalone">
        <div className="account__card">
          <h1 className="account__title">Check your email</h1>
          <div data-testid="forgot-confirmation">
            <Alert tone="success" title="Request received">
              <p>{notice}</p>
            </Alert>
          </div>
          <p className="account__hint">
            The link expires in one hour and can be used once. If a newer link
            is issued, earlier ones stop working.
          </p>
          <div className="account__actions">
            <Link className="account__link" to="/login">Back to sign in</Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="account account--standalone">
      <div className="account__card">
        <h1 className="account__title">Reset your password</h1>
        <p className="account__lead">
          Enter your username. If an account exists for it, we will send a
          reset link to the email address on file.
        </p>

        {error ? (
          <Alert tone="danger" title="Could not send the request">
            <p>{error}</p>
          </Alert>
        ) : null}

        <form className="account__form" onSubmit={submit} noValidate>
          <TextField
            label="Username"
            id="forgot-username"
            data-testid="forgot-username"
            value={username}
            autoComplete="username"
            required
            onChange={(event) => setUsername(event.target.value)}
          />
          <Button
            type="submit"
            variant="primary"
            disabled={submitting || !username.trim()}
            data-testid="request-reset"
          >
            {submitting ? 'Sending…' : 'Send reset link'}
          </Button>
        </form>

        <div className="account__actions">
          <Link className="account__link" to="/login">Back to sign in</Link>
        </div>
      </div>
    </main>
  );
}
