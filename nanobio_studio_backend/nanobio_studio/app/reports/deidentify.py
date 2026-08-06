"""Best-effort de-identification for retained or exported documents.

HONEST STATEMENT OF WHAT THIS IS
--------------------------------
A **pattern-based redactor**, not a de-identification guarantee. It removes
common direct identifiers that follow recognisable shapes. It does **not**
implement HIPAA Safe Harbor, it is not certified, and it will miss identifiers
written in free text — a name inside a narrative sentence, an institution named
in passing, a rare diagnosis that identifies someone by itself.

Because it cannot promise removal, the platform does not rely on it as a control.
Real patient documents are refused at intake regardless (see
``app/reports/policy.py``); this exists so a user can further scrub a document
they are permitted to hold, and so an export can be made less identifying.

Anything claiming to be "de-identified" here carries that caveat with it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["DEIDENTIFY_VERSION", "RedactionReport", "deidentify_text"]

DEIDENTIFY_VERSION = "pattern-redactor-1.0.0"

#: Ordered so that more specific patterns run before more general ones.
_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL REMOVED]"),
    ("us_ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN REMOVED]"),
    ("nhs_number", re.compile(r"\b\d{3}[ -]?\d{3}[ -]?\d{4}\b"),
     "[ID REMOVED]"),
    ("phone", re.compile(r"(?<!\d)(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?"
                         r"\d{3,4}[ -]\d{3,4}(?:[ -]\d{3,4})?(?!\d)"),
     "[PHONE REMOVED]"),
    ("record_number", re.compile(
        r"\b(?:MRN|NHS|Record\s*(?:number|no\.?)|Patient\s*ID|Hospital\s*no\.?)"
        r"\s*[.:]*\s*[A-Z0-9-]{3,}", re.IGNORECASE), "[RECORD ID REMOVED]"),
    ("named_patient", re.compile(
        r"\b(?:Patient\s*name|Name\s*of\s*patient|Patient)\s*[.:]*\s*"
        r"[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,3}", re.IGNORECASE),
     "Patient name: [NAME REMOVED]"),
    ("dob", re.compile(
        r"\b(?:Date\s*of\s*birth|DOB|D\.O\.B\.?)\s*[.:]*\s*[^\n]{4,40}",
        re.IGNORECASE), "Date of birth: [DATE REMOVED]"),
    ("full_date", re.compile(
        r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{4}\b", re.IGNORECASE),
     "[DATE REMOVED]"),
    ("iso_date", re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[DATE REMOVED]"),
    ("postcode_uk", re.compile(
        r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b"), "[POSTCODE REMOVED]"),
    ("us_zip", re.compile(r"\b\d{5}(?:-\d{4})?\b"), "[POSTAL CODE REMOVED]"),
)


@dataclass(frozen=True)
class RedactionReport:
    """What the redactor changed, and what it explicitly does not promise."""

    text: str
    #: Pattern name -> number of replacements made.
    counts: dict[str, int]
    version: str
    limitations: tuple[str, ...]

    @property
    def total_redactions(self) -> int:
        return sum(self.counts.values())


_LIMITATIONS: tuple[str, ...] = (
    "Pattern-based redaction only. It removes identifiers that follow "
    "recognisable shapes and cannot detect identifiers written in free text.",
    "This is NOT HIPAA Safe Harbor de-identification and is not certified. "
    "It must not be relied on to make a real patient document shareable.",
    "A person's name inside a narrative sentence, a named institution, or a "
    "rare diagnosis that identifies someone on its own will not be removed.",
    "Review the redacted text yourself before relying on it. The platform "
    "treats this as an aid, never as a guarantee.",
)


def deidentify_text(text: str) -> RedactionReport:
    """Redact recognisable direct identifiers from ``text``."""
    counts: dict[str, int] = {}
    redacted = text

    for name, pattern, replacement in _PATTERNS:
        redacted, hits = pattern.subn(replacement, redacted)
        if hits:
            counts[name] = hits

    return RedactionReport(
        text=redacted,
        counts=counts,
        version=DEIDENTIFY_VERSION,
        limitations=_LIMITATIONS,
    )
