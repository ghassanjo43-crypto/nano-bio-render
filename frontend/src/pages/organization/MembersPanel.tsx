/**
 * Members and organization roles.
 *
 * What this screen deliberately does not offer
 * -------------------------------------------
 * * **No password field, anywhere.** People are added by invitation and
 *   authenticate with their own credentials. An administrator who can set
 *   somebody's password can also sign in as them, which would make every
 *   attribution in the registry unfalsifiable.
 * * **No control to change your own role.** The backend refuses it for
 *   everybody including owners, and offering a control that is always refused
 *   would teach users to ignore refusals. The reason is shown in its place.
 * * **No "make approver" shortcut on a study.** Scientific authority takes a
 *   role change and a study assignment, by two different acts. Collapsing them
 *   into one button here would rebuild the escalation path the model exists to
 *   prevent.
 *
 * Sensitive actions — removal, demotion, suspension — go through
 * `ConfirmAction`, which requires the subject's name to be typed.
 */

import { useState } from 'react';

import {
  Alert, Badge, Button, Card, SelectField, SkeletonBlock,
} from '../../design-system/components';
import * as api from '../../api/organizationClient';
import { useAuth } from '../../auth/AuthContext';
import { ConfirmAction } from './ConfirmAction';
import { RoleBadge } from './AuthorityLegend';
import { PanelTable } from './OrganizationAdminPage';
import { useScopedData } from './useScopedData';

type Pending =
  | { kind: 'revoke'; member: api.Member }
  | { kind: 'suspend'; member: api.Member }
  | { kind: 'demote'; member: api.Member; role: string }
  | null;

const HEAD = [
  { key: 'person', label: 'Person' },
  { key: 'authority', label: 'Authority' },
  { key: 'scope', label: 'Reach' },
  { key: 'status', label: 'Status' },
  { key: 'expires', label: 'Expires' },
  { key: 'actions', label: 'Actions' },
] as const;

export function MembersPanel({ organizationId, mayManage }: {
  organizationId: number; mayManage: boolean;
}) {
  const { user } = useAuth();
  const members = useScopedData(
    (signal) => api.listMembers(organizationId, signal), [organizationId]);
  const [pending, setPending] = useState<Pending>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (members.loading) return <SkeletonBlock lines={6} />;
  if (members.error) {
    return (
      <Alert tone="danger" title="Could not load members" role="alert">
        {members.error}
      </Alert>
    );
  }

  const rows = members.data?.members ?? [];
  const activeOwners = rows.filter(
    (m) => m.role === 'owner' && m.is_active).length;

  const run = async (
    action: () => Promise<{ status: string; error?: { message: string } }>,
    success: string,
  ) => {
    setBusy(true);
    setError(null);
    const result = await action();
    setBusy(false);
    if (result.status === 'error') {
      setError(result.error?.message ?? 'The change was not applied.');
      return;
    }
    setPending(null);
    setNotice(success);
    members.reload();
  };

  const confirmCopy = (): {
    title: string; description: string; consequence: React.ReactNode;
    label: string; phrase: string;
  } | null => {
    if (!pending) return null;
    if (pending.kind === 'revoke') {
      return {
        title: 'Remove this member',
        phrase: pending.member.username,
        label: 'Remove access',
        description:
          `${pending.member.username} will lose access to this organization `
          + 'from their next request.',
        consequence: (
          <>
            <p>
              Every study assignment they hold here ends at the same time.
            </p>
            <p>
              <strong>Their work is not deleted or reattributed.</strong>{' '}
              Experiments they performed still name them, because an experiment
              somebody ran is still an experiment they ran.
            </p>
          </>
        ),
      };
    }
    if (pending.kind === 'suspend') {
      return {
        title: 'Suspend this member',
        phrase: pending.member.username,
        label: 'Suspend access',
        description:
          `${pending.member.username} will be blocked from this organization `
          + 'until they are reinstated.',
        consequence: (
          <p>
            Reversible. The membership row and its history are kept, which is
            what makes this the right tool for "stop this person for now".
          </p>
        ),
      };
    }
    return {
      title: 'Change this role',
      phrase: pending.member.username,
      label: 'Change role',
      description:
        `${pending.member.username} will hold the role `
        + `${api.roleLabel(pending.role)} instead of `
        + `${api.roleLabel(pending.member.role)}.`,
      consequence: (
        <p>
          A membership carries exactly one role. Moving somebody onto the
          scientific ladder removes their organization authority in the same
          act, and moving them onto the administrative ladder removes their
          eligibility for scientific work.
        </p>
      ),
    };
  };

  const copy = confirmCopy();

  return (
    <Card
      title="Members and organization roles"
      subtitle={
        'Organization authority governs people and access. It is never '
        + 'scientific authority.'
      }
    >
      {notice && <Alert tone="success" role="status">{notice}</Alert>}
      {error && !pending && (
        <Alert tone="danger" role="alert">{error}</Alert>
      )}

      {activeOwners === 1 && (
        <Alert tone="info" title="One active owner">
          This organization has a single active owner, so that membership
          cannot be removed, demoted or suspended. Appoint a second owner
          first — an organization with no owner cannot be administered by
          anybody inside it.
        </Alert>
      )}

      <PanelTable
        caption="Members"
        head={HEAD}
        empty={rows.length === 0}
        testId="members-table"
        rows={rows.map((member) => {
          const isSelf = user?.username === member.username;
          const lastOwner = member.role === 'owner' && activeOwners === 1;
          return (
            <tr key={member.id} data-testid={`member-${member.username}`}>
              <td>
                <span className="org-admin__person">{member.username}</span>
                {member.is_external && (
                  <Badge tone="info">
                    External · {member.external_organization}
                  </Badge>
                )}
                {isSelf && <span className="org-admin__muted"> (you)</span>}
              </td>
              <td>
                <RoleBadge
                  role={member.role}
                  testId={`member-role-${member.username}`}
                />
              </td>
              <td>
                {member.scope === 'organization'
                  ? 'Every study'
                  : 'Assigned studies only'}
              </td>
              <td>
                <Badge
                  tone={member.is_active ? 'success'
                    : member.status === 'suspended' ? 'warn' : 'neutral'}
                  dot
                >
                  {member.status}
                </Badge>
              </td>
              <td>
                {member.expires_at
                  ? new Date(member.expires_at).toLocaleDateString()
                  : '—'}
              </td>
              <td>
                {!mayManage && (
                  <span className="org-admin__muted">
                    Managing members requires an owner or administrator.
                  </span>
                )}
                {mayManage && isSelf && (
                  <span
                    className="org-admin__muted"
                    data-testid={`self-locked-${member.username}`}
                  >
                    You cannot change your own role or status. Ask another
                    owner or administrator, so no one person can grant
                    themselves authority.
                  </span>
                )}
                {mayManage && !isSelf && (
                  <div className="org-admin__row-actions">
                    <SelectField
                      id={`role-${member.id}`}
                      label="Change role"
                      value={member.role}
                      disabled={lastOwner}
                      options={api.ORGANIZATION_ROLES.map((r) => ({
                        value: r.value, label: r.label,
                      }))}
                      onChange={(e) => {
                        if (e.target.value !== member.role) {
                          setPending({
                            kind: 'demote', member, role: e.target.value,
                          });
                        }
                      }}
                    />
                    {member.status === 'suspended' ? (
                      <Button
                        variant="ghost"
                        data-testid={`reinstate-${member.username}`}
                        onClick={() => run(
                          () => api.setMemberStatus(
                            organizationId, member.id,
                            { status: 'active',
                              expected_revision: member.revision }),
                          `${member.username} reinstated.`)}
                      >
                        Reinstate
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        disabled={lastOwner}
                        data-testid={`suspend-${member.username}`}
                        onClick={() => setPending({ kind: 'suspend', member })}
                      >
                        Suspend
                      </Button>
                    )}
                    <Button
                      variant="danger"
                      disabled={lastOwner}
                      data-testid={`remove-${member.username}`}
                      onClick={() => setPending({ kind: 'revoke', member })}
                    >
                      Remove
                    </Button>
                  </div>
                )}
              </td>
            </tr>
          );
        })}
      />

      {pending && copy && (
        <ConfirmAction
          open
          title={copy.title}
          description={copy.description}
          consequence={copy.consequence}
          confirmPhrase={copy.phrase}
          confirmLabel={copy.label}
          busy={busy}
          error={error}
          testId={`confirm-${pending.kind}`}
          onCancel={() => { setPending(null); setError(null); }}
          onConfirm={(reason) => {
            if (pending.kind === 'revoke') {
              void run(
                () => api.revokeMember(organizationId, pending.member.id, {
                  reason: reason || undefined,
                  expected_revision: pending.member.revision,
                }),
                `${pending.member.username} no longer has access.`);
            } else if (pending.kind === 'suspend') {
              void run(
                () => api.setMemberStatus(organizationId, pending.member.id, {
                  status: 'suspended',
                  reason: reason || undefined,
                  expected_revision: pending.member.revision,
                }),
                `${pending.member.username} is suspended.`);
            } else {
              void run(
                () => api.changeMemberRole(organizationId, pending.member.id, {
                  role: pending.role,
                  expected_revision: pending.member.revision,
                }),
                `${pending.member.username} is now `
                + `${api.roleLabel(pending.role)}.`);
            }
          }}
        />
      )}
    </Card>
  );
}
