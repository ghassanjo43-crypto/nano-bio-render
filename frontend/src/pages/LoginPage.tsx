/**
 * NanoBio Studio sign-in — split-screen product entrance.
 *
 * Left: value proposition over a subtle nanoparticle motif.
 * Right: the authentication panel.
 *
 * Security notes preserved from the containment work: no default credentials are
 * displayed, failure messages stay generic, and nothing about the HttpOnly
 * cookie flow changes.
 */

import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Alert, Button, PasswordField, TextField } from '../design-system/components';
import { BrandMark } from '../shell/Icon';
import './LoginPage.css';

const CAPABILITIES = [
  {
    title: 'Formulation design scoring',
    body: 'Delivery, toxicity and cost computed by a canonical, version-tracked scientific engine.',
  },
  {
    title: 'Traceable results',
    body: 'Every score carries its inputs, model version, evidence level and limitations.',
  },
  {
    title: 'Honest scientific status',
    body: 'Validation state is always shown. Nothing is presented as experimentally confirmed.',
  },
] as const;

export default function LoginPage() {
  const { user, initialising, signIn, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{ username?: string; password?: string }>({});
  const [authError, setAuthError] = useState<string | null>(null);
  const [errorKind, setErrorKind] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (initialising) {
    return (
      <div className="login">
        <div className="login__panel">
          <div className="login__card login__card--checking" role="status">
            <span className="login__spinner" aria-hidden="true" />
            <p>Checking your session…</p>
          </div>
        </div>
      </div>
    );
  }

  if (user) {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from ?? '/start'} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setAuthError(null);
    setErrorKind(null);

    const errors: { username?: string; password?: string } = {};
    if (!username.trim()) errors.username = 'Enter your username.';
    if (!password) errors.password = 'Enter your password.';
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      const result = await signIn(username.trim(), password);
      if (result.ok) {
        const from = (location.state as { from?: string } | null)?.from;
        navigate(from ?? '/start', { replace: true });
      } else {
        setErrorKind(result.error.error);
        setAuthError(result.error.message);
        setPassword('');
      }
    } finally {
      setSubmitting(false);
    }
  }

  const alertTone = errorKind === 'network_error' ? 'warn'
    : errorKind === 'rate_limited' ? 'warn' : 'danger';
  const alertTitle = errorKind === 'network_error' ? 'Service unavailable'
    : errorKind === 'rate_limited' ? 'Temporarily locked' : 'Sign-in failed';

  return (
    <div className="login">
      {/* ------------------------------------------------ brand / value */}
      <section className="login__brandside" aria-label="About NanoBio Studio">
        <div className="login__motif" aria-hidden="true">
          <svg viewBox="0 0 600 600" preserveAspectRatio="xMidYMid slice">
            <defs>
              <radialGradient id="lpCore" cx="50%" cy="45%">
                <stop offset="0%" stopColor="#7ad4e8" stopOpacity="0.55" />
                <stop offset="100%" stopColor="#12a5c4" stopOpacity="0" />
              </radialGradient>
            </defs>
            <circle cx="300" cy="280" r="190" fill="url(#lpCore)" />
            {[0, 34, 68, 102, 136].map((rot) => (
              <ellipse
                key={rot}
                cx="300" cy="280" rx="215" ry="96"
                fill="none" stroke="#7ad4e8" strokeOpacity="0.16" strokeWidth="1.2"
                transform={`rotate(${rot} 300 280)`}
              />
            ))}
            <circle cx="300" cy="280" r="58" fill="#0d8ba6" fillOpacity="0.22"
                    stroke="#7ad4e8" strokeOpacity="0.4" strokeWidth="1.4" />
            {[[168, 196], [432, 214], [388, 402], [206, 396], [300, 96]].map(([cx, cy], i) => (
              <circle key={i} cx={cx} cy={cy} r={i % 2 ? 5 : 7}
                      fill="#7ad4e8" fillOpacity="0.42" />
            ))}
          </svg>
        </div>

        <div className="login__brandcontent">
          <div className="login__brandmark">
            <BrandMark size={42} />
            <div>
              <p className="login__brandname">NanoBio Studio</p>
              <p className="login__brandsub">Connecting Nanotechnology &amp; Biotechnology</p>
            </div>
          </div>

          <h2 className="login__headline">
            A research platform for designing and evaluating nanoparticle
            formulations.
          </h2>

          <ul className="login__capabilities">
            {CAPABILITIES.map((c) => (
              <li key={c.title}>
                <span className="login__cap-check" aria-hidden="true">✓</span>
                <div>
                  <p className="login__cap-title">{c.title}</p>
                  <p className="login__cap-body">{c.body}</p>
                </div>
              </li>
            ))}
          </ul>

          <p className="login__brandfoot">
            Research use only. Outputs are computational and are not
            experimentally or clinically validated.
          </p>
        </div>
      </section>

      {/* --------------------------------------------------- login panel */}
      <section className="login__panel" aria-label="Sign in">
        <div className="login__card">
          <div className="login__mobilebrand">
            <BrandMark size={34} />
            <span>NanoBio Studio</span>
          </div>

          <h1 className="login__title">Sign in</h1>
          <p className="login__subtitle">
            Access is restricted to authorised research accounts.
          </p>

          <form onSubmit={handleSubmit} noValidate className="login__form">
            <TextField
              id="username"
              label="Username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              error={fieldErrors.username}
              disabled={submitting}
              required
              autoFocus
            />

            <PasswordField
              id="password"
              label="Password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={fieldErrors.password}
              disabled={submitting}
              required
            />

            {/* An expired session is not a failed sign-in: it is explained
                separately so the user knows nothing went wrong with their
                credentials. Suppressed once they have actually tried again. */}
            {/* The wording deliberately does NOT assert a cause. A 401 can mean
                an idle timeout (30 minutes), an absolute expiry (8 hours), a
                revoked session, or a cookie the browser declined to send. The
                client cannot tell these apart, so it must not claim to. */}
            {sessionExpired && !authError && (
              <div data-testid="session-expired" className="login__alert">
                <Alert tone="info" title="You were signed out">
                  The server did not accept your session, so you have been
                  returned here. Nothing was lost. Sessions end after 30 minutes
                  of inactivity; signing in again will restore access.
                </Alert>
              </div>
            )}

            {authError && (
              <div data-testid="auth-error" className="login__alert">
                <Alert tone={alertTone} title={alertTitle}>{authError}</Alert>
              </div>
            )}

            <Button type="submit" size="lg" fullWidth loading={submitting}>
              {submitting ? 'Signing in…' : 'Sign In'}
            </Button>
          </form>

          <p className="login__reset" data-testid="reset-note">
            <Link to="/account/forgot" data-testid="forgot-password-link">
              Forgotten your password?
            </Link>
          </p>

          <div className="login__notice">
            <strong>Computational research use only.</strong> This platform
            produces modelled, non-validated results for research planning. It
            does not provide clinical diagnoses or treatment decisions.
          </div>
        </div>
      </section>
    </div>
  );
}
