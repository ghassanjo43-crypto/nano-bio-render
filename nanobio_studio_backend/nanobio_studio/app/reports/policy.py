"""Intake policy: which documents this platform is permitted to accept.

The decision this enforces
--------------------------
Real patient reports are **refused**. Synthetic and de-identified documents are
accepted. This is a deliberate scope decision (2026-08-02), taken because the
current stack cannot honestly support protected health information:

* no encryption at rest — assessments live in a local SQLite file;
* no HTTPS in the development deployment, so a session cookie and an uploaded
  document both cross the network in clear text;
* no enforced retention or disposal schedule;
* no schema migrations, so the store is not yet operationally durable;
* no recorded legal basis, data-processing agreement or ethics approval.

Accepting real reports under those conditions would create a patient-data
honeypot that currently performs no extraction and therefore delivers nothing in
exchange for the risk. The gate lifts when the controls above exist — not when
the feature is merely convenient.

How it is enforced
------------------
Two independent mechanisms, because either alone is weak:

1. **Explicit attestation.** The uploader must positively declare the document's
   classification. There is no default, and "real patient report" is refused
   server-side with the reason. An attestation is recorded with the assessment
   and is auditable.
2. **Identifier screening.** The document is scanned for patterns that look like
   direct identifiers. Hits do not silently block — they surface a warning,
   because a synthetic fixture legitimately contains identifier-shaped strings.
   What they cannot do is pass unnoticed.

Screening is explicitly **not** a guarantee: it cannot detect a real name in a
narrative sentence. It raises the cost of an accident; the attestation carries
the responsibility.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

__all__ = [
    "INTAKE_POLICY_VERSION",
    "DocumentClassification",
    "PolicyRefusal",
    "IntakeDecision",
    "evaluate_intake",
    "POLICY_STATEMENT",
]

INTAKE_POLICY_VERSION = "intake-policy-1.0.0"


class DocumentClassification(str, enum.Enum):
    """What the uploader declares the document to be."""

    #: Fabricated content. The demonstration fixtures, or a user's own test file.
    SYNTHETIC = "synthetic"
    #: Derived from a real report with direct identifiers already removed by the
    #: uploader, before it reached this platform.
    DEIDENTIFIED = "deidentified"
    #: A real patient report. REFUSED under the current policy.
    REAL_PATIENT_DATA = "real_patient_data"


#: Accepted classifications. Anything else is refused.
_ACCEPTED = (DocumentClassification.SYNTHETIC,
             DocumentClassification.DEIDENTIFIED)

POLICY_STATEMENT = (
    "This platform accepts synthetic and de-identified documents only. Real "
    "patient reports are refused, because the current deployment has no "
    "encryption at rest, no enforced retention schedule and no recorded legal "
    "basis for processing patient data. This restriction is a deliberate scope "
    "decision, not a technical oversight."
)

#: Patterns that suggest direct identifiers survived. Deliberately broad: a
#: false positive costs a warning, a false negative costs a disclosure.
_IDENTIFIER_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("email address", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
     "an email address"),
    ("national identifier", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
     "a national-insurance or social-security style number"),
    ("telephone number",
     re.compile(r"(?<!\d)(?:\+\d{1,3}[ -])?\d{3,4}[ -]\d{3,4}[ -]\d{3,4}(?!\d)"),
     "a telephone number"),
    ("postal code", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b"),
     "a postal code"),
)

#: Markers a synthetic document is expected to carry. Their absence on a
#: SYNTHETIC declaration is worth flagging, since it may mean the wrong file was
#: chosen.
_SYNTHETIC_MARKERS = ("synthetic", "fictional", "not a real", "test data",
                      "demonstration")


class PolicyRefusal(Exception):
    """Intake was refused on policy grounds."""

    def __init__(self, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class IntakeDecision:
    """The outcome of applying intake policy to a document."""

    classification: DocumentClassification
    policy_version: str
    #: Non-blocking notices for the uploader. Never suppressed.
    warnings: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return self.classification in _ACCEPTED


def evaluate_intake(classification: DocumentClassification,
                    attested: bool,
                    text: str | None) -> IntakeDecision:
    """Apply intake policy. Raises ``PolicyRefusal`` when the document is refused.

    ``text`` is screened only when the format was readable; a PDF cannot be
    screened here because no reader exists, which is itself reported as a
    warning rather than passed over.
    """
    if classification is DocumentClassification.REAL_PATIENT_DATA:
        raise PolicyRefusal(
            "real_patient_data_refused",
            "This platform does not accept real patient reports.",
            POLICY_STATEMENT,
        )

    if classification not in _ACCEPTED:      # pragma: no cover - defensive
        raise PolicyRefusal(
            "unsupported_classification",
            "The document classification is not recognised.",
            f"Accepted: {', '.join(c.value for c in _ACCEPTED)}.",
        )

    if not attested:
        raise PolicyRefusal(
            "attestation_required",
            "You must confirm the document contains no real patient "
            "information before it can be uploaded.",
            "The attestation is recorded with the assessment and is auditable.",
        )

    warnings: list[str] = []

    if text is None:
        warnings.append(
            "This document's text could not be read, so it was not screened "
            "for identifiers. Your attestation is the only control that "
            "applied."
        )
    else:
        found = [description for _, pattern, description in _IDENTIFIER_PATTERNS
                 if pattern.search(text)]
        if found:
            warnings.append(
                "The document contains text resembling "
                + ", ".join(sorted(set(found)))
                + ". This is expected in a synthetic fixture, but check it is "
                "not a real identifier."
            )

        lowered = text.lower()
        if (classification is DocumentClassification.SYNTHETIC
                and not any(m in lowered for m in _SYNTHETIC_MARKERS)):
            warnings.append(
                "This document was declared synthetic but contains none of the "
                "usual markers ('synthetic', 'fictional', 'not a real'). Check "
                "you uploaded the file you intended."
            )

    warnings.append(
        "Identifier screening is pattern-based and cannot detect a name or "
        "other identifier written into ordinary prose. It reduces the chance of "
        "an accident; it does not guarantee the document is free of "
        "identifiers."
    )

    return IntakeDecision(
        classification=classification,
        policy_version=INTAKE_POLICY_VERSION,
        warnings=tuple(warnings),
    )
