"""Synthetic medical-report fixtures for exercising the upload workflow.

WHAT THESE ARE
--------------
Entirely fabricated documents with **fictional identities and invented clinical
content**, written for this test suite. They exist so the complete upload →
validate → review → confirm → map journey can be exercised without any real
patient information ever entering the system.

WHAT THESE ARE NOT
------------------
Not real reports. Not de-identified real reports. Not derived from any real
case, dataset or publication. The names, identifiers, dates, institutions and
findings are all invented. Any resemblance to a real person is coincidental.

THE RULE THAT MATTERS HERE
--------------------------
These fixtures contain **documents only** — never extracted results. When a
fixture is loaded it goes through the *same* upload, validation and extraction
path as a user's own file. Nothing is short-circuited, and no confirmation
screen is pre-populated from a stored answer. That is what makes the demo a
genuine test of the pipeline rather than a mock-up of one.

Concretely: because no extraction engine is connected, loading one of these
produces exactly what a real upload produces — every field ``NOT_FOUND``, with
the honest "no engine connected" status. The demo therefore demonstrates the
platform's real capability, including its real limits.

The third fixture deliberately contains an internal contradiction so that the
review workflow's conflict handling can be exercised once an engine exists.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SYNTHETIC_REPORTS", "fixture_by_slug", "fixture_slugs"]

#: Version of the fixture set, recorded on any assessment created from one.
REPORT_FIXTURE_VERSION = "synthetic-reports-1.0.0"

#: Banner prepended to every fixture document, so the classification is carried
#: by the document itself and survives download, print or copy-paste.
_BANNER = """\
================================================================================
SYNTHETIC DEMONSTRATION DOCUMENT -- NOT A REAL MEDICAL REPORT
This document is entirely fabricated for software testing. The patient does not
exist. The identifiers, dates, institution and clinical findings are invented.
It is not real patient data, not de-identified real data, and not derived from
any real case. It must not be used for any clinical purpose.
================================================================================

"""


@dataclass(frozen=True)
class SyntheticReport:
    slug: str
    title: str
    purpose: str
    #: What the review workflow should demonstrate with this document.
    demonstrates: str
    filename: str
    body: str

    @property
    def content(self) -> str:
        return _BANNER + self.body

    def as_bytes(self) -> bytes:
        return self.content.encode("utf-8")


_BREAST = """\
FICTIONAL ONCOLOGY CENTRE -- SURGICAL PATHOLOGY REPORT

Patient name .......... JANE Q. EXAMPLE            (FICTIONAL)
Record number ......... SYN-0000001                (NOT A REAL MRN)
Date of birth ......... 01 January 1970            (FICTIONAL)
Report date ........... 12 March 2026
Document type ......... Surgical pathology report
Specimen .............. Left breast, lumpectomy with sentinel node sampling

CLINICAL HISTORY
Fictional 56-year-old presenting with a self-detected left breast mass.

GROSS DESCRIPTION
Lumpectomy specimen measuring 62 x 48 x 30 mm containing a firm, ill-defined
tan mass measuring 22 mm in maximum dimension.

MICROSCOPIC DESCRIPTION
Sections show an invasive ductal carcinoma, no special type. The tumour shows
moderate nuclear pleomorphism, tubule formation in under 10% of the lesion and
a mitotic count of 14 per 10 high-power fields.

Combined histological grade: Grade 3 (poorly differentiated).

Three sentinel lymph nodes were examined. Two of three contain metastatic
carcinoma, the largest deposit measuring 6 mm.

IMMUNOHISTOCHEMISTRY
  Oestrogen receptor (ER) ......... NEGATIVE (Allred score 0)
  Progesterone receptor (PR) ...... NEGATIVE (Allred score 0)
  HER2 (immunohistochemistry) ..... 3+ POSITIVE
  Ki-67 proliferation index ....... 45%

PATHOLOGICAL STAGE
  pT2 pN1 -- Stage IIB

DIAGNOSIS
Invasive ductal carcinoma of the left breast, HER2-positive, hormone
receptor-negative, grade 3, with metastatic involvement of two of three
sentinel lymph nodes.

TREATMENT TO DATE
No systemic therapy administered prior to surgery.

LABORATORY FINDINGS
  Haemoglobin ..... 11.8 g/dL
  Neutrophils ..... 3.4 x10^9/L
  Platelets ....... 245 x10^9/L
  ALT ............. 26 U/L
  Creatinine ...... 68 umol/L

Reported by Dr A. Fictional, Consultant Histopathologist (FICTIONAL)
"""

_LUNG = """\
FICTIONAL REGIONAL HOSPITAL -- ONCOLOGY CLINIC LETTER

Patient name .......... JOHN R. SPECIMEN           (FICTIONAL)
Record number ......... SYN-0000002                (NOT A REAL MRN)
Date of birth ......... 14 June 1958               (FICTIONAL)
Report date ........... 03 February 2026
Document type ......... Clinic letter

DIAGNOSIS
Non-small cell lung cancer, adenocarcinoma, of the right upper lobe.

STAGING
Radiological staging: cT3 cN2 cM1a -- Stage IVA.
Contralateral pleural nodules are present. No extrathoracic metastatic disease
was identified on the staging CT.

MOLECULAR PROFILE
  EGFR ............ No mutation detected
  ALK ............. No rearrangement detected
  ROS1 ............ No rearrangement detected
  KRAS ............ p.G12C detected
  PD-L1 (22C3) .... Tumour proportion score 65%

TREATMENT
The patient commenced pembrolizumab monotherapy on 20 January 2026 and has
received two cycles. Treatment is ongoing and tolerated without dose reduction.

PERFORMANCE STATUS
ECOG 1.

LABORATORY FINDINGS
  Haemoglobin ..... 12.4 g/dL
  Lymphocytes ..... 1.1 x10^9/L
  LDH ............. 288 U/L
  Albumin ......... 38 g/L

NOTE
This letter records disease status only. It contains no recommendation.

Signed: Dr B. Notreal, Consultant Medical Oncologist (FICTIONAL)
"""

# Deliberately self-contradictory, so conflict handling can be exercised.
_COLORECTAL = """\
FICTIONAL TEACHING HOSPITAL -- MULTIDISCIPLINARY TEAM SUMMARY

Patient name .......... SAM T. TESTCASE            (FICTIONAL)
Record number ......... SYN-0000003                (NOT A REAL MRN)
Report date ........... 28 January 2026
Document type ......... MDT meeting summary

SUMMARY OF FINDINGS
Colorectal adenocarcinoma of the sigmoid colon.

*** NOTE FOR SOFTWARE TESTING ***
This document contains DELIBERATE INTERNAL CONTRADICTIONS and INCOMPLETE
sections. It exists to exercise conflict detection and missing-field handling
in the review workflow. It is not a coherent clinical document and must never
be read as one.

STAGING
The histopathology section of this summary records Stage II disease.
The radiology section of the same summary records Stage III disease.
These two statements are in conflict and are not reconciled anywhere in the
document.

MISMATCH REPAIR / MSI STATUS
An earlier paragraph states the tumour is microsatellite stable (MSS).
A later paragraph states the tumour is microsatellite unstable (MSI-High).
No resolution is recorded.

GRADE
[Section left blank in the source document.]

RECEPTOR AND BIOMARKER STATUS
Not assessed.

TREATMENT
No treatment has been recorded in this summary.

LABORATORY FINDINGS
Not included in this document.

Prepared by the fictional MDT coordinator (FICTIONAL)
"""


SYNTHETIC_REPORTS: tuple[SyntheticReport, ...] = (
    SyntheticReport(
        slug="synthetic-breast-pathology",
        title="Synthetic breast pathology report",
        purpose=(
            "A complete, internally consistent surgical pathology report "
            "covering indication, histology, grade, stage, receptor status and "
            "laboratory findings."
        ),
        demonstrates=(
            "The ordinary path: a well-formed document uploaded, validated and "
            "presented for review. Because no extraction engine is connected, "
            "every field is reported as not found and must be entered by hand — "
            "which is what this platform genuinely does today."
        ),
        filename="synthetic-breast-pathology.txt",
        body=_BREAST,
    ),
    SyntheticReport(
        slug="synthetic-lung-clinic-letter",
        title="Synthetic lung oncology clinic letter",
        purpose=(
            "A narrative clinic letter rather than a structured pathology "
            "report, including a molecular profile and an ongoing treatment."
        ),
        demonstrates=(
            "A different document shape. Prose reports are markedly harder to "
            "extract from than tabulated pathology, which is part of why "
            "connecting an extraction engine requires validation rather than "
            "regular expressions."
        ),
        filename="synthetic-lung-clinic-letter.txt",
        body=_LUNG,
    ),
    SyntheticReport(
        slug="synthetic-colorectal-conflicting",
        title="Synthetic colorectal summary with conflicting findings",
        purpose=(
            "A deliberately contradictory and incomplete document: two "
            "different stages, two different MSI statuses, and several sections "
            "left blank."
        ),
        demonstrates=(
            "Conflict and missing-field handling. A contradiction must be "
            "surfaced as ambiguous for a human to resolve, never silently "
            "resolved by picking one value. Blank sections must read as 'not "
            "found', never as a blank guess."
        ),
        filename="synthetic-colorectal-conflicting.txt",
        body=_COLORECTAL,
    ),
)


def fixture_slugs() -> tuple[str, ...]:
    return tuple(r.slug for r in SYNTHETIC_REPORTS)


def fixture_by_slug(slug: str) -> SyntheticReport | None:
    for report in SYNTHETIC_REPORTS:
        if report.slug == slug:
            return report
    return None
