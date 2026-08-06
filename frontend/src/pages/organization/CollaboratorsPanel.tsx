/**
 * External collaborators — CROs, partner laboratories, anybody not staff.
 *
 * A separate screen rather than a filter on the members list, because "who from
 * outside can currently reach our data" is the question an access review
 * actually asks, and it is not reliably answered by scanning forty rows for the
 * four that carry a badge.
 *
 * Least privilege is stated here in the terms it is enforced in: an assigned
 * study, a start and expiry date, and whether attachments may leave the
 * building. Each of those is a real constraint the backend evaluates on every
 * request — none of them is a label this screen applies.
 */

import { useState } from 'react';

import {
  Alert, Badge, Button, Card, SkeletonBlock,
} from '../../design-system/components';
import * as api from '../../api/organizationClient';
import { ConfirmAction } from './ConfirmAction';
import { RoleBadge } from './AuthorityLegend';
import { PanelTable } from './OrganizationAdminPage';
import { useScopedData } from './useScopedData';

const HEAD = [
  { key: 'person', label: 'Person' },
  { key: 'body', label: 'Outside body' },
  { key: 'role', label: 'Eligibility' },
  { key: 'window', label: 'Access window' },
  { key: 'attachments', label: 'Attachments' },
  { key: 'actions', label: 'Actions' },
] as const;

function formatWindow(member: api.Member): string {
  const from = member.starts_at
    ? new Date(member.starts_at).toLocaleDateString() : 'immediately';
  const to = member.expires_at
    ? new Date(member.expires_at).toLocaleDateString() : 'no end date';
  return `${from} → ${to}`;
}

export function CollaboratorsPanel({ organizationId, mayManage }: {
  organizationId: number; mayManage: boolean;
}) {
  const collaborators = useScopedData(
    (signal) => api.listCollaborators(organizationId, signal),
    [organizationId]);
  const [ending, setEnding] = useState<api.Member | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (collaborators.loading) return <SkeletonBlock lines={5} />;
  if (collaborators.error) {
    return (
      <Alert tone="danger" title="Could not load collaborators" role="alert">
        {collaborators.error}
      </Alert>
    );
  }

  const rows = collaborators.data?.collaborators ?? [];

  return (
    <Card
      title="External collaborators"
      subtitle={collaborators.data?.notice}
    >
      <Alert tone="info" title="What an external collaborator can reach">
        <ul>
          <li>Only the studies they are explicitly assigned to.</li>
          <li>
            No organization-wide records, and no study they have not been
            assigned — including studies in this organization.
          </li>
          <li>
            Attachment downloads only where the collaboration and the specific
            assignment both permit them.
          </li>
          <li>
            Expiry is evaluated on <strong>every request</strong>, not at
            sign-in. A lapsed collaboration stops working the moment it lapses,
            whether or not anything has marked it expired.
          </li>
        </ul>
      </Alert>

      {error && !ending && <Alert tone="danger" role="alert">{error}</Alert>}

      <PanelTable
        caption="External collaborators"
        head={HEAD}
        empty={rows.length === 0}
        testId="collaborators-table"
        rows={rows.map((member) => (
          <tr key={member.id}
              data-testid={`collaborator-${member.username}`}>
            <td>{member.username}</td>
            <td>{member.external_organization ?? '—'}</td>
            <td><RoleBadge role={member.role} /></td>
            <td>{formatWindow(member)}</td>
            <td>
              <Badge tone={member.may_download_attachments
                ? 'neutral' : 'warn'} dot>
                {member.may_download_attachments
                  ? 'Downloads permitted' : 'Downloads withheld'}
              </Badge>
            </td>
            <td>
              {mayManage && member.is_active ? (
                <Button
                  variant="danger"
                  data-testid={`end-collaboration-${member.username}`}
                  onClick={() => setEnding(member)}
                >
                  End collaboration
                </Button>
              ) : (
                <Badge tone="neutral">{member.status}</Badge>
              )}
            </td>
          </tr>
        ))}
      />

      {ending && (
        <ConfirmAction
          open
          title="End this collaboration"
          confirmPhrase={ending.username}
          confirmLabel="End access now"
          testId="confirm-end-collaboration"
          description={
            `${ending.username} of ${ending.external_organization} will lose `
            + 'access from their next request.'
          }
          consequence={
            <>
              <p>Every study assignment they hold here ends at the same time.</p>
              <p>
                Measurements and experiments they contributed keep naming them.
                Revocation governs what happens next, not what already happened.
              </p>
            </>
          }
          busy={busy}
          error={error}
          onCancel={() => { setEnding(null); setError(null); }}
          onConfirm={async (reason) => {
            setBusy(true);
            const result = await api.revokeMember(organizationId, ending.id, {
              reason: reason || undefined,
              expected_revision: ending.revision,
            });
            setBusy(false);
            if (result.status === 'error') {
              setError(result.error.message);
              return;
            }
            setEnding(null);
            collaborators.reload();
          }}
        />
      )}
    </Card>
  );
}
