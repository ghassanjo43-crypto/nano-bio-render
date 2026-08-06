"""What may be written into an audit trail, and what may not.

The problem
-----------
An audit event is the one record that outlives everything it describes. That is
what makes it useful and what makes it dangerous: a patient identifier, a
measurement value or a fragment of an uploaded document written into a summary
survives the deletion of the record it came from, survives the retention job,
and is exported with the trail to whoever asks for it.

So the rule is not "be careful what you pass". It is that the trail accepts a
**bounded vocabulary** — identifiers, status names, counts, labels — and
everything else is refused at the boundary rather than trusted at each of the
forty-odd call sites that write an event.

How the boundary works
----------------------
``redact`` is the only way text reaches ``ValidationAuditLog.summary`` or
``.reason``. It:

* collapses whitespace, so a pasted document fragment cannot smuggle structure;
* removes anything matching a pattern that indicates content rather than
  context — long digit runs, email addresses, dates of birth, file paths,
  base64-looking blobs;
* truncates to the column length, marking the truncation so a reader knows the
  text was cut rather than written that way.

What it deliberately does NOT do
--------------------------------
It does not try to detect a patient name. A general-purpose personal-name
detector is not achievable here and pretending otherwise would be worse than
useless: it would license writing free text into the trail on the belief that
something downstream would catch a leak. The actual control is that the
application never *passes* clinical fields to the audit writer — this module is
the second line, catching a path that forgets, not the first.

Stated as a limitation because a control that is described as stronger than it
is will be relied upon as though it were.
"""

from __future__ import annotations

import re

__all__ = ["redact", "REDACTED_MARKER", "MAX_REASON", "MAX_SUMMARY"]

#: What replaces a removed fragment. Visible on purpose: a reader must be able
#: to see that something was taken out, or the trail quietly reads as complete.
REDACTED_MARKER = "[redacted]"

MAX_REASON = 500
MAX_SUMMARY = 600

#: Patterns that indicate *content* rather than *context*.
#:
#: Ordered by how specific they are, because an earlier substitution changes
#: what a later one sees. Each is here for a concrete leak it would catch:
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Email address — the single most likely identifier to be pasted in.
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    # A date in any of the three common orders. A date of birth in a lock
    # reason is exactly the kind of thing that reaches a trail by accident.
    ("date", re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b")),
    # Long digit runs: record numbers, national identifiers, phone numbers.
    # Seven is chosen so an ordinary primary key ("version 128") survives.
    ("digits", re.compile(r"\b\d{7,}\b")),
    # A filesystem path leaks the server's layout as well as a filename.
    ("path", re.compile(r"(?:[A-Za-z]:)?[\\/](?:[\w .-]+[\\/])+[\w .-]+")),
    # A long unbroken token is a hash, a token or a base64 blob. Fifty is
    # above any word and below a SHA-256 hex digest, which is deliberate:
    # checksums belong in their own columns, not in prose.
    ("blob", re.compile(r"\b[A-Za-z0-9+/=_-]{50,}\b")),
)

_WHITESPACE = re.compile(r"\s+")


def redact(text: str | None, *, limit: int = MAX_SUMMARY) -> str | None:
    """Return ``text`` fit to store in an append-only trail, or None.

    Returns None for empty input rather than an empty string, so a caller that
    passed nothing and a caller that passed something entirely redacted are
    distinguishable in the stored row.
    """
    if text is None:
        return None

    cleaned = _WHITESPACE.sub(" ", str(text)).strip()
    if not cleaned:
        return None

    for _name, pattern in _PATTERNS:
        cleaned = pattern.sub(REDACTED_MARKER, cleaned)

    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    if not cleaned:
        return None

    if len(cleaned) > limit:
        # Marked, not silently cut. A reason that ends mid-sentence with no
        # indication reads as though the author stopped typing.
        keep = max(0, limit - len(" …[truncated]"))
        cleaned = cleaned[:keep].rstrip() + " …[truncated]"

    return cleaned
