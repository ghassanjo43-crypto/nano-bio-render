"""Which routes are exempt from the organization boundary, and why.

Fail-closed by construction
---------------------------
The rule is not "routes listed here are scoped". It is the opposite: **every
route is required to resolve an ``AccessContext`` unless it appears below with
a written reason.** A new route added next year is scoped by default, and if
its author forgets the dependency the structural test fails on the first run.

That direction matters. A registry of *protected* routes fails open — the
route somebody forgot to add is simply absent, and absence looks exactly like
a route nobody has written yet. A registry of *exemptions* fails closed: the
only way to be unprotected is to write down that you meant it.

What may legitimately be exempt
-------------------------------
Three kinds of route, and no others:

* **Unauthenticated** — health, readiness probes, login. There is no actor to
  resolve a context for.
* **Static vocabulary** — enum members, labels, the data dictionary. Identical
  for every caller in every organization, and derived from source code rather
  than from the database.
* **Account-self** — routes that act only on the caller's own session or
  profile and touch no organization-scoped record.

A route that reads or writes any row carrying an ``organization_id`` is never
exempt, whatever else is true of it.
"""

from __future__ import annotations

__all__ = ["EXEMPT_ROUTES", "KNOWN_UNCONVERTED_ROUTES", "GROUPS",
           "is_exempt", "classify"]


#: path -> why it needs no organization context.
#:
#: Deliberately exact paths, not prefixes. A prefix rule is how a scoped route
#: ends up exempt by accident: someone exempts ``/api/v1/auth/`` for login and
#: silently exempts every account-management route added afterwards.
EXEMPT_ROUTES: dict[str, str] = {
    # --- unauthenticated ---
    "/health": "Liveness probe. No actor.",
    "/ready": "Readiness probe. No actor.",
    "/api": "Service descriptor. Static.",
    "/api/v1/auth/login": "Establishes the session a context is resolved from.",
    "/api/v1/auth/logout": "Ends the caller's own session.",
    "/api/v1/auth/cookie-policy": (
        "Reports which attributes this server sets on the session cookie. "
        "Static configuration, identical for every caller, and not a secret — "
        "knowing a cookie is HttpOnly and Secure helps an attacker not at "
        "all. It exists so a deployment check can verify the RUNNING "
        "configuration rather than the source."),
    "/api/v1/account/activate": (
        "Sets a first password using a single-use activation token. "
        "Unauthenticated by necessity: the caller has no password yet, so "
        "there is no session to resolve a context from. Protected by the "
        "token, which is 256 random bits, single-use, short-lived and bound "
        "to its purpose."),
    "/api/v1/account/reset": (
        "Sets a password using a single-use reset token. Unauthenticated by "
        "necessity: the caller has forgotten their password. Same token "
        "properties as activation."),
    "/api/v1/account/forgot": (
        "Requests a reset link. Unauthenticated by necessity, and answers "
        "identically whether or not the account exists, so it discloses "
        "nothing about who has an account."),

    # --- account-self ---
    #
    # Each of these acts on the CALLER's own account and nothing else. Every
    # query is filtered by the authenticated user id, so there is no record
    # belonging to an organization for a context to scope — and adding one
    # would be misleading, implying an organization boundary where the
    # boundary is actually the account.
    #
    # The administrative account routes are NOT here. They act on somebody
    # else, they take an organization in the path, and they resolve a context
    # and require MANAGE_ACCOUNTS within it.
    "/api/v1/auth/me": (
        "Returns the caller's own identity and roles. Touches no "
        "organization-scoped record."),
    "/api/v1/account/password-policy": (
        "The password rules. Constants from source, identical for every "
        "caller."),
    "/api/v1/account/password": (
        "Changes the caller's OWN password, having re-verified their current "
        "one. Scoped to the authenticated account by construction."),
    "/api/v1/account/sessions": (
        "Lists the caller's OWN sessions, filtered by their user id."),
    "/api/v1/account/sessions/revoke": (
        "Ends one of the caller's OWN sessions. A handle belonging to anybody "
        "else is 404, so the route cannot reach another account."),
    "/api/v1/account/sessions/revoke-all": (
        "Ends the caller's OWN other sessions."),
    "/api/v1/account/security-activity": (
        "The caller's OWN security trail, filtered by their user id. Carries "
        "no password, token or session identifier."),

    # --- static vocabulary, derived from source not from the database ---
    "/api/v1/validation/vocabulary": (
        "Subtypes, purposes, statuses and evidence levels. Enum members and "
        "labels, identical for every caller."),
    "/api/v1/science/vocabulary": (
        "Readiness areas, statuses and evidence levels. Enum members."),
    "/api/v1/science/dictionary": (
        "The scientific data dictionary: field definitions and units. A "
        "specification, not anybody's data."),
    "/api/v1/demo/scenarios": (
        "Built-in demonstration scenario catalogue, shipped as fixtures. "
        "Synthetic and identical for every caller."),
    "/api/v1/demo/scenarios/{slug}": (
        "One built-in demonstration scenario fixture. Synthetic."),

    # --- stateless calculation ---
    # These take inputs in the request, return a number, and persist nothing.
    # Verified: no session dependency, no model import, no write. There is no
    # record for an organization to own, so there is nothing to scope.
    "/api/v1/design/score": (
        "Pure calculation. Scores the inputs in the request body and stores "
        "nothing; there is no record for an organization to own."),
    "/api/v1/pk/simulate": (
        "Pure calculation. Two-compartment solve over request inputs; "
        "persists nothing."),
    "/api/v1/pk/simulate-routed": (
        "Pure calculation. Route-aware two-compartment solve; persists "
        "nothing."),
    "/api/v1/pk/plan": (
        "Static planning guidance derived from the route vocabulary."),
    "/api/v1/pk/administration-routes": (
        "The administration-route vocabulary. Enum members."),

    # --- frontend ---
    "/": "Serves the single-page application shell. No database record.",
}


#: Routes that **should** be organization-scoped and are not yet.
#:
#: Separate from ``EXEMPT_ROUTES`` on purpose, and the distinction is the
#: whole point. An exemption says "this route owns no organization data". An
#: entry here says "this route owns organization data and is not protected" —
#: a gap being tracked, not a decision that has been taken.
#:
#: Keeping them apart is what stops a gap from quietly becoming a policy. If
#: these were folded into the exemption list, the boundary would look complete
#: while endpoints served another organization's clinical assessments.
#:
#: **Now empty.** The medical report routes were the last entry and were
#: converted in the medical-report isolation pass: every one of them resolves
#: an ``AccessContext``, every lookup applies the organization predicate inside
#: the SQL, and ``organization_id`` is derived from the caller's selection or
#: the stored parent rather than accepted from a request.
#:
#: The dictionary is kept rather than deleted, and a test pins it empty. That
#: is deliberate: re-introducing a gap should require adding an entry here with
#: a written reason and changing a test that says the list is empty, not
#: quietly omitting a dependency. An empty tracked-gap list is a claim, and it
#: is checked.
KNOWN_UNCONVERTED_ROUTES: dict[str, str] = {}


#: Route groups, for reporting and for targeting mutation checks. Prefix-based
#: because this is descriptive only — it grants nothing.
GROUPS: dict[str, tuple[str, ...]] = {
    "Organization management": ("/api/v1/organizations",),
    "Validation Registry": ("/api/v1/validation/",),
    "Workspace / projects": ("/api/v1/projects",),
    "Runs / studies": ("/api/v1/runs", "/api/v1/demo/"),
    "Scientific Readiness": ("/api/v1/science/",),
    "Reports": ("/api/v1/reports",),
    "Calculation": ("/api/v1/design/", "/api/v1/pk/"),
    "Authentication": ("/api/v1/auth/",),
    "Account & session": ("/api/v1/account/",),
    "Meta": ("/health", "/ready", "/api"),
}


def is_exempt(path: str) -> bool:
    return path in EXEMPT_ROUTES


def classify(path: str) -> str:
    """Which group a path belongs to. Longest matching prefix wins."""
    best, best_len = "Unclassified", -1
    for group, prefixes in GROUPS.items():
        for prefix in prefixes:
            if path.startswith(prefix) and len(prefix) > best_len:
                best, best_len = group, len(prefix)
    return best
