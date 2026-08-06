/**
 * Authentication state for the application shell.
 *
 * Session restoration works by asking the server who we are (`GET /auth/me`)
 * using the HttpOnly cookie the browser holds. Nothing sensitive is kept in
 * JavaScript: there is no token in memory, in `localStorage`, in
 * `sessionStorage`, or in a readable cookie. On a browser refresh the app
 * re-asks the server, which is why a refresh preserves the session and an
 * expired session correctly lands back on the login page.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  fetchProfile,
  login as apiLogin,
  logout as apiLogout,
  type AuthError,
  type UserProfile,
} from '../api/auth';
import { setUnauthorizedHandler } from '../api/client';

interface AuthContextValue {
  user: UserProfile | null;
  /** True until the initial session check completes. */
  initialising: boolean;
  signIn: (username: string, password: string) => Promise<
    { ok: true } | { ok: false; error: AuthError }
  >;
  signOut: () => Promise<void>;
  /** Re-check the session with the server. */
  refresh: () => Promise<void>;
  /**
   * True when a previously-valid session was rejected by the server, so the
   * login page can explain what happened instead of looking like a random
   * logout.
   */
  sessionExpired: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [initialising, setInitialising] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  const refresh = useCallback(async () => {
    const profile = await fetchProfile();
    setUser(profile);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const profile = await fetchProfile();
      if (!cancelled) {
        setUser(profile);
        setInitialising(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /**
   * React to a session the server no longer accepts.
   *
   * Sessions expire after 30 minutes idle. The initial `/auth/me` check happens
   * once at mount, so without this the application went on showing a cached
   * user as signed in while every request returned 401 — the user saw
   * "Sign in to continue." inside a page they appeared to be signed into.
   *
   * Clearing the user lets `ProtectedRoute` do its job and send them to the
   * login page, where `sessionExpired` explains why.
   */
  useEffect(() => {
    setUnauthorizedHandler(() => {
      // Guard on the current value: a 401 while already signed out is the
      // ordinary logged-out path and must not raise an expiry notice.
      setUser((current) => {
        if (current !== null) setSessionExpired(true);
        return null;
      });
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const signIn = useCallback(
    async (username: string, password: string) => {
      const result = await apiLogin(username, password);
      if (result.status === 'ok') {
        setUser(result.data.user);
        setSessionExpired(false);   // a fresh sign-in clears the notice
        return { ok: true } as const;
      }
      setUser(null);
      return { ok: false, error: result.error } as const;
    },
    [],
  );

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
    // A deliberate sign-out is not an expiry, so no notice is shown.
    setSessionExpired(false);
  }, []);

  const value = useMemo(
    () => ({ user, initialising, signIn, signOut, refresh, sessionExpired }),
    [user, initialising, signIn, signOut, refresh, sessionExpired],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside an AuthProvider');
  return ctx;
}
