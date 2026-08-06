/**
 * Organization administration.
 *
 * Five views of one organization: its profile, its members, outstanding
 * invitations, external collaborators and the access history. They are tabs
 * rather than five menu entries because they are five questions about the same
 * subject, and an administrator answering "why can this person see that"
 * crosses between them constantly.
 *
 * Two rules govern everything on these screens
 * --------------------------------------------
 * 1. **Authority is shown as two separate things, never one column.** See
 *    `AuthorityLegend`. A user who reads "Administrator" and concludes they can
 *    approve evidence has misunderstood the model the platform rests on.
 * 2. **A hidden control is a courtesy, not a control.** Everything hidden here
 *    is also refused by the backend. The reverse is not a valid inference: a
 *    visible button may still be refused, and the response is the authority.
 *
 * No password is displayed, chosen or transmitted anywhere in this file. People
 * are added by invitation, and they authenticate with their own credentials.
 */

import { useState } from 'react';

import {
  Alert, Badge, Button, Card, DataTable, EmptyState, SectionHeading,
  SkeletonBlock, Tabs, TextField,
} from '../../design-system/components';
import {
  PROBLEM_MESSAGE, useOrganization,
} from '../../organizations/OrganizationContext';
import * as api from '../../api/organizationClient';
import { AuthorityLegend, RoleBadge } from './AuthorityLegend';
import { MembersPanel } from './MembersPanel';
import { AccountsPanel } from './AccountsPanel';
import { InvitationsPanel } from './InvitationsPanel';
import { CollaboratorsPanel } from './CollaboratorsPanel';
import { AccessHistoryPanel } from './AccessHistoryPanel';
import { useScopedData } from './useScopedData';
import './OrganizationAdmin.css';

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'members', label: 'Members & roles' },
  { id: 'accounts', label: 'Accounts & access' },
  { id: 'invitations', label: 'Invitations' },
  { id: 'collaborators', label: 'External collaborators' },
  { id: 'history', label: 'Access history' },
] as const;

export default function OrganizationAdminPage() {
  const { activeId, problem, loading: orgLoading } = useOrganization();
  const [tab, setTab] = useState<string>('profile');

  const profile = useScopedData(
    (signal) => api.getOrganization(activeId as number, signal), []);

  if (orgLoading && activeId === null) {
    return <SkeletonBlock lines={6} />;
  }

  // Every blocking organization state is named explicitly. "No memberships" is
  // not an error and must not be reported as one; "cannot reach the service" is
  // not a permission problem and must not be reported as one either.
  if (problem !== 'none') {
    const message = PROBLEM_MESSAGE[problem];
    return (
      <EmptyState
        title={message.title}
        testId={`organization-problem-${problem}`}
      >
        <p>{message.body}</p>
      </EmptyState>
    );
  }

  if (activeId === null) {
    return (
      <EmptyState title="Choose an organization" testId="no-active-organization">
        <p>
          Select an organization before managing its members. Nothing is chosen
          for you, because records are never shared between organizations.
        </p>
      </EmptyState>
    );
  }

  const capabilities = profile.data?.capabilities ?? {};
  const mayManageMembers = capabilities.manage_members === true;
  const mayManageOrganization = capabilities.manage_organization === true;
  const mayViewHistory = capabilities.view_access_history === true;

  return (
    <div className="org-admin">
      <SectionHeading
        eyebrow="Organization"
        title={profile.data?.name ?? 'Organization'}
        description={
          'Who belongs to this organization, what authority they hold, and '
          + 'every change that has been made to it.'
        }
      />

      <AuthorityLegend />

      {profile.error && (
        <Alert tone="danger" title="Could not load the organization" role="alert">
          {profile.error}
        </Alert>
      )}

      <Tabs
        tabs={TABS.map((t) => ({ id: t.id, label: t.label }))}
        active={tab}
        onChange={setTab}
        ariaLabel="Organization administration"
      />

      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="org-admin__panel"
      >
        {tab === 'profile' && (
          <ProfilePanel
            organizationId={activeId}
            profile={profile.data}
            loading={profile.loading}
            mayManage={mayManageOrganization}
            onChanged={profile.reload}
          />
        )}
        {tab === 'members' && (
          <MembersPanel
            organizationId={activeId}
            mayManage={mayManageMembers}
          />
        )}
        {/* Accounts sits next to members deliberately: the two are what get
            confused with each other. Ending a *membership* is on the members
            tab; suspending an *account* is here, and each says at the point of
            use which one it is. */}
        {tab === 'accounts' && (
          <AccountsPanelLoader
            organizationId={activeId}
            canAdminister={mayManageMembers}
          />
        )}
        {tab === 'invitations' && (
          <InvitationsPanel
            organizationId={activeId}
            mayManage={mayManageMembers}
          />
        )}
        {tab === 'collaborators' && (
          <CollaboratorsPanel
            organizationId={activeId}
            mayManage={mayManageMembers}
          />
        )}
        {tab === 'history' && (
          <AccessHistoryPanel
            organizationId={activeId}
            mayView={mayViewHistory}
          />
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------ */
/* Profile, including confirmation of a migrated organization                */
/* ------------------------------------------------------------------------ */

function ProfilePanel({
  organizationId, profile, loading, mayManage, onChanged,
}: {
  organizationId: number;
  profile: api.OrganizationProfile | null;
  loading: boolean;
  mayManage: boolean;
  onChanged: () => void;
}) {
  const [name, setName] = useState<string | null>(null);
  const [description, setDescription] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmPhrase, setConfirmPhrase] = useState('');

  if (loading || !profile) return <SkeletonBlock lines={5} />;

  const save = async () => {
    setBusy(true);
    setError(null);
    setSaved(null);
    const result = await api.updateOrganization(organizationId, {
      name: name ?? profile.name,
      description: description ?? profile.description,
    });
    setBusy(false);
    if (result.status === 'error') {
      setError(result.error.message);
      return;
    }
    setSaved('Profile updated. The change is in the access history.');
    onChanged();
  };

  const confirm = async () => {
    setBusy(true);
    setError(null);
    const result = await api.confirmOrganization(organizationId);
    setBusy(false);
    setConfirming(false);
    setConfirmPhrase('');
    if (result.status === 'error') {
      setError(result.error.message);
      return;
    }
    setSaved(result.data.notice ?? 'Organization confirmed.');
    onChanged();
  };

  return (
    <>
      {profile.awaiting_confirmation && (
        <Card
          title="This organization was created by an upgrade"
          accent
          className="org-admin__pending"
        >
          <Alert tone="warn" title="Scientific changes are on hold">
            <p>
              The upgrade created this organization to hold data that existed
              before organizations did. It could not know which accounts should
              hold scientific authority, so it granted none — guessing would
              have silently created approvers.
            </p>
            <p>
              Check the members list, then confirm. <strong>Confirming grants
              nobody scientific authority.</strong> It only lifts the hold on
              scientific changes; reviewers and approvers must still be
              appointed explicitly, on each study.
            </p>
          </Alert>

          {mayManage ? (
            confirming ? (
              <div data-testid="confirm-organization-dialog">
                <TextField
                  id="confirm-organization-phrase"
                  label={`Type ${profile.slug} to confirm`}
                  value={confirmPhrase}
                  autoComplete="off"
                  onChange={(e) => setConfirmPhrase(e.target.value)}
                  help="Typing the slug makes you check which organization you are confirming."
                />
                <div className="org-admin__row-actions">
                  <Button variant="ghost" onClick={() => setConfirming(false)}>
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    loading={busy}
                    disabled={confirmPhrase.trim() !== profile.slug}
                    onClick={confirm}
                    data-testid="confirm-organization-submit"
                  >
                    Confirm memberships
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="primary"
                onClick={() => setConfirming(true)}
                data-testid="confirm-organization"
              >
                Confirm this organization
              </Button>
            )
          ) : (
            <p className="org-admin__muted">
              Only the organization owner can confirm this.
            </p>
          )}
        </Card>
      )}

      <Card title="Organization profile">
        {saved && <Alert tone="success" role="status">{saved}</Alert>}
        {error && <Alert tone="danger" role="alert">{error}</Alert>}

        <dl className="org-admin__facts">
          <div>
            <dt>Identifier</dt>
            <dd>
              <code>{profile.slug}</code>
              <p className="org-admin__muted">
                Fixed. Audit records written years ago name this organization by
                its identifier, so a rename stays traceable.
              </p>
            </dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>
              <Badge
                tone={profile.status === 'active' ? 'success' : 'warn'}
                dot
              >
                {profile.status.replace(/_/g, ' ')}
              </Badge>
            </dd>
          </div>
          <div>
            <dt>Your role here</dt>
            <dd>
              {profile.your_role
                ? <RoleBadge role={profile.your_role} testId="your-role" />
                : '—'}
            </dd>
          </div>
        </dl>

        {mayManage ? (
          <>
            <TextField
              id="organization-name"
              label="Display name"
              value={name ?? profile.name}
              onChange={(e) => setName(e.target.value)}
            />
            <TextField
              id="organization-description"
              label="Description"
              value={description ?? profile.description ?? ''}
              onChange={(e) => setDescription(e.target.value)}
            />
            <Button variant="primary" loading={busy} onClick={save}
                    data-testid="save-profile">
              Save profile
            </Button>
          </>
        ) : (
          <Alert tone="info" title="Read-only">
            Changing the organization profile requires the organization owner.
            You can see everything on this page; the controls that would change
            it are not offered, and the service would refuse them in any case.
          </Alert>
        )}
      </Card>
    </>
  );
}

/** Shared by the panels: a table with an explicit empty state. */
export function PanelTable({
  caption, head, rows, empty, testId,
}: {
  caption: string;
  head: ReadonlyArray<{ key: string; label: string; width?: string }>;
  rows: React.ReactNode;
  empty: boolean;
  testId: string;
}) {
  if (empty) {
    return <EmptyState title={caption} testId={`${testId}-empty`} />;
  }
  return (
    <div data-testid={testId}>
      <DataTable caption={caption} head={head}>{rows}</DataTable>
    </div>
  );
}


/**
 * Loads the roster for the accounts panel.
 *
 * Separate from `AccountsPanel` so the panel stays a pure rendering of a list
 * it is given, and reuses `useScopedData` so switching organization mid-load
 * discards the previous organization's roster rather than rendering it under
 * the new organization's name.
 */
function AccountsPanelLoader({
  organizationId, canAdminister,
}: { organizationId: number; canAdminister: boolean }) {
  const members = useScopedData(
    (signal) => api.listMembers(organizationId, signal),
    [organizationId],
  );

  if (members.loading) return <SkeletonBlock lines={4} />;
  if (members.error) {
    return (
      <Alert tone="danger" title="Could not load accounts" role="alert">
        {members.error}
      </Alert>
    );
  }

  return (
    <AccountsPanel
      organizationId={organizationId}
      members={members.data?.members ?? []}
      canAdminister={canAdminister}
      onChanged={members.reload}
    />
  );
}
