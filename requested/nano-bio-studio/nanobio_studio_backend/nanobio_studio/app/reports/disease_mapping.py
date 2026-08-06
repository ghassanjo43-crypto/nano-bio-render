"""Validation of a disease / subtype / therapeutic-agent triple.

Why the mapping is read from the frontend file
----------------------------------------------
``frontend/src/workflow/diseaseData.ts`` is *generated* from the legacy
``data/disease_drug_mapping.py`` and is the single copy the running application
offers the user. Re-typing it here would create a second copy that silently
drifts, and a drifted copy would either reject a combination the user can
legitimately select or accept one they cannot.

So this module parses that file. It is a temporary arrangement with the same
status as the ``sys.path`` bootstrap in the scientific adapters: the mapping
belongs in a shared data module once the scientific core is ported.

The parse result is cached, because the file is static for the process lifetime.
A parse failure is **not** swallowed into "accept everything" — it raises, so a
broken mapping surfaces as an error rather than as a silently disabled control.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

__all__ = ["DiseaseMappingError", "load_mapping", "is_valid_triple",
           "MAPPING_SOURCE"]

_REPO_ROOT = Path(__file__).resolve().parents[4]
MAPPING_SOURCE = _REPO_ROOT / "frontend" / "src" / "workflow" / "diseaseData.ts"

_ARRAY = re.compile(r"=\s*(\[[\s\S]*?\])\s*as const;")


class DiseaseMappingError(RuntimeError):
    """The curated mapping could not be read."""


@lru_cache(maxsize=1)
def load_mapping() -> dict[str, dict[str, frozenset[str]]]:
    """Parse the curated mapping into ``{disease: {subtype: {drugs}}}``."""
    try:
        source = MAPPING_SOURCE.read_text(encoding="utf-8")
    except OSError as exc:
        raise DiseaseMappingError(
            f"Could not read the disease mapping at {MAPPING_SOURCE}") from exc

    match = _ARRAY.search(source)
    if match is None:
        raise DiseaseMappingError(
            "Could not locate the DISEASES array in the mapping file. Its "
            "shape may have changed; this parser must be updated rather than "
            "the validation disabled.")

    try:
        diseases = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise DiseaseMappingError(
            "The disease mapping is not valid JSON-compatible data.") from exc

    return {
        d["name"]: {
            st["name"]: frozenset(st["drugs"]) for st in d.get("subtypes", [])
        }
        for d in diseases
    }


def is_valid_triple(disease: str, subtype: str, drug: str) -> bool:
    """True when the combination exists in the curated mapping."""
    mapping = load_mapping()
    subtypes = mapping.get(disease)
    if subtypes is None:
        return False
    drugs = subtypes.get(subtype)
    if drugs is None:
        return False
    return drug in drugs
