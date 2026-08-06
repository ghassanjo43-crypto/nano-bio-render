/**
 * The study team: who may do scientific work on one study, and until when.
 *
 * Why this is a separate screen from members
 * -----------------------------------------
 * Because they answer different questions, and merging them is precisely the
 * confusion the access model exists to prevent. The members screen answers
 * "who belongs to this organization and what authority do they hold over
 * access". This one answers "who may submit, review or approve evidence on
 * *this* study". Somebody can be an organization administrator and appear
 * nowhere here; somebody can be a reviewer here and be unable to add a single
 * person to the organization.
 *
 * The appointment rule, stated on the screen
 * ------------------------------------------
 * Appointment is an administrative act; eligibility comes from the
 * organization role; nobody changes their own. So the role menu for each
 * person is built from `assignable_study_roles`, which the *backend* computes
 * from their membership — not from a copy of the mapping kept here, which
 * would drift and would then offer a role that is always refused.
 */

import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import {
  Alert, Badge, Button, Card, SectionHeading, SelectField, SkeletonBlock,
  TextField,
} from '../../design-system/components';
import * as api from '../../api/organizationClient';
import { useOrganization } from '../../organizations/OrganizationContext';
import { ConfirmAction } from './ConfirmAction';
import { AuthorityLegend, RoleBadge } from './AuthorityLegend';
import { PanelTable } from './OrganizationAdminPage';
import { useScopedData } from './useScopedData';
import './OrganizationAdmin.css';

const HEAD = [
  { key: 'person', label: 'Person' },
  { key: 'role', label: 'Scientific assignment' },
  { key: 'window', label: 'From → until' },
  { key: 'attachments', label: 'Attachments' },
  { key: 'note', label: 'Reason' },
  { key: 'status', label: 'Status' },
  { key: 'actions', label: 'Actions' },
] as const;

function windowOf(assignment: api.Assignment): string {
  const from = assignment.starts_at
    ? new Date(assignment.starts_at).toLocaleDateString() : 'immediately';
  const to = assignment.expires_at
    ? new Date(assignment.expires_at).toLocaleDateString() : 'no end date';
  return `${from} → ${to}`;
}

export default function StudyTeamPage() {
  const { studyId } = useParams();
  const { activeId } = useOrganization();
  const study = Number(studyId);

  const team = useScopedData(
    (signal) => api.listStudyTeam(activeId as number, study, signal),
    [activeId, study]);
  const members = useScopedData(
    (signal) => api.listMembers(activeId as number, signal), [activeId]);
  const history = useScopedData(
    (signal) => api.getTeamHistory(activeId as number, study, signal),
    [activeId, study]);

  const [personId, setPersonId] = useState('');
  const [role, setRole] = useState('');
  const [startsAt, setStartsAt] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [withholdDownloads, setWithholdDownloads] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<api.Assignment | null>(null);

  const roster = members.data?.members ?? [];
  const selected = useMemo(
    () => roster.find((m) => String(m.user_id) === personId),
    [roster, personId]);

  // Straight from the membership the backend returned. Never a client-side
  // copy of the eligibility mapping.
  const eligibleRoles = selected?.assignable_study_roles ?? [];

  if (!activeId) {
    return (
      <Alert tone="info" title="Choose an organization">
        A study belongs to one organization. Select it before managing the team.
      </Alert>
    );
  }

  if (team.loading || members.loading) return <SkeletonBlock lines={8} />;

  if (team.error) {
    return (
      <Alert tone="danger" title="Study team unavailable" role="alert">
        <p>{team.error}</p>
        <p>
          A study from another organization is correctly invisible here. If you
          have just switched organization, this is expected rather than an
          error.
        </p>
      </Alert>
    );
  }

  const assignments = team.data?.assignments ?? [];

  const appoint = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    const result = await api.assignToStudy(activeId, study, {
      user_id: Number(personId),
      role,
      starts_at: startsAt ? new Date(startsAt).toISOString() : null,
      expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      // Only ever sent as a restriction. `true` is never sent, because an
      // assignment cannot grant downloads a membership withholds.
      may_download_attachments: withholdDownloads ? false : null,
      note: note.trim() || null,
    });
    setBusy(false);
    if (result.status === 'error') {
      setError(result.error.message);
      return;
    }
    setNotice(`${result.data.username} assigned as `
      + `${api.roleLabel(result.data.role)}.`);
    setPersonId('');
    setRole('');
    setNote('');
    team.reload();
    history.reload();
  };

  return (
    <div className="org-admin">
      <SectionHeading
        eyebrow="Study team"
        title={`Scientific assignments — study #${study}`}
        description={
          'Scientific capability comes from these assignments and nowhere '
          + 'else. Organization authority grants none of it.'
        }
      />

      <AuthorityLegend />

      <Alert tone="info" title="Who may appoint, and why that cannot escalate">
        <p>
          Appointing is an administrative act, so it needs an organization owner
          or administrator. What they may appoint somebody to comes from that
          person's organization role — an administrator cannot appoint anybody
          to a role their membership does not already make them eligible for.
        </p>
        <p>
          And nobody may change their own organization role, including owners.
          So making somebody an approver takes two acts by two different people:
          a role change, and this assignment. Neither alone is enough.
        </p>
        <p>
          Assignment still never overrides independence: a person who performed
          or authored an experiment cannot review or approve <em>that</em>{' '}
          experiment, whatever they are assigned.
        </p>
      </Alert>

      {notice && <Alert tone="success" role="status">{notice}</Alert>}
      {error && !revoking && <Alert tone="danger" role="alert">{error}</Alert>}

      <Card title="Appoint somebody to this study">
        <SelectField
          id="team-person"
          label="Person"
          value={personId}
          onChange={(e) => { setPersonId(e.target.value); setRole(''); }}
          options={[
            { value: '', label: 'Select a member…' },
            ...roster
              .filter((m) => m.is_active)
              .map((m) => ({
                value: String(m.user_id),
                label: `${m.username} — organization ${api.roleLabel(m.role)}`,
              })),
          ]}
          help="Only active members of this organization can be appointed."
        />

        <SelectField
          id="team-role"
          label="Scientific role on this study"
          value={role}
          disabled={!selected}
          onChange={(e) => setRole(e.target.value)}
          options={[
            { value: '', label: selected ? 'Select a role…' : 'Select a person first' },
            ...eligibleRoles.map((r) => ({
              value: r, label: api.roleLabel(r),
            })),
          ]}
          help={selected
            ? `An organization ${api.roleLabel(selected.role)} is eligible for: `
              + `${eligibleRoles.map(api.roleLabel).join(', ') || 'nothing'}. `
              + 'To widen this, change their organization role first — a '
              + 'separate, audited act.'
            : undefined}
        />

        <TextField
          id="team-starts"
          label="Starts on"
          type="date"
          value={startsAt}
          onChange={(e) => setStartsAt(e.target.value)}
        />
        <TextField
          id="team-expires"
          label="Expires on"
          type="date"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
          help="Evaluated on every request. Leave empty for an open-ended assignment."
        />
        <label className="org-admin__check">
          <input
            type="checkbox"
            checked={withholdDownloads}
            data-testid="team-withhold-downloads"
            onChange={(e) => setWithholdDownloads(e.target.checked)}
          />
          {' '}Withhold attachment downloads on this study
          <span className="org-admin__muted">
            {' '}For an agreement narrower than the collaboration as a whole.
            This can only restrict; it never grants downloads a membership
            withholds.
          </span>
        </label>
        <TextField
          id="team-note"
          label="Reason for this appointment"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          help="Recorded in the assignment history. A contract or protocol reference is usually what a later reviewer wants."
        />

        <Button
          variant="primary"
          loading={busy}
          disabled={!personId || !role}
          onClick={appoint}
          data-testid="appoint-to-study"
        >
          Appoint
        </Button>
      </Card>

      <Card title="Current and past assignments" flush>
        <PanelTable
          caption="Study team"
          head={HEAD}
          empty={assignments.length === 0}
          testId="study-team-table"
          rows={assignments.map((assignment) => (
            <tr key={assignment.id}
                data-testid={`assignment-${assignment.id}`}>
              <td>{assignment.username}</td>
              <td><RoleBadge role={assignment.role} /></td>
              <td>{windowOf(assignment)}</td>
              <td>
                {assignment.may_download_attachments === false
                  ? <Badge tone="warn" dot>Withheld here</Badge>
                  : <span className="org-admin__muted">As membership</span>}
              </td>
              <td>{assignment.note ?? '—'}</td>
              <td>
                <Badge tone={assignment.is_active ? 'success' : 'neutral'} dot>
                  {assignment.status}
                </Badge>
              </td>
              <td>
                {assignment.is_active && (
                  <Button
                    variant="danger"
                    data-testid={`revoke-assignment-${assignment.id}`}
                    onClick={() => setRevoking(assignment)}
                  >
                    Revoke
                  </Button>
                )}
              </td>
            </tr>
          ))}
        />
      </Card>

      <Card title="Assignment and revocation history" flush>
        {history.error ? (
          <Alert tone="info" title="Not available to this role">
            Who appointed whom is access-control information, available to
            owners, administrators and auditors.
          </Alert>
        ) : (
          <PanelTable
            caption="Assignment history"
            head={[
              { key: 'when', label: 'When' },
              { key: 'event', label: 'Event' },
              { key: 'actor', label: 'Who did it' },
              { key: 'summary', label: 'What happened' },
            ]}
            empty={(history.data?.events ?? []).length === 0}
            testId="team-history-table"
            rows={(history.data?.events ?? []).map((event) => (
              <tr key={event.id}>
                <td>{new Date(event.created_at).toLocaleString()}</td>
                <td>{event.event.replace(/_/g, ' ')}</td>
                <td>{event.actor_username ?? 'the system'}</td>
                <td>{event.summary}</td>
              </tr>
            ))}
          />
        )}
      </Card>

      {revoking && (
        <ConfirmAction
          open
          title="Revoke this assignment"
          confirmPhrase={revoking.username}
          confirmLabel="Revoke assignment"
          testId="confirm-revoke-assignment"
          description={
            `${revoking.username} will lose their `
            + `${api.roleLabel(revoking.role)} capability on this study from `
            + 'their next request.'
          }
          consequence={
            <>
              <p>
                Immediate. Access is re-evaluated on every request, so there is
                no window in which the revoked assignment still works.
              </p>
              <p>
                <strong>Historical attribution is unchanged.</strong> Anything
                they submitted, reviewed or approved still names them.
              </p>
            </>
          }
          busy={busy}
          error={error}
          onCancel={() => { setRevoking(null); setError(null); }}
          onConfirm={async (reason) => {
            setBusy(true);
            const result = await api.revokeAssignment(
              activeId, study, revoking.id, {
                reason: reason || undefined,
                expected_revision: revoking.revision,
              });
            setBusy(false);
            if (result.status === 'error') {
              setError(result.error.message);
              return;
            }
            setRevoking(null);
            setNotice(result.data.notice ?? 'Assignment revoked.');
            team.reload();
            history.reload();
          }}
        />
      )}
    </div>
  );
}
