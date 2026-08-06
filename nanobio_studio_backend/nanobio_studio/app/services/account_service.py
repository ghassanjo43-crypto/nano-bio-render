"""Account lifecycle: activation, password reset, account state, sessions.

The one rule this module exists to make structural
--------------------------------------------------
**Nobody but the account holder ever knows their password.** An administrator
creates an account and causes a *link* to exist; the person behind the address
chooses the password. There is deliberately no function here that takes an
administrator and a password for somebody else, so "show me their password" and
"set it to something I can tell them" are not features that were left out —
they are shapes the code cannot express.

That is what fixes the reported usability problem. An administrator previously
created a subscriber and then had nowhere to go, because the only way to make
the account usable was to know its password. Now they issue an activation link,
and the interface tells them whether it was delivered, recorded for them to
pass on, expired, withdrawn or accepted.

Tokens
------
Random from ``secrets``, stored as ``sha256``, single-use, time-limited, and
**bound to a purpose**. A reset token cannot activate and an activation token
cannot reset: the two have different preconditions, and a token that satisfied
both would let one workflow be driven through the other's checks.

Redemption claims the row with a conditional ``UPDATE`` on ``revision``, so two
simultaneous redemptions of one link set one password and refuse the other
rather than racing.

Sessions after a password change
--------------------------------
Documented policy, implemented here: **every other session ends, and the
session that performed the change survives.** Ending that one too would sign
the user out of the act they just completed, and a user who is bounced to the
login screen after changing their password reasonably concludes it did not
work. Every other session is ended because a password change is what somebody
does when they think a session is not theirs.

A reset — where the password was changed by somebody holding a link rather than
by an authenticated session — ends **all** sessions, because there is no
session that can be trusted as the legitimate one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.core.config import settings
from nanobio_studio.app.core.passwords import (
    PasswordRejected, algorithm_of, check_password_policy,
    generate_account_token, hash_account_token, hash_password,
)
from nanobio_studio.app.db.auth_models import (
    AccountState, AccountToken, AuthAuditLog, AuthEvent, TokenPurpose,
    TokenState, User, UserSession, utcnow,
)

__all__ = [
    "AccountError", "TokenRejected",
    "issue_activation", "issue_password_reset", "redeem_token",
    "revoke_token", "list_tokens", "token_status",
    "change_password", "set_account_state", "erase_account",
    "list_sessions", "revoke_session", "revoke_all_sessions",
    "ACTIVATION_TTL", "RESET_TTL",
]

#: How long an activation link stays redeemable. Longer than a reset: a new
#: colleague may not be at their desk today, and the account grants nothing
#: until it is used.
ACTIVATION_TTL = timedelta(days=7)

#: Short, because a reset link is requested by somebody who is at their desk
#: right now, and because it can change an existing password.
RESET_TTL = timedelta(hours=1)


class AccountError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TokenRejected(AccountError):
    """Every bad token, for every reason, with one message.

    Unknown, expired, revoked, already redeemed, wrong purpose and wrong
    account all raise this with identical text. Distinguishing them would tell
    somebody holding a link that it was once real — which tells them the
    account exists.
    """

    def __init__(self) -> None:
        super().__init__(
            "invalid_token",
            "This link cannot be used. It may have expired, already been used, "
            "or been replaced by a newer one. Ask for a new link.")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def _audit(session: AsyncSession, event: AuthEvent, *,
                 user_id: int | None = None, actor_id: int | None = None,
                 ip_address: str | None = None, detail: str | None = None
                 ) -> None:
    """Append one security event.

    ``detail`` carries codes, counts and token *prefixes* only. Never a
    password, never a whole token, never a session identifier — the trail is
    read by more people, and kept longer, than any of those should be.
    """
    session.add(AuthAuditLog(
        event=event, user_id=user_id, ip_address=ip_address,
        detail=(detail[:500] if detail else None)))


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IssuedToken:
    token: AccountToken
    #: Returned exactly once, to the caller who issued it. Unrecoverable after.
    raw: str
    link: str


async def _issue(session: AsyncSession, *, user: User, purpose: TokenPurpose,
                 ttl: timedelta, actor_id: int | None,
                 ip_address: str | None = None) -> IssuedToken:
    """Create a token, retiring any live one for the same purpose.

    Retiring first is what makes re-issue safe: the previous link stops working
    the instant a new one exists. Leaving it alive would mean a link recovered
    from an old mailbox stayed valid for as long as anybody kept re-issuing.
    """
    now = utcnow()

    live = (await session.execute(
        select(AccountToken).where(
            AccountToken.user_id == user.id,
            AccountToken.purpose == purpose,
            AccountToken.state == TokenState.PENDING)
    )).scalars().all()
    for previous in live:
        previous.state = TokenState.REVOKED
        previous.ended_at = now
        previous.end_reason = "superseded by a newer link"
    await session.flush()

    raw = generate_account_token()
    token = AccountToken(
        user_id=user.id, purpose=purpose, state=TokenState.PENDING,
        token_hash=hash_account_token(raw), token_prefix=raw[:8],
        expires_at=now + ttl, created_by=actor_id)
    session.add(token)
    await session.flush()

    link = _build_link(purpose, raw)
    delivery = _deliver(user=user, purpose=purpose, link=link,
                        expires_at=token.expires_at)
    token.delivery_provider = delivery.provider
    token.delivery_status = delivery.status
    token.delivery_detail = delivery.detail

    await _audit(
        session,
        AuthEvent.ACTIVATION_ISSUED if purpose is TokenPurpose.ACTIVATION
        else AuthEvent.PASSWORD_RESET_REQUESTED,
        user_id=user.id, actor_id=actor_id, ip_address=ip_address,
        # The prefix, not the token. Enough to match an audit line to a link an
        # administrator is holding; far too short to redeem.
        detail=f"purpose={purpose.value} link={token.token_prefix}… "
               f"delivery={delivery.status} superseded={len(live)}")
    return IssuedToken(token=token, raw=raw, link=link)


def _build_link(purpose: TokenPurpose, raw: str) -> str:
    """Compose the link. Takes no destination from any caller.

    Same rule as an organization invitation: there is no parameter anywhere
    through which a request could aim this somewhere else. An account-setup
    link is unusually good phishing bait — it arrives unexpectedly, it is meant
    to be clicked, and it is meant to lead somewhere the recipient has not been.
    """
    from urllib.parse import quote

    base = ("/account/activate" if purpose is TokenPurpose.ACTIVATION
            else "/account/reset")
    configured = (settings.account_link_base or "").strip()
    if configured:
        from nanobio_studio.app.services.invitation_delivery import _is_safe_base
        if _is_safe_base(configured):
            base = configured.rstrip("/") + (
                "/activate" if purpose is TokenPurpose.ACTIVATION else "/reset")
    return f"{base}?token={quote(raw, safe='')}"


@dataclass(frozen=True)
class _Delivery:
    provider: str
    status: str
    detail: str


def _deliver(*, user: User, purpose: TokenPurpose, link: str,
             expires_at: datetime) -> _Delivery:
    """Hand the link to the configured provider. Reuses the invitation one.

    One delivery mechanism for both, because "did this reach them" is the same
    question whichever workflow asked it, and two providers would drift.
    """
    from nanobio_studio.app.services import invitation_delivery

    provider = invitation_delivery.get_provider()
    result = provider.send(invitation_delivery.InvitationMessage(
        recipient_email=(user.email or ""),
        organization_name="your NanoBio Studio account",
        role=("account activation" if purpose is TokenPurpose.ACTIVATION
              else "password reset"),
        invited_by="an administrator",
        expires_at=expires_at,
        link=link,
    ))
    return _Delivery(provider=result.provider, status=result.status,
                     detail=result.detail)


async def issue_activation(session: AsyncSession, *, user: User,
                           actor_id: int | None = None,
                           ip_address: str | None = None) -> IssuedToken:
    """A first-time password-setup link for an account with no usable password."""
    if user.state in {AccountState.DELETED, AccountState.DELETION_PENDING}:
        raise AccountError(
            "account_not_available",
            "That account has been removed and cannot be activated.")
    return await _issue(session, user=user, purpose=TokenPurpose.ACTIVATION,
                        ttl=ACTIVATION_TTL, actor_id=actor_id,
                        ip_address=ip_address)


async def issue_password_reset(session: AsyncSession, *, user: User,
                               actor_id: int | None = None,
                               ip_address: str | None = None) -> IssuedToken:
    """A reset link. Issued for an active or suspended account.

    A suspended account may hold one: the suspension is what stops them signing
    in, and making them ask twice — once to be unsuspended, once to reset —
    helps nobody.
    """
    if user.state in {AccountState.DELETED, AccountState.DELETION_PENDING}:
        raise AccountError(
            "account_not_available",
            "That account has been removed.")
    return await _issue(session, user=user, purpose=TokenPurpose.PASSWORD_RESET,
                        ttl=RESET_TTL, actor_id=actor_id,
                        ip_address=ip_address)


async def token_status(session: AsyncSession, *, user_id: int,
                       purpose: TokenPurpose) -> dict:
    """What an administrator needs to see, in the terms they asked in.

    Five outcomes, named: delivered, recorded for manual delivery, expired,
    withdrawn, accepted. "No token" is a sixth and is stated rather than
    rendered as an empty space.
    """
    row = (await session.execute(
        select(AccountToken)
        .where(AccountToken.user_id == user_id,
               AccountToken.purpose == purpose)
        .order_by(AccountToken.id.desc()).limit(1)
    )).scalars().first()

    if row is None:
        return {"state": "none",
                "summary": "No link has been issued for this account."}

    expires = _aware(row.expires_at)
    lapsed = row.state is TokenState.PENDING and expires and utcnow() >= expires

    if row.state is TokenState.REDEEMED:
        summary = "Accepted. The account holder has set their password."
        state = "accepted"
    elif row.state is TokenState.REVOKED:
        summary = "Withdrawn. That link no longer works."
        state = "withdrawn"
    elif lapsed or row.state is TokenState.EXPIRED:
        summary = "Expired without being used. Issue a new one."
        state = "expired"
    elif row.delivery_status in {"sent", "logged"}:
        summary = "Delivered. Waiting for the account holder to use it."
        state = "delivered"
    else:
        summary = ("Recorded for manual delivery. Nothing was emailed — pass "
                   "the link on yourself. It was shown once when it was "
                   "created and cannot be shown again.")
        state = "recorded"

    return {
        "state": state, "summary": summary, "purpose": purpose.value,
        "link_prefix": row.token_prefix, "expires_at": row.expires_at,
        "created_at": row.created_at, "redeemed_at": row.redeemed_at,
        "delivery_status": row.delivery_status,
        "delivery_provider": row.delivery_provider,
    }


async def revoke_token(session: AsyncSession, *, user_id: int,
                       purpose: TokenPurpose, actor_id: int | None = None,
                       reason: str | None = None) -> int:
    """Withdraw every live link of one purpose. Returns how many."""
    now = utcnow()
    rows = (await session.execute(
        select(AccountToken).where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.state == TokenState.PENDING)
    )).scalars().all()
    for row in rows:
        row.state = TokenState.REVOKED
        row.ended_at = now
        row.end_reason = reason or "withdrawn by an administrator"
    if rows:
        await _audit(session, AuthEvent.ACTIVATION_REVOKED, user_id=user_id,
                     actor_id=actor_id, detail=f"withdrew {len(rows)} link(s)")
    await session.flush()
    return len(rows)


async def redeem_token(session: AsyncSession, *, raw_token: str,
                       new_password: str, confirmation: str | None,
                       purpose: TokenPurpose,
                       ip_address: str | None = None) -> User:
    """Set a password using a link. The only way a password is ever set here.

    Every failure raises the same :class:`TokenRejected`. The policy check runs
    *before* the token is claimed, so a rejected password does not consume the
    link — otherwise a user who typed something too short would have to ask for
    a new one, and would learn to pick whatever the form accepted first.
    """
    if not raw_token or len(raw_token) > 512:
        raise TokenRejected()

    row = (await session.execute(
        select(AccountToken).where(
            AccountToken.token_hash == hash_account_token(raw_token))
    )).scalars().first()

    now = utcnow()
    expires = _aware(row.expires_at) if row else None
    if (row is None
            or row.purpose is not purpose
            or row.state is not TokenState.PENDING
            or (expires is not None and now >= expires)):
        raise TokenRejected()

    user = await session.get(User, row.user_id)
    if user is None or user.state in {AccountState.DELETED,
                                      AccountState.DELETION_PENDING}:
        raise TokenRejected()

    # Policy first, so a refused password does not spend the link.
    check_password_policy(new_password, confirmation=confirmation,
                          username=user.username, email=user.email)

    # Claim the row. Two simultaneous redemptions reach here together; exactly
    # one wins, and the other is refused rather than both setting a password.
    claimed = await session.execute(
        update(AccountToken)
        .where(AccountToken.id == row.id,
               AccountToken.revision == row.revision,
               AccountToken.state == TokenState.PENDING)
        .values(revision=row.revision + 1, state=TokenState.REDEEMED,
                redeemed_at=now, ended_at=now)
    )
    if claimed.rowcount == 0:
        raise TokenRejected()

    user.password_hash = hash_password(new_password)
    user.password_algorithm = algorithm_of(user.password_hash)
    user.password_changed_at = now
    user.must_set_password = False
    if user.state is AccountState.PENDING_ACTIVATION:
        user.state = AccountState.ACTIVE
        user.state_changed_at = now
        user.is_active = True

    # Every session ends. The password was changed by whoever held the link,
    # and no existing session can be shown to belong to that person.
    ended = await _end_sessions(session, user_id=user.id, keep_token_hash=None,
                                reason="password_reset")

    await _audit(
        session,
        AuthEvent.ACTIVATION_COMPLETED if purpose is TokenPurpose.ACTIVATION
        else AuthEvent.PASSWORD_RESET_COMPLETED,
        user_id=user.id, ip_address=ip_address,
        detail=f"link={row.token_prefix}… sessions_ended={ended}")
    await session.flush()
    return user


# ---------------------------------------------------------------------------
# Password change by an authenticated user
# ---------------------------------------------------------------------------

async def change_password(session: AsyncSession, *, user: User,
                          current_password: str, new_password: str,
                          confirmation: str | None,
                          current_session_token_hash: str | None = None,
                          ip_address: str | None = None) -> int:
    """Change a password from inside a session. Returns sessions ended.

    The current password is required even though the caller is authenticated:
    it is what stops an unattended desk, or a stolen session, from becoming a
    permanent account takeover.
    """
    from nanobio_studio.app.core.passwords import verify_password

    if not verify_password(current_password, user.password_hash):
        # Deliberately not a generic message: the caller is already
        # authenticated as this account, so telling them the current password
        # is wrong reveals nothing they do not have.
        raise AccountError("current_password_incorrect",
                           "The current password is not correct.")

    check_password_policy(new_password, confirmation=confirmation,
                          username=user.username, email=user.email)

    now = utcnow()
    user.password_hash = hash_password(new_password)
    user.password_algorithm = algorithm_of(user.password_hash)
    user.password_changed_at = now
    user.must_set_password = False

    # Documented policy: every OTHER session ends; this one survives. Ending
    # this one too would sign the user out of the act they just completed, and
    # being bounced to the login screen reads as "it did not work".
    ended = await _end_sessions(session, user_id=user.id,
                                keep_token_hash=current_session_token_hash,
                                reason="password_changed")

    await _audit(session, AuthEvent.PASSWORD_CHANGED, user_id=user.id,
                 ip_address=ip_address,
                 detail=f"other_sessions_ended={ended}")
    await session.flush()
    return ended


# ---------------------------------------------------------------------------
# Account state
# ---------------------------------------------------------------------------

#: Transitions an administrator may make directly.
_SETTABLE_STATES = frozenset({
    AccountState.ACTIVE, AccountState.SUSPENDED, AccountState.DISABLED,
    AccountState.DELETION_PENDING,
})


async def set_account_state(session: AsyncSession, *, user: User,
                            state: AccountState, actor_id: int | None,
                            reason: str | None = None,
                            ip_address: str | None = None) -> int:
    """Change an account's state. Returns sessions ended.

    ``DELETED`` is not settable here. Clearing identifying fields is a separate,
    deliberate act with its own function, because it is the one thing on this
    list that cannot be undone.
    """
    if state not in _SETTABLE_STATES:
        raise AccountError(
            "state_not_settable",
            f"{state.value!r} cannot be set directly. Suspend or disable the "
            f"account; erasure is a separate, irreversible act.")
    if user.state is AccountState.DELETED:
        raise AccountError("account_deleted",
                           "That account has been erased and cannot be changed.")

    now = utcnow()
    previous = user.state
    user.state = state
    user.state_changed_at = now
    user.state_reason = reason
    # Kept in step, so every existing `is_active` check keeps working.
    user.is_active = state is AccountState.ACTIVE

    ended = 0
    if state is not AccountState.ACTIVE:
        # The next request must be refused, not the one after the cache
        # expires. Ending the sessions here is what makes that immediate.
        ended = await _end_sessions(session, user_id=user.id,
                                    keep_token_hash=None,
                                    reason=f"account_{state.value}")

    await _audit(
        session,
        AuthEvent.ACCOUNT_RESTORED if state is AccountState.ACTIVE
        else AuthEvent.ACCOUNT_SUSPENDED,
        user_id=user.id, actor_id=actor_id, ip_address=ip_address,
        detail=f"{previous.value} -> {state.value} sessions_ended={ended}"
               + (f" reason={reason}" if reason else ""))
    await session.flush()
    return ended


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

async def _end_sessions(session: AsyncSession, *, user_id: int,
                        keep_token_hash: str | None, reason: str) -> int:
    """Delete sessions. Returns how many ended.

    Deleted rather than flagged: a revoked row that still resolves because
    somebody forgot a predicate is exactly the failure this is preventing, and
    a row that is absent cannot be resolved by anything.
    """
    query = select(UserSession).where(UserSession.user_id == user_id)
    if keep_token_hash:
        query = query.where(UserSession.token_hash != keep_token_hash)
    rows = (await session.execute(query)).scalars().all()
    for row in rows:
        await session.delete(row)
    await session.flush()
    return len(rows)


async def list_sessions(session: AsyncSession, *, user_id: int
                        ) -> list[UserSession]:
    """A person's own open sessions, newest first."""
    return list((await session.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .order_by(UserSession.last_activity_at.desc())
    )).scalars().all())


async def revoke_session(session: AsyncSession, *, user_id: int, handle: str,
                         ip_address: str | None = None) -> bool:
    """End one of a person's own sessions, named by its non-secret handle.

    A handle rather than the token: a screen that could name a session by its
    token would be a screen that had the token, and the whole point of storing
    only a digest is that nothing does.
    """
    row = (await session.execute(
        select(UserSession).where(UserSession.user_id == user_id,
                                  UserSession.handle == handle)
    )).scalars().first()
    if row is None:
        return False
    await session.delete(row)
    await _audit(session, AuthEvent.SESSION_REVOKED, user_id=user_id,
                 ip_address=ip_address, detail=f"session={handle}")
    await session.flush()
    return True


async def revoke_all_sessions(session: AsyncSession, *, user_id: int,
                              keep_token_hash: str | None = None,
                              ip_address: str | None = None,
                              actor_id: int | None = None) -> int:
    """Sign out everywhere. Optionally keeping the caller's own session."""
    ended = await _end_sessions(session, user_id=user_id,
                                keep_token_hash=keep_token_hash,
                                reason="signed_out_everywhere")
    await _audit(session, AuthEvent.LOGOUT_ALL, user_id=user_id,
                 actor_id=actor_id, ip_address=ip_address,
                 detail=f"sessions_ended={ended}")
    await session.flush()
    return ended


# ---------------------------------------------------------------------------
# Erasure
# ---------------------------------------------------------------------------

#: Fields cleared when an account is erased. Everything here identifies a
#: person; nothing here identifies a *record*.
_IDENTIFYING_FIELDS = ("email", "full_name")


async def erase_account(session: AsyncSession, *, user: User,
                        actor_id: int | None, reason: str | None = None,
                        ip_address: str | None = None) -> dict:
    """Clear the identifying fields, keep the row, keep the attribution.

    Why the row survives
    --------------------
    Every experiment, review, approval and audit line references this user by
    id. Deleting the row would either cascade that history away or leave it
    pointing at nothing — and an approval whose approver cannot be named is not
    an approval. A regulated record that loses its author stops being a record.

    So erasure clears what identifies the *person* — email, full name — and
    replaces the username with a stable, non-identifying pseudonym derived from
    the id. Attribution survives as "erased account #41", which is exactly what
    an auditor needs: not who they were, but that it was consistently one
    account and which one.

    **This is irreversible, and it is the only thing in this module that is.**
    That is why it is a separate function from ``set_account_state``, which
    refuses ``DELETED``, and why it requires the account to be in
    ``DELETION_PENDING`` first — the two-step is what makes an accidental
    erasure a recoverable mistake rather than a permanent one.
    """
    if user.state is AccountState.DELETED:
        return {"erased": False, "reason": "already erased",
                "user_id": user.id}
    if user.state is not AccountState.DELETION_PENDING:
        raise AccountError(
            "not_pending_deletion",
            "An account must be marked for deletion before it can be erased. "
            "That two-step exists because erasure is the one act here that "
            "cannot be undone.")

    now = utcnow()
    pseudonym = f"erased-account-{user.id}"

    cleared = []
    for field in _IDENTIFYING_FIELDS:
        if getattr(user, field, None):
            cleared.append(field)
        setattr(user, field, None)

    user.username = pseudonym
    # Not a valid hash for any algorithm, so nothing verifies against it and
    # there is no plaintext that produces it.
    user.password_hash = "!erased"
    user.password_algorithm = None
    user.must_set_password = False
    user.state = AccountState.DELETED
    user.state_changed_at = now
    user.state_reason = reason
    user.is_active = False

    # Every session and every live token goes.
    ended = await _end_sessions(session, user_id=user.id, keep_token_hash=None,
                                reason="account_erased")
    for purpose in TokenPurpose:
        await revoke_token(session, user_id=user.id, purpose=purpose,
                           actor_id=actor_id, reason="account erased")

    await _audit(
        session, AuthEvent.ACCOUNT_STATE_CHANGED, user_id=user.id,
        actor_id=actor_id, ip_address=ip_address,
        # Names the fields cleared, never their values — the audit row must not
        # become the copy of the data the erasure was meant to remove.
        detail=(f"erased; cleared {','.join(cleared) or 'nothing'}; "
                f"sessions_ended={ended}; attribution preserved as {pseudonym}"))
    await session.flush()

    return {
        "erased": True,
        "user_id": user.id,
        "pseudonym": pseudonym,
        "fields_cleared": cleared,
        "sessions_ended": ended,
        "notice": (
            "Identifying information has been removed. The account row and "
            "every experiment, review and approval it performed are kept: "
            "scientific attribution and the audit trail are regulated records "
            "and do not disappear with the person's name."),
    }
