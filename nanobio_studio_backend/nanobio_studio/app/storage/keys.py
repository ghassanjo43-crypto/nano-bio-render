"""Object keys, and everything they must not contain.

Why a key is not a filename
---------------------------
An object key is visible in far more places than a database column: provider
consoles, access logs, billing exports, lifecycle rules, CDN caches, support
tickets and bucket inventories. Several of those are readable by people with no
clinical authorisation at all, and some are retained long after the record is
deleted.

So a key may not carry a patient name or identifier, a diagnosis, the original
filename, an email address, an organization or study name, a candidate code, or
anything else that would tell a reader what the object is about. Not "should
not" — the generator below cannot produce one, because it is built from
integers and random bytes and never sees a string from the user.

The user-facing filename is kept in ``validation_attachments.original_filename``,
behind the same authorization as the rest of the record.

What a key *is*
---------------
    att/{organization_id}/{attachment_id}/{32 hex characters}

Three components, each earning its place:

* ``att/`` — a prefix, so a bucket shared with anything else stays sortable and
  a lifecycle rule can target attachments alone.
* the organization and attachment ids — **integers**, and internal ones. They
  are not secret and they are not sensitive: knowing that object belongs to
  organization 4 tells a reader nothing about organization 4. What they buy is
  operational: an object found loose in a bucket can be traced back to its row
  without a full-table scan, which is the difference between a reconciliation
  report you can act on and a list of orphans you cannot.
* 32 hex characters from ``secrets`` — 128 bits. This is what makes the key
  unguessable and collision-resistant. Two uploads of the same file by the same
  person produce different keys, so a retry cannot silently overwrite a
  finalised object.

The random component is *not* an access control. Possession of a key grants
nothing: every download goes through the API and the policy first. It is there
so that a key which does leak — into a log, a screenshot, a bucket listing —
cannot be used to enumerate its neighbours.

Never from the client
---------------------
There is no code path anywhere in this application that accepts a key or a
bucket name from a request. ``parse_key`` exists to *read* a key the
application generated, and refuses anything else.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

__all__ = [
    "ATTACHMENT_PREFIX",
    "REPORT_PREFIX",
    "new_attachment_key",
    "is_valid_key",
    "parse_key",
    "ParsedKey",
    "InvalidObjectKey",
]

ATTACHMENT_PREFIX = "att"
REPORT_PREFIX = "rpt"

#: Exactly what the generator produces, and nothing else.
_KEY_RE = re.compile(
    r"^(?P<prefix>att|rpt)/(?P<organization_id>\d{1,12})/"
    r"(?P<record_id>\d{1,12})/(?P<token>[0-9a-f]{32})$"
)


class InvalidObjectKey(ValueError):
    """A key that this application did not generate."""


@dataclass(frozen=True)
class ParsedKey:
    prefix: str
    organization_id: int
    record_id: int
    token: str


def new_attachment_key(*, organization_id: int, attachment_id: int) -> str:
    """A fresh key for one attachment.

    Takes integers only. There is deliberately no parameter through which a
    filename, a display name or any other string could reach the key — the
    signature is the enforcement.
    """
    if organization_id is None or attachment_id is None:
        raise InvalidObjectKey(
            "An object key needs both an organization and a record id, so an "
            "object found loose in a bucket can be traced back to its row.")
    if organization_id < 0 or attachment_id < 0:
        raise InvalidObjectKey("Identifiers must be non-negative.")
    return (f"{ATTACHMENT_PREFIX}/{int(organization_id)}/{int(attachment_id)}/"
            f"{secrets.token_hex(16)}")


def is_valid_key(key: str) -> bool:
    return bool(_KEY_RE.match(key or ""))


def parse_key(key: str) -> ParsedKey:
    """Read a key this application generated. Refuses anything else.

    Used by reconciliation to attribute a loose object to an organization
    without consulting the database. A key that does not match is reported as
    unattributable rather than guessed at — an object in the wrong shape is a
    finding, not an input.
    """
    match = _KEY_RE.match(key or "")
    if match is None:
        raise InvalidObjectKey(
            "That is not a key this application generates. Keys are built from "
            "internal identifiers and random bytes; one that does not match "
            "was written by something else.")
    return ParsedKey(
        prefix=match.group("prefix"),
        organization_id=int(match.group("organization_id")),
        record_id=int(match.group("record_id")),
        token=match.group("token"),
    )
