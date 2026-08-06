/**
 * Typed client for organization and study-team management.
 *
 * Every function here is a transport. **None of them decides anything.** The
 * management screens hide controls the caller cannot use, and that is a
 * courtesy to the user, not a control on the data — every one of these calls is
 * re-authorised by the backend policy, and a hidden button protects nothing.
 *
 * Reuses `apiRequest` so the management screens share one 401 handler, one
 * error shape, and — critically — the one place that attaches the
 * `X-Organization-Id` header. A second fetch wrapper here would be one
 * forgotten header away from an administration screen listing members across
 * every organization the user belongs to.
 */

import { apiRequest } from './client';

/* ------------------------------------------------------------------------ */
/* Shapes                                                                    */
/* ------------------------------------------------------------------------ */

export interface OrganizationProfile {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  status: string;
  is_legacy: boolean;
  awaiting_confirmation: boolean;
  confirmed_at: string | null;
  created_at: string;
  your_role?: string;
  is_administrative?: boolean;
  capabilities?: Record<string, boolean>;
  notice?: string;
}

export interface Member {
  id: number;
  user_id: number;
  username: string;
  role: string;
  is_administrative: boolean;
  scope: string;
  status: string;
  is_active: boolean;
  starts_at: string | null;
  expires_at: string | null;
  external_organization: string | null;
  is_external: boolean;
  may_download_attachments: boolean;
  created_at: string;
  ended_at: string | null;
  end_reason: string | null;
  /** Echoed back on the next write so a stale screen cannot overwrite. */
  revision: number;
  assignable_study_roles: string[];
}

export interface Invitation {
  id: number;
  organization_id: number;
  email: string;
  role: string;
  scope: string;
  status: string;
  is_administrative: boolean;
  token_prefix: string;
  expires_at: string;
  membership_expires_at: string | null;
  external_organization: string | null;
  is_external: boolean;
  may_download_attachments: boolean;
  delivery_provider: string | null;
  delivery_status: string | null;
  delivery_detail: string | null;
  created_at: string;
  accepted_at: string | null;
  ended_at: string | null;
  end_reason: string | null;
  /** Present ONLY in the response that issued it. Never stored, never re-read. */
  invitation_link?: string;
  link_shown_once?: boolean;
  notice?: string;
}

export interface Assignment {
  id: number;
  user_id: number;
  username: string;
  study_id: number;
  role: string;
  status: string;
  is_active: boolean;
  starts_at: string | null;
  expires_at: string | null;
  may_download_attachments: boolean | null;
  note: string | null;
  permitted_subtypes: string[] | null;
  created_at: string;
  ended_at: string | null;
  end_reason: string | null;
  revision: number;
  notice?: string;
}

export interface AuditEvent {
  id: number;
  event: string;
  subject_type: string | null;
  subject_id: number | null;
  actor_username: string | null;
  summary: string;
  created_at: string;
}

/* ------------------------------------------------------------------------ */
/* Vocabulary, mirrored for labelling only                                   */
/* ------------------------------------------------------------------------ */
/*
 * These lists drive the *labels* on the screens. They are deliberately not a
 * client-side copy of the eligibility rules: which study roles a person may
 * hold comes from `assignable_study_roles` on their membership, which the
 * backend computes. Restating that mapping here would give the interface a
 * second opinion, and the two would drift.
 */

/** Roles that manage people and access. Never scientific authority. */
export const ADMINISTRATIVE_ROLES = ['owner', 'administrator'] as const;

export const ORGANIZATION_ROLES = [
  { value: 'owner', label: 'Owner', kind: 'authority' },
  { value: 'administrator', label: 'Administrator', kind: 'authority' },
  { value: 'researcher', label: 'Researcher', kind: 'scientific' },
  { value: 'lab_contributor', label: 'Laboratory contributor', kind: 'scientific' },
  { value: 'reviewer', label: 'Reviewer', kind: 'scientific' },
  { value: 'approver', label: 'Approver', kind: 'scientific' },
  { value: 'auditor', label: 'Auditor', kind: 'read-only' },
] as const;

export const STUDY_ROLES = [
  { value: 'study_owner', label: 'Study owner' },
  { value: 'contributor', label: 'Research contributor' },
  { value: 'lab_contributor', label: 'CRO / laboratory contributor' },
  { value: 'reviewer', label: 'Scientific reviewer' },
  { value: 'approver', label: 'Scientific approver' },
  { value: 'auditor', label: 'Auditor' },
] as const;

export function isAdministrativeRole(role: string): boolean {
  return (ADMINISTRATIVE_ROLES as readonly string[]).includes(role);
}

export function roleLabel(role: string): string {
  return ORGANIZATION_ROLES.find((r) => r.value === role)?.label
    ?? STUDY_ROLES.find((r) => r.value === role)?.label
    ?? role.replace(/_/g, ' ');
}

/* ------------------------------------------------------------------------ */
/* Transport                                                                 */
/* ------------------------------------------------------------------------ */

const hasKeys = <T>(...keys: string[]) => (body: unknown): body is T =>
  typeof body === 'object' && body !== null && keys.every((k) => k in body);

const base = '/api/v1/organizations';

/** GET /api/v1/organizations/{id} */
export function getOrganization(id: number, signal?: AbortSignal) {
  return apiRequest<OrganizationProfile>(
    `${base}/${id}`, { method: 'GET', signal },
    hasKeys<OrganizationProfile>('id', 'slug', 'status'),
  );
}

/** PATCH /api/v1/organizations/{id} */
export function updateOrganization(
  id: number, body: { name?: string; description?: string | null },
) {
  return apiRequest<OrganizationProfile>(
    `${base}/${id}`, { method: 'PATCH', body: JSON.stringify(body) },
    hasKeys<OrganizationProfile>('id', 'slug'),
  );
}

/** POST /api/v1/organizations/{id}/confirm */
export function confirmOrganization(id: number) {
  return apiRequest<OrganizationProfile>(
    `${base}/${id}/confirm`, { method: 'POST' },
    hasKeys<OrganizationProfile>('id', 'status'),
  );
}

/** GET /api/v1/organizations/{id}/members */
export function listMembers(id: number, signal?: AbortSignal) {
  return apiRequest<{ organization_id: number; members: Member[] }>(
    `${base}/${id}/members`, { method: 'GET', signal },
    hasKeys('members'),
  );
}

/** GET /api/v1/organizations/{id}/members/{membershipId} */
export function getMember(id: number, membershipId: number,
                          signal?: AbortSignal) {
  return apiRequest<Member>(
    `${base}/${id}/members/${membershipId}`, { method: 'GET', signal },
    hasKeys<Member>('id', 'role', 'revision'),
  );
}

/** PATCH /api/v1/organizations/{id}/members/{membershipId} */
export function changeMemberRole(
  id: number, membershipId: number,
  body: { role?: string; scope?: string; expected_revision?: number },
) {
  return apiRequest<Member>(
    `${base}/${id}/members/${membershipId}`,
    { method: 'PATCH', body: JSON.stringify(body) },
    hasKeys<Member>('id', 'role'),
  );
}

/** POST /api/v1/organizations/{id}/members/{membershipId}/status */
export function setMemberStatus(
  id: number, membershipId: number,
  body: { status: 'active' | 'suspended'; reason?: string;
          expected_revision?: number },
) {
  return apiRequest<Member>(
    `${base}/${id}/members/${membershipId}/status`,
    { method: 'POST', body: JSON.stringify(body) },
    hasKeys<Member>('id', 'status'),
  );
}

/** DELETE /api/v1/organizations/{id}/members/{membershipId} */
export function revokeMember(
  id: number, membershipId: number,
  body: { reason?: string; expected_revision?: number } = {},
) {
  return apiRequest<Member>(
    `${base}/${id}/members/${membershipId}`,
    { method: 'DELETE', body: JSON.stringify(body) },
    hasKeys<Member>('id', 'status'),
  );
}

/** GET /api/v1/organizations/{id}/collaborators */
export function listCollaborators(id: number, signal?: AbortSignal) {
  return apiRequest<{
    organization_id: number; collaborators: Member[]; notice: string;
  }>(
    `${base}/${id}/collaborators`, { method: 'GET', signal },
    hasKeys('collaborators'),
  );
}

/** GET /api/v1/organizations/{id}/invitations */
export function listInvitations(
  id: number, includeClosed = false, signal?: AbortSignal,
) {
  return apiRequest<{
    organization_id: number; invitations: Invitation[];
    delivery_provider: string;
  }>(
    `${base}/${id}/invitations?include_closed=${includeClosed}`,
    { method: 'GET', signal },
    hasKeys('invitations'),
  );
}

export interface InviteBody {
  email: string;
  role: string;
  scope?: string;
  /** When the resulting MEMBERSHIP expires, not the link. */
  expires_at?: string | null;
  external_organization?: string | null;
  may_download_attachments?: boolean;
}

/** POST /api/v1/organizations/{id}/invitations */
export function createInvitation(id: number, body: InviteBody) {
  return apiRequest<Invitation>(
    `${base}/${id}/invitations`,
    { method: 'POST', body: JSON.stringify(body) },
    hasKeys<Invitation>('id', 'email', 'status'),
  );
}

/** POST /api/v1/organizations/{id}/invitations/{invitationId}/resend */
export function resendInvitation(id: number, invitationId: number) {
  return apiRequest<Invitation>(
    `${base}/${id}/invitations/${invitationId}/resend`, { method: 'POST' },
    hasKeys<Invitation>('id', 'status'),
  );
}

/** DELETE /api/v1/organizations/{id}/invitations/{invitationId} */
export function revokeInvitation(
  id: number, invitationId: number, reason?: string,
) {
  return apiRequest<Invitation>(
    `${base}/${id}/invitations/${invitationId}`,
    { method: 'DELETE', body: JSON.stringify({ reason: reason ?? null }) },
    hasKeys<Invitation>('id', 'status'),
  );
}

/** POST /api/v1/organizations/invitations/accept */
export function acceptInvitation(token: string) {
  return apiRequest<{
    organization_id: number; membership_id: number; role: string;
    is_administrative: boolean; expires_at: string | null; notice: string;
  }>(
    `${base}/invitations/accept`,
    { method: 'POST', body: JSON.stringify({ token }) },
    hasKeys('organization_id', 'membership_id'),
  );
}

/** GET /api/v1/organizations/{id}/studies/{studyId}/team */
export function listStudyTeam(id: number, studyId: number,
                              signal?: AbortSignal) {
  return apiRequest<{ study_id: number; assignments: Assignment[] }>(
    `${base}/${id}/studies/${studyId}/team`, { method: 'GET', signal },
    hasKeys('assignments'),
  );
}

export interface AssignBody {
  user_id: number;
  role: string;
  starts_at?: string | null;
  expires_at?: string | null;
  may_download_attachments?: boolean | null;
  note?: string | null;
}

/** POST /api/v1/organizations/{id}/studies/{studyId}/team */
export function assignToStudy(id: number, studyId: number, body: AssignBody) {
  return apiRequest<Assignment>(
    `${base}/${id}/studies/${studyId}/team`,
    { method: 'POST', body: JSON.stringify(body) },
    hasKeys<Assignment>('id', 'role'),
  );
}

/** PATCH /api/v1/organizations/{id}/studies/{studyId}/team/{assignmentId} */
export function amendAssignment(
  id: number, studyId: number, assignmentId: number,
  body: {
    starts_at?: string | null; expires_at?: string | null;
    may_download_attachments?: boolean | null; note?: string | null;
    expected_revision?: number;
  },
) {
  return apiRequest<Assignment>(
    `${base}/${id}/studies/${studyId}/team/${assignmentId}`,
    { method: 'PATCH', body: JSON.stringify(body) },
    hasKeys<Assignment>('id', 'role'),
  );
}

/** DELETE /api/v1/organizations/{id}/studies/{studyId}/team/{assignmentId} */
export function revokeAssignment(
  id: number, studyId: number, assignmentId: number,
  body: { reason?: string; expected_revision?: number } = {},
) {
  return apiRequest<Assignment>(
    `${base}/${id}/studies/${studyId}/team/${assignmentId}`,
    { method: 'DELETE', body: JSON.stringify(body) },
    hasKeys<Assignment>('id', 'status'),
  );
}

/** GET /api/v1/organizations/{id}/studies/{studyId}/team/history */
export function getTeamHistory(id: number, studyId: number,
                               signal?: AbortSignal) {
  return apiRequest<{ study_id: number; events: AuditEvent[] }>(
    `${base}/${id}/studies/${studyId}/team/history`, { method: 'GET', signal },
    hasKeys('events'),
  );
}

/** GET /api/v1/organizations/{id}/audit */
export function getAccessHistory(
  id: number, subjectType?: string, signal?: AbortSignal,
) {
  const query = subjectType ? `?subject_type=${encodeURIComponent(subjectType)}`
    : '';
  return apiRequest<{
    organization_id: number; events: AuditEvent[]; append_only: boolean;
  }>(
    `${base}/${id}/audit${query}`, { method: 'GET', signal },
    hasKeys('events'),
  );
}
