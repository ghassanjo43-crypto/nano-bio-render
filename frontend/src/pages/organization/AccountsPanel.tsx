/**
 * Administrative account management: activation status, links, account state.
 *
 * The control that is deliberately absent
 * ---------------------------------------
 * There is no "show password", no "set password", and no "copy password". Not
 * hidden behind a role — absent. The API cannot express any of them, and this
 * panel says so on screen, because an administrator who cannot find the button
 * will otherwise assume it exists somewhere and go looking, or ask the user to
 * tell them their password over the phone. Naming the absence is what stops
 * that.
 *
 * What an administrator can do is cause a *link* to exist and see what became
 * of it: sent, issued-but-not-emailed, used, expired, or replaced.
 *
 * The distinction this panel exists to keep visible
 * -------------------------------------------------
 * Four different things get confused with each other, and confusing them
 * causes real harm:
 *
 *  - **Account suspension** stops sign-in everywhere, across every
 *    organization. It is not a way to remove somebody from one study.
 *  - **Membership suspension or revocation** removes access to *this*
 *    organization. The account still works elsewhere.
 *  - **A password reset in progress** changes nothing about either. The
 *    account state is untouched; a link merely exists.
 *  - **Historical attribution** survives all three. Nothing here removes
 *    somebody's name from work they did.
 *
 * An administrator who wants to take a departing collaborator off one study
 * and reaches for "suspend account" has locked them out of their own
 * institution's work too. So the panel states the scope of every action at the
 * point of use, not in documentation.
 */

import { useCallback, useState } from 'react';

import {
  accountStatus, describeAccountState, describeTokenState,
  initiatePasswordReset, issuedLinkValue, reissueActivation, setAccountState,
  type AccountStateName, type AccountSummary, type IssuedLink,
} from '../../api/accountClient';
import type { Member } from '../../api/organizationClient';
import { Alert, Badge, Button, Card, SectionHeading } from '../../design-system/components';
import { ConfirmAction } from './ConfirmAction';

interface Props {
  organizationId: number;
  members: Member[];
  /** True when the viewer holds administrative authority here. */
  canAdminister: boolean;
  onChanged: () => void;
}

type PendingState = {
  member: Member;
  state: AccountStateName;
  title: string;
  description: string;
  consequence: string;
};

function formatWhen(value: string | null | undefined): string {
  if (!value) return '—';
  const at = new Date(value);
  return Number.isNaN(at.getTime()) ? '—' : at.toLocaleString();
}

export function AccountsPanel({
  organizationId, members, canAdminister, onChanged,
}: Props) {
  const [selected, setSelected] = useState<AccountSummary | null>(null);
  const [selectedFor, setSelectedFor] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * The one-time link, held only in component state.
   *
   * Never written to storage, never put in the URL, and discarded when the
   * panel closes or another account is opened. The backend returns it exactly
   * once — on the response to issuing it — and there is no endpoint that can
   * return it again, so this is genuinely the only copy.
   */
  const [issued, setIssued] = useState<
    (IssuedLink & { kind: 'activation' | 'reset'; username: string }) | null
  >(null);
  const issuedLink = issued ? issuedLinkValue(issued) : undefined;

  const [pending, setPending] = useState<PendingState | null>(null);
  const [busy, setBusy] = useState(false);

  /**
   * Load one account's status.
   *
   * `keepIssuedLink` exists because of a defect a test caught: issuing a link
   * set it in state and then refreshed the status, and the refresh cleared it
   * — so the only copy of a one-time link vanished in the same tick it was
   * created, before an administrator could read it. Since there is no endpoint
   * that can return it again, that link was simply lost, and the only recovery
   * was to issue another one and hope the same thing did not happen.
   *
   * Opening a *different* account still clears it, which is the case the
   * clearing was for: a link must never appear under somebody else's name.
   */
  const open = useCallback(async (member: Member,
                                  keepIssuedLink = false) => {
    setSelectedFor(member.user_id);
    setLoading(true);
    setError(null);
    if (!keepIssuedLink) setIssued(null);
    setSelected(null);

    const result = await accountStatus(organizationId, member.user_id);
    setLoading(false);

    if (result.status !== 'ok') {
      setError(result.error.message);
      return;
    }
    setSelected(result.data);
  }, [organizationId]);

  const issueLink = useCallback(async (
    member: Member, kind: 'activation' | 'reset',
  ) => {
    setBusy(true);
    setError(null);

    const call = kind === 'activation' ? reissueActivation : initiatePasswordReset;
    const result = await call(organizationId, member.user_id);
    setBusy(false);

    if (result.status !== 'ok') {
      setError(result.error.message);
      return;
    }
    setIssued({ ...result.data, kind, username: member.username });
    void open(member, true);
    onChanged();
  }, [onChanged, open, organizationId]);

  const applyState = useCallback(async (reason: string) => {
    if (!pending) return;
    setBusy(true);
    setError(null);

    const result = await setAccountState(organizationId, pending.member.user_id, {
      state: pending.state,
      reason: reason || undefined,
    });
    setBusy(false);

    if (result.status !== 'ok') {
      setError(result.error.message);
      return;
    }
    setPending(null);
    void open(pending.member);   // clears any displayed link, deliberately
    onChanged();
  }, [onChanged, open, organizationId, pending]);

  if (!canAdminister) {
    return (
      <Card>
        <SectionHeading title="Accounts" />
        <p className="org-panel__hint">
          Account activation and status are managed by this organization's
          owners and administrators.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <SectionHeading
        title="Accounts"
        description="Activation status, links and account access."
      />

      <Alert tone="info" title="Passwords are never visible to administrators">
        <p>
          You can issue an activation or reset link. You cannot see, set,
          recover or copy anyone's password — the system has no way to do it,
          by design. If someone cannot sign in, issue them a link.
        </p>
      </Alert>

      {error ? (
        <div data-testid="accounts-error">
          <Alert tone="danger" title="Could not complete that">
            <p>{error}</p>
          </Alert>
        </div>
      ) : null}

      {/* --- the one-time link ------------------------------------------ */}
      {issued ? (
        <div data-testid="issued-link">
          <Alert
            tone={issuedLink ? 'warn' : 'success'}
            title={
              issuedLink
                ? 'Copy this link now — it cannot be shown again'
                : `Link sent to ${issued.username}`
            }
          >
            {issuedLink ? (
              <>
                <p>
                  Email delivery is not configured on this deployment, so the{' '}
                  {issued.kind === 'activation' ? 'activation' : 'password reset'}{' '}
                  link is shown here instead. <strong>This is the only time
                  it will be displayed.</strong> Closing or reloading this page
                  loses it, and there is no way to retrieve it — you would have
                  to issue a new link, which invalidates this one.
                </p>
                <p className="org-panel__hint">
                  Send it to {issued.username} over a channel you trust. Anyone
                  who has this link can set the account password.
                </p>
                <code
                  className="org-panel__link-value"
                  data-testid="one-time-link"
                >
                  {issuedLink}
                </code>
                <p className="org-panel__hint">
                  Expires {formatWhen(issued.expires_at)}.
                </p>
              </>
            ) : (
              <p>
                The link was emailed and expires{' '}
                {formatWhen(issued.expires_at)}. It works once.
              </p>
            )}
          </Alert>
        </div>
      ) : null}

      {/* --- the roster -------------------------------------------------- */}
      <ul className="org-panel__accounts" data-testid="accounts-list">
        {members.map((member) => {
          const isOpen = selectedFor === member.user_id;
          const detail = isOpen ? selected : null;
          const presentation = detail
            ? describeAccountState(detail.state)
            : null;

          return (
            <li
              key={member.user_id}
              className="org-panel__account"
              data-testid="account-row"
              data-username={member.username}
            >
              <div className="org-panel__account-head">
                <div>
                  <strong>{member.username}</strong>
                  {detail ? (
                    <span data-testid="account-state">
                      <Badge tone={presentation!.tone} dot>
                        {presentation!.label}
                      </Badge>
                    </span>
                  ) : null}
                </div>
                <Button
                  variant="ghost"
                  data-testid="open-account"
                  data-username={member.username}
                  onClick={() => (isOpen ? setSelectedFor(null) : void open(member))}
                >
                  {isOpen ? 'Close' : 'Account status'}
                </Button>
              </div>

              {isOpen && loading ? (
                <p className="org-panel__hint">Loading account status…</p>
              ) : null}

              {detail ? (
                <div className="org-panel__account-body">
                  <p className="org-panel__hint" data-testid="account-state-meaning">
                    {presentation!.meaning}
                  </p>

                  <dl className="org-panel__account-meta">
                    <div>
                      <dt>Activation link</dt>
                      <dd data-testid="activation-status">
                        {describeTokenState(detail.activation.state).label}
                        {detail.activation.expires_at
                          ? ` — expires ${formatWhen(detail.activation.expires_at)}`
                          : ''}
                      </dd>
                    </div>
                    <div>
                      <dt>Reset link</dt>
                      <dd data-testid="reset-status">
                        {describeTokenState(detail.password_reset.state).label}
                      </dd>
                    </div>
                    <div>
                      <dt>Last signed in</dt>
                      <dd>{formatWhen(detail.last_login_at)}</dd>
                    </div>
                    <div>
                      <dt>Membership of this organization</dt>
                      {/* Stated next to the account state precisely because
                          the two are constantly confused. */}
                      <dd data-testid="membership-status">
                        {member.is_active ? 'Active' : `Ended${member.end_reason ? ` — ${member.end_reason}` : ''}`}
                      </dd>
                    </div>
                  </dl>

                  <div className="org-panel__account-actions">
                    {detail.state === 'pending_activation' ? (
                      <Button
                        variant="secondary"
                        loading={busy}
                        data-testid="reissue-activation"
                        onClick={() => void issueLink(member, 'activation')}
                      >
                        Reissue activation link
                      </Button>
                    ) : null}

                    {detail.state === 'active' ? (
                      <Button
                        variant="secondary"
                        loading={busy}
                        data-testid="initiate-reset"
                        onClick={() => void issueLink(member, 'reset')}
                      >
                        Send password reset link
                      </Button>
                    ) : null}

                    {detail.state === 'active' ? (
                      <Button
                        variant="secondary"
                        data-testid="suspend-account"
                        onClick={() => setPending({
                          member,
                          state: 'suspended',
                          title: `Suspend ${member.username}'s account?`,
                          description:
                            'Sign-in is blocked and every current session ends immediately.',
                          consequence:
                            'This affects the whole account, not just this organization. If you only want to remove them from this organization’s work, end their membership instead. Their past experiments, reviews and approvals are unaffected either way.',
                        })}
                      >
                        Suspend account
                      </Button>
                    ) : null}

                    {detail.state === 'suspended' || detail.state === 'disabled' ? (
                      <Button
                        variant="secondary"
                        data-testid="restore-account"
                        onClick={() => setPending({
                          member,
                          state: 'active',
                          title: `Restore ${member.username}'s account?`,
                          description:
                            'Sign-in is allowed again, using their existing password.',
                          consequence:
                            'No new password is needed and none is set. If they have forgotten theirs, send a reset link separately.',
                        })}
                      >
                        Restore access
                      </Button>
                    ) : null}

                    {detail.state === 'active' || detail.state === 'suspended' ? (
                      <Button
                        variant="danger"
                        data-testid="disable-account"
                        onClick={() => setPending({
                          member,
                          state: 'disabled',
                          title: `Disable ${member.username}'s account?`,
                          description:
                            'Sign-in is blocked indefinitely and every session ends. Intended for somebody who has left.',
                          consequence:
                            'Reversible by an administrator. Their scientific record — every experiment, review and approval — is kept and stays attributed to them.',
                        })}
                      >
                        Disable account
                      </Button>
                    ) : null}
                  </div>

                  <p className="org-panel__hint" data-testid="no-password-control">
                    {detail.notice}
                  </p>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>

      <ConfirmAction
        open={pending !== null}
        title={pending?.title ?? ''}
        description={pending?.description ?? ''}
        consequence={pending?.consequence}
        confirmPhrase={pending?.member.username ?? ''}
        confirmLabel={pending?.state === 'active' ? 'Restore access' : 'Confirm'}
        busy={busy}
        error={error}
        askForReason
        testId="account-state-confirm"
        onCancel={() => setPending(null)}
        onConfirm={(reason) => void applyState(reason)}
      />
    </Card>
  );
}
