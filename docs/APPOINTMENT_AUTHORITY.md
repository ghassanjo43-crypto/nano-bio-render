# Appointment authority

Who may appoint scientific reviewers and approvers, and why that cannot be
used to escalate.

---

## The rule

> **Administrative roles appoint. Scientific roles act. One membership carries
> exactly one role, and nobody may change their own.**

Three clauses, each load-bearing.

### 1. Appointment is an administrative act

Creating, amending or revoking a study assignment requires
`Action.MANAGE_ASSIGNMENTS`, held only by an active organization **OWNER** or
**ADMINISTRATOR**.

Appointing a reviewer is a decision about *who does the work*, not a scientific
judgement. It belongs with the people who manage access.

### 2. Eligibility comes from the organization role, not the appointment

An administrator cannot appoint anybody to a study role their organization role
does not already make them eligible for. The mapping is data, in
`organizations/vocabulary.ROLE_MAY_BE_ASSIGNED_STUDY_ROLES`:

| Organization role | May be assigned |
|---|---|
| `OWNER` | `AUDITOR` only |
| `ADMINISTRATOR` | `AUDITOR` only |
| `RESEARCHER` | `OWNER`, `CONTRIBUTOR`, `AUDITOR` |
| `LAB_CONTRIBUTOR` | `LAB_CONTRIBUTOR` only |
| `REVIEWER` | `REVIEWER`, `CONTRIBUTOR`, `AUDITOR` |
| `APPROVER` | `APPROVER`, `REVIEWER`, `AUDITOR` |
| `AUDITOR` | `AUDITOR` only |

So appointing somebody an approver takes **two separate acts by two different
kinds of authority**: a role change making them an organization `APPROVER`, and
a study assignment. Neither alone is enough.

### 3. Nobody changes their own organization role

`change_member_role` refuses when `membership.user_id == actor.user_id`, for
everyone including owners.

**This clause is the whole security of the scheme, and it was missing.** Without
it the first two clauses are decorative:

```
1. Administrator holds MANAGE_MEMBERS.
2. Administrator sets their own role to APPROVER.       ← now eligible
3. Administrator assigns themselves as study approver.  ← now authorised
4. Administrator approves evidence.
```

Two requests, no second person, and the audit trail shows nothing more alarming
than a role change. This was a real hole in the implementation, found by probing
the service directly, and closed before the management API was written.

With clause 3, escalation always requires somebody else. And because a
membership carries exactly one role, an administrator who *is* promoted to
approver **stops being an administrator** — losing `MANAGE_MEMBERS` in the same
act that grants scientific authority. The two ladders are mutually exclusive at
any instant.

---

## Getting somebody into the organization in the first place

Two routes in, and neither of them can grant scientific authority.

### Adding an existing account

`POST /organizations/{id}/members` takes a `user_id`. Administrative, so it
needs `MANAGE_MEMBERS`. The role given is subject to clause 2 above, so adding
somebody as `APPROVER` makes them *eligible* and nothing more; they still need
a study assignment, which is a second act.

### Inviting an address

`POST /organizations/{id}/invitations` takes an email address and issues a
single-use token.

An invitation is deliberately **not** a `MembershipStatus.INVITED` membership.
A row in `organization_memberships` is the thing every access query reads, and
the simplest way to guarantee an unaccepted invitation grants nothing is for
there to be no row for a query to read. Acceptance creates the membership;
until then there is only an offer.

Four properties, each closing something:

| Property | Closes |
|---|---|
| Only `sha256(token)` is stored; the raw value is returned once | A database backup full of working credentials for accounts nobody is watching |
| Redeemable only by an account whose email matches | A forwarded message becoming a bearer credential for a role in your organization |
| Single-use, and re-issuing invalidates the previous token | A link recovered from an old mailbox staying valid indefinitely |
| Unknown, expired, revoked, used and wrong-account all answer identically | An oracle confirming that a token was real, and therefore that the organization exists and was recruiting |

Accepting grants membership only. The acceptance response says so in as many
words, because "you have joined" is otherwise easy to read as "you can now get
on with the work", and the work needs an assignment.

---

## External collaborators

A CRO or partner is an ordinary membership with three extra facts:
`external_organization` names the outside body, `expires_at` bounds it, and
`may_download_attachments` may withhold copies of raw instrument files.

Least privilege here is not a setting; it falls out of the model:

* **Scope.** `default_scope_for` gives every non-administrative role
  `ASSIGNED_STUDIES`, so a collaborator reaches the studies they are assigned
  to and nothing else — including nothing organization-wide.
* **Expiry on read.** `_is_in_force` is evaluated per request, so a lapsed
  collaboration stops granting at the instant it lapses whether or not the
  sweep has marked it `EXPIRED`. A failed housekeeping job cannot silently
  extend an external collaboration.
* **Attachments, twice.** The membership flag governs the collaboration; a
  per-assignment `may_download_attachments = False` narrows it on one study,
  for an agreement covering only part of the work. The assignment can only ever
  *subtract*: setting it `True` grants nothing a membership withholds, because
  the policy requires both.
* **Revocation is immediate and non-destructive.** `revoke_member` ends the
  membership and every assignment under it in one transaction, and the rows
  survive. Somebody who ran an assay last month still performed it.

---

## Concurrent administration

Membership, assignment and invitation rows carry a `revision`. Every mutation
takes the row with a conditional
`UPDATE … SET revision = revision + 1 WHERE id = ? AND revision = ?`, and a
statement matching no row is answered **409 `concurrent_modification`** rather
than applied.

A version column rather than a lock, because these are human-paced edits over
HTTP: holding a row lock across a think-time gap is how an administration
screen deadlocks a database. The management API echoes `revision` on every
read, and the screens send back the one they rendered — so the check is not
merely "nothing changed during this request" but "nothing changed since you
looked", which is the case that actually loses a change.

The same mechanism makes redemption single-use under concurrency: two
simultaneous accepts of one token both reach the claim, exactly one wins, and
the other is refused instead of producing a second membership.

---

## Why not a dedicated "appointer" role

Considered and rejected. It would be a third ladder needing its own
appointment rule, and the question just moves up a level: who appoints the
appointer? The self-change bar answers it without adding a role, because it
makes *every* grant of authority a two-person act by construction.

---

## What appointment still does not confer

Assignment grants the *capacity* to review or approve on a study. It never
overrides the independence rules, which are evaluated per experiment:

* **A performer cannot approve their own experiment.** Checked against
  `performer_ids` on the version.
* **An author cannot approve their own experiment.** Checked against
  `owner_id`, so somebody who created the record but did not run the assay is
  equally barred.
* **A performer or author cannot review it either** — not merely approve.

Somebody may legitimately hold both `CONTRIBUTOR` and `APPROVER` on one study;
what they cannot be is both on the *same experiment*. Assignment does not
override self-approval restrictions, and the policy re-checks on every call
rather than trusting the assignment.

---

## Confirming a migrated organization

`confirm_organization` releases a `PENDING_CONFIRMATION` organization created by
the upgrade backfill. It requires `MANAGE_ORGANIZATION` — **owner only**.

Confirmation grants **no scientific authority to anybody**. It only lifts the
hold that blocked scientific writes. The backfill deliberately creates no
reviewer or approver assignment, so after confirming, an administrator still has
to appoint approvers explicitly through the two-act path above.

That is the point: an upgrade must not resume approving evidence under
memberships a machine guessed.

---

## Enforcement points

| Rule | Enforced in |
|---|---|
| Appointment is administrative | `policy.may()` — `MANAGE_ASSIGNMENTS` in `ADMINISTRATIVE_ACTIONS` |
| Eligibility gate | `organization_service.assign_to_study` |
| No self role-change | `organization_service.change_member_role` |
| No self status-change | `organization_service.set_membership_status` |
| Administrative ≠ scientific | `policy.may()` — administrative roles refused every `SCIENTIFIC_ACTION` |
| Last active owner protected | `organization_service._require_another_owner` |
| Self-approval / authorship | `policy.may()` under `Action.APPROVE`, `START_REVIEW`, `REJECT`, `REQUEST_REVISION` |
| Invitation grants nothing until accepted | No membership row exists until `accept_invitation` |
| Invitation is single-use | `_claim` on the invitation row, plus the `PENDING`-only status check |
| Invitation is not a bearer token | `accept_invitation` — the account's email must match |
| Every invitation failure is indistinguishable | `accept_invitation` — one `RecordNotVisible` for every cause |
| Collaborator reaches assigned studies only | `default_scope_for` → `ASSIGNED_STUDIES`, applied in `visible_study_ids` |
| Expiry evaluated per request | `policy._is_in_force`, called from `resolve_context` |
| Per-study attachment restriction | `policy.may()` under `DOWNLOAD_ATTACHMENT`, via `studies_without_downloads` |
| No lost update under concurrent administration | `organization_service._claim` |
| Duplicate active assignment | `uq_study_assignment_study_user_role` |
| Two live invitations to one address | `uq_org_invitation_pending` (partial, `PENDING` only) |
| Invitation link cannot be aimed | `invitation_delivery.build_invitation_link` — no caller input |

All service-layer, all re-checked per request. Hiding a control in the interface
is a courtesy; these are the controls.
