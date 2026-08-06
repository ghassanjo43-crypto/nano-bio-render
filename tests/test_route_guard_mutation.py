"""Does the fail-closed route guard actually detect an unguarded route?

Why a guard needs its own test
------------------------------
``TestEveryScopedRouteIsGuarded`` passes. That is compatible with two very
different worlds: one where every route resolves an ``AccessContext``, and one
where the check is broken and would pass whatever the routes did. A green
structural test is evidence for the first only if the test is known to fail
against the second.

So this file breaks routes on purpose, one at a time, and asserts the guard
notices — then puts them back and asserts it is quiet again. That is the whole
content of a mutation check: a control nobody has ever seen fail is not yet
known to be a control.

Mutation in memory, not in the source tree
------------------------------------------
Each check removes the access-context dependency from one live route's
``dependant`` and restores it in a ``finally``. Editing files would leave the
repository broken if the process died mid-run — and the guard reads exactly
this structure, so removing it here is a faithful reproduction of the mistake
being guarded against: somebody writes a route and omits the dependency.

The restoration is asserted, not assumed. A mutation check that silently failed
to restore would turn one deliberate hole into a permanent one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.api.deps_organization import (  # noqa: E402
    get_access_context,
)

from tests.test_organization_routes import (  # noqa: E402
    _app_routes, _resolves_access_context,
)


#: One representative route per converted group, named by (method, path).
#:
#: Representative rather than exhaustive: the guard is one predicate applied
#: uniformly, so proving it detects a hole in each group proves it detects a
#: hole. Mutating all ninety would take longer and say the same thing.
#:
#: The two organization-management entries are the point of this pass: those
#: routes hand out access, so a guard that failed to notice one of them was
#: unprotected would be the most expensive kind of gap.
REPRESENTATIVE_ROUTES: tuple[tuple[str, str, str], ...] = (
    ("Organization management", "GET",
     "/api/v1/organizations/{organization_id}/members"),
    ("Organization management", "POST",
     "/api/v1/organizations/{organization_id}/invitations"),
    ("Study-team management", "POST",
     "/api/v1/organizations/{organization_id}/studies/{study_id}/team"),
    ("Study-team management", "GET",
     "/api/v1/organizations/{organization_id}/studies/{study_id}"
     "/team/history"),
    ("Validation Registry", "GET", "/api/v1/validation/experiments"),
    ("Workspace / projects", "GET", "/api/v1/projects"),
    ("Runs / studies", "GET", "/api/v1/runs"),
    ("Scientific Readiness", "GET",
     "/api/v1/science/studies/{study_id}/readiness"),

    # --- medical reports ------------------------------------------------
    #
    # One per kind of surface, because they fail differently: a list leaks in
    # aggregate, a detail leaks a document, a mutation writes across the
    # boundary, a download takes bytes off-site, and a history leaks who did
    # what to a record the reader may not open. These hold the most sensitive
    # data in the application, so they get five entries rather than one.
    ("Reports: list/search", "GET", "/api/v1/reports"),
    ("Reports: detail", "GET", "/api/v1/reports/{assessment_id}"),
    ("Reports: mutation", "POST", "/api/v1/reports/{assessment_id}/confirm"),
    ("Reports: document download", "GET",
     "/api/v1/reports/{assessment_id}/document"),
    ("Reports: audit history", "GET",
     "/api/v1/reports/{assessment_id}/history"),
)


def _find(method: str, path: str):
    for route, route_path, methods in _app_routes():
        if route_path == path and method in methods:
            return route
    return None


def _unguarded_paths() -> list[str]:
    """What the structural guard would report right now."""
    from nanobio_studio.app.api.route_classification import (
        EXEMPT_ROUTES, KNOWN_UNCONVERTED_ROUTES,
    )

    found = []
    for route, path, _methods in _app_routes():
        if path in EXEMPT_ROUTES or path in KNOWN_UNCONVERTED_ROUTES:
            continue
        if not _resolves_access_context(route):
            found.append(path)
    return found


class TestTheGuardDetectsAnUnguardedRoute:

    def test_the_guard_is_quiet_to_begin_with(self):
        """Positive control. Everything below depends on this being true."""
        assert _unguarded_paths() == [], (
            "the guard is already reporting routes; the mutation checks below "
            "could not distinguish their own effect from this one")

    @pytest.mark.parametrize(
        "group,method,path", REPRESENTATIVE_ROUTES,
        ids=[f"{g}:{m} {p}" for g, m, p in REPRESENTATIVE_ROUTES])
    def test_removing_the_dependency_is_detected(self, group, method, path):
        route = _find(method, path)
        assert route is not None, (
            f"{method} {path} is not a route. If it was renamed, update "
            f"REPRESENTATIVE_ROUTES — a mutation check pointed at a route "
            f"that no longer exists proves nothing and would pass forever.")

        original = list(route.dependant.dependencies)
        assert _resolves_access_context(route), (
            f"{method} {path} does not resolve an AccessContext even before "
            f"mutation")

        try:
            route.dependant.dependencies = [
                d for d in route.dependant.dependencies
                if d.call is not get_access_context
            ]
            for dep in route.dependant.dependencies:
                dep.dependencies = [
                    d for d in dep.dependencies
                    if d.call is not get_access_context
                ]

            assert not _resolves_access_context(route), (
                "the mutation did not take effect")
            reported = _unguarded_paths()
            assert path in reported, (
                f"THE GUARD DID NOT NOTICE. {method} {path} was stripped of "
                f"its access-context dependency and the structural check "
                f"stayed green, so it is not evidence that the other "
                f"{len(REPRESENTATIVE_ROUTES)} groups are protected either.")
        finally:
            route.dependant.dependencies = original

        # Restoration is asserted, not assumed.
        assert _resolves_access_context(route), (
            f"{method} {path} was NOT restored after the mutation check")
        assert _unguarded_paths() == [], (
            "the application was left with an unguarded route after a "
            "mutation check")

    def test_the_guard_is_quiet_again_afterwards(self):
        """Ordered last by declaration; asserts the file left nothing behind."""
        assert _unguarded_paths() == []
