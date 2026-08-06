"""Account activation, password reset, password change and session management.

What an administrator can and cannot do here
--------------------------------------------
They can create an account, issue an activation link, re-issue it, withdraw it,
start a password reset, and suspend or restore access. They **cannot** choose,
view or recover anybody's password — there is no route that would let them, and
no field in any request or response that carries one.

That is the fix for the reported problem. An administrator used to create a
subscriber and then have nowhere to go, because the only way to make the
account usable was to know its password. Now they issue a link, and the
interface tells them whether it was delivered, recorded for them to hand over,
expired, withdrawn or accepted.

Which of these need a session
-----------------------------
``/activate`` and ``/reset`` are **unauthenticated** by necessity: the caller
has no password yet, or has forgotten it. They are protected by the token, and
by the token alone — which is why the token is 256 random bits, single-use,
short-lived and bound to its purpose.

They are listed in ``EXEMPT_ROUTES`` for the structural guard with that written
reason, exactly as login is.

Enumeration
-----------
``/forgot`` always answers the same way. Telling a caller "no account with that
address" turns the endpoint into a directory of who has an account here — and
whoever asked was, by construction, not signed in.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nanobio_studio.app.api.deps_auth import client_ip, get_current_user
from nanobio_studio.app.api.deps_organization import (
    get_access_context as _access_context,
)
from nanobio_studio.app.core.passwords import (
    MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, PasswordRejected,
)
from nanobio_studio.app.core.security import hash_session_token
from nanobio_studio.app.db.auth_models import (
    AccountState, AccountToken, AuthAuditLog, TokenPurpose, User,
)
from nanobio_studio.app.db.auth_session import get_auth_session
from nanobio_studio.app.services import account_service as accounts
from nanobio_studio.app.services.auth_service import SESSION_COOKIE_NAME

router = APIRouter(prefix="/api/v1/account", tags=["account"])


def _error(code: str, message: str, http: int) -> JSONResponse:
    return JSONResponse(status_code=http, content={
        "error": code, "message": message, "detail": None,
        "data_available": False})


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class SetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=8, max_length=512)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    #: Required, so a typo becomes a refusal rather than a password nobody
    #: knows. There is deliberately no way to skip it.
    confirm_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Username or email. Whichever the caller has to hand.
    identifier: str = Field(min_length=1, max_length=320)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    confirm_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class RevokeSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The non-secret handle shown on the sessions screen, never a token.
    handle: str = Field(min_length=4, max_length=12)


# ---------------------------------------------------------------------------
# Policy, so the interface can state the rules rather than guess them
# ---------------------------------------------------------------------------

@router.get("/password-policy", summary="What a password must satisfy")
async def password_policy() -> dict:
    """Deliberately unauthenticated.

    It used to require a session, which put it out of reach of the two screens
    that need it most: activation and reset are used by people who have no
    session — that is *why* they are there. A new colleague setting their first
    password would have been shown a form with no stated rules, guessed, been
    refused, and guessed again.

    Nothing here is a secret. These rules are already visible in every
    rejection message, and stating them up front is the difference between one
    attempt and four. Knowing the minimum length tells an attacker only that
    passwords shorter than it do not exist, which shortens their search by
    nothing worth having.
    """
    return {
        # Both spellings, because the screens read `min_length` and existing
        # callers may read `minimum_length`. Renaming one would be a silent
        # break in whichever caller was not checked.
        "min_length": MIN_PASSWORD_LENGTH,
        "max_length": MAX_PASSWORD_LENGTH,
        "minimum_length": MIN_PASSWORD_LENGTH,
        "maximum_length": MAX_PASSWORD_LENGTH,
        "rules": [
            f"At least {MIN_PASSWORD_LENGTH} characters.",
            "Not a common password, or a common word with digits added.",
            "Not your username or email address.",
            "Both entries must match.",
        ],
        "notice": (
            "There are deliberately no rules about uppercase letters, digits "
            "or symbols. They add very little and reliably produce the same "
            "few predictable passwords. Length and unfamiliarity do more."),
    }


# ---------------------------------------------------------------------------
# Unauthenticated: activation and reset
# ---------------------------------------------------------------------------

@router.post("/activate", summary="Set a password using an activation link")
async def activate(request_body: SetPasswordRequest, request: Request,
                   session: AsyncSession = Depends(get_auth_session)):
    """First-time password setup. Unauthenticated by necessity."""
    return await _redeem(request_body, request, session,
                         TokenPurpose.ACTIVATION)


@router.post("/reset", summary="Set a password using a reset link")
async def reset(request_body: SetPasswordRequest, request: Request,
                session: AsyncSession = Depends(get_auth_session)):
    return await _redeem(request_body, request, session,
                         TokenPurpose.PASSWORD_RESET)


async def _redeem(body: SetPasswordRequest, request: Request,
                  session: AsyncSession, purpose: TokenPurpose):
    try:
        user = await accounts.redeem_token(
            session, raw_token=body.token, new_password=body.password,
            confirmation=body.confirm_password, purpose=purpose,
            ip_address=client_ip(request))
        await session.commit()
    except PasswordRejected as exc:
        await session.rollback()
        # The link is NOT spent: the policy check runs before the token is
        # claimed, so a user who typed something too short tries again rather
        # than having to ask for a new link.
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST)
    except accounts.AccountError as exc:
        await session.rollback()
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST)

    response = JSONResponse(status_code=status.HTTP_200_OK, content={
        "username": user.username,
        "message": ("Your password is set. Sign in with it."
                    if purpose is TokenPurpose.ACTIVATION
                    else "Your password has been changed. Sign in with it."),
        "sessions_ended": True,
        "notice": ("Every existing session for this account has been signed "
                   "out, including any you did not recognise."),
    })
    # Any session cookie the browser arrived with is cleared: the password just
    # changed, so whatever it authenticated is no longer current.
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.post("/forgot", summary="Request a password-reset link")
async def forgot(body: ForgotPasswordRequest, request: Request,
                 session: AsyncSession = Depends(get_auth_session)):
    """Always the same answer, whether or not the account exists.

    Naming a missing account here would make this endpoint a directory of who
    has an account, readable by anybody, without signing in.
    """
    identifier = (body.identifier or "").strip()
    user = (await session.execute(
        select(User).where(
            (User.username == identifier) | (User.email == identifier.lower()))
    )).scalars().first()

    if user is not None and user.state not in {AccountState.DELETED,
                                               AccountState.DELETION_PENDING}:
        try:
            await accounts.issue_password_reset(
                session, user=user, ip_address=client_ip(request))
            await session.commit()
        except accounts.AccountError:
            await session.rollback()

    # Identical body and status in every case, including for an address that
    # has never existed.
    return {
        "requested": True,
        "message": ("If that account exists, a reset link has been issued. "
                    "Check your email, or ask an administrator — this "
                    "deployment may not have email delivery configured."),
    }


# ---------------------------------------------------------------------------
# Authenticated: password change and sessions
# ---------------------------------------------------------------------------

@router.post("/password", summary="Change your own password")
async def change_password(body: ChangePasswordRequest, request: Request,
                          user: User = Depends(get_current_user),
                          session: AsyncSession = Depends(get_auth_session)):
    """Requires the current password even though the caller is signed in.

    That is what stops an unattended desk, or a stolen session, from becoming a
    permanent account takeover.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    try:
        ended = await accounts.change_password(
            session, user=user, current_password=body.current_password,
            new_password=body.password, confirmation=body.confirm_password,
            current_session_token_hash=hash_session_token(token) if token else None,
            ip_address=client_ip(request))
        await session.commit()
    except PasswordRejected as exc:
        await session.rollback()
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST)
    except accounts.AccountError as exc:
        await session.rollback()
        return _error(exc.code, exc.message, status.HTTP_400_BAD_REQUEST)

    return {
        "changed": True,
        "other_sessions_ended": ended,
        "notice": (
            f"Your password is changed and {ended} other session(s) were "
            f"signed out. You are still signed in here — you have just proved "
            f"who you are."),
    }


@router.get("/sessions", summary="Your active sessions")
async def list_sessions(request: Request,
                        user: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_auth_session)):
    """Never returns a session token, only a non-secret handle.

    A screen that could name a session by its token would be a screen that had
    the token, and the point of storing only a digest is that nothing does.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_hash = hash_session_token(token) if token else None

    rows = await accounts.list_sessions(session, user_id=user.id)
    return {
        "sessions": [{
            "handle": row.handle or (row.token_hash[:12]),
            "is_current": row.token_hash == current_hash,
            "created_at": row.created_at,
            "last_activity_at": row.last_activity_at,
            "expires_at": row.expires_at,
            # Truncated: enough to recognise your own laptop, not enough to
            # fingerprint you from an exported audit file.
            "user_agent": (row.user_agent or "")[:120] or None,
            "ip_address": row.ip_address,
        } for row in rows],
        "notice": ("Signing out a session ends it immediately — the next "
                   "request it makes is refused."),
    }


@router.post("/sessions/revoke", summary="Sign out another session")
async def revoke_session(body: RevokeSessionRequest, request: Request,
                         user: User = Depends(get_current_user),
                         session: AsyncSession = Depends(get_auth_session)):
    removed = await accounts.revoke_session(
        session, user_id=user.id, handle=body.handle,
        ip_address=client_ip(request))
    await session.commit()
    if not removed:
        # 404, not 403: a handle that is not yours must look the same as one
        # that does not exist, or the endpoint becomes a way to test handles.
        return _error("session_not_found", "No such session.",
                      status.HTTP_404_NOT_FOUND)
    return {"revoked": True, "handle": body.handle}


@router.post("/sessions/revoke-all", summary="Sign out everywhere else")
async def revoke_all_sessions(request: Request,
                              user: User = Depends(get_current_user),
                              session: AsyncSession = Depends(get_auth_session)):
    """Ends every other session and keeps this one.

    Keeping the current session is deliberate: the person asking is signed in
    and has just acted, and signing them out of the act they performed reads as
    a failure. "Sign out everywhere including here" is logout, which exists.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    ended = await accounts.revoke_all_sessions(
        session, user_id=user.id,
        keep_token_hash=hash_session_token(token) if token else None,
        ip_address=client_ip(request))
    await session.commit()
    return {"sessions_ended": ended,
            "notice": "You are still signed in on this device."}


@router.get("/security-activity", summary="Recent security events on your account")
async def security_activity(user: User = Depends(get_current_user),
                            session: AsyncSession = Depends(get_auth_session)):
    """Your own security trail. Never anybody else's, and never a secret.

    Shown to the account holder because they are the person best placed to
    notice a sign-in they did not make — which is a detection capability no
    amount of server-side monitoring replaces.
    """
    rows = list((await session.execute(
        select(AuthAuditLog)
        .where(AuthAuditLog.user_id == user.id)
        .order_by(AuthAuditLog.created_at.desc(), AuthAuditLog.id.desc())
        .limit(100)
    )).scalars().all())

    return {
        "events": [{
            "id": row.id,
            "event": row.event.value,
            "created_at": row.created_at,
            "ip_address": row.ip_address,
            "user_agent": (row.user_agent or "")[:120] or None,
            "detail": row.detail,
        } for row in rows],
        "append_only": True,
        "notice": ("These records cannot be amended or deleted. They carry no "
                   "password, token or session identifier."),
    }


# ===========================================================================
# Administrative
# ===========================================================================
#
# Every route below requires MANAGE_ACCOUNTS in the caller's *organization*,
# and acts only on accounts holding a membership there. A cross-organization
# administrator therefore cannot reach past their own organization to a global
# account — which is why these are scoped rather than gated on the platform
# admin role alone.


class CreateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=3, max_length=320)
    full_name: str | None = Field(default=None, max_length=255)
    #: The organization role the new member holds. Subject to the same rules as
    #: every other membership: it decides what they are *eligible* for and
    #: grants no scientific authority on any study by itself.
    role: str = "researcher"
    #: Notably absent: any password field. An administrator does not choose
    #: one, and there is nowhere to put one if they tried — extra keys are
    #: forbidden, so an attempt is a 422 rather than a silently ignored field.


class AccountStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    reason: str | None = Field(default=None, max_length=500)


async def _administered_account(session: AsyncSession, ctx, user_id: int) -> User:
    """An account the caller may administer, or a 404.

    Shared membership in one of the caller's organizations is the test. An
    administrator of one organization must not be able to suspend, reset or
    activate an account belonging entirely to another — that would be reaching
    past the tenant boundary the rest of the application maintains, using the
    global account table as the way round it.
    """
    from nanobio_studio.app.db.organization_models import OrganizationMembership
    from nanobio_studio.app.organizations.policy import (
        RecordNotVisible, visible_organization_ids,
    )

    shared = (await session.execute(
        select(OrganizationMembership.id).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id.in_(
                visible_organization_ids(ctx)))
    )).scalars().first()
    if shared is None:
        raise RecordNotVisible("account")

    account = await session.get(User, user_id)
    if account is None:
        raise RecordNotVisible("account")
    return account


def _require_account_authority(ctx, organization_id: int) -> None:
    from nanobio_studio.app.organizations.policy import (
        Action, RecordFacts, require,
    )
    require(ctx, Action.MANAGE_ACCOUNTS,
            RecordFacts(organization_id=organization_id))


@router.post("/admin/organizations/{organization_id}/accounts",
             status_code=status.HTTP_201_CREATED,
             summary="Create an account and issue an activation link")
async def admin_create_account(
    organization_id: int, body: CreateAccountRequest, request: Request,
    user: User = Depends(get_current_user),
    ctx=Depends(_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Creates a PENDING_ACTIVATION account and returns a one-time link.

    The administrator never chooses a password. The account cannot sign in
    until its owner sets one, and the link is shown exactly once — afterwards
    the server holds only a digest and could not reproduce it if asked.
    """
    from nanobio_studio.app.db.auth_models import UserRole
    from nanobio_studio.app.organizations.vocabulary import OrganizationRole
    from nanobio_studio.app.services import organization_service as orgs
    from nanobio_studio.app.services.auth_service import create_user

    _require_account_authority(ctx, organization_id)

    try:
        organization_role = OrganizationRole(body.role)
    except ValueError:
        permitted = ", ".join(sorted(r.value for r in OrganizationRole))
        return _error("unknown_role",
                      f"{body.role!r} is not an organization role. "
                      f"Permitted: {permitted}.",
                      status.HTTP_400_BAD_REQUEST)

    try:
        account = await create_user(
            session, username=body.username, password=None,
            role=UserRole.RESEARCHER, email=body.email,
            full_name=body.full_name)

        # The membership is created in the same act.
        #
        # Without it the administrator creates an account and immediately
        # cannot reach it: every administrative route here is scoped by shared
        # membership, so an account with none belongs to nobody and is
        # administrable by nobody. That was the shape of the original problem —
        # an account is created and then there is nowhere to go — reappearing
        # one level down.
        #
        # It goes through the ordinary membership service, so the role rules,
        # the audit row and the eligibility mapping are the same ones every
        # other membership gets. This is the controlled-assignment path, not a
        # second way in.
        await orgs.add_member(
            session, actor=ctx, organization_id=organization_id,
            user_id=account.id, role=organization_role)

        issued = await accounts.issue_activation(
            session, user=account, actor_id=user.id,
            ip_address=client_ip(request))
        await session.commit()
    except orgs.OrganizationError as exc:
        await session.rollback()
        return _error("membership_not_created", str(exc),
                      status.HTTP_409_CONFLICT)
    except ValueError as exc:
        await session.rollback()
        return _error("account_not_created", str(exc),
                      status.HTTP_409_CONFLICT)
    except accounts.AccountError as exc:
        await session.rollback()
        return _error(exc.code, exc.message, status.HTTP_409_CONFLICT)

    return {
        "user_id": account.id,
        "username": account.username,
        "state": account.state.value,
        "organization_id": organization_id,
        "organization_role": organization_role.value,
        "activation_link": issued.link,
        "link_shown_once": True,
        "delivery_status": issued.token.delivery_status,
        "delivery_detail": issued.token.delivery_detail,
        "expires_at": issued.token.expires_at,
        "notice": (
            "This link is shown once and cannot be retrieved again. It lets "
            "the account holder set their own password — you do not choose it, "
            "and you will never be able to see it."),
    }


@router.post(
    "/admin/organizations/{organization_id}/accounts/{user_id}/activation",
    summary="Re-issue an activation link")
async def admin_reissue_activation(
    organization_id: int, user_id: int, request: Request,
    user: User = Depends(get_current_user),
    ctx=Depends(_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Issues a fresh link. The previous one stops working immediately."""
    _require_account_authority(ctx, organization_id)
    account = await _administered_account(session, ctx, user_id)
    try:
        issued = await accounts.issue_activation(
            session, user=account, actor_id=user.id,
            ip_address=client_ip(request))
        await session.commit()
    except accounts.AccountError as exc:
        await session.rollback()
        return _error(exc.code, exc.message, status.HTTP_409_CONFLICT)
    return {
        "user_id": account.id, "activation_link": issued.link,
        "link_shown_once": True,
        "delivery_status": issued.token.delivery_status,
        "expires_at": issued.token.expires_at,
        "notice": "The previous link no longer works.",
    }


@router.post("/admin/organizations/{organization_id}/accounts/{user_id}/reset",
             summary="Start a password reset for somebody else")
async def admin_start_reset(
    organization_id: int, user_id: int, request: Request,
    user: User = Depends(get_current_user),
    ctx=Depends(_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Issues a reset link. The administrator still never learns the password.

    Their entire involvement is causing a link to exist. What is chosen behind
    it is never shown to anybody else, including them.
    """
    _require_account_authority(ctx, organization_id)
    account = await _administered_account(session, ctx, user_id)
    try:
        issued = await accounts.issue_password_reset(
            session, user=account, actor_id=user.id,
            ip_address=client_ip(request))
        await session.commit()
    except accounts.AccountError as exc:
        await session.rollback()
        return _error(exc.code, exc.message, status.HTTP_409_CONFLICT)
    return {
        "user_id": account.id, "reset_link": issued.link,
        "link_shown_once": True,
        "delivery_status": issued.token.delivery_status,
        "expires_at": issued.token.expires_at,
        "notice": ("You are not told, and cannot find out, what password they "
                   "choose."),
    }


@router.get("/admin/organizations/{organization_id}/accounts/{user_id}",
            summary="Account status, including activation state")
async def admin_account_status(
    organization_id: int, user_id: int,
    user: User = Depends(get_current_user),
    ctx=Depends(_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    _require_account_authority(ctx, organization_id)
    account = await _administered_account(session, ctx, user_id)
    return {
        "user_id": account.id,
        "username": account.username,
        "email": account.email,
        "state": account.state.value,
        "state_reason": account.state_reason,
        "must_set_password": account.must_set_password,
        "last_login_at": account.last_login_at,
        "password_algorithm": account.password_algorithm,
        "activation": await accounts.token_status(
            session, user_id=account.id, purpose=TokenPurpose.ACTIVATION),
        "password_reset": await accounts.token_status(
            session, user_id=account.id, purpose=TokenPurpose.PASSWORD_RESET),
        # Stated, so nobody goes looking for a control that must not exist.
        "notice": ("There is no way to view or set this account password. "
                   "Issue an activation or reset link instead."),
    }


@router.post("/admin/organizations/{organization_id}/accounts/{user_id}/state",
             summary="Suspend, disable or restore an account")
async def admin_set_state(
    organization_id: int, user_id: int, body: AccountStateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    ctx=Depends(_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """Changing the state ends that account's sessions immediately.

    Not at the next cache expiry — immediately, so the very next request the
    session makes is refused.
    """
    _require_account_authority(ctx, organization_id)

    if user_id == user.id:
        return _error(
            "cannot_change_own_state",
            "You cannot change your own account state. Ask another "
            "administrator, so no one person can lock everybody out.",
            status.HTTP_409_CONFLICT)

    account = await _administered_account(session, ctx, user_id)
    try:
        state = AccountState(body.state)
    except ValueError:
        return _error("unknown_state",
                      f"{body.state!r} is not an account state.",
                      status.HTTP_400_BAD_REQUEST)

    try:
        ended = await accounts.set_account_state(
            session, user=account, state=state, actor_id=user.id,
            reason=body.reason, ip_address=client_ip(request))
        await session.commit()
    except accounts.AccountError as exc:
        await session.rollback()
        return _error(exc.code, exc.message, status.HTTP_409_CONFLICT)

    return {
        "user_id": account.id, "state": account.state.value,
        "sessions_ended": ended,
        "notice": ("Scientific attribution and audit history are unchanged. "
                   "Suspending or disabling an account stops sign-in; it does "
                   "not erase the work the account performed."),
    }


@router.post("/admin/organizations/{organization_id}/accounts/{user_id}/erase",
             summary="Permanently remove identifying information")
async def admin_erase_account(
    organization_id: int, user_id: int, body: AccountStateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    ctx=Depends(_access_context),
    session: AsyncSession = Depends(get_auth_session),
):
    """The second step of deletion, and the only irreversible act here.

    ``DELETED`` used to be a selectable state with no behaviour behind it — an
    administrator could move an account into it and nothing was erased, which
    is the worst of both readings: it looks like a deletion to whoever set it
    and it deletes nothing. So the state is no longer reachable through
    ``/state`` at all, and arriving at it means calling this, from
    ``DELETION_PENDING``, deliberately.

    What is erased is the person: email, full name, the username replaced by a
    non-identifying pseudonym. What is kept is the record: the row, its id, and
    every experiment, review and approval that references it. An approval whose
    approver cannot be named is not an approval, and a regulated record that
    loses its author stops being a record.
    """
    _require_account_authority(ctx, organization_id)

    if user_id == user.id:
        return _error(
            "cannot_erase_own_account",
            "You cannot erase your own account.",
            status.HTTP_409_CONFLICT)

    account = await _administered_account(session, ctx, user_id)
    try:
        result = await accounts.erase_account(
            session, user=account, actor_id=user.id, reason=body.reason,
            ip_address=client_ip(request))
        await session.commit()
    except accounts.AccountError as exc:
        await session.rollback()
        return _error(exc.code, exc.message, status.HTTP_409_CONFLICT)

    return result
