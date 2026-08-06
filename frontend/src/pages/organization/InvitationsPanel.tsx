/**
 * Invitations, and the administrator-controlled workflow when nothing sends them.
 *
 * The link is shown once
 * ----------------------
 * The backend stores only a hash of the token, so the link genuinely cannot be
 * retrieved a second time — not by this screen, not by anybody. That is not an
 * inconvenience to work around: the token is a working credential for an
 * account that may not exist yet, and a list endpoint that could reproduce it
 * would put a live credential behind every administrator's session.
 *
 * So the link appears exactly once, in the response that created it, and this
 * screen says so plainly. Losing it costs a re-issue, which also stops the
 * previous link working.
 *
 * No password is set, shown or chosen anywhere in this flow. The recipient
 * authenticates with their own credentials and redeems the token; an
 * administrator never learns it.
 */

import { useState } from 'react';

import {
  Alert, Badge, Button, Card, SelectField, SkeletonBlock, TextField,
} from '../../design-system/components';
import * as api from '../../api/organizationClient';
import { ConfirmAction } from './ConfirmAction';
import { RoleBadge } from './AuthorityLegend';
import { PanelTable } from './OrganizationAdminPage';
import { useScopedData } from './useScopedData';

const HEAD = [
  { key: 'email', label: 'Invited address' },
  { key: 'role', label: 'Authority offered' },
  { key: 'expires', label: 'Link expires' },
  { key: 'delivery', label: 'Delivery' },
  { key: 'status', label: 'Status' },
  { key: 'actions', label: 'Actions' },
] as const;

export function InvitationsPanel({ organizationId, mayManage }: {
  organizationId: number; mayManage: boolean;
}) {
  const invitations = useScopedData(
    (signal) => api.listInvitations(organizationId, true, signal),
    [organizationId]);

  const [email, setEmail] = useState('');
  const [role, setRole] = useState('researcher');
  const [external, setExternal] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [allowDownloads, setAllowDownloads] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<api.Invitation | null>(null);
  const [withdrawing, setWithdrawing] = useState<api.Invitation | null>(null);

  if (!mayManage) {
    return (
      <Alert tone="info" title="Read-only">
        Inviting people requires an organization owner or administrator.
      </Alert>
    );
  }

  if (invitations.loading) return <SkeletonBlock lines={6} />;

  const rows = invitations.data?.invitations ?? [];
  const provider = invitations.data?.delivery_provider ?? 'recorded';

  const invite = async () => {
    setBusy(true);
    setError(null);
    setIssued(null);
    const result = await api.createInvitation(organizationId, {
      email: email.trim(),
      role,
      expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      external_organization: external.trim() || null,
      may_download_attachments: allowDownloads,
    });
    setBusy(false);
    if (result.status === 'error') {
      setError(result.error.message);
      return;
    }
    setIssued(result.data);
    setEmail('');
    setExternal('');
    invitations.reload();
  };

  return (
    <>
      <Card
        title="Invite somebody to this organization"
        subtitle="Membership grants no scientific authority on any study."
      >
        {provider === 'recorded' && (
          <Alert tone="info" title="No delivery service is configured">
            <p>
              Nothing is emailed. The invitation link is shown to you once, here,
              and you pass it to the recipient by whatever channel you already
              trust.
            </p>
            <p>
              This is deliberate rather than a gap: an invitation that silently
              failed to send looks exactly like one that arrived, and the
              recipient is the only person who would ever find out.
            </p>
          </Alert>
        )}

        {error && <Alert tone="danger" role="alert">{error}</Alert>}

        {issued?.invitation_link && (
          <Alert
            tone="success"
            title="Invitation created — copy this link now"
            role="status"
          >
            <p data-testid="invitation-link" className="org-admin__link">
              <code>{issued.invitation_link}</code>
            </p>
            <p>{issued.notice}</p>
            <Button
              variant="secondary"
              data-testid="copy-invitation-link"
              onClick={() => {
                void navigator.clipboard?.writeText(
                  issued.invitation_link as string);
              }}
            >
              Copy link
            </Button>
          </Alert>
        )}

        <TextField
          id="invite-email"
          label="Email address"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          help="The invitation can only be redeemed by an account holding this address."
        />
        <SelectField
          id="invite-role"
          label="Organization role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          options={api.ORGANIZATION_ROLES.map((r) => ({
            value: r.value,
            label: `${r.label} — ${r.kind === 'authority'
              ? 'manages access, cannot approve evidence'
              : r.kind === 'scientific'
                ? 'eligible for scientific work once assigned to a study'
                : 'reads only'}`,
          }))}
          help={
            'This decides what they are eligible for. It never assigns them to '
            + 'a study, and a reviewer or approver still has to be appointed '
            + 'per study.'
          }
        />
        <TextField
          id="invite-external"
          label="External organization (for a CRO or partner)"
          value={external}
          onChange={(e) => setExternal(e.target.value)}
          help="Naming an outside body marks this as an external collaboration in every access review."
        />
        <TextField
          id="invite-expires"
          label="Access expires on"
          type="date"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
          help="Evaluated on every request, not only at sign-in. Leave empty for permanent staff."
        />
        <label className="org-admin__check">
          <input
            type="checkbox"
            checked={allowDownloads}
            data-testid="invite-allow-downloads"
            onChange={(e) => setAllowDownloads(e.target.checked)}
          />
          {' '}May download attachments
          <span className="org-admin__muted">
            {' '}Clear this for a collaboration that permits reading results but
            not taking raw instrument files off-site.
          </span>
        </label>

        <Button
          variant="primary"
          loading={busy}
          disabled={!email.trim()}
          onClick={invite}
          data-testid="send-invitation"
        >
          Create invitation
        </Button>
      </Card>

      <Card title="Invitations" flush>
        <PanelTable
          caption="Invitations"
          head={HEAD}
          empty={rows.length === 0}
          testId="invitations-table"
          rows={rows.map((invitation) => (
            <tr key={invitation.id}
                data-testid={`invitation-${invitation.id}`}>
              <td>
                {invitation.email}
                {invitation.is_external && (
                  <Badge tone="info">
                    External · {invitation.external_organization}
                  </Badge>
                )}
              </td>
              <td><RoleBadge role={invitation.role} /></td>
              <td>{new Date(invitation.expires_at).toLocaleString()}</td>
              <td>
                <Badge tone={invitation.delivery_status === 'sent'
                  ? 'success' : 'neutral'}>
                  {invitation.delivery_status ?? '—'}
                </Badge>
              </td>
              <td>
                <Badge
                  tone={invitation.status === 'pending' ? 'accent'
                    : invitation.status === 'accepted' ? 'success' : 'neutral'}
                  dot
                >
                  {invitation.status}
                </Badge>
              </td>
              <td>
                {invitation.status === 'pending' && (
                  <div className="org-admin__row-actions">
                    <Button
                      variant="ghost"
                      data-testid={`resend-${invitation.id}`}
                      onClick={async () => {
                        const result = await api.resendInvitation(
                          organizationId, invitation.id);
                        if (result.status === 'ok') {
                          setIssued(result.data);
                          invitations.reload();
                        } else {
                          setError(result.error.message);
                        }
                      }}
                    >
                      Re-issue link
                    </Button>
                    <Button
                      variant="danger"
                      data-testid={`withdraw-${invitation.id}`}
                      onClick={() => setWithdrawing(invitation)}
                    >
                      Withdraw
                    </Button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        />
      </Card>

      {withdrawing && (
        <ConfirmAction
          open
          title="Withdraw this invitation"
          confirmPhrase={withdrawing.email}
          confirmLabel="Withdraw invitation"
          testId="confirm-withdraw"
          description={
            `The link sent to ${withdrawing.email} will stop working `
            + 'immediately.'
          }
          consequence={
            <p>
              If they have already opened it but not accepted, they will see the
              same "not found" as somebody with a token that never existed.
            </p>
          }
          busy={busy}
          error={error}
          onCancel={() => { setWithdrawing(null); setError(null); }}
          onConfirm={async (reason) => {
            setBusy(true);
            const result = await api.revokeInvitation(
              organizationId, withdrawing.id, reason || undefined);
            setBusy(false);
            if (result.status === 'error') {
              setError(result.error.message);
              return;
            }
            setWithdrawing(null);
            invitations.reload();
          }}
        />
      )}
    </>
  );
}
