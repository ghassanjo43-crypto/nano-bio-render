/**
 * Redeeming an invitation.
 *
 * The page takes the token from the query string and sends it to the backend.
 * It does not read a `next`, `return_to` or `redirect` parameter, and it never
 * navigates anywhere the link asked it to — landing is decided here, in the
 * application. An invitation link that could be told where to send somebody
 * afterwards would be a phishing primitive arriving with an organization's name
 * on it, and no feature needs one.
 *
 * Every failure reads the same. The backend answers unknown, expired, revoked,
 * already-used and wrong-account identically, and this page must not helpfully
 * distinguish them: telling a stranger their token "has expired" confirms it
 * was real, which confirms the organization exists and was inviting people.
 */

import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import {
  Alert, Button, Card, SectionHeading,
} from '../../design-system/components';
import * as api from '../../api/organizationClient';
import { useOrganization } from '../../organizations/OrganizationContext';
import './OrganizationAdmin.css';

export default function AcceptInvitationPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { refresh, select } = useOrganization();
  const token = params.get('token') ?? '';

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<{
    organization_id: number; role: string; notice: string;
  } | null>(null);

  const accept = async () => {
    setBusy(true);
    setError(null);
    const result = await api.acceptInvitation(token);
    setBusy(false);
    if (result.status === 'error') {
      // Deliberately one message for every cause.
      setError(
        'This invitation cannot be used. It may have been withdrawn, already '
        + 'accepted, or issued to a different account. Ask whoever invited you '
        + 'to issue a new one.');
      return;
    }
    setAccepted(result.data);
    // The new membership changes what the switcher may offer, so the listing
    // is reloaded and the new organization selected explicitly.
    select(result.data.organization_id);
    await refresh();
  };

  return (
    <div className="org-admin org-admin--narrow">
      <SectionHeading
        eyebrow="Invitation"
        title="Join an organization"
        description="Accepting adds you to an organization. It grants no scientific authority on any study."
      />

      {!token && (
        <Alert tone="warn" title="No invitation token" role="status">
          This page needs the link you were sent. Open the invitation link
          itself rather than navigating here.
        </Alert>
      )}

      {error && (
        <div data-testid="invitation-error">
          <Alert tone="danger" title="Cannot accept this invitation" role="alert">
            {error}
          </Alert>
        </div>
      )}

      {accepted ? (
        <Card title="You have joined">
          <Alert tone="success" role="status">
            <div data-testid="invitation-accepted">
            <p>{accepted.notice}</p>
            <p>
              Your role here is <strong>{api.roleLabel(accepted.role)}</strong>.
              Reviewing and approving evidence require a separate assignment on
              each study, made by an owner or administrator.
            </p>
            </div>
          </Alert>
          <Button variant="primary" onClick={() => navigate('/start')}>
            Continue to the workspace
          </Button>
        </Card>
      ) : (
        <Card title="Accept this invitation">
          <p>
            You will be added to the organization that invited you, with the
            role chosen by whoever invited you. Nothing is shared between
            organizations, and joining one does not change your access to any
            other.
          </p>
          <Button
            variant="primary"
            loading={busy}
            disabled={!token}
            onClick={accept}
            data-testid="accept-invitation"
          >
            Accept invitation
          </Button>
        </Card>
      )}
    </div>
  );
}
