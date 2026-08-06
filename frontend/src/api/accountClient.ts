/**
 * Typed client for account activation, password and session management.
 *
 * One rule shapes this whole file: **no function here accepts an administrator
 * and a password for somebody else.** There is no `setPassword(userId, value)`
 * and no `getPassword(userId)`, because those are not features that were left
 * out — they are shapes the API cannot express. An administrator causes a
 * *link* to exist; the person behind the address chooses the password.
 *
 * The unauthenticated calls (`activate`, `resetPassword`, `forgotPassword`,
 * `passwordPolicy`) go through `publicRequest` rather than `apiRequest`.
 * `apiRequest` treats a 401 as "your session ended" and pushes the user to the
 * login screen — which is exactly wrong on the activation page, where the user
 * has no session yet and is *trying* to get one. Routing them through the
 * session handler would bounce somebody off a valid activation link.
 */

import type { BadgeTone } from '../design-system/components';
import { apiRequest } from './client';
import type { ApiResult } from './types';

/**
 * `apiRequest` requires a type guard, so responses are checked for the keys the
 * screens actually read rather than cast blindly. A missing key here surfaces
 * as a handled error instead of `undefined` rendering as "undefined" in a
 * security screen.
 */
const hasKeys = <T,>(...keys: string[]) => (body: unknown): body is T =>
  typeof body === 'object' && body !== null && keys.every((k) => k in body);

/** For endpoints whose useful response is a notice with no fixed key. */
const anyObject = <T,>(body: unknown): body is T =>
  typeof body === 'object' && body !== null;

/* ------------------------------------------------------------------------ */
/* Shapes                                                                    */
/* ------------------------------------------------------------------------ */

/**
 * The six account states, as they appear **on the wire**.
 *
 * Lowercase, because `AccountState` is a `str` enum whose *values* are
 * lowercase and it is the value that gets serialised — the uppercase form is
 * the Python member name and never leaves the backend.
 *
 * This was originally typed in uppercase. Nothing failed to compile, because
 * the strings came from JSON as `string`; instead every presentation lookup
 * silently returned `undefined` and the accounts panel crashed on render for
 * every account. A type that describes the wire wrongly is worse than no type,
 * because it looks like it was checked.
 */
export type AccountStateName =
  | 'pending_activation'
  | 'active'
  | 'suspended'
  | 'disabled'
  | 'deletion_pending'
  | 'deleted';

/** Lifecycle of an activation or reset link, as the backend reports it. */
export type TokenStateName =
  | 'none'
  | 'delivered'
  | 'recorded'
  | 'accepted'
  | 'withdrawn'
  | 'expired';

export interface TokenStatus {
  state: TokenStateName;
  issued_at?: string | null;
  expires_at?: string | null;
  ended_at?: string | null;
  delivery_status?: string | null;
  delivery_provider?: string | null;
  /** First few characters only. Never enough to redeem. */
  link_prefix?: string | null;
}

export interface PasswordPolicy {
  min_length: number;
  max_length: number;
  rules: string[];
  notice?: string;
}

export interface SessionSummary {
  /** Opaque handle. Never the session token, and never a prefix of it. */
  handle: string;
  /** True for the session making the request. */
  is_current: boolean;
  created_at: string;
  last_activity_at: string | null;
  expires_at: string | null;
  ip_address: string | null;
  user_agent: string | null;
}

export interface SecurityEvent {
  id: number;
  /** Lowercase wire value, e.g. `login_success`. */
  event: string;
  created_at: string;
  ip_address: string | null;
  user_agent: string | null;
  detail: string | null;
}

export interface AccountSummary {
  user_id: number;
  username: string;
  email: string | null;
  state: AccountStateName;
  state_reason: string | null;
  must_set_password: boolean;
  last_login_at: string | null;
  password_algorithm: string | null;
  activation: TokenStatus;
  password_reset: TokenStatus;
  notice?: string;
}

/**
 * What comes back when a link is issued.
 *
 * `link` is present **only** when delivery is not configured, and only on the
 * response to the act of issuing it. It is never returned by a later read —
 * see `AccountSummary.activation`, which carries a prefix and a state and no
 * redeemable value. That is what makes "shown once" true rather than a UI
 * convention: there is no second call that could show it again.
 */
export interface IssuedLink {
  delivery_status: string;
  delivery_provider?: string;
  delivery_detail?: string | null;
  expires_at: string;
  /**
   * The redeemable link, present only when delivery is not configured.
   *
   * The API names it by purpose — `activation_link` on the activation routes,
   * `reset_link` on the reset one — so `issuedLinkValue()` below reads
   * whichever is present rather than a single invented `link` field. Guessing
   * one name meant the panel rendered "sent by email" over an empty code
   * block, which reads as a successful send and silently loses the only copy
   * of a link that cannot be reissued without invalidating it.
   */
  activation_link?: string;
  reset_link?: string;
  link_shown_once?: boolean;
  notice?: string;
}

/** The one-time link from an issue response, whichever route produced it. */
export function issuedLinkValue(issued: IssuedLink): string | undefined {
  return issued.activation_link ?? issued.reset_link;
}

export interface CreatedAccount extends IssuedLink {
  user_id: number;
  username: string;
  state: AccountStateName;
}

/* ------------------------------------------------------------------------ */
/* Unauthenticated transport                                                 */
/* ------------------------------------------------------------------------ */

/**
 * A fetch that does not interpret 401 as an expired session.
 *
 * Deliberately small and deliberately separate. The alternative — a flag on
 * `apiRequest` — puts the "is this a session failure?" decision at every call
 * site, and the one that gets it wrong is the activation page, where being
 * wrong means redirecting a new colleague away from their own activation link
 * to a login form they cannot yet use.
 */
async function publicRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`/api/v1${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(init.headers ?? {}),
      },
    });

    const text = await response.text();
    const body = text ? JSON.parse(text) : null;

    if (!response.ok) {
      // FastAPI nests the application error under `detail`. The `error` code
      // is what the activation screen branches on to tell "this link is dead"
      // apart from "that password was refused" — the two need opposite
      // responses from the user, so losing the code here would collapse them
      // into one unhelpful message.
      const detail = body?.detail ?? body;
      return {
        status: 'error',
        error: {
          error: detail?.error ?? 'request_failed',
          message:
            detail?.message ??
            detail?.detail ??
            'The request could not be completed.',
          data_available: false,
        },
      };
    }
    return { status: 'ok', data: body as T };
  } catch {
    return {
      status: 'error',
      error: {
        error: 'network_error',
        message:
          'Could not reach the server. Check your connection and try again.',
        data_available: false,
      },
    };
  }
}

/* ------------------------------------------------------------------------ */
/* Unauthenticated workflows                                                 */
/* ------------------------------------------------------------------------ */

export function passwordPolicy(signal?: AbortSignal) {
  return publicRequest<PasswordPolicy>('/account/password-policy', { signal });
}

/**
 * Set a password using an activation link.
 *
 * The wire names come from `SetPasswordRequest`: `confirm_password`, not
 * `confirmation`. Every request model here sets `extra="forbid"`, so a wrong
 * name is a 422 rather than a dropped field — which is a good property, and
 * the reason these are written out explicitly instead of spreading a
 * conveniently-shaped object through.
 */
export function activate(body: {
  token: string;
  password: string;
  confirmation: string;
}) {
  return publicRequest<{ username: string; notice?: string }>(
    '/account/activate',
    {
      method: 'POST',
      body: JSON.stringify({
        token: body.token,
        password: body.password,
        confirm_password: body.confirmation,
      }),
    },
  );
}

/** Set a password using a reset link. */
export function resetPassword(body: {
  token: string;
  password: string;
  confirmation: string;
}) {
  return publicRequest<{ username: string; sessions_ended?: number; notice?: string }>(
    '/account/reset',
    {
      method: 'POST',
      body: JSON.stringify({
        token: body.token,
        password: body.password,
        confirm_password: body.confirmation,
      }),
    },
  );
}

/**
 * Request a reset link.
 *
 * The response is identical whether or not the account exists, and the screen
 * must render it verbatim. A caller that branched on "did we find them?" would
 * reintroduce the account-enumeration disclosure the backend went to the
 * trouble of removing.
 */
export function forgotPassword(body: { username: string }) {
  return publicRequest<{ requested: boolean; message: string }>('/account/forgot', {
    method: 'POST',
    // `identifier`, because the backend accepts a username *or* an email —
    // somebody who has forgotten their password often cannot remember which
    // of the two they signed up with either.
    body: JSON.stringify({ identifier: body.username }),
  });
}

/* ------------------------------------------------------------------------ */
/* Authenticated workflows                                                   */
/* ------------------------------------------------------------------------ */

export function changePassword(body: {
  current_password: string;
  password: string;
  confirmation: string;
}) {
  return apiRequest<{ changed: boolean; other_sessions_ended: number;
                      notice?: string }>(
    '/api/v1/account/password',
    {
      method: 'POST',
      body: JSON.stringify({
        current_password: body.current_password,
        password: body.password,
        confirm_password: body.confirmation,
      }),
    },
    hasKeys<{ changed: boolean; other_sessions_ended: number;
              notice?: string }>('other_sessions_ended'),
  );
}

export function listSessions(signal?: AbortSignal) {
  return apiRequest<{ sessions: SessionSummary[]; notice?: string }>(
    '/api/v1/account/sessions',
    { method: 'GET', signal },
    hasKeys<{ sessions: SessionSummary[]; notice?: string }>('sessions'),
  );
}

export function revokeSession(handle: string) {
  return apiRequest<{ revoked: boolean; notice?: string }>(
    '/api/v1/account/sessions/revoke',
    { method: 'POST', body: JSON.stringify({ handle }) },
    anyObject,
  );
}

export function revokeAllSessions() {
  return apiRequest<{ sessions_ended: number; notice?: string }>(
    '/api/v1/account/sessions/revoke-all',
    { method: 'POST', body: JSON.stringify({}) },
    hasKeys<{ sessions_ended: number; notice?: string }>('sessions_ended'),
  );
}

export function securityActivity(signal?: AbortSignal) {
  return apiRequest<{ events: SecurityEvent[]; notice?: string }>(
    '/api/v1/account/security-activity',
    { method: 'GET', signal },
    hasKeys<{ events: SecurityEvent[]; notice?: string }>('events'),
  );
}

/* ------------------------------------------------------------------------ */
/* Administrative workflows                                                  */
/* ------------------------------------------------------------------------ */

const admin = (organizationId: number) =>
  `/api/v1/account/admin/organizations/${organizationId}/accounts`;

/**
 * Create an account.
 *
 * Note what this does not take. There is no `password` parameter, and the
 * backend rejects one outright rather than ignoring it — so an administrator
 * cannot choose a password even by crafting the request by hand.
 */
export function createAccount(
  organizationId: number,
  body: {
    username: string;
    email: string;
    full_name?: string;
    /**
     * The **organization** role. One field, not two.
     *
     * This carried a second `organization_role` alongside it, which the API
     * forbids outright (`extra="forbid"`), so every creation attempt was a
     * 422. Worth keeping as one field for a better reason than the schema
     * though: two role fields on a creation form is how somebody ends up
     * appointed as a reviewer in the organization and a contributor on its
     * studies, with no idea which one governs what.
     */
    role: string;
  },
) {
  return apiRequest<CreatedAccount>(
    admin(organizationId),
    { method: 'POST', body: JSON.stringify(body) },
    hasKeys<CreatedAccount>('user_id', 'state'),
  );
}

export function accountStatus(
  organizationId: number,
  userId: number,
  signal?: AbortSignal,
) {
  return apiRequest<AccountSummary>(
    `${admin(organizationId)}/${userId}`,
    { method: 'GET', signal },
    hasKeys<AccountSummary>('user_id', 'state', 'activation'),
  );
}

export function reissueActivation(organizationId: number, userId: number) {
  return apiRequest<IssuedLink>(
    `${admin(organizationId)}/${userId}/activation`,
    { method: 'POST', body: JSON.stringify({}) },
    hasKeys<IssuedLink>('delivery_status'),
  );
}

export function initiatePasswordReset(organizationId: number, userId: number) {
  return apiRequest<IssuedLink>(
    `${admin(organizationId)}/${userId}/reset`,
    { method: 'POST', body: JSON.stringify({}) },
    hasKeys<IssuedLink>('delivery_status'),
  );
}

export function setAccountState(
  organizationId: number,
  userId: number,
  body: { state: AccountStateName; reason?: string },
) {
  return apiRequest<{
    user_id: number;
    state: AccountStateName;
    sessions_ended: number;
    notice?: string;
  }>(
    `${admin(organizationId)}/${userId}/state`,
    { method: 'POST', body: JSON.stringify(body) },
    hasKeys('user_id', 'state'),
  );
}

export function eraseAccount(
  organizationId: number,
  userId: number,
  reason: string,
) {
  return apiRequest<{
    erased: boolean;
    pseudonym?: string;
    fields_cleared?: string[];
    notice?: string;
  }>(
    `${admin(organizationId)}/${userId}/erase`,
    { method: 'POST', body: JSON.stringify({ state: 'deleted', reason }) },
    hasKeys('erased'),
  );
}

/* ------------------------------------------------------------------------ */
/* Presentation of the six states                                            */
/* ------------------------------------------------------------------------ */

/**
 * How each account state is described to a human.
 *
 * Written here rather than in each screen so the four things the brief
 * distinguishes cannot drift apart between screens:
 *
 *  - an **account** suspension or disablement (this table),
 *  - an **organization membership** suspension or revocation (a different
 *    thing entirely — the account still signs in, it just cannot see this
 *    organization's work),
 *  - a **password reset in progress** (a link exists; the account state is
 *    untouched),
 *  - **historical attribution**, which none of the above changes.
 *
 * Conflating the first two is the mistake this table exists to prevent: an
 * administrator who suspends an *account* to remove somebody from *one study*
 * has locked them out of every organization they belong to.
 */
export const ACCOUNT_STATE_PRESENTATION: Record<
  AccountStateName,
  { label: string; tone: BadgeTone; meaning: string }
> = {
  pending_activation: {
    label: 'Awaiting activation',
    tone: 'warn',
    meaning:
      'The account exists but has no password yet. The holder must set one using an activation link. Nobody, including an administrator, can set it for them.',
  },
  active: {
    label: 'Active',
    tone: 'success',
    meaning: 'The account can sign in normally.',
  },
  suspended: {
    label: 'Suspended',
    tone: 'warn',
    meaning:
      'Sign-in is blocked and existing sessions have ended. This is reversible: restoring the account returns it to active without a new password. Work the account performed is unchanged.',
  },
  disabled: {
    label: 'Disabled',
    tone: 'danger',
    meaning:
      'Sign-in is blocked indefinitely. Intended for someone who has left. Reversible by an administrator; work the account performed is unchanged.',
  },
  deletion_pending: {
    label: 'Marked for deletion',
    tone: 'danger',
    meaning:
      'Sign-in is blocked and the account is queued for erasure. Still reversible — nothing has been removed yet.',
  },
  deleted: {
    label: 'Erased',
    tone: 'danger',
    meaning:
      'Identifying information has been permanently removed. This cannot be undone. Experiments, reviews and approvals the account performed are kept and remain attributed to it.',
  },
};

/**
 * Look up a state's presentation, tolerating anything unexpected.
 *
 * A screen that throws because the backend added a seventh state is worse than
 * one that shows the raw name: the crash takes the whole accounts panel with
 * it, including the states it *does* understand, and an administrator loses
 * the ability to suspend anybody because of a display concern.
 */
export function describeAccountState(state: string) {
  return ACCOUNT_STATE_PRESENTATION[state as AccountStateName] ?? {
    label: state.replace(/_/g, ' '),
    tone: 'neutral' as BadgeTone,
    meaning:
      'This account state is not one this interface recognises. Its effect on '
      + 'sign-in is decided by the server, not by this screen.',
  };
}

export function describeTokenState(state: string) {
  return TOKEN_STATE_PRESENTATION[state as TokenStateName]
    ?? { label: state.replace(/_/g, ' '), tone: 'neutral' as BadgeTone };
}

/** Human wording for each link state, used by both the user and admin screens. */
export const TOKEN_STATE_PRESENTATION: Record<
  TokenStateName,
  { label: string; tone: BadgeTone }
> = {
  none: { label: 'No link issued', tone: 'neutral' },
  delivered: { label: 'Sent by email', tone: 'success' },
  recorded: { label: 'Issued — not emailed', tone: 'warn' },
  accepted: { label: 'Used', tone: 'success' },
  withdrawn: { label: 'Replaced or withdrawn', tone: 'neutral' },
  expired: { label: 'Expired', tone: 'warn' },
};
