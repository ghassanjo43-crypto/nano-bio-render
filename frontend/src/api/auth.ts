/**
 * Authentication API client.
 *
 * Every request uses `credentials: 'include'` so the browser sends the
 * HttpOnly session cookie. The token itself is NEVER read, stored or handled by
 * JavaScript — there is deliberately no localStorage/sessionStorage use
 * anywhere in this application.
 */

import { API_BASE_URL } from './client';

export type UserRole = 'admin' | 'researcher' | 'viewer';

export interface UserProfile {
  id: number;
  username: string;
  email?: string | null;
  full_name?: string | null;
  role: UserRole;
  is_active: boolean;
  last_login_at?: string | null;
}

export interface LoginResponse {
  user: UserProfile;
  session_expires_at: string;
  idle_timeout_minutes: number;
}

export interface AuthError {
  error: string;
  message: string;
  retry_after_seconds?: number | null;
}

export type LoginResult =
  | { status: 'ok'; data: LoginResponse }
  | { status: 'error'; error: AuthError };

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export async function login(
  username: string,
  password: string,
): Promise<LoginResult> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: JSON_HEADERS,
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    });
  } catch (cause) {
    return {
      status: 'error',
      error: {
        error: 'network_error',
        message:
          'Cannot reach the authentication service. Check that the backend ' +
          `is running at ${API_BASE_URL}.`,
        retry_after_seconds: null,
      },
    };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return {
      status: 'error',
      error: { error: 'invalid_response', message: 'Unexpected server response.' },
    };
  }

  if (!response.ok) {
    const err = body as Partial<AuthError>;
    return {
      status: 'error',
      error: {
        error: err.error ?? 'login_failed',
        message: err.message ?? 'Sign-in failed.',
        retry_after_seconds: err.retry_after_seconds ?? null,
      },
    };
  }
  return { status: 'ok', data: body as LoginResponse };
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch {
    // Ignore: the client clears local state regardless.
  }
}

/** Returns the current user, or null when there is no valid session. */
export async function fetchProfile(signal?: AbortSignal): Promise<UserProfile | null> {
  try {
    const r = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      credentials: 'include',
      signal,
    });
    if (!r.ok) return null;
    return (await r.json()) as UserProfile;
  } catch {
    return null;
  }
}
