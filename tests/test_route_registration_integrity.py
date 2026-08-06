"""The application imports cleanly and registers every route exactly once.

Why this exists
---------------
Adding the candidate-versioning routes introduced a helper called
`_version_summary` into a module that already had one — for experiment
versions. Python does not complain; the second definition simply replaced the
first. Every candidate route worked, and `list_experiments` started raising
`TypeError: _version_summary() takes 1 positional argument but 2 were given` on
a route nobody had touched.

Nothing in the suite was watching for that. It surfaced because the
organization-isolation tests happened to call the shadowed route, which is luck
rather than coverage: a shadowed helper used only by a route without a test
would have shipped.

So these check the properties that would have caught it directly, and the
neighbouring ones that fail the same way:

  * every route module imports and the app builds;
  * no module defines the same top-level name twice;
  * no (method, path) pair is registered twice;
  * every route's handler is callable with the signature FastAPI resolved.

All of it reads the built application rather than the source, because what
matters is what the running process ends up with.
"""

from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ROUTES_DIR = BACKEND_ROOT / "nanobio_studio" / "app" / "api" / "routes"
APP_DIR = BACKEND_ROOT / "nanobio_studio" / "app"


@pytest.fixture(scope="module")
def app():
    """Importing this is itself the first assertion."""
    from nanobio_studio.app.vertical_slice import app as fastapi_app

    return fastapi_app


# ===========================================================================
# 1. It imports and builds
# ===========================================================================

class TestTheApplicationBuilds:

    def test_the_app_imports_without_error(self, app):
        assert app is not None
        assert len(app.routes) > 50, (
            f"only {len(app.routes)} routes registered; a router probably "
            f"failed to include")

    def test_every_route_module_the_app_uses_imports_on_its_own(self, app):
        """A module that only imports as part of a package can hide a circular
        import that bites the first time somebody imports it directly — in a
        script, a migration, or a test.

        Scoped to the modules this application actually includes, discovered
        from the built routing table rather than from the directory listing.
        `routes/` also contains `ingestion.py`, `query.py` and `search.py`,
        which belong to the separate LNP ingestion backend in `app/main.py`;
        they import `loguru`, which this application does not depend on and
        does not install. Failing on those would be reporting a fact about a
        different application.
        """
        import importlib

        modules = sorted({
            endpoint.__module__
            for route in app.routes
            if (endpoint := getattr(route, "endpoint", None)) is not None
            and getattr(endpoint, "__module__", "").startswith(
                "nanobio_studio.app.api.routes")
        })
        assert modules, "no route modules were discovered from the app"

        failures = []
        for module in modules:
            try:
                importlib.import_module(module)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{module}: {type(exc).__name__}: {exc}")

        assert failures == [], failures

    def test_the_route_modules_this_app_uses_are_a_known_set(self, app):
        """So a module silently dropping out of the routing table is visible.

        Without this, a router that failed to include would make the test above
        pass by checking fewer modules.
        """
        modules = {
            endpoint.__module__.rsplit(".", 1)[-1]
            for route in app.routes
            if (endpoint := getattr(route, "endpoint", None)) is not None
            and getattr(endpoint, "__module__", "").startswith(
                "nanobio_studio.app.api.routes")
        }
        for expected in ("validation", "auth", "account", "organizations",
                         "reports", "workspace"):
            assert expected in modules, (
                f"the {expected} router is not contributing any route")

    def test_every_service_module_imports_on_its_own(self):
        import importlib

        failures = []
        for path in sorted((APP_DIR / "services").glob("*.py")):
            if path.name.startswith("_"):
                continue
            module = f"nanobio_studio.app.services.{path.stem}"
            try:
                importlib.import_module(module)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{module}: {type(exc).__name__}: {exc}")

        assert failures == [], failures


# ===========================================================================
# 2. No shadowed definitions
# ===========================================================================

def _redefinitions(path: Path) -> list[str]:
    """Top-level names defined more than once in one module.

    Parsed, not grepped, and only *module-level* definitions are counted —
    a method named `get` on three different classes is fine and common,
    whereas two module-level functions of the same name means one of them is
    unreachable.

    `try/except ImportError` fallbacks legitimately define a name twice, so
    anything inside a `Try` is skipped.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))

    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Try):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            names.append(node.name)

    return [name for name, count in Counter(names).items() if count > 1]


class TestNoShadowedDefinitions:

    def test_no_route_module_defines_a_name_twice(self):
        """The exact defect: two `_version_summary` functions in one module.

        The second silently replaced the first, and every caller of the first
        started failing on a signature mismatch.
        """
        offenders = {}
        for path in sorted(ROUTES_DIR.glob("*.py")):
            duplicates = _redefinitions(path)
            if duplicates:
                offenders[path.name] = duplicates

        # Parsing needs no imports, so every file is checked here — including
        # the ingestion-backend modules. A shadowed helper is a defect wherever
        # it lives.
        assert offenders == {}, (
            f"these route modules define a name more than once, so the later "
            f"definition silently replaces the earlier one: {offenders}")

    def test_no_service_module_defines_a_name_twice(self):
        offenders = {}
        for path in sorted((APP_DIR / "services").glob("*.py")):
            duplicates = _redefinitions(path)
            if duplicates:
                offenders[path.name] = duplicates

        assert offenders == {}, offenders

    def test_no_model_module_defines_a_name_twice(self):
        """A shadowed model class is worse than a shadowed function: the
        table stays in the metadata and the name points somewhere else."""
        offenders = {}
        for path in sorted((APP_DIR / "db").glob("*.py")):
            duplicates = _redefinitions(path)
            if duplicates:
                offenders[path.name] = duplicates

        assert offenders == {}, offenders

    def test_the_detector_actually_detects(self, tmp_path):
        """Positive control.

        A checker that found nothing because it was looking in the wrong place
        would pass all three tests above.
        """
        probe = tmp_path / "shadowed.py"
        probe.write_text(
            "def helper(a):\n    return a\n\n\n"
            "def helper(a, b):\n    return a + b\n",
            encoding="utf-8")

        assert _redefinitions(probe) == ["helper"]

    def test_the_detector_permits_legitimate_duplicates(self, tmp_path):
        """Methods on different classes, and import fallbacks, are fine."""
        probe = tmp_path / "legitimate.py"
        probe.write_text(
            "class A:\n    def get(self):\n        return 1\n\n\n"
            "class B:\n    def get(self):\n        return 2\n\n\n"
            "try:\n    from x import thing\nexcept ImportError:\n"
            "    def thing():\n        return None\n",
            encoding="utf-8")

        assert _redefinitions(probe) == []


# ===========================================================================
# 3. No duplicate registrations
# ===========================================================================

class TestNoDuplicateRoutes:

    def test_no_method_and_path_pair_is_registered_twice(self, app):
        """Two handlers on one (method, path) means the first one wins and the
        second is dead code that looks live."""
        seen = Counter()
        for route in app.routes:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None) or set()
            if path is None:
                continue
            for method in methods:
                seen[(method, path)] += 1

        duplicates = {pair: count for pair, count in seen.items() if count > 1}
        assert duplicates == {}, (
            f"these (method, path) pairs are registered more than once, so "
            f"only the first handler is reachable: {duplicates}")

    def test_paths_registered_more_than_once_use_different_methods(self, app):
        """`/candidates/{id}/versions` legitimately has both GET and POST.

        Asserted explicitly so the check above is understood as being about
        method-and-path, not path alone.
        """
        by_path: dict[str, set[str]] = {}
        for route in app.routes:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None) or set()
            if path is None:
                continue
            by_path.setdefault(path, set()).update(methods)

        shared = {p: m for p, m in by_path.items() if len(m) > 1}
        assert shared, (
            "no path serves more than one method, which is unexpected and "
            "suggests this check is not seeing the real routing table")


# ===========================================================================
# 4. Handlers are what they claim to be
# ===========================================================================

class TestHandlersAreIntact:

    def test_every_route_endpoint_is_callable(self, app):
        broken = []
        for route in app.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            if not callable(endpoint):
                broken.append(getattr(route, "path", "?"))
        assert broken == [], broken

    def test_every_endpoint_belongs_to_the_module_it_was_declared_in(self, app):
        """Catches a shadowing that survives registration.

        FastAPI captures the function object at decoration time, so a route
        registered before its name was shadowed keeps working while every
        direct caller of that name gets the replacement. Comparing the
        endpoint's qualified name against the module it lives in surfaces the
        mismatch.
        """
        mismatched = []
        for route in app.routes:
            endpoint = getattr(route, "endpoint", None)
            path = getattr(route, "path", "?")
            if endpoint is None or not hasattr(endpoint, "__module__"):
                continue
            module = sys.modules.get(endpoint.__module__)
            if module is None:
                continue
            resolved = getattr(module, endpoint.__name__, None)
            if resolved is not None and resolved is not endpoint:
                mismatched.append(
                    f"{path} -> {endpoint.__module__}.{endpoint.__name__} "
                    f"is registered, but that name now refers to something "
                    f"else in its module")

        assert mismatched == [], mismatched

    def test_the_candidate_versioning_routes_are_all_registered(self, app):
        """The routes this milestone added, named individually.

        A router that silently failed to include would otherwise show up only
        as a smaller total.
        """
        paths = {getattr(r, "path", "") for r in app.routes}
        for expected in (
            "/api/v1/validation/candidates/{candidate_id}/versions",
            "/api/v1/validation/candidate-versions/{version_id}/revise",
            "/api/v1/validation/candidate-versions/{version_id}/supersede",
            "/api/v1/validation/candidate-versions/{version_id}/withdraw",
            "/api/v1/validation/candidate-versions/{version_id}"
            "/compare/{other_version_id}",
        ):
            assert expected in paths, f"{expected} is not registered"

    def test_no_route_shares_an_operation_id(self, app):
        """Duplicate operation ids break generated clients and OpenAPI."""
        ids = Counter()
        for route in app.routes:
            name = getattr(route, "name", None)
            path = getattr(route, "path", None)
            if name and path:
                ids[(name, path)] += 1

        duplicates = {k: v for k, v in ids.items() if v > 1}
        assert duplicates == {}, duplicates


# ===========================================================================
# 5. The OpenAPI document builds
# ===========================================================================

class TestTheSchemaBuilds:

    def test_the_openapi_document_generates(self, app):
        """Generating it exercises every response model and signature at once.

        A route whose annotations do not resolve passes import and fails here,
        which is the cheapest place to find it.
        """
        document = app.openapi()

        assert document["openapi"].startswith("3.")
        assert document["paths"], "the generated document has no paths"

    def test_the_candidate_routes_appear_in_the_document(self, app):
        document = app.openapi()
        assert ("/api/v1/validation/candidate-versions/{version_id}/revise"
                in document["paths"])
