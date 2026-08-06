# The active-organization contract

How a caller selects which organization they are acting within, what the
backend guarantees about that choice, and what the frontend must do when it
changes.

This is the single mechanism. Any new route, client or integration follows it;
there is no second way to select an organization and no plan to add one.

---

## 1. The mechanism: a request header

    X-Organization-Id: 42

Sent on every API request once an organization has been selected. Omitted when
the user has not chosen one.

### Why a header and not a session field

A session-stored active organization is *server state that outlives the
request*. Two browser tabs then share one selection, so switching organization
in one tab silently changes what the other tab is looking at — and the second
tab keeps rendering the previous organization's data under the new
organization's name. That is a disclosure bug that looks like a UI glitch.

A header makes the selection a property of the request. Every request states
what it is asking for, nothing is remembered between requests, and two tabs
cannot interfere. It also survives load balancing and makes any request
reproducible from its own contents, which matters when reading an access log
after the fact.

The cost is that the client must send it consistently. Section 5 covers that.

---

## 2. What the backend guarantees

`api/deps_organization.get_access_context` resolves the header into an
`AccessContext` once per request, and every organization-scoped route depends
on it.

### 2.1 Selection can only narrow, never widen

    visible_organization_ids(ctx) = memberships ∩ {active_organization_id}

The header is intersected with the caller's actual, currently-in-force
memberships. It is not trusted as an assertion of anything.

Consequences, all of them deliberate:

| Header value | Result |
|---|---|
| An organization the caller belongs to | Scope narrows to it |
| An organization the caller does **not** belong to | **Empty scope** — every list is empty, every record 404 |
| An organization that does not exist | Empty scope |
| Absent | All of the caller's organizations |
| Not an integer | **400**, request refused |

A forged or stale header is therefore inert. The worst it can achieve is
showing the caller *less* than they are entitled to.

### 2.2 A malformed header is refused, not ignored

`X-Organization-Id: banana` returns **400 `invalid_organization`**.

Falling back to "all organizations" would turn a client-side typo into a
silent widening of scope — the one direction this contract must never move in.

### 2.3 Membership is re-verified on every request

The context is rebuilt per request from `organization_memberships` and
`study_assignments`. Nothing about access is cached between requests.

Expiry is evaluated **on read**, not by a sweep job:

```python
if expires_at is not None and now >= expires_at:
    # grants nothing, whatever the stored status says
```

A membership whose `expires_at` has passed grants nothing from that instant,
whether or not anything has got round to marking it `EXPIRED`. A failed
housekeeping job cannot silently extend an external collaboration.

Membership states and their effect:

| Status | Access |
|---|---|
| `ACTIVE`, within `starts_at`/`expires_at` | Granted |
| `ACTIVE`, past `expires_at` | **None** |
| `ACTIVE`, before `starts_at` | **None** |
| `INVITED` | None — not yet accepted |
| `SUSPENDED` | None — restorable |
| `REVOKED` / `EXPIRED` | None — terminal |

An organization that is `SUSPENDED` or `ARCHIVED` grants nothing to anybody,
regardless of membership.

### 2.4 Absent membership is not an error

A caller with no memberships gets an empty scope, which produces
`organization_id IN ()` — an impossible predicate — rather than an early
return. Lists come back empty and records 404. There is no code path where the
filter is simply absent.

### 2.5 Not-found and not-yours are indistinguishable

Outside the caller's organizations → `RecordNotVisible` → **404**, with a body
carrying no organization, owner or reason.

Inside the organization but not permitted → `PolicyDenied` → **403**, with an
explanation (safe: the caller can already see the record exists).

A caller therefore cannot use status codes to discover whether an identifier
belongs to a real record elsewhere. Proven in
`test_organization_routes.py::test_a_real_foreign_id_and_an_absent_id_are_indistinguishable`,
which asserts identical status, keys and body.

### 2.6 Client-supplied organization identifiers are never trusted

There is no request body field anywhere that sets `organization_id`. A new
record inherits its organization from its **stored parent**:

* a study from its project;
* a candidate, experiment, measurement, attachment and readiness record from
  its study;
* a record with no parent from the caller's single organization — and if the
  caller belongs to several without selecting one, the request is refused with
  `organization_required` rather than guessed.

Cross-parent pairings are refused before the write. Passing your own study id
with another organization's project id returns 404, not a re-parented record.

---

## 3. Stale requests after switching

The header makes staleness self-limiting: a request carrying the old
organization id is evaluated against the old organization, and the response
contains only that organization's data — never a mixture.

What the backend cannot do is stop the *client* rendering an old response under
a new heading. That is section 5.

---

## 4. Server-side context that must be cleared

None. The backend stores no active organization, no active study and no active
candidate. There is no server-side workspace context to invalidate, which is
the main reason the header design was chosen.

The only per-request state is the `AccessContext`, which is constructed at the
start of the request and discarded at the end.

---

## 5. Frontend obligations

The backend cannot enforce these. They are the client's side of the contract.

1. **Send the header on every API request** once an organization is selected —
   including background polling and prefetches. A request that omits it is
   answered across *all* the user's organizations, which is correct but is not
   what the interface is showing.

2. **On switch, discard all cached data before the first new request.**
   Studies, candidates, experiments, readiness reports, dashboard counts,
   attachment metadata and in-flight promises. Clearing after the response
   arrives is too late — the old data is on screen under the new name in the
   interval.

3. **Clear the active study, candidate and pathway context.** A study id from
   the previous organization will now 404. Carrying the selection across a
   switch produces an error page where a clean state was wanted.

4. **Cancel or ignore in-flight requests issued before the switch.** They carry
   the old header and will return the old organization's data, arriving after
   the switch has visually completed.

5. **Treat 404 after a switch as expected**, not as an error to report. A
   bookmarked or in-memory identifier from the previous organization is
   correctly invisible.

6. **Never rely on hiding a control.** Every button the interface hides is also
   refused by the backend. The reverse is not a valid inference: a visible
   control may still be refused, and the response is the authority.

---

## 6. Adding a new route

1. Depend on `get_access_context` and thread the `AccessContext` down.
2. Read through `organizations/scoping.scoped()` or one of the `_scoped_*`
   resolvers — never `session.get()` followed by a check.
3. Derive `organization_id` for writes from the stored parent.
4. Let `RecordNotVisible` and `PolicyDenied` propagate; the app-level handlers
   produce the correct status and body.

If the route genuinely owns no organization data — a health probe, a static
vocabulary, a stateless calculation — add its exact path to
`api/route_classification.EXEMPT_ROUTES` **with a written reason**.

Forgetting is caught mechanically. `EXEMPT_ROUTES` is fail-closed: every route
is required to resolve a context unless it is listed, so a new route that omits
the dependency fails
`test_organization_routes.py::TestEveryScopedRouteIsGuarded` on the first run.
The organization-management and study-team routes are covered by that guard
automatically, precisely because it is a list of exemptions rather than a list
of protected routes — nothing had to be added for them.

The guard itself is mutation-tested by
`test_route_guard_mutation.py`, which strips the dependency from one
representative route per converted group, asserts the guard reports it, and
restores it. A green structural test is evidence only if it is known to fail
against a broken route, and that file is what knows it.

---

## 7. Known gap

Medical report routes (`/api/v1/reports/*`) are **not yet converted**. They
remain owner-scoped only, exactly as workspace and readiness were before this
milestone, and they hold the most sensitive data in the application.

They are listed in `api/route_classification.KNOWN_UNCONVERTED_ROUTES` —
deliberately a separate list from `EXEMPT_ROUTES`, because an exemption says
"owns no organization data" and this says "owns organization data and is not
protected yet". A test pins that list to the reports group, so a future
unconverted route anywhere else fails rather than joining it quietly.
