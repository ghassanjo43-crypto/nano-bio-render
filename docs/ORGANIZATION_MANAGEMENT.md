# Organization and study-team management

The API and the screens that hand out access, and the reasons each of them is
shaped the way it is.

Read alongside:

* `ACTIVE_ORGANIZATION_CONTRACT.md` — how a caller selects an organization.
* `APPOINTMENT_AUTHORITY.md` — who may appoint reviewers and approvers.

---

## 1. The surface

Everything is under `/api/v1/organizations`, and every route resolves an
`AccessContext` — which is not a convention here but a mechanically enforced
one, because the route guard is fail-closed (see §6).

### Organization

| Method | Path | Requires |
|---|---|---|
| `GET` | `/organizations` | membership |
| `POST` | `/organizations` | any authenticated account |
| `GET` | `/organizations/{id}` | membership |
| `PATCH` | `/organizations/{id}` | `MANAGE_ORGANIZATION` — owner |
| `POST` | `/organizations/{id}/confirm` | `MANAGE_ORGANIZATION` — owner |

### Members

| Method | Path | Requires |
|---|---|---|
| `GET` | `/organizations/{id}/members` | membership |
| `GET` | `/organizations/{id}/members/{membership_id}` | membership |
| `POST` | `/organizations/{id}/members` | `MANAGE_MEMBERS` |
| `PATCH` | `/organizations/{id}/members/{membership_id}` | `MANAGE_MEMBERS` |
| `POST` | `/organizations/{id}/members/{membership_id}/status` | `MANAGE_MEMBERS` |
| `DELETE` | `/organizations/{id}/members/{membership_id}` | `MANAGE_MEMBERS` |
| `GET` | `/organizations/{id}/collaborators` | membership |

### Invitations

| Method | Path | Requires |
|---|---|---|
| `GET` | `/organizations/{id}/invitations` | `MANAGE_MEMBERS` |
| `POST` | `/organizations/{id}/invitations` | `MANAGE_MEMBERS` |
| `POST` | `/organizations/{id}/invitations/{iid}/resend` | `MANAGE_MEMBERS` |
| `DELETE` | `/organizations/{id}/invitations/{iid}` | `MANAGE_MEMBERS` |
| `POST` | `/organizations/invitations/accept` | authentication + a valid token |

### Study teams

| Method | Path | Requires |
|---|---|---|
| `GET` | `/organizations/{id}/studies/{sid}/team` | membership |
| `POST` | `/organizations/{id}/studies/{sid}/team` | `MANAGE_ASSIGNMENTS` |
| `PATCH` | `/organizations/{id}/studies/{sid}/team/{aid}` | `MANAGE_ASSIGNMENTS` |
| `DELETE` | `/organizations/{id}/studies/{sid}/team/{aid}` | `MANAGE_ASSIGNMENTS` |
| `GET` | `/organizations/{id}/studies/{sid}/team/history` | `VIEW_ACCESS_HISTORY` |

### History and housekeeping

| Method | Path | Requires |
|---|---|---|
| `GET` | `/organizations/{id}/audit` | `VIEW_ACCESS_HISTORY` |
| `POST` | `/organizations/{id}/maintenance/expire` | `MANAGE_MEMBERS` |
| `GET` | `/organizations/notifications/mine` | authentication |
| `POST` | `/organizations/notifications/{nid}/read` | recipient only |

---

## 2. Three status codes, and why they are different

| Code | Meaning | Example |
|---|---|---|
| **404** | Outside the caller's organizations, or a parent that is not theirs | A membership id from another organization, under your own organization's path |
| **403** | Inside the organization, not permitted | A researcher reading the audit trail |
| **409** | Well-formed, authorised, refused by the model | Removing the last owner; a duplicate assignment; a stale revision |

409 rather than 400 because these are *state* conflicts: the same request may
succeed once the state changes. A 400 invites the client to fix the request,
which is the wrong advice.

Two distinct 409 codes, because they need different responses from the user:

* `not_permitted` — appoint another owner, change their organization role.
* `concurrent_modification` — reload and look before acting again.

Collapsing them would make a management screen offer "retry" for a lost update,
which is how the other administrator's change disappears.

---

## 3. What the study-team screen may not decide

The role menu for a person is built from `assignable_study_roles`, which the
backend computes from their membership and puts on every member row. It is
never a client-side copy of `ROLE_MAY_BE_ASSIGNED_STUDY_ROLES`.

A copy would drift, and the direction of drift matters: the interface would
start offering a role the service refuses, which teaches users that refusals
are noise. The list is data, and it travels with the data.

The same reasoning governs the whole management interface: every hidden control
is also refused by the backend, and no visible control is trusted. A test
asserts the reverse inference is never made — a visible button may still be
refused, and the response is the authority.

---

## 4. Attachment restriction, in two layers

| Layer | Field | Meaning |
|---|---|---|
| Membership | `may_download_attachments` | Governs the collaboration as a whole |
| Assignment | `may_download_attachments` (nullable) | `NULL` defers; `False` withholds on this study |

The assignment layer can only subtract. Setting it `True` grants nothing a
membership withholds, because `policy.may()` requires both to permit. That
asymmetry is deliberate: a narrower agreement on one study is a real case, and
a *wider* one is not — it would mean a study assignment quietly overriding the
terms of the collaboration it sits inside.

---

## 5. Invitation delivery

Provider-neutral, in `services/invitation_delivery.py`. Three providers, none
carrying a credential:

| Provider | Behaviour | Use |
|---|---|---|
| `recorded` (default) | Sends nothing; returns the link to the administrator | An installation with no mail service |
| `console` | Writes the link to the log | Local development only — a log line with a redemption link is a credential in a log |
| `smtp` | Reads host, port, sender and credentials from the environment | Production, once configured |

Selected by `INVITATION_DELIVERY`. `SmtpDelivery` refuses to construct when
`SMTP_HOST` or `SMTP_FROM_ADDRESS` is unset, rather than defaulting to
something that would either fail obscurely or relay through somebody else's
server. There is no SMTP host, sender or password anywhere in the repository,
and a test asserts the constructor names the missing variable.

`recorded` is the honest default rather than a placeholder. An invitation that
silently failed to send is indistinguishable from one that arrived, and the
recipient is the only person who would ever find out. So the default states
plainly that nothing was sent and hands the administrator the link.

### The link

`build_invitation_link(token)` composes the destination from configuration and
the token, and from nothing else. There is no request field, query parameter or
body key anywhere in the API through which a caller can influence where an
invitation points — and the acceptance page reads only `token`.

That is the whole defence against an open redirect, and it is worth stating why
an invitation is unusually good bait: it arrives unexpectedly, it is *expected*
to be clicked, and it is expected to lead somewhere the recipient has never
been. A `next` parameter threaded through it would be a phishing primitive with
an organization's name attached.

An absolute `invitation_link_base` must be `http(s)` with a host. A
protocol-relative `//evil.example`, a `javascript:` scheme or a path containing
`..` falls back to the relative default and logs an error. Configuration is not
user input, but it is edited under time pressure by people who are not thinking
about redirects.

---

## 6. Database constraints and migrations

New table, `organization_invitations`. New columns on two existing tables. All
additive — no existing row changes, and an installation that never issues an
invitation is completely unaffected.

| Constraint | Prevents |
|---|---|
| `uq_org_invitation_pending` — partial unique on `(organization_id, email)` where `status = 'PENDING'` | Two live tokens for one address, where revoking "the" invitation leaves another working |
| `organization_invitations.token_hash` unique | A duplicated issue or a collision becoming two live invitations |
| `uq_study_assignment_study_user_role` (existing) | A duplicate active assignment, under concurrency as well as in sequence |
| `uq_org_membership_org_user` (existing) | One person holding two roles in one organization, so "what may they do" has one answer |

Migrations, in `db/migrations.py`:

| Change | Note |
|---|---|
| `organization_invitations` table | Created by `create_all`; listed in `EXPECTED_TABLES` so an upgrade reports it |
| `organization_memberships.revision` | `INTEGER NOT NULL DEFAULT 1` — defaulted, not nullable, because `NULL <> NULL` would make every conditional update on a pre-existing row a phantom conflict |
| `study_assignments.revision` | As above |
| `study_assignments.may_download_attachments` | `BOOLEAN NULL` — `NULL` means "defer to the membership", which is exactly what every pre-existing assignment did |
| `study_assignments.note` | `TEXT NULL` |

---

## 7. What the screens are for

Five tabs on `/organization`, plus a study-team screen and an acceptance page.

The rule they all obey: **organization authority and scientific eligibility are
never one column.** They are two badges, with the *kind* written in words
rather than carried by colour — because a colour-only distinction is invisible
to a colour-blind reader and to anybody printing the page for an audit file,
and because a user who reads "Administrator" as "can approve" has misread the
one distinction the platform rests on.

Sensitive actions — removing a member, demoting an owner, revoking an
assignment, confirming a migrated organization — require the subject's name to
be typed. Not because a yes/no dialog is too little friction in general, but
because these sit one click away from a list of similar-looking rows, and a
reflexive "yes" after a mis-click is produced by the same reflex as the click.
Typing the name forces the reader to look at *which* row.

**No password is displayed, requested or transmitted anywhere in these
screens**, and a test asserts it across every tab. People are added by
invitation and authenticate with their own credentials. An administrator who
can set somebody's password can sign in as them, which would make every
attribution in the registry unfalsifiable.

---

## 8. The browser walkthrough

`frontend/organization-walkthrough.mjs`, run against a live server:

```powershell
$env:NANOBIO_WALKTHROUGH_USER        = 'walkthrough_owner'
$env:NANOBIO_WALKTHROUGH_PASSWORD    = '<password>'
$env:NANOBIO_ORG_ADMIN_USER          = 'walkthrough_admin'
$env:NANOBIO_ORG_ADMIN_PASSWORD      = '<password>'
$env:NANOBIO_ORG_NEWCOMER_USER       = 'walkthrough_newcomer'
$env:NANOBIO_ORG_NEWCOMER_PASSWORD   = '<password>'
$env:NANOBIO_ORG_NEWCOMER_EMAIL      = 'walkthrough_newcomer@example.test'
node frontend/organization-walkthrough.mjs http://127.0.0.1:5173
```

Three accounts, because the escalation bar is a rule about acting on
*yourself*: a single-account run would skip the control the model rests on. The
owner must already belong to an organization holding at least one study.

### What it found

Two defects, neither reachable from any unit test:

1. **The organization context never left its loading state in development.**
   `OrganizationProvider` cleared a `mounted` ref on unmount and never set it
   on mount, so React StrictMode's mount–unmount–remount left it permanently
   false and every response was discarded as belonging to an unmounted
   provider. The symptom was "Loading workspace…" forever beside a perfectly
   good 200 in the network tab. Testing Library renders without StrictMode, so
   no component test could reproduce it.

2. **The study-team list leaked a roster.** `list_assignments` checked
   organization membership and stopped there, so a member with
   `ASSIGNED_STUDIES` scope and no assignment on a study got a 200 listing
   everybody on it. It now applies the same visibility rule as the study
   itself and 404s. Pinned by
   `test_study_team_api.py::test_a_member_who_cannot_see_the_study_gets_404_not_a_roster`.

---

## 9. Known gaps

* Medical report routes remain unconverted — see
  `ACTIVE_ORGANIZATION_CONTRACT.md` §7 and `KNOWN_UNCONVERTED_ROUTES`.
* Notifications are stored and served but not surfaced in the interface.
* `POST /organizations` is open to any authenticated account. Appropriate while
  the deployment is a single laboratory; a hosted deployment would gate it.
