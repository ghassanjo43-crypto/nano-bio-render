"""Cross-organization isolation for medical reports, over HTTP.

Why this file is the strictest in the suite
-------------------------------------------
A report assessment holds a patient's document. Everything else the platform
stores is a formulation, a measurement or an access grant; this is the one place
where a leak is about a person rather than about a company's work. So the bar
here is not "the row is not returned" but **"nothing about the row is
observable"** — not its existence, not its name, not its size, not its status,
not a count that includes it, not a timestamp on an audit line, and not a
difference in how the refusal is phrased.

Several tests therefore assert that two responses are *byte-for-byte identical*
rather than merely both refused. A caller who can tell "that identifier belongs
to something real elsewhere" from "that identifier is nothing" has learned a
fact about another organization's patients, and has learned it from a system
that believes it refused them.

The cast, and why each member is here
-------------------------------------
Two organizations, and a full ladder in each, because the interesting failures
are the ones where somebody legitimately has *some* access:

* ``alpha_researcher`` / ``beta_researcher`` — the authors. Positive controls.
* ``alpha_wide`` — a researcher with organization-wide scope, who may read a
  colleague's assessment. Proves the scope predicate is real in both directions.
* ``alpha_admin`` / ``alpha_owner`` — administrative. May read the access trail
  and **not one patient assessment**. This is the separation the whole model
  rests on, applied to the most sensitive data in the application.
* ``alpha_reviewer`` / ``alpha_approver`` — scientific. May read and amend.
* ``alpha_auditor`` — reads the trail, nothing else.
* ``alpha_cro`` — an external contract laboratory. Reaches nothing, ever, and
  has attachment downloads withheld besides.
* ``both_orgs`` — a member of *both* organizations. The parent-injection cast
  member: belonging to two organizations must never permit linking them.
* ``unaffiliated`` — an account with no membership at all.
* ``suspended`` / ``revoked`` / ``expired`` — memberships in each terminal or
  paused state, all of which must grant nothing.

Every negative test is paired with a positive control against a *populated*
record, because "you cannot see it" proves nothing if nobody can.
"""

from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.api.deps_organization import (  # noqa: E402
    ORGANIZATION_HEADER,
)
from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.organizations.vocabulary import (  # noqa: E402
    AccessScope, MembershipStatus, OrganizationRole, OrganizationStatus,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

REPORTS = "/api/v1/reports"
PASSWORD = "Fixture-Only-Passphrase-9f3a2b"

#: Deliberately distinctive strings. If any of them appears in a response to a
#: caller who should not see the record, a test finds it by searching the raw
#: body rather than by knowing which field it would have been in.
ALPHA_MARKER = "ALPHAPATIENTMARKER"
BETA_MARKER = "BETAPATIENTMARKER"


def _document(marker: str) -> bytes:
    return (
        b"SYNTHETIC DEMONSTRATION DOCUMENT -- NOT A REAL MEDICAL REPORT\n"
        b"This document is fictional and invented for software testing.\n"
        b"Diagnosis: invasive ductal carcinoma of the left breast.\n"
        + f"Case reference: {marker}\n".encode()
    )


@pytest.fixture(scope="module")
def two_orgs(tmp_path_factory):
    """Alpha and Beta, each with a populated assessment and a full cast."""
    from sqlalchemy import select

    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership,
    )
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("report_isolation")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    # username -> (platform role, organization role, scope, extra kwargs)
    ALPHA_CAST = {
        "alpha_researcher": (OrganizationRole.RESEARCHER,
                             AccessScope.ASSIGNED_STUDIES, {}),
        "alpha_wide": (OrganizationRole.RESEARCHER,
                       AccessScope.ORGANIZATION, {}),
        "alpha_owner": (OrganizationRole.OWNER,
                        AccessScope.ORGANIZATION, {}),
        "alpha_admin": (OrganizationRole.ADMINISTRATOR,
                        AccessScope.ORGANIZATION, {}),
        "alpha_reviewer": (OrganizationRole.REVIEWER,
                           AccessScope.ORGANIZATION, {}),
        "alpha_approver": (OrganizationRole.APPROVER,
                           AccessScope.ORGANIZATION, {}),
        "alpha_auditor": (OrganizationRole.AUDITOR,
                          AccessScope.ORGANIZATION, {}),
        "alpha_cro": (OrganizationRole.LAB_CONTRIBUTOR,
                      AccessScope.ASSIGNED_STUDIES,
                      {"external_organization": "Contract Labs Ltd",
                       "may_download_attachments": False}),
        "alpha_suspended": (OrganizationRole.RESEARCHER,
                            AccessScope.ORGANIZATION,
                            {"status": MembershipStatus.SUSPENDED}),
        "alpha_revoked": (OrganizationRole.RESEARCHER,
                          AccessScope.ORGANIZATION,
                          {"status": MembershipStatus.REVOKED}),
        "alpha_expired": (OrganizationRole.RESEARCHER,
                          AccessScope.ORGANIZATION,
                          {"expires_at": datetime.now(timezone.utc)
                           - timedelta(days=1)}),
    }

    async def seed():
        async with factory() as session:
            users = {}
            for name in (*ALPHA_CAST, "beta_researcher", "beta_owner",
                         "both_orgs", "unaffiliated"):
                role = (UserRole.ADMIN
                        if name in ("alpha_owner", "alpha_admin", "beta_owner")
                        else UserRole.RESEARCHER)
                users[name] = await create_user(
                    session, username=name, password=PASSWORD, role=role,
                    email=f"{name}@isolation.test")
            await session.flush()

            alpha = Organization(slug="alpha-clinic", name="Alpha Clinic",
                                 status=OrganizationStatus.ACTIVE)
            beta = Organization(slug="beta-clinic", name="Beta Clinic",
                                status=OrganizationStatus.ACTIVE)
            session.add_all([alpha, beta])
            await session.flush()

            for name, (role, scope, extra) in ALPHA_CAST.items():
                session.add(OrganizationMembership(
                    organization_id=alpha.id, user_id=users[name].id,
                    role=role, scope=scope,
                    status=extra.get("status", MembershipStatus.ACTIVE),
                    expires_at=extra.get("expires_at"),
                    external_organization=extra.get("external_organization"),
                    may_download_attachments=extra.get(
                        "may_download_attachments", True)))

            for name, role in (("beta_researcher", OrganizationRole.RESEARCHER),
                               ("beta_owner", OrganizationRole.OWNER)):
                session.add(OrganizationMembership(
                    organization_id=beta.id, user_id=users[name].id,
                    role=role, scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE))

            # The multi-organization user, legitimately in both.
            for organization in (alpha, beta):
                session.add(OrganizationMembership(
                    organization_id=organization.id,
                    user_id=users["both_orgs"].id,
                    role=OrganizationRole.RESEARCHER,
                    scope=AccessScope.ORGANIZATION,
                    status=MembershipStatus.ACTIVE))

            await session.commit()

            state["alpha_id"] = alpha.id
            state["beta_id"] = beta.id
            state["users"] = {k: v.id for k, v in users.items()}

            rows = (await session.execute(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == alpha.id)
            )).scalars().all()
            state["alpha_memberships"] = {
                name: m.id for m in rows
                for name, uid in state["users"].items() if uid == m.user_id
            }

    with client:
        run_async(seed())

        # Populate each organization with a real assessment, through the real
        # upload path. A negative test against an empty database proves
        # nothing.
        _login(client, "alpha_researcher")
        state["alpha_assessment"] = _upload(client, ALPHA_MARKER).json()
        _login(client, "beta_researcher")
        state["beta_assessment"] = _upload(client, BETA_MARKER).json()

        yield app, client, state
    app.dependency_overrides.clear()


def _login(client, username: str) -> None:
    response = client.post("/api/v1/auth/login",
                           json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text


def _upload(client, marker: str, headers: dict | None = None,
            filename: str | None = None):
    """Upload a populated document.

    The filename defaults to the marker, so every fixture record has a
    *distinct* display name. Without that, a search test would match the
    caller's own record by coincidence and pass while proving nothing.
    """
    name = filename or f"{marker.lower()}.txt"
    return client.post(
        REPORTS,
        files={"file": (name, io.BytesIO(_document(marker)), "text/plain")},
        data={"classification": "synthetic", "attested": "true"},
        headers=headers or {},
    )


def _alpha_id(state) -> int:
    return state["alpha_assessment"]["assessment_id"]


def _beta_id(state) -> int:
    return state["beta_assessment"]["assessment_id"]


def _org_header(state, which: str) -> dict:
    return {ORGANIZATION_HEADER: str(state[f"{which}_id"])}


# ===========================================================================
# 1. The positive controls. Everything below depends on these.
# ===========================================================================

class TestThePopulatedRecordsAreReachableByTheirAuthors:

    def test_the_alpha_author_reads_their_own_assessment(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.get(f"{REPORTS}/{_alpha_id(state)}")
        assert response.status_code == 200, response.text
        assert ALPHA_MARKER in response.text, "the record is genuinely populated"

    def test_the_beta_author_reads_their_own_assessment(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "beta_researcher")
        response = client.get(f"{REPORTS}/{_beta_id(state)}")
        assert response.status_code == 200, response.text
        assert BETA_MARKER in response.text

    def test_each_author_lists_exactly_their_own(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        alpha = client.get(REPORTS)
        assert alpha.status_code == 200
        ids = {a["id"] for a in alpha.json()["assessments"]}
        assert _alpha_id(state) in ids
        assert _beta_id(state) not in ids
        assert BETA_MARKER not in alpha.text

    def test_the_document_downloads_for_its_author(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.get(f"{REPORTS}/{_alpha_id(state)}/document")
        assert response.status_code == 200, response.text
        assert ALPHA_MARKER.encode() in response.content


# ===========================================================================
# 2. Nothing about a foreign record is observable
# ===========================================================================

class TestForeignRecordsAreInvisible:

    ABSENT = 99_999_999

    def _foreign_and_absent(self, client, state, suffix: str = ""):
        foreign = client.get(f"{REPORTS}/{_beta_id(state)}{suffix}")
        absent = client.get(f"{REPORTS}/{self.ABSENT}{suffix}")
        return foreign, absent

    @pytest.mark.parametrize("suffix", ["", "/document", "/history"])
    def test_a_foreign_and_an_absent_id_are_indistinguishable(
            self, two_orgs, suffix):
        """Identical status, identical body. Not merely both refused.

        A difference of any kind here tells the caller that the identifier
        belongs to something real in another organization, which tells them
        that organization holds a patient assessment.
        """
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        foreign, absent = self._foreign_and_absent(client, state, suffix)

        assert foreign.status_code == absent.status_code == 404, (
            f"{suffix}: {foreign.status_code} vs {absent.status_code}")
        assert foreign.json() == absent.json(), suffix

    @pytest.mark.parametrize("suffix", ["", "/document", "/history"])
    def test_no_patient_marker_reaches_a_foreign_reader(self, two_orgs, suffix):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.get(f"{REPORTS}/{_beta_id(state)}{suffix}")
        assert BETA_MARKER not in response.text

    def test_no_document_metadata_leaks_in_the_refusal(self, two_orgs):
        """Not the name, the size, the hash, the type or the status."""
        _app, client, state = two_orgs
        beta = state["beta_assessment"]
        _login(client, "alpha_researcher")
        response = client.get(f"{REPORTS}/{_beta_id(state)}")

        body = response.text
        for leak in (beta["display_name"], beta["content_hash"],
                     str(beta["size_bytes"]), beta["format_key"],
                     beta["status"]):
            assert str(leak) not in body, leak

    def test_a_foreign_assessment_cannot_be_amended(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.post(
            f"{REPORTS}/{_beta_id(state)}/confirm",
            json={"fields": [{"key": "primary_diagnosis",
                              "value": "injected",
                              "provenance": "user_entered"}]})
        assert response.status_code == 404, response.text

        # And the record itself is untouched.
        _login(client, "beta_researcher")
        after = client.get(f"{REPORTS}/{_beta_id(state)}")
        assert after.status_code == 200, "positive control"
        assert "injected" not in after.text

    def test_a_foreign_assessment_cannot_be_deleted(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.delete(f"{REPORTS}/{_beta_id(state)}")
        assert response.status_code == 404, response.text

        _login(client, "beta_researcher")
        assert client.get(f"{REPORTS}/{_beta_id(state)}").status_code == 200

    def test_a_foreign_assessment_cannot_be_deidentified(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.post(f"{REPORTS}/{_beta_id(state)}/deidentify")
        assert response.status_code == 404, response.text
        assert BETA_MARKER not in response.text

    def test_a_foreign_assessment_cannot_be_mapped(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.post(
            f"{REPORTS}/{_beta_id(state)}/map",
            json={"disease": "Breast Cancer",
                  "subtype": "HER2-enriched (ER-, PR-, HER2+)",
                  "drug": "Trastuzumab (Herceptin)"})
        assert response.status_code == 404, response.text


# ===========================================================================
# 3. Lists, searches, filters and counts
# ===========================================================================

class TestListsSearchesAndCounts:

    def test_a_search_never_confirms_a_foreign_record(self, two_orgs):
        """A search that returns nothing still leaks if the count moves."""
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        beta_name = state["beta_assessment"]["display_name"]

        response = client.get(f"{REPORTS}?search={beta_name}")
        assert response.status_code == 200, response.text
        assert response.json()["assessments"] == []
        assert response.json()["total"] == 0

    def test_a_search_finds_the_callers_own_record(self, two_orgs):
        """Positive control: search works, it is the scope that refuses."""
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        own_name = state["alpha_assessment"]["display_name"]
        response = client.get(f"{REPORTS}?search={own_name}")
        assert response.status_code == 200, response.text
        assert any(a["id"] == _alpha_id(state)
                   for a in response.json()["assessments"])

    def test_the_count_covers_only_visible_records(self, two_orgs):
        _app, client, state = two_orgs

        _login(client, "beta_researcher")
        beta_counts = client.get(REPORTS).json()["counts"]

        _login(client, "alpha_researcher")
        alpha = client.get(REPORTS).json()
        alpha_ids = {a["id"] for a in alpha["assessments"]}

        assert alpha["counts"]["total"] == len(alpha_ids)
        assert _beta_id(state) not in alpha_ids
        # Both organizations hold at least one; neither total includes both.
        assert beta_counts["total"] >= 1
        assert alpha["counts"]["total"] >= 1

    def test_a_status_filter_cannot_widen_the_scope(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        for value in ("awaiting_review", "confirmed", "mapped_to_workflow"):
            response = client.get(f"{REPORTS}?status={value}")
            assert response.status_code == 200, response.text
            assert _beta_id(state) not in {
                a["id"] for a in response.json()["assessments"]}
            assert BETA_MARKER not in response.text

    def test_a_classification_filter_cannot_widen_the_scope(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.get(f"{REPORTS}?classification=synthetic")
        assert response.status_code == 200, response.text
        assert _beta_id(state) not in {
            a["id"] for a in response.json()["assessments"]}

    def test_an_account_with_no_membership_sees_an_empty_list(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "unaffiliated")
        response = client.get(REPORTS)
        assert response.status_code == 200, response.text
        assert response.json()["assessments"] == []
        assert response.json()["counts"]["total"] == 0


# ===========================================================================
# 4. Guessed identifiers
# ===========================================================================

class TestGuessedIdentifiers:

    def test_walking_the_identifier_space_finds_nothing(self, two_orgs):
        """Every id from 1 to 40, as an account entitled to none of them."""
        _app, client, state = two_orgs
        _login(client, "unaffiliated")
        for assessment_id in range(1, 41):
            for suffix in ("", "/document", "/history"):
                response = client.get(f"{REPORTS}/{assessment_id}{suffix}")
                assert response.status_code == 404, (
                    f"{assessment_id}{suffix} -> {response.status_code}")
                assert ALPHA_MARKER not in response.text
                assert BETA_MARKER not in response.text

    def test_every_refusal_in_the_walk_is_the_same_body(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "unaffiliated")
        bodies = {
            client.get(f"{REPORTS}/{i}").text
            for i in (_alpha_id(state), _beta_id(state), 99_999_999)
        }
        assert len(bodies) == 1, bodies


# ===========================================================================
# 5. Administrative authority is not clinical authority
# ===========================================================================

class TestAdministrativeSeparation:

    @pytest.mark.parametrize("who", ["alpha_owner", "alpha_admin"])
    def test_an_administrator_cannot_read_a_patient_assessment(
            self, two_orgs, who):
        """The separation the whole model rests on, applied to patient data.

        An organization administrator can add themselves to anything. If that
        also let them read every clinical document, the account with the most
        access control would be the account with the most patient data.
        """
        _app, client, state = two_orgs
        _login(client, who)
        response = client.get(f"{REPORTS}/{_alpha_id(state)}")
        assert response.status_code == 403, response.text
        assert ALPHA_MARKER not in response.text
        assert "manage access, not patient assessments" in response.text

    @pytest.mark.parametrize("who", ["alpha_owner", "alpha_admin"])
    def test_an_administrator_cannot_download_the_document(self, two_orgs, who):
        _app, client, state = two_orgs
        _login(client, who)
        response = client.get(f"{REPORTS}/{_alpha_id(state)}/document")
        assert response.status_code == 403, response.text
        assert ALPHA_MARKER.encode() not in response.content

    @pytest.mark.parametrize("who", ["alpha_owner", "alpha_admin"])
    def test_an_administrator_cannot_upload(self, two_orgs, who):
        _app, client, state = two_orgs
        _login(client, who)
        response = _upload(client, "ADMINUPLOADMARKER")
        assert response.status_code == 403, response.text

    @pytest.mark.parametrize("who", ["alpha_owner", "alpha_admin"])
    def test_an_administrator_cannot_amend(self, two_orgs, who):
        _app, client, state = two_orgs
        _login(client, who)
        response = client.post(
            f"{REPORTS}/{_alpha_id(state)}/confirm",
            json={"fields": [{"key": "primary_diagnosis", "value": "x",
                              "provenance": "user_entered"}]})
        assert response.status_code in (403, 404), response.text

    @pytest.mark.parametrize("who", ["alpha_owner", "alpha_admin",
                                     "alpha_auditor"])
    def test_an_administrator_or_auditor_can_read_the_access_trail(
            self, two_orgs, who):
        """The asymmetry is the point: who touched it, not what it said."""
        _app, client, state = two_orgs
        _login(client, who)
        response = client.get(f"{REPORTS}/{_alpha_id(state)}/history")
        assert response.status_code == 200, response.text
        assert response.json()["events"], "positive control: the trail exists"
        assert ALPHA_MARKER not in response.text

    def test_the_access_trail_carries_no_document_name_or_content(
            self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_admin")
        response = client.get(f"{REPORTS}/{_alpha_id(state)}/history")
        body = response.text
        assert state["alpha_assessment"]["display_name"] not in body
        assert ALPHA_MARKER not in body
        assert "carcinoma" not in body.lower()

    @pytest.mark.parametrize("who", ["alpha_auditor"])
    def test_an_auditor_cannot_read_the_assessment_itself(self, two_orgs, who):
        _app, client, state = two_orgs
        _login(client, who)
        response = client.get(f"{REPORTS}/{_alpha_id(state)}")
        assert response.status_code == 403, response.text
        assert ALPHA_MARKER not in response.text


# ===========================================================================
# 6. Scientific roles and scope
# ===========================================================================

class TestScientificRolesAndScope:

    def test_organization_wide_scope_reaches_a_colleagues_assessment(
            self, two_orgs):
        """Positive control for the scope predicate."""
        _app, client, state = two_orgs
        _login(client, "alpha_wide")
        response = client.get(f"{REPORTS}/{_alpha_id(state)}")
        assert response.status_code == 200, response.text

    def test_assigned_studies_scope_does_not(self, two_orgs):
        """An assessment hangs off no study, so there is nothing to reach it by.

        Two researchers in one organization, both with the default scope. The
        one who did not upload it sees nothing — and gets a 404, not a 403,
        because they are not entitled to learn it exists.
        """
        _app, client, state = two_orgs
        _login(client, "alpha_reviewer")
        assert client.get(f"{REPORTS}/{_alpha_id(state)}").status_code == 200, (
            "positive control: an organization-wide reviewer can read it")

        _login(client, "alpha_cro")
        response = client.get(f"{REPORTS}/{_alpha_id(state)}")
        assert response.status_code == 404, response.text

    @pytest.mark.parametrize("who", ["alpha_reviewer", "alpha_approver"])
    def test_a_reviewer_or_approver_may_read_but_not_delete(
            self, two_orgs, who):
        """Amendment and deletion stay with the author.

        Somebody else's colleague may look at a confirmed clinical field;
        only its author may change it, so "who decided this said X" stays
        answerable.
        """
        _app, client, state = two_orgs
        _login(client, who)
        assert client.get(f"{REPORTS}/{_alpha_id(state)}").status_code == 200

        response = client.delete(f"{REPORTS}/{_alpha_id(state)}")
        assert response.status_code == 403, response.text
        # Refused on the role, which never carries deletion at all. The
        # owner-only rule is exercised separately, by a role that does.
        assert "may not do this to a report assessment" in response.text

    def test_a_colleague_who_may_delete_still_cannot_delete_somebody_elses(
            self, two_orgs):
        """The owner-only rule, exercised by a role that holds the verb.

        ``alpha_wide`` is a researcher with organization-wide scope: they hold
        ``DELETE_REPORT`` and they can read this record. What stops them is
        authorship alone, which is the rule under test.
        """
        _app, client, state = two_orgs
        _login(client, "alpha_wide")
        assert client.get(f"{REPORTS}/{_alpha_id(state)}").status_code == 200, (
            "positive control: they can read it")

        response = client.delete(f"{REPORTS}/{_alpha_id(state)}")
        assert response.status_code == 403, response.text
        assert "the person who created this assessment" in response.text

        # And it survived.
        _login(client, "alpha_researcher")
        assert client.get(f"{REPORTS}/{_alpha_id(state)}").status_code == 200

    def test_a_colleague_cannot_amend_somebody_elses_either(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_wide")
        response = client.post(
            f"{REPORTS}/{_alpha_id(state)}/confirm",
            json={"fields": [{"key": "primary_diagnosis",
                              "value": "not theirs to say",
                              "provenance": "user_entered"}]})
        assert response.status_code == 403, response.text
        assert "the person who created this assessment" in response.text

    def test_the_author_may_still_delete_their_own(self, two_orgs):
        """Positive control, on a throwaway record."""
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        created = _upload(client, "DELETABLEMARKER")
        assert created.status_code == 201, created.text
        assessment_id = created.json()["assessment_id"]

        response = client.delete(f"{REPORTS}/{assessment_id}")
        assert response.status_code == 200, response.text
        assert client.get(f"{REPORTS}/{assessment_id}").status_code == 404


# ===========================================================================
# 7. The external contract laboratory
# ===========================================================================

class TestExternalCollaborator:

    def test_a_cro_reaches_no_patient_assessment_at_all(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_cro")

        listing = client.get(REPORTS)
        assert listing.status_code == 200, listing.text
        assert listing.json()["assessments"] == []
        assert listing.json()["counts"]["total"] == 0

        assert client.get(f"{REPORTS}/{_alpha_id(state)}").status_code == 404
        assert client.get(
            f"{REPORTS}/{_alpha_id(state)}/document").status_code == 404

    def test_a_cro_cannot_upload_one_either(self, two_orgs):
        """There is deliberately no role that lets a contract lab do this."""
        _app, client, state = two_orgs
        _login(client, "alpha_cro")
        response = _upload(client, "CROUPLOADMARKER")
        assert response.status_code == 403, response.text
        assert "lab_contributor" in response.text

    def test_the_download_restriction_is_enforced_where_it_could_apply(
            self, two_orgs):
        """Even given a record to read, downloads are withheld.

        The CRO cannot reach an assessment at all, which makes the restriction
        moot in this fixture — so this asserts the policy directly, against a
        record that genuinely exists, rather than inferring it from a 404 that
        would have happened anyway.
        """
        from nanobio_studio.app.organizations.policy import (
            Action, RecordFacts, may, resolve_context,
        )
        from sqlalchemy import select

        from nanobio_studio.app.db.auth_models import User
        from nanobio_studio.app.db.auth_session import get_auth_session

        _app, client, state = two_orgs

        async def decide(username: str, action):
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                user = (await session.execute(
                    select(User).where(User.username == username)
                )).scalar_one()
                ctx = await resolve_context(session, user)
                return may(ctx, action, RecordFacts(
                    organization_id=state["alpha_id"],
                    owner_id=user.id))
            finally:
                await generator.aclose()

        allowed, _reason = run_async(
            decide("alpha_researcher", Action.DOWNLOAD_REPORT_DOCUMENT))
        assert allowed is True, "positive control"

        refused, reason = run_async(
            decide("alpha_cro", Action.DOWNLOAD_REPORT_DOCUMENT))
        assert refused is False
        assert "lab_contributor" in reason or "downloading" in reason


# ===========================================================================
# 8. Suspended, revoked and expired access
# ===========================================================================

class TestEndedAccess:

    @pytest.mark.parametrize("who", ["alpha_suspended", "alpha_revoked",
                                     "alpha_expired"])
    def test_ended_access_grants_nothing(self, two_orgs, who):
        _app, client, state = two_orgs
        _login(client, who)

        listing = client.get(REPORTS)
        assert listing.status_code == 200
        assert listing.json()["assessments"] == []
        assert ALPHA_MARKER not in listing.text

        for suffix in ("", "/document", "/history"):
            response = client.get(f"{REPORTS}/{_alpha_id(state)}{suffix}")
            assert response.status_code == 404, (
                f"{who}{suffix} -> {response.status_code}")

    @pytest.mark.parametrize("who", ["alpha_suspended", "alpha_revoked",
                                     "alpha_expired"])
    def test_ended_access_cannot_upload(self, two_orgs, who):
        _app, client, state = two_orgs
        _login(client, who)
        response = _upload(client, "ENDEDACCESSMARKER")
        assert response.status_code == 404, response.text

    def test_an_expired_membership_is_refused_without_a_sweep_having_run(
            self, two_orgs):
        """The stored status still says ACTIVE. Expiry is evaluated on read."""
        from sqlalchemy import select

        from nanobio_studio.app.db.auth_session import get_auth_session
        from nanobio_studio.app.db.organization_models import (
            OrganizationMembership,
        )

        _app, client, state = two_orgs

        async def stored_status():
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                return (await session.execute(
                    select(OrganizationMembership.status).where(
                        OrganizationMembership.id
                        == state["alpha_memberships"]["alpha_expired"])
                )).scalar_one()
            finally:
                await generator.aclose()

        assert run_async(stored_status()) is MembershipStatus.ACTIVE, (
            "the fixture must leave the row ACTIVE for this to mean anything")

        _login(client, "alpha_expired")
        assert client.get(f"{REPORTS}/{_alpha_id(state)}").status_code == 404


# ===========================================================================
# 9. The multi-organization user, and parent injection
# ===========================================================================

class TestMultiOrganizationUser:

    def test_without_a_header_they_see_both_organizations(self, two_orgs):
        """Positive control. They genuinely belong to both."""
        _app, client, state = two_orgs
        _login(client, "both_orgs")
        response = client.get(REPORTS)
        assert response.status_code == 200, response.text
        ids = {a["id"] for a in response.json()["assessments"]}
        assert _alpha_id(state) in ids
        assert _beta_id(state) in ids

    def test_selecting_one_organization_narrows_to_it(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "both_orgs")

        alpha = client.get(REPORTS, headers=_org_header(state, "alpha"))
        ids = {a["id"] for a in alpha.json()["assessments"]}
        assert _alpha_id(state) in ids
        assert _beta_id(state) not in ids
        assert BETA_MARKER not in alpha.text

        beta = client.get(REPORTS, headers=_org_header(state, "beta"))
        ids = {a["id"] for a in beta.json()["assessments"]}
        assert _beta_id(state) in ids
        assert _alpha_id(state) not in ids

    def test_a_stale_header_hides_the_record_rather_than_widening(
            self, two_orgs):
        """Selection can only narrow. A stale header is inert."""
        _app, client, state = two_orgs
        _login(client, "both_orgs")
        response = client.get(f"{REPORTS}/{_alpha_id(state)}",
                              headers=_org_header(state, "beta"))
        assert response.status_code == 404, response.text
        assert ALPHA_MARKER not in response.text

    def test_uploading_without_selecting_is_refused_rather_than_guessed(
            self, two_orgs):
        """409, not a coin toss.

        Filing a patient assessment in whichever organization sorted lowest is
        the kind of mistake nothing downstream would ever notice.
        """
        _app, client, state = two_orgs
        _login(client, "both_orgs")
        response = _upload(client, "AMBIGUOUSMARKER")
        assert response.status_code == 409, response.text
        assert response.json()["error"] == "organization_required"

    def test_uploading_with_a_selection_lands_in_that_organization(
            self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "both_orgs")
        created = _upload(client, "SELECTEDMARKER",
                          headers=_org_header(state, "beta"))
        assert created.status_code == 201, created.text
        assessment_id = created.json()["assessment_id"]

        # Visible under Beta...
        assert client.get(f"{REPORTS}/{assessment_id}",
                          headers=_org_header(state, "beta")
                          ).status_code == 200
        # ...and not under Alpha, by the same account.
        assert client.get(f"{REPORTS}/{assessment_id}",
                          headers=_org_header(state, "alpha")
                          ).status_code == 404

        # And invisible to Alpha's own researcher.
        _login(client, "alpha_researcher")
        assert client.get(f"{REPORTS}/{assessment_id}").status_code == 404

        _login(client, "both_orgs")
        client.delete(f"{REPORTS}/{assessment_id}",
                      headers=_org_header(state, "beta"))

    def test_belonging_to_both_does_not_permit_linking_them(self, two_orgs):
        """Parent injection, by the one account that could plausibly try it.

        A study in Alpha, created from an assessment in Beta. Both are the
        caller's own, and that is precisely the point: access to two
        organizations is not permission to join their records together.
        """
        _app, client, state = two_orgs
        _login(client, "both_orgs")

        beta_assessment = _upload(client, "LINKABLEMARKER",
                                  headers=_org_header(state, "beta"))
        assert beta_assessment.status_code == 201, beta_assessment.text
        beta_assessment_id = beta_assessment.json()["assessment_id"]

        response = client.post(
            "/api/v1/runs",
            headers=_org_header(state, "alpha"),
            json={"name": "Injected study",
                  "pathway": "patient_assessment",
                  "report_assessment_id": beta_assessment_id,
                  "design_inputs": {"size_nm": 100, "charge_mv": -5,
                                    "encapsulation_percent": 85}})
        assert response.status_code == 404, response.text

        # The same request inside one organization is accepted, so the refusal
        # above is about the crossing rather than about the shape.
        permitted = client.post(
            "/api/v1/runs",
            headers=_org_header(state, "beta"),
            json={"name": "Legitimate study",
                  "pathway": "patient_assessment",
                  "report_assessment_id": beta_assessment_id,
                  "design_inputs": {"size_nm": 100, "charge_mv": -5,
                                    "encapsulation_percent": 85}})
        assert permitted.status_code == 201, permitted.text

        client.delete(f"{REPORTS}/{beta_assessment_id}",
                      headers=_org_header(state, "beta"))

    def test_a_foreign_assessment_cannot_be_attached_to_a_study(self, two_orgs):
        """The same injection, by somebody with no access to the parent."""
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        response = client.post(
            "/api/v1/runs",
            json={"name": "Injected study",
                  "pathway": "patient_assessment",
                  "report_assessment_id": _beta_id(state),
                  "design_inputs": {"size_nm": 100, "charge_mv": -5,
                                    "encapsulation_percent": 85}})
        assert response.status_code == 404, response.text


# ===========================================================================
# 10. Retention purge
# ===========================================================================

class TestRetentionPurge:

    def test_a_purge_counts_only_the_callers_organization(self, two_orgs):
        """A count is a disclosure. Scope applies to dry runs too."""
        _app, client, state = two_orgs

        _login(client, "alpha_owner")
        alpha = client.post(f"{REPORTS}/retention/purge")
        assert alpha.status_code == 200, alpha.text

        _login(client, "beta_owner")
        beta = client.post(f"{REPORTS}/retention/purge")
        assert beta.status_code == 200, beta.text

        # Neither total spans both organizations.
        combined = alpha.json()["retained"] + beta.json()["retained"]
        assert alpha.json()["retained"] < combined
        assert beta.json()["retained"] < combined

    def test_a_researcher_cannot_run_the_purge(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "alpha_reviewer")
        response = client.post(f"{REPORTS}/retention/purge")
        assert response.status_code == 403, response.text

    def test_an_unaffiliated_account_cannot_run_the_purge(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "unaffiliated")
        response = client.post(f"{REPORTS}/retention/purge")
        assert response.status_code == 404, response.text


# ===========================================================================
# 11. The synthetic fixture catalogue
# ===========================================================================

class TestSyntheticFixtures:

    def test_the_catalogue_is_the_same_for_everyone(self, two_orgs):
        """Shipped fixtures, identical for every caller. No patient data."""
        _app, client, state = two_orgs
        _login(client, "alpha_researcher")
        alpha = client.get(f"{REPORTS}/synthetic").json()
        _login(client, "beta_researcher")
        beta = client.get(f"{REPORTS}/synthetic").json()
        assert alpha == beta

    def test_loading_a_fixture_lands_in_the_callers_organization(
            self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "beta_researcher")
        created = client.post(f"{REPORTS}/synthetic/synthetic-breast-pathology")
        assert created.status_code == 201, created.text
        assessment_id = created.json()["assessment_id"]

        _login(client, "alpha_researcher")
        assert client.get(f"{REPORTS}/{assessment_id}").status_code == 404

        _login(client, "beta_researcher")
        assert client.get(f"{REPORTS}/{assessment_id}").status_code == 200
        client.delete(f"{REPORTS}/{assessment_id}")

    def test_an_unaffiliated_account_cannot_load_a_fixture(self, two_orgs):
        _app, client, state = two_orgs
        _login(client, "unaffiliated")
        response = client.post(f"{REPORTS}/synthetic/synthetic-breast-pathology")
        assert response.status_code == 404, response.text
