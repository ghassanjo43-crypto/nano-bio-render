"""Rule-based extraction of oncology fields from report text.

WHAT THIS IS, STATED PLAINLY
----------------------------
A **deterministic, rule-based reader**. It locates labelled fields and known
clinical vocabulary using regular expressions, and returns each finding with the
verbatim text that produced it and the page it came from.

It is **not** a trained model, **not** calibrated against annotated reports, and
its performance on real-world documents is **unmeasured**. The `confidence`
figure below is a heuristic pattern-strength score, NOT a probability: 0.9 means
"matched an explicitly labelled field", not "90% likely correct". This is stated
in the response and rendered in the interface.

Why rule-based rather than a model
----------------------------------
A trained clinical NER model would need annotated reports to train and validate
against, and none exist here. A rule-based reader has the compensating virtue
that every output is traceable to a literal span the reader can check — which is
what makes human confirmation meaningful rather than ceremonial.

THE THREE RULES IT EXISTS TO ENFORCE
------------------------------------
1. **Nothing is invented.** A field is only ever populated from a literal match
   in the document. Absence is reported as ``NOT_FOUND``, never as a blank guess.
2. **Derived values are marked derived.** HER2 status read from an equivocal IHC
   plus an amplified ISH is an *inference*, not a statement, and is returned as
   ``INFERRED``. It can never be auto-promoted to a confirmed value.
3. **Contradictions are surfaced, not resolved.** Two different stages in one
   document produce ``CONFLICTING`` with both readings and both spans. The
   extractor does not pick a winner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Final, Iterable, Sequence

__all__ = [
    "EXTRACTOR_NAME",
    "EXTRACTOR_VERSION",
    "Finding",
    "extract_clinical_fields",
]

EXTRACTOR_NAME: Final[str] = "rule-based-oncology-extractor"
EXTRACTOR_VERSION: Final[str] = "1.0.0"

#: Heuristic pattern-strength scores. NOT probabilities.
_CONF_LABELLED: Final[float] = 0.90   # an explicitly labelled field
_CONF_PROSE: Final[float] = 0.70      # known vocabulary found in narrative text
_CONF_DERIVED: Final[float] = 0.50    # combined from other findings
_CONF_CONFLICT: Final[float] = 0.30   # two readings disagree


@dataclass(frozen=True)
class Finding:
    """One extracted value with the evidence for it."""

    value: str
    page: int
    excerpt: str
    confidence: float
    #: True when the value came from a labelled field rather than loose prose.
    labelled: bool = False


@dataclass(frozen=True)
class _Located:
    text: str
    page: int
    start: int


def _pages_of(pages: Sequence[tuple[int, str]]) -> list[_Located]:
    """Flatten (page_number, text) pairs for scanning."""
    return [_Located(text=text, page=number, start=0)
            for number, text in pages if text]


def _excerpt(text: str, match: re.Match[str], width: int = 110) -> str:
    """A readable span around a match, so a human can verify the claim."""
    start = max(0, match.start() - width // 3)
    end = min(len(text), match.end() + width)
    snippet = text[start:end].replace("\n", " ")
    snippet = re.sub(r"\s{2,}", " ", snippet).strip()
    return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")


def _search(pages: Sequence[_Located], pattern: re.Pattern[str],
            group: int | str = 0) -> list[Finding]:
    """Every match of ``pattern`` across all pages, with provenance."""
    out: list[Finding] = []
    for page in pages:
        for match in pattern.finditer(page.text):
            # A pattern may legitimately lack the requested group on some
            # branches; fall back to the whole match rather than dropping it.
            try:
                raw = match.group(group)
            except (IndexError, re.error):
                raw = match.group(0)
            if raw is None:
                continue
            out.append(Finding(
                value=re.sub(r"\s+", " ", raw).strip(" .;:,"),
                page=page.page,
                excerpt=_excerpt(page.text, match),
                confidence=_CONF_LABELLED,
                labelled=True,
            ))
    return out


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
# Mapped to the platform's curated indications where one exists, so a confirmed
# indication can flow into Disease & Therapeutic Selection without a second
# guess. An indication with no curated equivalent is still reported.

_INDICATION_TERMS: Final[tuple[tuple[str, str], ...]] = (
    (r"invasive\s+breast\s+carcinoma", "Breast Cancer"),
    (r"breast\s+(?:cancer|carcinoma)", "Breast Cancer"),
    (r"non[- ]small\s+cell\s+lung\s+(?:cancer|carcinoma)", "Lung Cancer"),
    (r"small\s+cell\s+lung\s+(?:cancer|carcinoma)", "Lung Cancer"),
    (r"lung\s+(?:cancer|carcinoma|adenocarcinoma)", "Lung Cancer"),
    (r"colorectal\s+(?:cancer|carcinoma|adenocarcinoma)", "Colorectal Cancer"),
    (r"(?:colon|rectal|sigmoid)\s+(?:cancer|carcinoma|adenocarcinoma)",
     "Colorectal Cancer"),
    (r"pancreatic\s+ductal\s+adenocarcinoma", "Pancreatic Cancer"),
    (r"pancreatic\s+(?:cancer|carcinoma)", "Pancreatic Cancer"),
    (r"hepatocellular\s+carcinoma", "Liver Cancer (HCC)"),
    (r"\bHCC\b", "Liver Cancer (HCC)"),
)

_SUBTYPE_TERMS: Final[tuple[str, ...]] = (
    r"invasive\s+ductal\s+carcinoma(?:\s*\((?:NST|no\s+special\s+type)\))?",
    r"invasive\s+lobular\s+carcinoma",
    r"ductal\s+carcinoma\s+in\s+situ",
    r"mucinous\s+adenocarcinoma",
    r"adenocarcinoma",
    r"squamous\s+cell\s+carcinoma",
    r"neuroendocrine\s+(?:tumou?r|carcinoma)",
    r"acinar\s+cell\s+carcinoma",
)

_METASTATIC_SITES: Final[tuple[str, ...]] = (
    "liver", "lung", "bone", "brain", "pleura", "peritoneum", "adrenal",
    "lymph node", "skin", "spleen",
)

_GENE_TERMS: Final[tuple[str, ...]] = (
    "PIK3CA", "BRCA1", "BRCA2", "BRCA1/2", "TP53", "EGFR", "KRAS", "NRAS",
    "ALK", "ROS1", "BRAF", "MET", "RET", "PTEN", "ESR1", "ERBB2", "AKT1",
    "MSI", "MMR", "NTRK",
)

_DOCUMENT_TYPES: Final[tuple[tuple[str, str], ...]] = (
    (r"surgical\s+pathology\s+report", "Surgical pathology report"),
    (r"histopathology\s+report", "Histopathology report"),
    (r"pathology\s+report", "Pathology report"),
    (r"cytology\s+report", "Cytology report"),
    (r"molecular\s+pathology\s+report", "Molecular pathology report"),
    (r"(?:MDT|multidisciplinary)\s+(?:meeting\s+)?(?:summary|note)",
     "MDT meeting summary"),
    (r"clinic\s+letter", "Clinic letter"),
    (r"radiology\s+report", "Radiology report"),
    (r"discharge\s+summary", "Discharge summary"),
)

#: Anti-patterns: text that mentions a biomarker without reporting a result.
_NOT_TESTED = re.compile(
    r"\b(?:not\s+(?:tested|performed|assessed|available|done)|"
    r"no[t]?\s+evaluated|pending|N/?A|unknown)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Biomarker readers
# ---------------------------------------------------------------------------


def _biomarker(pages: Sequence[_Located], label: str,
               aliases: Iterable[str]) -> list[Finding]:
    """Read a labelled biomarker result, e.g. ``ER: POSITIVE (95%)``.

    Also recognises an explicit "not tested" statement, which is a genuine
    finding — the document saying it did not measure something is different from
    the document not mentioning it.
    """
    findings: list[Finding] = []
    alt = "|".join(aliases)
    # The value is a NAMED group: an alias may legitimately contain its own
    # capturing group, which would otherwise shift positional numbering and make
    # the extractor read the wrong span.
    pattern = re.compile(
        rf"\b(?:{alt})\b[^\n:]{{0,40}}?[:\-–]\s*(?P<value>[^\n]{{1,80}})",
        re.IGNORECASE)

    for page in pages:
        for match in pattern.finditer(page.text):
            captured = match.group("value")
            if captured is None:
                continue
            raw = captured.strip(" .;,")
            if not raw:
                continue
            findings.append(Finding(
                value=re.sub(r"\s+", " ", raw),
                page=page.page,
                excerpt=_excerpt(page.text, match),
                confidence=_CONF_LABELLED,
                labelled=True,
            ))
    return findings


def _normalise_receptor(value: str) -> str | None:
    """Reduce a receptor result to POSITIVE / NEGATIVE / EQUIVOCAL / NOT TESTED."""
    low = value.lower()
    if _NOT_TESTED.search(low):
        return "Not tested / not available"
    if re.search(r"\bequivocal\b|\b2\s*\+", low):
        return "Equivocal"
    if re.search(r"\bnegative\b|\bneg\b|\b0\b(?!\d)", low):
        return "Negative"
    if re.search(r"\bpositive\b|\bpos\b", low):
        return "Positive"
    return None


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------


def _first_or_conflict(findings: Sequence[Finding],
                       normalise: Callable[[str], str | None] | None = None
                       ) -> tuple[list[Finding], bool]:
    """Collapse findings to distinct values; flag disagreement.

    Returns ``(distinct_findings, conflicting)``. A repeated identical value is
    corroboration, not conflict.
    """
    seen: dict[str, Finding] = {}
    for finding in findings:
        value = normalise(finding.value) if normalise else finding.value
        if value is None:
            continue
        key = value.strip().lower()
        if key not in seen:
            seen[key] = Finding(value=value, page=finding.page,
                                excerpt=finding.excerpt,
                                confidence=finding.confidence,
                                labelled=finding.labelled)
    distinct = list(seen.values())
    return distinct, len(distinct) > 1


def _vocabulary(pages: Sequence[_Located],
                terms: Iterable[tuple[str, str] | str]) -> list[Finding]:
    """Find known clinical vocabulary in prose, longest patterns first."""
    findings: list[Finding] = []
    for entry in terms:
        pattern_text, canonical = (entry if isinstance(entry, tuple)
                                   else (entry, None))
        pattern = re.compile(pattern_text, re.IGNORECASE)
        for page in pages:
            match = pattern.search(page.text)
            if match:
                findings.append(Finding(
                    value=canonical or re.sub(r"\s+", " ", match.group(0)).strip(),
                    page=page.page,
                    excerpt=_excerpt(page.text, match),
                    confidence=_CONF_PROSE,
                ))
                break     # first page carrying the term is enough
    return findings


def extract_clinical_fields(
    pages: Sequence[tuple[int, str]],
) -> dict[str, dict]:
    """Extract every supported field from ``(page_number, text)`` pairs.

    Returns ``{field_key: {value, status, page, excerpt, confidence,
    alternatives, note}}``. ``status`` is one of ``explicitly_stated``,
    ``inferred``, ``ambiguous``, ``conflicting`` or ``not_found``.
    """
    located = _pages_of(pages)
    out: dict[str, dict] = {}

    def record(key: str, findings: Sequence[Finding], *, conflicting: bool = False,
               status: str | None = None, note: str | None = None,
               confidence: float | None = None) -> None:
        if not findings:
            out[key] = _absent(note)
            return
        primary = findings[0]
        if conflicting:
            out[key] = {
                "value": primary.value,
                "status": "conflicting",
                "page": primary.page,
                "excerpt": primary.excerpt,
                "confidence": _CONF_CONFLICT,
                "alternatives": [f.value for f in findings[1:]],
                "supporting_excerpts": [f.excerpt for f in findings],
                "note": note or (
                    "The document reports more than one value for this field "
                    "and does not reconcile them. Both readings are shown; the "
                    "platform does not choose between them."),
            }
            return
        out[key] = {
            "value": primary.value,
            "status": status or ("explicitly_stated" if primary.labelled
                                 else "explicitly_stated"),
            "page": primary.page,
            "excerpt": primary.excerpt,
            "confidence": confidence if confidence is not None
                          else primary.confidence,
            "alternatives": [],
            "supporting_excerpts": [primary.excerpt],
            "note": note,
        }

    # --- indication -------------------------------------------------------
    indications, conflict = _first_or_conflict(_vocabulary(located,
                                                            _INDICATION_TERMS))
    record("cancer_indication", indications, conflicting=conflict)

    # --- histological subtype --------------------------------------------
    subtypes = _vocabulary(located, _SUBTYPE_TERMS)
    # The vocabulary is ordered specific-first; a more specific match supersedes
    # a generic one on the same page rather than conflicting with it.
    if len(subtypes) > 1:
        subtypes = [max(subtypes, key=lambda f: len(f.value))]
    record("histological_subtype", subtypes)

    # --- tumour site ------------------------------------------------------
    # Labels are tried in priority order rather than as one alternation: a
    # generic "Specimen:" earlier in the document would otherwise beat a
    # specific "Primary site:" further down, purely because of position.
    record("tumor_site", _labelled_in_priority(located, (
        r"primary\s+site", r"tumou?r\s+site", r"site\s+of\s+(?:origin|tumou?r)",
        r"anatomical\s+site", r"specimen", r"location")))

    # --- stage ------------------------------------------------------------
    stage_findings = _search(located, re.compile(
        r"\b((?:clinical|pathological|path|c|p)?\s*stage\s*"
        r"(?:group\s*)?[:\-–]?\s*"
        r"(?:0|I{1,3}V?|IV|[1-4])[ABC]?)\b", re.IGNORECASE), group=1)
    stages, stage_conflict = _first_or_conflict(
        stage_findings, normalise=_normalise_stage)
    record("stage", stages, conflicting=stage_conflict)

    # --- TNM (recorded separately; it corroborates rather than conflicts) --
    tnm = _search(located, re.compile(
        r"\b((?:c|p|yp)?T[0-4isX][a-c]?\s*,?\s*(?:c|p)?N[0-3X][a-c]?"
        r"(?:\s*,?\s*(?:c|p)?M[01X][a-c]?)?)\b"), group=1)
    record("tnm_classification", tnm[:1])

    # --- grade ------------------------------------------------------------
    grade_findings = _search(located, re.compile(
        r"\b(?:combined\s+)?(?:histolog(?:ic|ical)\s+)?grade\s*[:\-–]?\s*"
        r"((?:[1-3]|I{1,3})\b[^\n]{0,40})", re.IGNORECASE), group=1)
    grades, grade_conflict = _first_or_conflict(grade_findings,
                                                normalise=_normalise_grade)
    record("grade", grades, conflicting=grade_conflict)

    # --- metastatic sites -------------------------------------------------
    record("metastatic_sites", _metastatic(located))

    # --- receptors and biomarkers ----------------------------------------
    er, er_conflict = _first_or_conflict(
        _biomarker(located, "ER", (r"ER", r"(o?estrogen|estrogen)\s+receptor")),
        normalise=_normalise_receptor)
    record("er_status", er, conflicting=er_conflict)

    pr, pr_conflict = _first_or_conflict(
        _biomarker(located, "PR", (r"PR", r"PgR",
                                   r"progesterone\s+receptor")),
        normalise=_normalise_receptor)
    record("pr_status", pr, conflicting=pr_conflict)

    her2_ihc, ihc_conflict = _first_or_conflict(
        _biomarker(located, "HER2 IHC",
                   (r"HER-?2\s*(?:/neu)?\s*(?:IHC|immunohistochem\w*)",
                    r"(?:IHC|immunohistochem\w*)\s*(?:for\s*)?HER-?2")),
        normalise=_normalise_her2_ihc)
    record("her2_ihc", her2_ihc, conflicting=ihc_conflict)

    her2_ish, ish_conflict = _first_or_conflict(
        _biomarker(located, "HER2 ISH",
                   (r"HER-?2\s*(?:/neu)?\s*(?:ISH|FISH|SISH|CISH)",
                    r"(?:ISH|FISH|SISH|CISH)\s*(?:for\s*)?HER-?2")),
        normalise=_normalise_her2_ish)
    record("her2_ish", her2_ish, conflicting=ish_conflict)

    _record_her2_overall(out, her2_ihc, her2_ish, located)

    her3, her3_conflict = _first_or_conflict(
        _biomarker(located, "HER3", (r"HER-?3", r"ERBB3")),
        normalise=_normalise_receptor)
    record("her3_status", her3, conflicting=her3_conflict)

    ki67 = _biomarker(located, "Ki-67",
                      (r"Ki-?67", r"MIB-?1"))
    record("ki67", ki67[:1])

    pdl1 = _biomarker(located, "PD-L1",
                      (r"PD-?L1", r"CD274"))
    record("pdl1", pdl1[:1])

    # --- genomic alterations ---------------------------------------------
    record("genomic_alterations", _genomic(located))

    # --- narrative fields -------------------------------------------------
    record("pathology_findings", _section(located, (
        r"microscop(?:ic|y)\s+(?:description|findings)",
        r"pathology\s+findings", r"diagnosis", r"gross\s+description")))

    record("current_treatment", _treatment(located))

    record("therapeutic_context", _section(located, (
        r"treatment\s+(?:to\s+date|history|context)", r"therapy",
        r"performance\s+status")))

    record("laboratory_findings", _section(located, (
        r"laboratory\s+(?:findings|results)", r"blood\s+(?:results|counts)",
        r"haematology", r"biochemistry")))

    # --- document metadata ------------------------------------------------
    record("report_date", _report_date(located))
    record("document_type", _vocabulary(located, _DOCUMENT_TYPES)[:1])

    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _absent(note: str | None = None) -> dict:
    return {
        "value": None, "status": "not_found", "page": None, "excerpt": None,
        "confidence": 0.0, "alternatives": [], "supporting_excerpts": [],
        "note": note or "No statement of this field was found in the document.",
    }


def _normalise_stage(value: str) -> str | None:
    match = re.search(r"(0|IV|I{1,3}|[1-4])\s*([ABC])?", value, re.IGNORECASE)
    if not match:
        return None
    roman = {"1": "I", "2": "II", "3": "III", "4": "IV"}
    core = match.group(1).upper()
    core = roman.get(core, core)
    suffix = (match.group(2) or "").upper()
    return f"Stage {core}{suffix}"


def _normalise_grade(value: str) -> str | None:
    match = re.search(r"\b([1-3]|I{1,3})\b", value, re.IGNORECASE)
    if not match:
        return None
    roman = {"I": "1", "II": "2", "III": "3"}
    core = match.group(1).upper()
    return f"Grade {roman.get(core, core)}"


def _normalise_her2_ihc(value: str) -> str | None:
    low = value.lower()
    if _NOT_TESTED.search(low):
        return "Not tested / not available"
    score = re.search(r"\b([0-3])\s*\+", low)
    if "equivocal" in low or (score and score.group(1) == "2"):
        return f"Equivocal (2+)" if (score and score.group(1) == "2") \
            else "Equivocal"
    if score:
        label = {"0": "Negative (0)", "1": "Negative (1+)",
                 "3": "Positive (3+)"}.get(score.group(1))
        if label:
            return label
    if "negative" in low:
        return "Negative"
    if "positive" in low:
        return "Positive"
    return None


def _normalise_her2_ish(value: str) -> str | None:
    low = value.lower()
    if _NOT_TESTED.search(low):
        return "Not tested / not available"
    if re.search(r"\bnon[- ]?amplified\b|\bnot\s+amplified\b", low):
        return "Not amplified"
    if "amplified" in low:
        return "Amplified"
    if "negative" in low:
        return "Not amplified"
    if "positive" in low:
        return "Amplified"
    return None


def _record_her2_overall(out: dict, ihc: Sequence[Finding],
                         ish: Sequence[Finding],
                         pages: Sequence[_Located]) -> None:
    """Derive an overall HER2 reading — and mark it as DERIVED.

    An equivocal IHC followed by an amplified ISH is conventionally reported as
    HER2-positive, but that conclusion is the *reader's*, not the document's.
    It is therefore returned as ``inferred`` and can never be auto-confirmed:
    the user must accept it explicitly or type their own value.
    """
    ihc_value = ihc[0].value if ihc else None
    ish_value = ish[0].value if ish else None

    if ihc_value is None and ish_value is None:
        out["her2_status"] = _absent(
            "Neither a HER2 immunohistochemistry nor an in-situ hybridisation "
            "result was found.")
        return

    parts = []
    if ihc_value:
        parts.append(f"IHC {ihc_value}")
    if ish_value:
        parts.append(f"ISH {ish_value}")
    summary = "; ".join(parts)

    derived = None
    if ish_value == "Amplified":
        derived = "HER2 positive (by ISH amplification)"
    elif ish_value == "Not amplified" and ihc_value in ("Equivocal (2+)",
                                                        "Equivocal"):
        derived = "HER2 negative (equivocal IHC, ISH not amplified)"
    elif ihc_value == "Positive (3+)":
        derived = "HER2 positive (IHC 3+)"
    elif ihc_value in ("Negative (0)", "Negative (1+)") and ish_value is None:
        derived = "HER2 negative (by IHC)"

    excerpt = (ish[0].excerpt if ish else ihc[0].excerpt)
    page = (ish[0].page if ish else ihc[0].page)

    if derived is None:
        out["her2_status"] = {
            "value": summary, "status": "ambiguous", "page": page,
            "excerpt": excerpt, "confidence": _CONF_DERIVED,
            "alternatives": [], "supporting_excerpts": [excerpt],
            "note": "The component results do not combine into an "
                    "unambiguous overall status. Resolve it yourself.",
        }
        return

    out["her2_status"] = {
        "value": derived,
        "status": "inferred",
        "page": page,
        "excerpt": excerpt,
        "confidence": _CONF_DERIVED,
        "alternatives": [],
        "supporting_excerpts": [f.excerpt for f in list(ihc)[:1] + list(ish)[:1]],
        "note": (
            f"Derived from the component results ({summary}); the document does "
            "not state this overall status in these words. It requires your "
            "explicit decision and is never confirmed automatically."),
    }


#: Negation cues. Matched against the WHOLE line, never a forward-only window:
#: reading "No systemic therapy administered" as "therapy administered" inverts
#: the clinical meaning, which is the most dangerous failure this reader can
#: have. Line-level evaluation keeps the negation attached to what it negates.
_NEGATION = re.compile(
    r"\b(?:no|not|none|negative\s+for|without|absent|free\s+of|denies)\b",
    re.IGNORECASE)


def _lines_with(pages: Sequence[_Located],
                keyword: re.Pattern[str]) -> list[tuple[_Located, str, re.Match[str]]]:
    """Every whole line containing ``keyword``, with its page and match.

    Whole lines, because a clinical statement's meaning depends on words that
    may sit either side of the keyword.
    """
    hits: list[tuple[_Located, str, re.Match[str]]] = []
    for page in pages:
        for line in page.text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            match = keyword.search(stripped)
            if match:
                hits.append((page, stripped, match))
    return hits


def _line_finding(page: _Located, line: str, value: str,
                  confidence: float, labelled: bool) -> Finding:
    return Finding(value=value, page=page.page,
                   excerpt=re.sub(r"\s{2,}", " ", line).strip(),
                   confidence=confidence, labelled=labelled)


def _metastatic(pages: Sequence[_Located]) -> list[Finding]:
    keyword = re.compile(
        r"metasta(?:sis|ses|tic)|secondar(?:y|ies)|\bdeposits?\b",
        re.IGNORECASE)
    for page, line, _ in _lines_with(pages, keyword):
        # Negation is judged on the whole line, so "No evidence of distant
        # metastatic disease" is not read as a metastatic site.
        if _NEGATION.search(line):
            return [_line_finding(page, line,
                                  "No distant metastatic disease reported",
                                  _CONF_LABELLED, True)]
        sites = [s for s in _METASTATIC_SITES if s in line.lower()]
        if sites:
            return [_line_finding(page, line,
                                  ", ".join(sorted({s.title() for s in sites})),
                                  _CONF_PROSE, False)]
    return []


def _genomic(pages: Sequence[_Located]) -> list[Finding]:
    """Report each gene mentioned with its stated result."""
    results: list[str] = []
    first: Finding | None = None
    for gene in _GENE_TERMS:
        pattern = re.compile(
            rf"\b{re.escape(gene)}\b[^\n]{{0,100}}", re.IGNORECASE)
        for page in pages:
            match = pattern.search(page.text)
            if not match:
                continue
            window = match.group(0)
            if re.search(r"\bno\s+(?:pathogenic\s+)?(?:variant|mutation|"
                         r"rearrangement)\w*\s+(?:detected|identified|found)|"
                         r"\bnegative\b|\bwild[- ]?type\b|\bnot\s+detected\b",
                         window, re.IGNORECASE):
                results.append(f"{gene}: negative / not detected")
            elif re.search(r"\bmutation\b|\bvariant\b|\bdetected\b|"
                           r"\bamplif\w+\b|\brearrangement\b|\bfusion\b|"
                           r"\bp\.[A-Z]\d+", window, re.IGNORECASE):
                detail = re.search(r"p\.[A-Za-z]\d+[A-Za-z*]*", window)
                results.append(
                    f"{gene}: {detail.group(0)} mutation detected" if detail
                    else f"{gene}: alteration detected")
            else:
                continue
            if first is None:
                first = Finding(value="", page=page.page,
                                excerpt=_excerpt(page.text, match),
                                confidence=_CONF_LABELLED, labelled=True)
            break
    if not results or first is None:
        return []
    return [Finding(value="; ".join(results), page=first.page,
                    excerpt=first.excerpt, confidence=_CONF_LABELLED,
                    labelled=True)]


def _labelled_in_priority(pages: Sequence[_Located],
                          labels: Sequence[str]) -> list[Finding]:
    """Read the first label that appears, trying labels in priority order.

    Position in the document must not decide which label wins — a specific
    label beats a generic one wherever each happens to sit.
    """
    for label in labels:
        pattern = re.compile(rf"{label}\s*[:\-–]\s*([^\n]{{2,80}})",
                             re.IGNORECASE)
        found = _search(pages, pattern, group=1)
        if found:
            return found[:1]
    return []


def _section(pages: Sequence[_Located],
             headings: Sequence[str]) -> list[Finding]:
    """Capture the text under a recognised section heading."""
    for heading in headings:
        pattern = re.compile(
            rf"{heading}\s*[:\-–]?\s*\n?([^\n]{{10,300}})", re.IGNORECASE)
        for page in pages:
            match = pattern.search(page.text)
            if match:
                body = re.sub(r"\s+", " ", match.group(1)).strip(" .;:,")
                if body:
                    return [Finding(value=body, page=page.page,
                                    excerpt=_excerpt(page.text, match),
                                    confidence=_CONF_LABELLED, labelled=True)]
    return []


def _treatment(pages: Sequence[_Located]) -> list[Finding]:
    """Read the treatment statement from a whole line.

    Whole lines matter here more than anywhere: "No systemic therapy
    administered prior to surgery" and "therapy administered prior to surgery"
    are opposite clinical claims, and a forward-only window produced the second
    from the first.
    """
    keyword = re.compile(
        r"\b(?:treatment|therapy|chemotherapy|received|commenced|started)\b",
        re.IGNORECASE)
    # Skip section headings, which carry the keyword but state nothing.
    heading = re.compile(r"^[A-Z0-9 /()-]{4,40}$")

    for page, line, _ in _lines_with(pages, keyword):
        if heading.match(line):
            continue
        if _NEGATION.search(line):
            return [_line_finding(page, line,
                                  "No prior systemic therapy recorded",
                                  _CONF_LABELLED, True)]
        body = re.sub(r"\s+", " ", line).strip(" .;:,")
        if len(body) > 20:
            return [_line_finding(page, line, body, _CONF_PROSE, False)]
    return []


def _report_date(pages: Sequence[_Located]) -> list[Finding]:
    patterns = (
        re.compile(r"(?:report(?:ed)?\s+date|date\s+of\s+report|reported\s+on)"
                   r"\s*[:\-–]?\s*([^\n]{4,40})", re.IGNORECASE),
        re.compile(r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|"
                   r"July|August|September|October|November|December)\s+\d{4})\b",
                   re.IGNORECASE),
        re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    )
    for pattern in patterns:
        found = _search(pages, pattern, group=1)
        if found:
            return found[:1]
    return []
