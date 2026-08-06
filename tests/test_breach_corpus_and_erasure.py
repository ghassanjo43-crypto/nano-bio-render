"""Two things that were left as selectable-but-undefined, now defined.

Breach corpus
-------------
The embedded common-password list is the deployed default and is recorded as a
stated limitation. The optional local corpus is what closes it. These tests
assert the part that would otherwise fail silently: a corpus that is configured
but wrong must stop startup, because a check somebody has written down as a
control and which does nothing is worse than no check at all.

Erasure
-------
``DELETED`` was reachable in the state enum with no behaviour behind it, which
reads as a deletion to whoever selects it and deletes nothing. Now it is
unreachable through the state route and requires a separate, irreversible act
from ``DELETION_PENDING`` — and what that act keeps matters as much as what it
clears: attribution survives, because an approval whose approver cannot be
named is not an approval.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.core import breach_corpus  # noqa: E402
from nanobio_studio.app.core.breach_corpus import (  # noqa: E402
    MIN_OCCURRENCES, BreachCorpus, CorpusUnusable, corpus_status, load_corpus,
)
from nanobio_studio.app.core.passwords import (  # noqa: E402
    PasswordRejected, check_password_policy,
)
from nanobio_studio.app.db.auth_models import (  # noqa: E402
    AccountState, TokenPurpose, UserRole,
)
from nanobio_studio.app.services import account_service as accounts  # noqa: E402
from nanobio_studio.app.services.auth_service import (  # noqa: E402
    authenticate, create_user,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402


def _sha1(value: str) -> str:
    return hashlib.sha1(value.encode()).hexdigest().upper()  # noqa: S324


def write_corpus(path: Path, entries: dict[str, int]) -> Path:
    """Write a sorted pwned-passwords-format file."""
    lines = sorted(f"{_sha1(word)}:{count}" for word, count in entries.items())
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


#: Passwords that pass every embedded rule — long, no common base, no sequence,
#: no repetition — so a rejection can only come from the corpus.
CORPUS_ONLY = "wharfinger-consequent-lodestar"
ALSO_CORPUS_ONLY = "belfry-antimacassar-quill"


@pytest.fixture
def corpus_file(tmp_path):
    return write_corpus(tmp_path / "pwned.txt", {
        CORPUS_ONLY: 4_312,
        ALSO_CORPUS_ONLY: 2,          # below the occurrence floor
        "another-breached-phrase": 900,
        "yet-another-breached-one": 51,
        "a-fourth-breached-phrase": 77,
    })


@pytest.fixture(autouse=True)
def _no_corpus_by_default():
    """Every test starts with the deployed default, and leaves it that way.

    Without this, a test that loads a corpus would change the password policy
    for every test that runs after it in the same process.
    """
    load_corpus(None)
    yield
    load_corpus(None)


# ===========================================================================
# 1. The corpus, when one is configured
# ===========================================================================

class TestBreachCorpusLookup:

    def test_a_breached_password_is_rejected_even_though_it_passes_every_other_rule(
            self, corpus_file):
        """The gap the corpus exists to close.

        This password is long, unusual, has no common base and no sequence. The
        embedded list has no opinion about it. Only a corpus knows it appeared
        in a breach.
        """
        check_password_policy(CORPUS_ONLY)  # accepted without a corpus

        load_corpus(corpus_file)
        with pytest.raises(PasswordRejected) as caught:
            check_password_policy(CORPUS_ONLY)

        assert caught.value.code == "password_compromised"
        assert "4,312" in caught.value.message, (
            "the count is what makes the message persuasive rather than "
            "sounding like an arbitrary refusal")
        assert "may never have been yours" in caught.value.message, (
            "a user told their password was 'breached' reasonably fears their "
            "account was; the message must say what actually happened")

    def test_a_password_absent_from_the_corpus_is_accepted(self, corpus_file):
        """Positive control: the corpus rejects specific passwords, not all."""
        load_corpus(corpus_file)
        check_password_policy("tumour-margin-assay-fourteen")

    def test_a_single_ancient_sighting_is_not_disqualifying(self, corpus_file):
        """Rejecting singletons pushes users toward shorter, more memorable
        passwords — which is what the corpus is full of."""
        load_corpus(corpus_file)
        check_password_policy(ALSO_CORPUS_ONLY)

    def test_the_binary_search_finds_every_entry(self, corpus_file):
        """A binary search that only finds the middle entry would look correct
        in a one-entry test and pass compromised passwords in production."""
        load_corpus(corpus_file)
        corpus = breach_corpus.active_corpus()

        for word in ("another-breached-phrase", "yet-another-breached-one",
                     "a-fourth-breached-phrase", CORPUS_ONLY):
            found, occurrences = corpus.is_compromised(word)
            assert found, f"{word} is in the corpus and was not found"
            assert occurrences >= MIN_OCCURRENCES

    def test_a_large_corpus_is_searched_without_loading_it(self, tmp_path):
        """Constant memory is the property that makes the full download usable.

        Ten thousand entries is not large, but it is enough that a lookup which
        worked by reading the file into a set would be visibly different from
        one that seeks — and the test asserts the *number of entries found*, so
        a broken search over a big file cannot pass by luck.
        """
        entries = {f"synthetic-breached-entry-{n:05d}": 100
                   for n in range(10_000)}
        corpus_path = write_corpus(tmp_path / "big.txt", entries)
        load_corpus(corpus_path)
        corpus = breach_corpus.active_corpus()

        for n in (0, 1, 4_999, 9_998, 9_999):
            found, _ = corpus.is_compromised(f"synthetic-breached-entry-{n:05d}")
            assert found, f"entry {n} was not found in a 10,000-entry corpus"

        found, _ = corpus.is_compromised("synthetic-breached-entry-99999")
        assert not found


# ===========================================================================
# 2. A configured corpus that is wrong must not be silently inert
# ===========================================================================

class TestAMisconfiguredCorpusIsFatalAtStartup:

    def test_a_missing_corpus_file_stops_startup(self, tmp_path):
        with pytest.raises(CorpusUnusable, match="does not exist"):
            load_corpus(tmp_path / "not-downloaded-yet.txt")

    def test_an_empty_corpus_stops_startup(self, tmp_path):
        empty = tmp_path / "empty.txt"
        empty.write_text("", encoding="ascii")
        with pytest.raises(CorpusUnusable, match="empty"):
            load_corpus(empty)

    def test_an_unsorted_corpus_stops_startup(self, tmp_path):
        """The worst case, and the one a filename cannot warn you about.

        The lookup is a binary search. Over an unsorted file it returns false
        negatives — it does not error, it just quietly passes compromised
        passwords while the configuration says the check is on.
        """
        unsorted = tmp_path / "unsorted.txt"
        unsorted.write_text("\n".join(
            f"{_sha1(f'entry-{n}')}:{100}" for n in range(400)) + "\n",
            encoding="ascii")

        with pytest.raises(CorpusUnusable, match="not sorted"):
            load_corpus(unsorted)

    def test_the_wrong_file_format_stops_startup(self, tmp_path):
        wrong = tmp_path / "wrong.txt"
        wrong.write_text("password,123456\nqwerty,7\n", encoding="ascii")
        with pytest.raises(CorpusUnusable, match="SHA-1"):
            load_corpus(wrong)

    def test_no_corpus_is_a_stated_limitation_not_a_silent_default(self):
        status = corpus_status()
        assert status["configured"] is False
        assert status["active"] is False
        assert "self-registration" in status["limitation"], (
            "the default must record the condition under which it stops being "
            "acceptable, not merely that it is the default")

    def test_the_status_never_reveals_the_host_filesystem_layout(
            self, corpus_file):
        load_corpus(corpus_file)
        status = corpus_status()

        assert status["active"] is True
        assert str(corpus_file.parent) not in str(status), (
            "the diagnostics must not publish the production directory layout")


# ===========================================================================
# 3. Erasure
# ===========================================================================

@pytest.fixture(scope="module")
def isolated(tmp_path_factory):
    app, client, _factory = make_isolated_auth_client(
        tmp_path_factory.mktemp("erasure"))
    with client:
        yield app, client
    app.dependency_overrides.clear()


def _session(app):
    from nanobio_studio.app.db.auth_session import get_auth_session
    return app.dependency_overrides[get_auth_session]()


async def _with_session(app, work):
    generator = _session(app)
    session = await generator.__anext__()
    try:
        result = await work(session)
        await session.commit()
        return result
    finally:
        await generator.aclose()


class TestErasureIsDefinedRatherThanSelectable:

    def test_deleted_cannot_be_reached_through_the_state_route(self, isolated):
        """The defect: a state you can select that does nothing.

        Setting it looks like a deletion to the administrator who chose it, and
        erases nothing at all.
        """
        app, _client = isolated

        async def work(session):
            user = await create_user(session, username="erase_state_probe",
                                     password="a-perfectly-good-passphrase",
                                     role=UserRole.RESEARCHER)
            await session.flush()
            with pytest.raises(accounts.AccountError) as caught:
                await accounts.set_account_state(
                    session, user=user, state=AccountState.DELETED,
                    actor_id=None)
            assert caught.value.code == "state_not_settable"
            assert "irreversible" in caught.value.message
            return True

        assert run_async(_with_session(app, work))

    def test_erasure_requires_the_pending_step_first(self, isolated):
        """Two steps are what make an accidental erasure recoverable."""
        app, _client = isolated

        async def work(session):
            user = await create_user(session, username="erase_two_step",
                                     password="a-perfectly-good-passphrase",
                                     role=UserRole.RESEARCHER)
            await session.flush()
            with pytest.raises(accounts.AccountError) as caught:
                await accounts.erase_account(session, user=user, actor_id=None)
            assert caught.value.code == "not_pending_deletion"
            return True

        assert run_async(_with_session(app, work))

    def test_erasure_clears_identity_and_keeps_attribution(self, isolated):
        """The whole point, in one test.

        The person goes. The record stays, with a stable pseudonym, because
        every experiment and approval in the system references this row by id.
        """
        app, _client = isolated

        async def work(session):
            user = await create_user(
                session, username="erase_me", password="a-good-long-passphrase",
                role=UserRole.RESEARCHER, email="real.person@example.test",
                full_name="A Real Person")
            await session.flush()
            user_id = user.id

            await accounts.set_account_state(
                session, user=user, state=AccountState.DELETION_PENDING,
                actor_id=None, reason="left the institute")
            result = await accounts.erase_account(
                session, user=user, actor_id=None, reason="left the institute")
            return user_id, result, user

        user_id, result, user = run_async(_with_session(app, work))

        assert result["erased"] is True
        assert set(result["fields_cleared"]) == {"email", "full_name"}

        # Identity gone.
        assert user.email is None
        assert user.full_name is None
        assert "real.person" not in (user.username or "")
        assert "A Real Person" not in str(user.username)

        # Record kept, and identifiable as one consistent account.
        assert user.id == user_id
        assert user.username == f"erased-account-{user_id}"
        assert user.state is AccountState.DELETED
        assert "attribution" in result["notice"]

    def test_an_erased_account_cannot_sign_in_with_the_old_password(
            self, isolated):
        """The sentinel hash must not be a hash of anything."""
        app, _client = isolated

        async def work(session):
            user = await create_user(session, username="erase_then_login",
                                     password="the-old-real-passphrase",
                                     role=UserRole.RESEARCHER)
            await session.flush()
            await accounts.set_account_state(
                session, user=user, state=AccountState.DELETION_PENDING,
                actor_id=None)
            await accounts.erase_account(session, user=user, actor_id=None)
            return user.id

        run_async(_with_session(app, work))

        async def attempt(session):
            from nanobio_studio.app.services.auth_service import AuthError
            for username in ("erase_then_login", "erased-account-1"):
                with pytest.raises(AuthError):
                    await authenticate(session, username=username,
                                       password="the-old-real-passphrase",
                                       ip_address="10.0.0.1",
                                       user_agent="tests")
            return True

        assert run_async(_with_session(app, attempt))

    def test_erasure_ends_every_session_and_every_live_link(self, isolated):
        app, _client = isolated

        async def work(session):
            user = await create_user(session, username="erase_with_sessions",
                                     password="a-good-long-passphrase",
                                     role=UserRole.RESEARCHER)
            await session.flush()

            await authenticate(session, username="erase_with_sessions",
                               password="a-good-long-passphrase",
                               ip_address="10.0.0.1", user_agent="tests")
            await authenticate(session, username="erase_with_sessions",
                               password="a-good-long-passphrase",
                               ip_address="10.0.0.2", user_agent="tests")
            await accounts.issue_password_reset(session, user=user,
                                                actor_id=None)
            await session.flush()

            marked = await accounts.set_account_state(
                session, user=user, state=AccountState.DELETION_PENDING,
                actor_id=None)
            result = await accounts.erase_account(session, user=user,
                                                  actor_id=None)
            remaining = await accounts.list_sessions(session, user_id=user.id)
            status = await accounts.token_status(
                session, user_id=user.id, purpose=TokenPurpose.PASSWORD_RESET)
            return marked, result, remaining, status

        marked, result, remaining, status = run_async(_with_session(app, work))

        # Marking for deletion already ends them — erasure finds none left,
        # which is the correct total rather than a second round of revocation.
        assert marked == 2, f"marking for deletion ended {marked} sessions"
        assert result["erased"] is True
        assert remaining == [], (
            f"sessions survived erasure: {remaining}")
        assert status["state"] in {"withdrawn", "none"}, (
            f"a live reset link survived erasure: {status}")

    def test_erasing_twice_is_not_an_error_and_not_a_second_erasure(
            self, isolated):
        app, _client = isolated

        async def work(session):
            user = await create_user(session, username="erase_twice",
                                     password="a-good-long-passphrase",
                                     role=UserRole.RESEARCHER)
            await session.flush()
            await accounts.set_account_state(
                session, user=user, state=AccountState.DELETION_PENDING,
                actor_id=None)
            await accounts.erase_account(session, user=user, actor_id=None)
            return await accounts.erase_account(session, user=user,
                                                actor_id=None)

        again = run_async(_with_session(app, work))
        assert again["erased"] is False
        assert "already" in again["reason"]

    def test_the_audit_row_names_the_fields_but_not_their_values(self, isolated):
        """The audit trail must not become the copy of the data the erasure was
        meant to remove."""
        from sqlalchemy import select

        from nanobio_studio.app.db.auth_models import AuthAuditLog

        app, _client = isolated

        async def work(session):
            user = await create_user(
                session, username="erase_audit",
                password="a-good-long-passphrase", role=UserRole.RESEARCHER,
                email="audit.person@example.test", full_name="Audit Person")
            await session.flush()
            await accounts.set_account_state(
                session, user=user, state=AccountState.DELETION_PENDING,
                actor_id=None)
            await accounts.erase_account(session, user=user, actor_id=None)
            await session.flush()

            rows = (await session.execute(
                select(AuthAuditLog).where(AuthAuditLog.user_id == user.id)
            )).scalars().all()
            return [r.detail or "" for r in rows]

        details = run_async(_with_session(app, work))
        joined = " ".join(details)

        assert "erased" in joined
        assert "email" in joined, "the audit should record WHICH fields went"
        assert "audit.person@example.test" not in joined
        assert "Audit Person" not in joined
