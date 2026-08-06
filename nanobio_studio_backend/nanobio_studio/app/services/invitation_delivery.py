"""How an invitation reaches the person it is for.

Provider-neutral on purpose
---------------------------
No email transport is configured in this deployment, and inventing one would
mean writing a host, a username and a password into the repository. So this
module defines the *shape* of a delivery provider and ships three
implementations, none of which carries a credential:

* ``recorded`` — the default. Sends nothing, records that nothing was sent, and
  hands the one-time link back to the administrator who created the invitation
  so they can pass it on by whatever channel they already trust. This is the
  administrator-controlled workflow the brief asks for, and it is the honest
  state for an installation with no mail service: an invitation that silently
  failed to send looks identical to one that was delivered, and the recipient
  is the only person who would ever find out.
* ``console`` — for development. Writes the link to the application log.
  Never enable it anywhere the log is retained or shipped: a log line
  containing a redemption link is a credential in a log.
* ``smtp`` — reads every connection detail from the environment. Refuses to
  start if the environment does not supply them, rather than falling back to a
  default that would either fail obscurely or send through somebody else's
  relay.

Nothing here decides *whether* somebody may be invited. That is the service's
job, and it has already happened by the time a message reaches this module.

The link, and why it cannot be an open redirect
-----------------------------------------------
:func:`build_invitation_link` composes the link from configuration and the
token, and from nothing else. There is no parameter through which a caller —
an administrator, a request body, a query string — can influence where the link
points.

That is the whole defence against an open redirect. An invitation link is
unusually good bait: it arrives unexpectedly, it is expected to be clicked, and
it is expected to lead somewhere the recipient has never been. A "next" or
"return_to" parameter threaded through it would be a phishing primitive with an
organization's name attached, and there is no feature that needs one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import quote, urlsplit

from nanobio_studio.app.core.config import settings

__all__ = [
    "InvitationMessage",
    "DeliveryResult",
    "InvitationDeliveryProvider",
    "RecordedDelivery",
    "ConsoleDelivery",
    "SmtpDelivery",
    "DeliveryNotConfigured",
    "build_invitation_link",
    "get_provider",
    "set_provider_for_tests",
]

log = logging.getLogger(__name__)


class DeliveryNotConfigured(RuntimeError):
    """A provider was selected whose configuration is incomplete."""


@dataclass(frozen=True)
class InvitationMessage:
    """Everything a provider is permitted to know.

    Deliberately no organization description, no inviter's email, no study and
    no scientific content. An invitation reaches an address that has not been
    verified as belonging to anybody, so it must be readable by a stranger
    without disclosing anything about the organization's work.
    """

    recipient_email: str
    organization_name: str
    role: str
    invited_by: str
    expires_at: datetime
    #: The one-time link. Present here because the provider has to send it;
    #: never logged by anything but :class:`ConsoleDelivery`, and never stored.
    link: str


@dataclass(frozen=True)
class DeliveryResult:
    """What happened, in terms an administrator can act on.

    ``delivered=False`` with ``status="recorded"`` is a *success*: the
    invitation exists and the link was returned to its creator. It is
    distinguished from ``status="failed"`` so the members screen can say "hand
    this link over yourself" rather than "something went wrong".
    """

    provider: str
    status: str
    delivered: bool
    #: Safe for the audit trail. Must never contain the token or the link.
    detail: str


class InvitationDeliveryProvider(Protocol):
    name: str

    def send(self, message: InvitationMessage) -> DeliveryResult:
        ...


class RecordedDelivery:
    """Sends nothing and says so.

    The default, and the only provider that is correct for an installation
    without a mail service. The administrator gets the link in the API
    response, once.
    """

    name = "recorded"

    def send(self, message: InvitationMessage) -> DeliveryResult:
        return DeliveryResult(
            provider=self.name, status="recorded", delivered=False,
            detail=("No delivery service is configured. The one-time link was "
                    "returned to the administrator who created the invitation "
                    "and must be passed on directly."))


class ConsoleDelivery:
    """Writes the link to the log. Development only."""

    name = "console"

    def send(self, message: InvitationMessage) -> DeliveryResult:
        log.warning(
            "Invitation for %s to join %s as %s: %s (expires %s). "
            "This link is a credential; the console provider is for local "
            "development only.",
            message.recipient_email, message.organization_name, message.role,
            message.link, message.expires_at.isoformat())
        return DeliveryResult(
            provider=self.name, status="logged", delivered=True,
            detail="Link written to the application log (development only).")


class SmtpDelivery:
    """Sends by SMTP, using only what the environment supplies.

    Every value comes from configuration. There is no default host, no default
    sender and no embedded password, so a misconfigured deployment fails at
    construction with a message naming the missing setting rather than
    attempting to relay through something unintended.
    """

    name = "smtp"

    def __init__(self) -> None:
        missing = [
            field for field, value in (
                ("SMTP_HOST", settings.smtp_host),
                ("SMTP_FROM_ADDRESS", settings.smtp_from_address),
            ) if not value
        ]
        if missing:
            raise DeliveryNotConfigured(
                "SMTP delivery is selected but "
                + ", ".join(missing)
                + " is not set. Set it in the environment; there is no "
                  "default, deliberately.")
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username or None
        self._password = settings.smtp_password or None
        self._sender = settings.smtp_from_address
        self._use_tls = settings.smtp_use_tls

    def send(self, message: InvitationMessage) -> DeliveryResult:
        import smtplib
        from email.message import EmailMessage

        mail = EmailMessage()
        mail["Subject"] = (
            f"You have been invited to {message.organization_name}")
        mail["From"] = self._sender
        mail["To"] = message.recipient_email
        mail.set_content(
            f"{message.invited_by} has invited you to join "
            f"{message.organization_name} as {message.role}.\n\n"
            f"Open this link to accept:\n{message.link}\n\n"
            f"The link can be used once and stops working on "
            f"{message.expires_at.date().isoformat()}.\n\n"
            f"If you were not expecting this, ignore it — the invitation "
            f"grants nothing unless it is accepted.\n")

        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username and self._password:
                    smtp.login(self._username, self._password)
                smtp.send_message(mail)
        except Exception as exc:  # noqa: BLE001 — reported, never swallowed
            # The exception text can name the host but must not be allowed to
            # carry the message body, which contains the link.
            return DeliveryResult(
                provider=self.name, status="failed", delivered=False,
                detail=f"Delivery failed: {type(exc).__name__}.")

        return DeliveryResult(
            provider=self.name, status="sent", delivered=True,
            detail="Sent by SMTP.")


_PROVIDERS: dict[str, type] = {
    RecordedDelivery.name: RecordedDelivery,
    ConsoleDelivery.name: ConsoleDelivery,
    SmtpDelivery.name: SmtpDelivery,
}

_override: InvitationDeliveryProvider | None = None


def set_provider_for_tests(
    provider: InvitationDeliveryProvider | None,
) -> None:
    """Test seam. ``None`` restores configuration-driven selection."""
    global _override
    _override = provider


def get_provider() -> InvitationDeliveryProvider:
    """The configured provider, falling back to ``recorded``.

    An unrecognised name falls back rather than raising: an invitation that
    exists with its link in the administrator's hands is a better outcome than
    a 500 on a typo in an environment variable, and the fallback is the
    provider that discloses least.
    """
    if _override is not None:
        return _override
    chosen = (settings.invitation_delivery or "recorded").strip().lower()
    factory = _PROVIDERS.get(chosen)
    if factory is None:
        log.warning(
            "Unknown invitation delivery provider %r; using 'recorded'. "
            "Valid providers: %s.", chosen, ", ".join(sorted(_PROVIDERS)))
        return RecordedDelivery()
    try:
        return factory()
    except DeliveryNotConfigured as exc:
        log.error("%s Falling back to 'recorded'.", exc)
        return RecordedDelivery()


def build_invitation_link(token: str) -> str:
    """Compose the acceptance link. Takes no destination from any caller.

    The base comes from configuration and is validated here rather than
    trusted: a base that is an absolute URL must point at an ``http(s)`` host,
    and anything else — a ``javascript:`` scheme, a protocol-relative
    ``//evil.example``, a path that escapes with ``..`` — is refused in favour
    of the relative default. Configuration is not user input, but it is edited
    under time pressure by people who are not thinking about redirects.
    """
    base = (settings.invitation_link_base or "").strip()
    if not _is_safe_base(base):
        if base:
            log.error(
                "invitation_link_base %r is not a safe destination; using the "
                "relative default instead.", base)
        base = "/invitations/accept"
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}token={quote(token, safe='')}"


def _is_safe_base(base: str) -> bool:
    if not base:
        return False
    # A protocol-relative reference inherits the scheme and names a foreign
    # host — the classic open-redirect shape, and it does not look like a URL
    # at a glance.
    if base.startswith("//"):
        return False
    parts = urlsplit(base)
    if parts.scheme:
        return parts.scheme in {"http", "https"} and bool(parts.netloc)
    # Relative: must be rooted at the application and must not climb out of it.
    return base.startswith("/") and ".." not in base
