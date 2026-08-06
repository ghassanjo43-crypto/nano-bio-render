/**
 * Access and audit history.
 *
 * The membership rows say who has access now. This says who had it in March,
 * who granted it and who took it away — which is the question an access review
 * asks, and the one the current rows cannot answer.
 *
 * Append-only, and shown as such. Nothing in this interface amends or deletes
 * an audit row, and the screen says so rather than leaving the reader to
 * wonder whether the absence of a delete button means anything.
 */

import { useState } from 'react';

import {
  Alert, Badge, Card, SelectField, SkeletonBlock,
} from '../../design-system/components';
import * as api from '../../api/organizationClient';
import { PanelTable } from './OrganizationAdminPage';
import { useScopedData } from './useScopedData';

const HEAD = [
  { key: 'when', label: 'When' },
  { key: 'event', label: 'Event' },
  { key: 'actor', label: 'Who did it' },
  { key: 'summary', label: 'What happened' },
] as const;

const FILTERS = [
  { value: '', label: 'Everything' },
  { value: 'membership', label: 'Memberships' },
  { value: 'study_assignment', label: 'Study assignments' },
  { value: 'invitation', label: 'Invitations' },
  { value: 'organization', label: 'The organization itself' },
] as const;

/** Events whose appearance in a trail is worth making visually obvious. */
const SIGNIFICANT = new Set([
  'member_revoked', 'member_suspended', 'member_role_changed',
  'assignment_revoked', 'invitation_revoked', 'organization_confirmed',
  'access_denied',
]);

export function AccessHistoryPanel({ organizationId, mayView }: {
  organizationId: number; mayView: boolean;
}) {
  const [subjectType, setSubjectType] = useState('');
  const history = useScopedData(
    (signal) => api.getAccessHistory(
      organizationId, subjectType || undefined, signal),
    [organizationId, subjectType]);

  if (!mayView) {
    return (
      <Alert tone="info" title="Not available to this role">
        <p>
          The access history maps who holds authority here and how it changed.
          That is administrative information, so it is available to organization
          owners, administrators and auditors.
        </p>
        <p>
          Organization-wide <em>scientific</em> visibility does not include it —
          deliberately, because reading the records and reading the access
          control are different needs.
        </p>
      </Alert>
    );
  }

  if (history.loading) return <SkeletonBlock lines={8} />;
  if (history.error) {
    return (
      <Alert tone="danger" title="Could not load the history" role="alert">
        {history.error}
      </Alert>
    );
  }

  const events = history.data?.events ?? [];

  return (
    <Card
      title="Access and audit history"
      subtitle="Append-only. Nothing here can be amended or deleted."
      flush
    >
      <div className="org-admin__filters">
        <SelectField
          id="audit-subject"
          label="Show"
          value={subjectType}
          options={FILTERS.map((f) => ({ value: f.value, label: f.label }))}
          onChange={(e) => setSubjectType(e.target.value)}
        />
      </div>

      <PanelTable
        caption="Access history"
        head={HEAD}
        empty={events.length === 0}
        testId="audit-table"
        rows={events.map((event) => (
          <tr key={event.id} data-testid={`audit-${event.id}`}>
            <td>{new Date(event.created_at).toLocaleString()}</td>
            <td>
              <Badge
                tone={SIGNIFICANT.has(event.event) ? 'warn' : 'neutral'}
                dot={SIGNIFICANT.has(event.event)}
              >
                {event.event.replace(/_/g, ' ')}
              </Badge>
            </td>
            <td>{event.actor_username ?? 'the system'}</td>
            <td>{event.summary}</td>
          </tr>
        ))}
      />
    </Card>
  );
}
