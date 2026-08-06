"""Persistence for organizations, memberships, assignments and notifications.

Where the organization boundary lives
-------------------------------------
Every non-global record carries its own ``organization_id`` column, rather than
deriving the owner by joining back to the study. That is a denormalisation, and
it is deliberate:

* A measurement is four joins from its study (measurement → experiment version
  → experiment → run). Deriving the boundary would put those joins in the hot
  path of every list, filter and detail read in the application.
* A derived value cannot be indexed. The brief asks for indexes supporting
  organization-scoped queries and for filtering in the query layer rather than
  in the application — both of which require a real column.
* Returning 404 rather than 403 for another organization's record means the
  organization predicate has to be part of the *same* ``WHERE`` clause that
  finds the row. If it were a post-load check, the row would already have been
  read, and the difference between "absent" and "forbidden" would already have
  leaked through timing.

The cost is that the column can disagree with the parent. That is closed by a
service-layer invariant — a child is always written with its parent's
organization — and by ``check_organization_consistency()`` in
``db/migrations.py``, which reports any row whose organization differs from its
study's.

Append-only, again
------------------
``OrganizationAuditLog`` holds no foreign key to its subject, for the same
reason ``ValidationAuditLog`` does not: a revoked membership is exactly when the
record of its revocation matters most, so the trail must outlive the row it
describes.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nanobio_studio.app.db.base import Base
from nanobio_studio.app.organizations.vocabulary import (
    AccessScope, InvitationStatus, MembershipStatus, OrganizationRole,
    OrganizationStatus, StudyRole,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class Organization(Base):
    """A tenant. Owns projects, studies and everything beneath them."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    #: Stable, URL-safe, unique. Used in audit records so a renamed
    #: organization stays identifiable in a trail written years earlier.
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, native_enum=False, length=32),
        nullable=False, default=OrganizationStatus.ACTIVE,
    )

    #: True only for the organization the upgrade migration created. Kept as a
    #: column rather than inferred from the slug so the fact survives a rename.
    is_legacy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False)

    #: Set when an administrator confirms the memberships the migration
    #: proposed. Until then the organization is PENDING_CONFIRMATION and holds
    #: no scientific authority for anybody.
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)

    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan")


class OrganizationMembership(Base):
    """One person's standing in one organization.

    A person may hold at most one membership per organization — the unique
    constraint enforces it. Multiple simultaneous roles would make "what may
    this person do" a question with several answers, which is precisely the
    ambiguity an access review must not have to resolve.
    """

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id",
                         name="uq_org_membership_org_user"),
        Index("ix_org_membership_user_status", "user_id", "status"),
        Index("ix_org_membership_org_status", "organization_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)

    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, native_enum=False, length=32), nullable=False)
    scope: Mapped[AccessScope] = mapped_column(
        Enum(AccessScope, native_enum=False, length=32),
        nullable=False, default=AccessScope.ASSIGNED_STUDIES,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, native_enum=False, length=32),
        nullable=False, default=MembershipStatus.ACTIVE,
    )

    #: External collaborators are time-boxed. Internal staff normally are not,
    #: so both bounds are nullable rather than defaulted to something arbitrary.
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    #: A collaborator whose agreement covers reading results but not taking
    #: copies of raw instrument files off-site.
    may_download_attachments: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True)

    #: Free text naming the outside body a collaborator belongs to. Present so
    #: an access review can see at a glance who is not staff.
    external_organization: Mapped[str | None] = mapped_column(
        String(200), nullable=True)

    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    #: Optimistic-concurrency counter. Incremented by a conditional UPDATE on
    #: every change, so two administrators editing the same membership from two
    #: screens cannot silently overwrite one another: the second write matches
    #: no row and is refused with a conflict rather than applied on top of a
    #: state its author never saw.
    #:
    #: A version column rather than a lock because these are human-paced edits
    #: over HTTP. Holding a row lock across a think-time gap is how an
    #: administration screen deadlocks a database; detecting the collision when
    #: it happens costs nothing when it does not.
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1")

    #: Why it ended. Retained after revocation; the row is never deleted,
    #: because historical attribution must survive loss of access.
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    ended_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped[Organization] = relationship(
        back_populates="memberships")


class StudyAssignment(Base):
    """One person's scientific role on one study.

    Scientific capability is granted here and nowhere else. Being an
    organization APPROVER makes somebody *eligible* to approve; it is this row
    that lets them approve on this study.

    A person may hold several assignments on one study — contributor and
    auditor, say — so there is no unique constraint on (study, user). What
    there is instead is a constraint on (study, user, role), because holding
    the same role twice means nothing and would double-count in a review.
    """

    __tablename__ = "study_assignments"
    __table_args__ = (
        UniqueConstraint("study_id", "user_id", "role",
                         name="uq_study_assignment_study_user_role"),
        Index("ix_study_assignment_user_status", "user_id", "status"),
        Index("ix_study_assignment_study_status", "study_id", "status"),
        Index("ix_study_assignment_org", "organization_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    #: Denormalised from the study so an "everything this person may reach"
    #: query does not have to join runs.
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    study_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_runs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)

    role: Mapped[StudyRole] = mapped_column(
        Enum(StudyRole, native_enum=False, length=32), nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, native_enum=False, length=32),
        nullable=False, default=MembershipStatus.ACTIVE,
    )

    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    #: Narrows a laboratory contributor to named subtypes where an agreement
    #: covers only part of the work. NULL means "no subtype restriction".
    permitted_subtypes_json: Mapped[str | None] = mapped_column(
        Text, nullable=True)

    #: Per-assignment attachment restriction, layered *under* the membership's.
    #:
    #: NULL means "whatever the membership says". ``False`` withholds downloads
    #: on this study alone, for the case where one study's agreement is
    #: narrower than the collaboration as a whole. It can only ever restrict:
    #: setting it ``True`` on an assignment does not grant downloads to a
    #: membership that lacks them, because the policy requires both.
    may_download_attachments: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True)

    #: Why this appointment was made. Free text, shown in the study-team
    #: screen and copied into the audit trail. Never contains scientific
    #: content — it records an access decision, not a finding.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    #: See ``OrganizationMembership.revision``.
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1")
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    ended_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------

class OrganizationInvitation(Base):
    """An offer of membership that has not been accepted.

    Why the token is stored as a hash and never as itself
    ----------------------------------------------------
    The token in the link *is* the credential: whoever holds it can claim the
    membership. Storing it in the clear would put a working credential in every
    database backup, every replication stream and every screenshot of a support
    query — for an account that does not exist yet, so nobody would notice it
    being used.

    So the row holds ``sha256(token)``. The raw value is returned exactly once,
    in the response to the administrator who created the invitation, and is
    unrecoverable afterwards. Losing it costs a re-issue, which is cheap;
    keeping it costs a permanent credential leak, which is not.

    A short, non-secret ``token_prefix`` is kept so an administrator can tell
    two outstanding invitations apart in the audit trail without the trail
    carrying anything that could redeem one.

    Why it grants nothing until accepted
    ------------------------------------
    There is no membership row until acceptance. An invitation is deliberately
    *not* a ``MembershipStatus.INVITED`` membership: a row in
    ``organization_memberships`` is the thing every access query reads, and the
    safest way to guarantee an unaccepted invitation grants nothing is for
    there to be no row for it to read.
    """

    __tablename__ = "organization_invitations"
    __table_args__ = (
        # One live invitation per address per organization. A partial index —
        # only PENDING rows participate — so an address can be re-invited after
        # a previous invitation is revoked or expires, while two simultaneous
        # outstanding tokens for one person cannot exist. Two tokens would mean
        # revoking "the" invitation left another one working.
        Index("uq_org_invitation_pending", "organization_id", "email",
              unique=True, sqlite_where=text("status = 'PENDING'"),
              postgresql_where=text("status = 'PENDING'")),
        Index("ix_org_invitation_org_status", "organization_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    #: Lowercased on write, so "A@b.com" and "a@b.com" cannot both be
    #: outstanding and the uniqueness index means what it appears to mean.
    email: Mapped[str] = mapped_column(String(320), nullable=False)

    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, native_enum=False, length=32), nullable=False)
    scope: Mapped[AccessScope] = mapped_column(
        Enum(AccessScope, native_enum=False, length=32),
        nullable=False, default=AccessScope.ASSIGNED_STUDIES)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus, native_enum=False, length=32),
        nullable=False, default=InvitationStatus.PENDING)

    #: ``sha256`` of the issued token, hex. Unique so a hash collision or a
    #: duplicated issue is a database error rather than two live invitations.
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True)

    #: First few characters of the token. Non-secret by construction: far too
    #: short to redeem, long enough to name one invitation in an audit line.
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)

    #: When the *invitation* stops being redeemable.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)

    #: When the *membership* it creates should expire. Separate field: a
    #: collaborator's link may be valid for a week while their access runs to
    #: the end of the contract.
    membership_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    external_organization: Mapped[str | None] = mapped_column(
        String(200), nullable=True)
    may_download_attachments: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True)

    #: What the delivery provider reported. ``recorded`` means nothing was
    #: sent and an administrator is expected to hand the link over directly —
    #: an honest state, not a failure.
    delivery_provider: Mapped[str | None] = mapped_column(
        String(32), nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True)
    #: Never contains the token, the link or a credential.
    delivery_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    accepted_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    ended_by: Mapped[int | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: See ``OrganizationMembership.revision``. Also what makes redemption
    #: single-use under concurrency: acceptance claims the row with a
    #: conditional UPDATE, so two simultaneous redemptions of one token produce
    #: one membership and one conflict.
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class OrganizationEvent(str, enum.Enum):
    """What happened to access. Every value here is security-relevant."""

    ORGANIZATION_CREATED = "organization_created"
    ORGANIZATION_UPDATED = "organization_updated"
    ORGANIZATION_STATUS_CHANGED = "organization_status_changed"
    ORGANIZATION_CONFIRMED = "organization_confirmed"

    MEMBER_INVITED = "member_invited"
    INVITATION_RESENT = "invitation_resent"
    INVITATION_ACCEPTED = "invitation_accepted"
    INVITATION_REVOKED = "invitation_revoked"
    INVITATION_EXPIRED = "invitation_expired"
    INVITATION_REJECTED = "invitation_rejected"
    MEMBER_ADDED = "member_added"
    MEMBER_ROLE_CHANGED = "member_role_changed"
    MEMBER_SCOPE_CHANGED = "member_scope_changed"
    MEMBER_SUSPENDED = "member_suspended"
    MEMBER_REINSTATED = "member_reinstated"
    MEMBER_REVOKED = "member_revoked"
    MEMBER_EXPIRED = "member_expired"

    ASSIGNMENT_CREATED = "assignment_created"
    ASSIGNMENT_AMENDED = "assignment_amended"
    ASSIGNMENT_REVOKED = "assignment_revoked"
    ASSIGNMENT_EXPIRED = "assignment_expired"

    COLLABORATION_GRANTED = "collaboration_granted"
    COLLABORATION_EXPIRING = "collaboration_expiring"
    COLLABORATION_REVOKED = "collaboration_revoked"

    #: Written once by the upgrade migration.
    LEGACY_DATA_MIGRATED = "legacy_data_migrated"

    #: Authentication and account lifecycle, recorded here as well as in the
    #: auth trail because an access review reads one place, not two.
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUIRED = "password_reset_required"
    SESSIONS_REVOKED = "sessions_revoked"
    USER_DEACTIVATED = "user_deactivated"
    USER_REACTIVATED = "user_reactivated"

    #: Recorded when the policy refuses a cross-organization read. A single
    #: one is noise; a pattern is somebody enumerating identifiers.
    ACCESS_DENIED = "access_denied"


class OrganizationAuditLog(Base):
    """Append-only. No foreign key to its subject, by design."""

    __tablename__ = "organization_audit_log"
    __table_args__ = (
        Index("ix_org_audit_org_created", "organization_id", "created_at"),
        Index("ix_org_audit_subject", "subject_type", "subject_id"),
        Index("ix_org_audit_actor", "actor_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    #: Nullable: a denied cross-organization read has no organization the
    #: reader is entitled to name.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True)

    event: Mapped[OrganizationEvent] = mapped_column(
        Enum(OrganizationEvent, native_enum=False, length=48), nullable=False)

    #: Plain strings, not foreign keys — see the module docstring.
    subject_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_username: Mapped[str | None] = mapped_column(
        String(150), nullable=True)

    #: Human-readable. Never contains a password, token or storage key.
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationType(str, enum.Enum):
    CANDIDATE_REVISION_CREATED = "candidate_revision_created"
    CANDIDATE_VERSION_LOCKED = "candidate_version_locked"
    RESULTS_STALE = "results_stale"
    RECALCULATION_REQUIRED = "recalculation_required"
    RECALCULATION_COMPLETED = "recalculation_completed"
    SCIENTIFIC_REASSESSMENT_REQUIRED = "scientific_reassessment_required"
    SAFETY_REASSESSMENT_REQUIRED = "safety_reassessment_required"
    REVIEW_SUBMITTED = "review_submitted"
    REVIEW_ACCEPTED = "review_accepted"
    REVIEW_REFUSED = "review_refused"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REFUSED = "approval_refused"
    SUPERSESSION_PROPOSED = "supersession_proposed"
    SUPERSESSION_ACCEPTED = "supersession_accepted"
    SUPERSESSION_REFUSED = "supersession_refused"
    REPORT_COMPLETED = "report_completed"
    REPORT_FAILED = "report_failed"
    EXPORT_COMPLETED = "export_completed"
    EXPORT_FAILED = "export_failed"
    CRO_PACKAGE_COMPLETED = "cro_package_completed"
    CRO_PACKAGE_FAILED = "cro_package_failed"
    MIGRATION_ACTION_REQUIRED = "migration_action_required"
    INTEGRITY_ACTION_REQUIRED = "integrity_action_required"
    ACCOUNT_SECURITY = "account_security"
    ACCESS_CHANGED = "access_changed"
    SESSION_SECURITY = "session_security"
    EXPERIMENT_SUBMITTED = "experiment_submitted"
    REVIEWER_ASSIGNED = "reviewer_assigned"
    APPROVER_ASSIGNED = "approver_assigned"
    REVISION_REQUESTED = "revision_requested"
    EXPERIMENT_APPROVED = "experiment_approved"
    EXPERIMENT_REJECTED = "experiment_rejected"
    CONTRADICTION_DETECTED = "contradiction_detected"
    CONTRADICTION_RESOLVED = "contradiction_resolved"
    CONTRADICTION_REOPENED = "contradiction_reopened"
    COLLABORATION_ASSIGNED = "collaboration_assigned"
    COLLABORATION_EXPIRING = "collaboration_expiring"
    COLLABORATION_REVOKED = "collaboration_revoked"


class Notification(Base):
    """A persistent in-app message to one recipient.

    Deliberately holds no scientific detail
    ---------------------------------------
    A notification stores a *reference* — organization, study, record type and
    identifier — plus a short subject line drawn from non-sensitive fields. It
    does not store measurements, conclusions or file names.

    That is what makes the retention rule safe. Somebody removed from a study
    keeps the historical fact that they were once asked to review something,
    which an access review needs; they cannot read the record, because opening
    it goes back through the policy. If the payload carried the science, losing
    access would not take the science back.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notification_recipient_read", "recipient_id", "read_at"),
        Index("ix_notification_recipient_created", "recipient_id",
              "created_at"),
        Index("ix_notification_org", "organization_id"),
        UniqueConstraint("recipient_id", "idempotency_key",
                         name="uq_notification_recipient_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False)

    organization_id: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True)

    study_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    study_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    event: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, native_enum=False, length=48), nullable=False)

    #: Safe reference to the underlying record. Not a foreign key: the
    #: notification must survive the record being superseded.
    subject_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: One line, safe to show to somebody who has since lost access.
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    #: Stable producer key. Required for new writes; nullable only so databases
    #: created before notification surfacing can be upgraded without inventing
    #: identities for historical rows.
    idempotency_key: Mapped[str | None] = mapped_column(String(160),
                                                        nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class NotificationAuditEvent(str, enum.Enum):
    CREATED = "created"
    MARKED_READ = "marked_read"
    BULK_MARKED_READ = "bulk_marked_read"


class NotificationAuditLog(Base):
    """Append-only history for notification creation and recipient state."""

    __tablename__ = "notification_audit_log"
    __table_args__ = (
        Index("ix_notification_audit_notification", "notification_id",
              "created_at"),
        Index("ix_notification_audit_actor", "actor_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event: Mapped[NotificationAuditEvent] = mapped_column(
        Enum(NotificationAuditEvent, native_enum=False, length=24),
        nullable=False)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow)


Index("ix_organizations_status", Organization.status)
