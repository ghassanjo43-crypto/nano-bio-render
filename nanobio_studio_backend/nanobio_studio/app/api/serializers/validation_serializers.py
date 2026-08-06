"""Explicit response shapes for the Experimental Validation Registry.

Why an allow-list rather than reflection
----------------------------------------
The first version of these responses serialised every column of
``ExperimentVersion`` by iterating ``__table__.columns``. That is convenient and
wrong: it makes the API surface a function of the database schema, so **any
column added later becomes externally visible the moment it is created**. A
future ``internal_review_notes``, ``reviewer_private_comment`` or
``storage_backend_credential`` would ship to every client without anybody
deciding it should.

So every field below is named. Adding a column to the model changes nothing a
client sees until somebody adds it here, which is a decision with a diff.

What is deliberately withheld
-----------------------------
* ``storage_key`` — the attachment store's internal handle. A client addresses
  an attachment by id through the download route; the backing layout is never
  disclosed, and exposing a key would invite it to be used as a path.
* Any future field carrying a filesystem path, a credential or an internal
  security marker. The allow-list is the mechanism that makes that guarantee
  hold without anybody having to remember it.

``ALLOWED_*`` tuples are exported so a test can assert the response contains
exactly these keys, and that no model column leaks in by accident.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from nanobio_studio.app.db.validation_models import (
    ExperimentAttachment, ExperimentVersion, Measurement,
)

__all__ = [
    "ALLOWED_VERSION_FIELDS",
    "ALLOWED_MEASUREMENT_FIELDS",
    "ALLOWED_ATTACHMENT_FIELDS",
    "ALLOWED_CANDIDATE_VERSION_FIELDS",
    "WITHHELD_VERSION_FIELDS",
    "serialize_version",
    "serialize_measurement",
    "serialize_attachment",
    "serialize_candidate_version",
]


def _plain(value: Any) -> Any:
    """Convert one stored value to something JSON can carry."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


#: Every field of an experiment version a client may see.
#:
#: Grouped by the section of the record they belong to, so a reviewer of this
#: file can see at a glance which part of the form each one serves.
ALLOWED_VERSION_FIELDS: tuple[str, ...] = (
    # identity and linkage
    "id", "experiment_id", "version_number", "candidate_version_id", "status",
    # scientific framing
    "scientific_question", "hypothesis",
    # provenance
    "laboratory_name", "investigator_name", "investigator_org",
    "start_date", "completion_date",
    "protocol_identifier", "protocol_version",
    "nanoparticle_batch", "payload_batch",
    # biological system
    "biological_model", "cell_line", "cell_source",
    "cell_authentication_status", "passage_number",
    # method
    "assay_method", "endpoints_json", "measurement_units",
    # controls and replication
    "control_positive", "control_negative", "control_vehicle",
    "controls_not_applicable_reason",
    "biological_replicates", "technical_replicates", "replicate_justification",
    # acceptance criteria
    "acceptance_criteria_json", "acceptance_criteria_recorded_at",
    "acceptance_criteria_met",
    # results and disclosure
    "raw_data_reference", "processed_results_summary", "statistical_method",
    "statistical_method_not_applicable_reason",
    "deviations", "exclusions", "missing_data", "disclosures_confirmed",
    "investigator_conclusion", "quality_issues_json", "provenance_declaration",
    # evidence decision
    "requested_level", "approved_level",
    "eligibility_ruleset_version",
    # workflow
    "submitted_at", "submitted_by", "review_started_at", "reviewer_id",
    "decision_at", "decision_by", "decision_comments", "performed_by",
    "superseded_by_version_id", "frozen_at",
    # timestamps
    "created_at", "updated_at",
)

#: Columns that exist on the model and are deliberately NOT served.
#:
#: Named explicitly rather than left as "whatever is not in the list above", so
#: the omission is a recorded decision and a test can assert each one stays out.
WITHHELD_VERSION_FIELDS: tuple[str, ...] = (
    # The stored verdict is large and is served by /eligibility, which returns
    # it in its structured form. Duplicating it here would let the two drift.
    "eligibility_json",
)

ALLOWED_MEASUREMENT_FIELDS: tuple[str, ...] = (
    "id", "endpoint_name", "sample_group", "replicate_id", "time_point",
    "dose_value", "dose_unit",
    "result_numeric", "result_text", "result_unit",
    "detection_limit", "quantification_limit",
    "method", "source_file_reference", "missing_value_reason",
    "excluded", "exclusion_justification",
    "normalized_value", "normalization_method",
)

#: Note the absence of ``storage_key``. That is the point of this tuple.
ALLOWED_ATTACHMENT_FIELDS: tuple[str, ...] = (
    "id", "category", "original_filename", "mime_type", "size_bytes",
    "checksum_sha256", "uploaded_by", "uploaded_at",
)


def serialize_version(version: ExperimentVersion) -> dict[str, Any]:
    return {name: _plain(getattr(version, name))
            for name in ALLOWED_VERSION_FIELDS}


def serialize_measurement(measurement: Measurement) -> dict[str, Any]:
    return {name: _plain(getattr(measurement, name))
            for name in ALLOWED_MEASUREMENT_FIELDS}


def serialize_attachment(attachment: ExperimentAttachment) -> dict[str, Any]:
    return {name: _plain(getattr(attachment, name))
            for name in ALLOWED_ATTACHMENT_FIELDS}


#: Every field of a *candidate* version a client may see.
#:
#: The design snapshot is deliberately absent. It can be large, the history is
#: a list, and the comparison route serves it in the structured form a reader
#: actually needs — a raw JSON blob in a list response would be paid for on
#: every page load and read by nobody.
ALLOWED_CANDIDATE_VERSION_FIELDS: tuple[str, ...] = (
    "id", "candidate_id", "version_number", "revision_label",
    "status", "results_state", "results_inherited_from_id",
    "predecessor_version_id", "revision_reason", "note",
    "snapshot_checksum",
    "locked_at", "lock_reason",
    "supersession_state", "superseded_by_version_id", "superseded_at",
    "supersession_reason", "supersession_decision_id",
    "model_version", "ruleset_version", "reference_data_version",
    "algorithm_selection",
    "created_at", "created_by", "revision",
)


def serialize_candidate_version(version) -> dict[str, Any]:
    """One candidate version, as every screen and route needs it.

    The three derived keys are computed here rather than left to each caller,
    because they are the ones an interface gets wrong. ``label`` so a reader
    never has to resolve an integer; ``editable`` so a form knows whether to
    offer a field at all; ``is_historical`` so a superseded version can be
    marked as such wherever it appears rather than only on the page that
    happens to check.
    """
    payload = {name: _plain(getattr(version, name))
               for name in ALLOWED_CANDIDATE_VERSION_FIELDS}
    payload["label"] = version.effective_label()
    payload["editable"] = version.is_editable()
    payload["is_historical"] = version.superseded_by_version_id is not None
    # Kept under its old name as well: the history route has served
    # ``checksum`` since this feature shipped, and renaming a field that
    # clients read is a breaking change dressed as a tidy-up.
    payload["checksum"] = version.snapshot_checksum
    return payload


def unlisted_model_columns() -> dict[str, tuple[str, ...]]:
    """Model columns that are neither served nor explicitly withheld.

    Used by a test rather than at runtime. A new column shows up here the
    moment it is added, which forces a decision — serve it, or record why not —
    instead of letting it appear in responses unnoticed.
    """
    version_known = set(ALLOWED_VERSION_FIELDS) | set(WITHHELD_VERSION_FIELDS)
    return {
        "version": tuple(
            c.name for c in ExperimentVersion.__table__.columns
            if c.name not in version_known),
        "measurement": tuple(
            c.name for c in Measurement.__table__.columns
            if c.name not in set(ALLOWED_MEASUREMENT_FIELDS)
            and c.name not in {"version_id", "created_at"}),
        "attachment": tuple(
            c.name for c in ExperimentAttachment.__table__.columns
            if c.name not in set(ALLOWED_ATTACHMENT_FIELDS)
            and c.name not in {"version_id", "storage_key"}),
    }
