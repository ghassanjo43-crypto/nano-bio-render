# pages/10_Tutorial.py
# NanoBio Studio — Pedagogical Tutorial Page (Option A)
# ----------------------------------------------------
# Goals:
# - Student-friendly, step-by-step, UAE-university friendly tone
# - Expandable sections (guided learning journey)
# - Mini exercises + common mistakes + practical checklists
# - 1–2 quizzes per section with scoring + progress + reset
# - Prevent double scoring per question (lock once answered)
#
# Notes:
# - This page is intentionally long and thorough (650+ lines target).
# - It is designed to work as a standalone Streamlit page.
# - It DOES NOT require importing internal app modules.
#   Instead, it teaches students how to use the existing modules in your app UI.

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import streamlit as st


# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
# =========================
# Page Configuration
# =========================
st.set_page_config(
    page_title="Tutorial — NanoBio Studio",
    page_icon="🎓",
    layout="wide",
)


# =========================
# Lightweight Styling
# =========================
st.markdown(
    """
<style>
/* Keep it clean, university-friendly */
.nb-title {
    font-size: 2.0rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
}
.nb-subtitle {
    font-size: 1.05rem;
    opacity: 0.85;
    margin-bottom: 1rem;
}
.nb-card {
    border: 1px solid rgba(49,51,63,0.15);
    border-radius: 14px;
    padding: 14px 16px;
    background: rgba(255,255,255,0.55);
}
.nb-micro {
    font-size: 0.95rem;
    opacity: 0.9;
}
.nb-muted {
    opacity: 0.75;
}
.nb-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    border: 1px solid rgba(49,51,63,0.15);
    font-size: 0.85rem;
    margin-right: 6px;
    background: rgba(255,255,255,0.6);
}
.nb-ok {
    color: #0B6E4F;
    font-weight: 700;
}
.nb-warn {
    color: #8A4B0F;
    font-weight: 700;
}
.nb-danger {
    color: #8E1A1A;
    font-weight: 800;
}
.nb-quiz-title {
    font-size: 1.1rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
}
.nb-hr {
    height: 1px;
    background: rgba(49,51,63,0.12);
    margin: 10px 0 14px 0;
}
.nb-kbd {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    background: rgba(27,31,35,.05);
    border: 1px solid rgba(27,31,35,.15);
    border-bottom-color: rgba(27,31,35,.2);
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 0.9rem;
}
.nb-note {
    border-left: 5px solid rgba(49,51,63,0.25);
    padding: 10px 12px;
    background: rgba(255,255,255,0.55);
    border-radius: 10px;
}
.nb-callout-good {
    border-left: 6px solid rgba(11,110,79,0.45);
    padding: 10px 12px;
    background: rgba(255,255,255,0.55);
    border-radius: 10px;
}
.nb-callout-warn {
    border-left: 6px solid rgba(138,75,15,0.45);
    padding: 10px 12px;
    background: rgba(255,255,255,0.55);
    border-radius: 10px;
}
.nb-callout-danger {
    border-left: 6px solid rgba(142,26,26,0.45);
    padding: 10px 12px;
    background: rgba(255,255,255,0.55);
    border-radius: 10px;
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# Quiz Data Structures
# =========================
@dataclass
class QuizQuestion:
    qid: str
    prompt: str
    qtype: str  # "mcq" | "tf" | "short"
    options: Optional[List[str]] = None  # for mcq/tf
    correct_index: Optional[int] = None  # for mcq/tf
    accepted_answers: Optional[List[str]] = None  # for short
    explanation: str = ""
    points: int = 1


# =========================
# State & Utilities
# =========================
def _init_state() -> None:
    """
    Initialize all session_state keys used by this tutorial page.
    Prevents KeyErrors and supports reset logic.
    """
    defaults = {
        # scoring
        "tut_total_points": 0,
        "tut_earned_points": 0,
        "tut_answered": {},  # qid -> {"correct": bool, "timestamp": float, "points": int}
        "tut_submissions": {},  # qid -> raw submission value
        "tut_last_reset": None,
        "tut_progress_notes": "",
        # checklist progress per section (optional)
        "tut_section_checks": {},  # section_id -> dict of check keys -> bool
        # UI convenience
        "tut_show_all_answers": False,
        "tut_course_start_ts": None,
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if st.session_state["tut_course_start_ts"] is None:
        st.session_state["tut_course_start_ts"] = time.time()


def normalize_text(s: str) -> str:
    """
    Normalize short-answer input:
    - lowercase
    - remove extra spaces
    - remove punctuation-like characters
    """
    if s is None:
        return ""
    s = s.strip().lower()
    s = re.sub(r"[\s]+", " ", s)
    s = re.sub(r"[^a-z0-9\s\-\+\/]", "", s)
    return s


def compute_total_points(questions: List[QuizQuestion]) -> int:
    return sum(q.points for q in questions)


def mark_answered(qid: str, correct: bool, points: int, submission_value: Union[str, int]) -> None:
    """
    Record an answer as "locked" so it cannot be scored again.
    This prevents double scoring.
    """
    st.session_state["tut_answered"][qid] = {
        "correct": bool(correct),
        "timestamp": time.time(),
        "points": int(points),
    }
    st.session_state["tut_submissions"][qid] = submission_value


def is_answered(qid: str) -> bool:
    return qid in st.session_state["tut_answered"]


def already_scored_message(qid: str) -> None:
    meta = st.session_state["tut_answered"].get(qid, {})
    correct = meta.get("correct", False)
    pts = meta.get("points", 0)
    if correct:
        st.success(f"✅ Already submitted and scored. You earned {pts} point(s) here.")
    else:
        st.warning("⚠️ Already submitted and scored. This question is locked to prevent double scoring.")


def render_progress_header(total_points: int) -> None:
    earned = int(st.session_state["tut_earned_points"])
    pct = 0.0 if total_points <= 0 else min(1.0, max(0.0, earned / total_points))

    colA, colB, colC, colD = st.columns([2.2, 1.2, 1.2, 1.4])
    with colA:
        st.markdown('<div class="nb-title">🎓 NanoBio Studio — Student Tutorial</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="nb-subtitle">A step-by-step learning journey through manual design + AI co-design, with quizzes and scoring.</div>',
            unsafe_allow_html=True,
        )
    with colB:
        st.markdown('<div class="nb-card">', unsafe_allow_html=True)
        st.markdown(f'<span class="nb-badge">Score</span> <b>{earned}</b> / <b>{total_points}</b>', unsafe_allow_html=True)
        st.progress(pct)
        st.markdown('</div>', unsafe_allow_html=True)
    with colC:
        st.markdown('<div class="nb-card">', unsafe_allow_html=True)
        answered_count = len(st.session_state["tut_answered"])
        st.markdown(f'<span class="nb-badge">Answered</span> <b>{answered_count}</b>', unsafe_allow_html=True)
        st.markdown(
            '<div class="nb-micro nb-muted">Each question can be scored once (anti double-scoring).</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
    with colD:
        st.markdown('<div class="nb-card">', unsafe_allow_html=True)
        st.checkbox("Show answer explanations everywhere", key="tut_show_all_answers")
        st.text_area(
            "Your notes (saved in session)",
            key="tut_progress_notes",
            placeholder="Write quick notes: what you learned, what confused you, what to review…",
            height=86,
        )
        st.markdown('</div>', unsafe_allow_html=True)


def reset_tutorial_state() -> None:
    """
    Full reset: clears scoring, answered questions, and section checks.
    """
    st.session_state["tut_total_points"] = 0
    st.session_state["tut_earned_points"] = 0
    st.session_state["tut_answered"] = {}
    st.session_state["tut_submissions"] = {}
    st.session_state["tut_section_checks"] = {}
    st.session_state["tut_last_reset"] = time.time()
    st.session_state["tut_progress_notes"] = ""
    st.session_state["tut_course_start_ts"] = time.time()


def section_check(section_id: str, check_key: str, label: str, help_text: str = "") -> bool:
    """
    Per-section checklist item stored in session state.
    Useful for students to self-report completion.
    """
    if section_id not in st.session_state["tut_section_checks"]:
        st.session_state["tut_section_checks"][section_id] = {}
    if check_key not in st.session_state["tut_section_checks"][section_id]:
        st.session_state["tut_section_checks"][section_id][check_key] = False

    widget_key = f"tut_chk__{section_id}__{check_key}"
    # keep widget in sync
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state["tut_section_checks"][section_id][check_key]

    val = st.checkbox(label, key=widget_key, help=help_text)
    st.session_state["tut_section_checks"][section_id][check_key] = bool(val)
    return bool(val)


def render_quiz_block(title: str, questions: List[QuizQuestion]) -> None:
    """
    Render a quiz block with multiple questions. Each question is scored once.
    """
    st.markdown('<div class="nb-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="nb-quiz-title">🧠 {title}</div>', unsafe_allow_html=True)
    st.markdown('<div class="nb-hr"></div>', unsafe_allow_html=True)

    for q in questions:
        render_question(q)

    st.markdown("</div>", unsafe_allow_html=True)


def render_question(q: QuizQuestion) -> None:
    """
    Render a single question with anti-double-scoring.
    """
    st.markdown(f"**{q.prompt}**")
    answered = is_answered(q.qid)

    # If answered, show locked status + optionally explanation.
    if answered:
        already_scored_message(q.qid)
        if st.session_state.get("tut_show_all_answers", False) and q.explanation:
            st.info(q.explanation)
        st.markdown("---")
        return

    # Not answered: allow input and submission
    if q.qtype in ("mcq", "tf"):
        assert q.options is not None and q.correct_index is not None, "MCQ/TF requires options and correct_index."
        choice = st.radio(
            "Choose one:",
            options=list(range(len(q.options))),
            format_func=lambda i: q.options[i],
            key=f"tut_in_{q.qid}",
            horizontal=False,
        )
        submit = st.button(f"Submit answer ({q.points} pt)", key=f"tut_btn_{q.qid}")
        if submit:
            correct = int(choice) == int(q.correct_index)
            earned_pts = q.points if correct else 0
            st.session_state["tut_earned_points"] += earned_pts
            mark_answered(q.qid, correct=correct, points=earned_pts, submission_value=int(choice))

            if correct:
                st.success(f"✅ Correct! +{earned_pts} point(s)")
            else:
                st.error("❌ Not quite. Review the explanation and try to understand the concept.")

            if q.explanation:
                st.info(q.explanation)
            st.markdown("---")
            st.rerun()

    elif q.qtype == "short":
        assert q.accepted_answers is not None, "Short answer requires accepted_answers."
        ans = st.text_input("Your answer:", key=f"tut_in_{q.qid}", placeholder="Type a short answer…")
        submit = st.button(f"Submit answer ({q.points} pt)", key=f"tut_btn_{q.qid}")
        if submit:
            norm = normalize_text(ans)
            accepted = [normalize_text(x) for x in q.accepted_answers]
            correct = norm in accepted
            earned_pts = q.points if correct else 0
            st.session_state["tut_earned_points"] += earned_pts
            mark_answered(q.qid, correct=correct, points=earned_pts, submission_value=ans)

            if correct:
                st.success(f"✅ Correct! +{earned_pts} point(s)")
            else:
                st.error("❌ Not quite. Compare your answer to the expected idea and try again next time.")

            if q.explanation:
                st.info(q.explanation)
            st.markdown("---")
            st.rerun()
    else:
        st.warning("Unknown question type.")
        st.markdown("---")


# =========================
# Build Quiz Bank
# =========================
# Keep QIDs stable and unique.
# Tip: prefix by section to prevent collisions.
QUIZZES: Dict[str, List[QuizQuestion]] = {}

# Section 0 — Orientation
QUIZZES["S0"] = [
    QuizQuestion(
        qid="S0_Q1",
        prompt="What is the main purpose of NanoBio Studio?",
        qtype="mcq",
        options=[
            "To replace laboratory experiments completely",
            "To help design and understand nanoparticle drug delivery using guided simulation + analysis",
            "To sell pharmaceuticals directly to hospitals",
            "To create 3D animations for biology students only",
        ],
        correct_index=1,
        explanation=(
            "NanoBio Studio is an educational + decision-support platform. It helps you explore design variables "
            "(size, charge, ligand, payload, etc.), simulate delivery behavior, and reflect on safety/cost/protocol steps."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S0_Q2",
        prompt="True or False: In this tutorial, each quiz question can be scored multiple times until you get it right.",
        qtype="tf",
        options=["True", "False"],
        correct_index=1,
        explanation=(
            "False. To keep scoring fair, each question is locked once submitted. "
            "You can still read the explanation and learn, but you won't gain extra points by re-submitting."
        ),
        points=1,
    ),
]

# Section 1 — Materials & Targets
QUIZZES["S1"] = [
    QuizQuestion(
        qid="S1_Q1",
        prompt="Which combination best matches the idea of 'Materials & Targets'?",
        qtype="mcq",
        options=[
            "Choosing a camera sensor and a lens",
            "Choosing nanoparticle building blocks and the biological tissue/cell/receptor you want to reach",
            "Choosing a hospital and selecting a doctor",
            "Choosing a font and a color theme",
        ],
        correct_index=1,
        explanation=(
            "This module is where you pick nanoparticle materials (e.g., polymers, lipids, metals) "
            "and define the biological target (e.g., tumor tissue, liver, EGFR receptor)."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S1_Q2",
        prompt="Short answer: Name ONE common mistake when selecting a biological target.",
        qtype="short",
        accepted_answers=[
            "choosing a target without a delivery pathway",
            "choosing a target that is not reachable",
            "picking a target without considering off target effects",
            "not considering off target effects",
            "not considering receptor availability",
            "ignoring receptor expression",
            "ignoring tissue barriers",
        ],
        explanation=(
            "Common mistakes include: selecting a target with no realistic delivery route, "
            "ignoring tissue barriers (e.g., BBB), ignoring off-target risk, or assuming the receptor is abundant."
        ),
        points=2,
    ),
]

# Section 2 — Design Nanoparticle
QUIZZES["S2"] = [
    QuizQuestion(
        qid="S2_Q1",
        prompt="In nanoparticle design, why do we care about particle size?",
        qtype="mcq",
        options=[
            "Size only changes the color of the nanoparticle",
            "Size affects circulation time, tissue penetration, clearance, and sometimes toxicity",
            "Size only matters for microscope pictures",
            "Size is irrelevant if you have a ligand",
        ],
        correct_index=1,
        explanation=(
            "Size influences biodistribution: too small may clear quickly (kidney filtration), "
            "too large may get trapped (spleen/liver) and may increase immune recognition. "
            "It also affects how particles move through tissue."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S2_Q2",
        prompt="True or False: A highly positive surface charge is always safer because cells are negatively charged.",
        qtype="tf",
        options=["True", "False"],
        correct_index=1,
        explanation=(
            "False. While positive charge may increase uptake in some cases, it can also raise toxicity, "
            "increase non-specific interactions, and trigger immune responses. Safety depends on balance and context."
        ),
        points=2,
    ),
]

# Section 3 — Delivery Simulation (PK/PD-lite)
QUIZZES["S3"] = [
    QuizQuestion(
        qid="S3_Q1",
        prompt="The two-compartment simulation typically separates concentration into:",
        qtype="mcq",
        options=[
            "Ocean vs desert",
            "Plasma (blood) vs tissue (target site)",
            "Left lung vs right lung",
            "DNA vs RNA",
        ],
        correct_index=1,
        explanation=(
            "A simple PK/PD-lite model often tracks drug (or nanoparticle payload) in plasma and in tissue. "
            "It helps you reason about exposure over time and delivery efficiency."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S3_Q2",
        prompt="Short answer: If the tissue curve stays very low while plasma stays high, what is a likely interpretation?",
        qtype="short",
        accepted_answers=[
            "poor tissue uptake",
            "low tissue uptake",
            "weak targeting",
            "poor targeting",
            "delivery barrier",
            "barrier prevents delivery",
        ],
        explanation=(
            "A common interpretation is poor delivery to the target tissue (weak uptake/transport), or a barrier effect. "
            "You may need to adjust size/ligand/release or consider a different target route."
        ),
        points=2,
    ),
]

# Section 4 — Toxicity & Safety
QUIZZES["S4"] = [
    QuizQuestion(
        qid="S4_Q1",
        prompt="Which factors can increase heuristic toxicity risk in nanoparticle systems?",
        qtype="mcq",
        options=[
            "Only the color of the UI",
            "High dose, extreme charge, very small size, high PDI, and poor steric stabilization",
            "Only the brand of the computer",
            "Whether the student is left-handed",
        ],
        correct_index=1,
        explanation=(
            "Safety scoring often uses heuristic inputs: dose, particle size, surface charge, polydispersity index (PDI), "
            "and stabilization/stealth features. These correlate with aggregation, immune response, and off-target interactions."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S4_Q2",
        prompt="True or False: A low PDI generally suggests a more uniform particle size distribution.",
        qtype="tf",
        options=["True", "False"],
        correct_index=0,
        explanation=(
            "True. Lower PDI usually indicates more uniform particle sizes. Higher PDI means broader distribution, "
            "which can cause unpredictable behavior and may increase safety concerns."
        ),
        points=1,
    ),
]

# Section 5 — Cost Estimator
QUIZZES["S5"] = [
    QuizQuestion(
        qid="S5_Q1",
        prompt="What is the BEST interpretation of the cost estimator at early design stage?",
        qtype="mcq",
        options=[
            "Exact manufacturing price in AED with guaranteed accuracy",
            "A relative complexity/cost index to compare options and guide design decisions",
            "A legal invoice generator for hospitals",
            "A stock market predictor",
        ],
        correct_index=1,
        explanation=(
            "Early-stage design lacks full process definition. The estimator is best used for comparison: "
            "which option is likely more complex, more costly, or harder to scale."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S5_Q2",
        prompt="Short answer: Name ONE design choice that often increases manufacturing complexity.",
        qtype="short",
        accepted_answers=[
            "more steps",
            "adding a ligand",
            "complex ligand",
            "rare material",
            "tight size control",
            "multiple components",
            "sterile processing",
        ],
        explanation=(
            "Examples: adding targeting ligands, multi-layer nanoparticles, tight size constraints, rare materials, "
            "or steps requiring sterile/controlled environments."
        ),
        points=2,
    ),
]

# Section 6 — Protocol Generator
QUIZZES["S6"] = [
    QuizQuestion(
        qid="S6_Q1",
        prompt="Why is the Protocol Generator useful for students and early-stage labs?",
        qtype="mcq",
        options=[
            "It replaces lab safety approvals",
            "It drafts an SOP-style outline so you can plan experiments clearly and consistently",
            "It manufactures the nanoparticles automatically",
            "It guarantees publication acceptance",
        ],
        correct_index=1,
        explanation=(
            "A good protocol outline improves clarity, repeatability, and helps teams discuss steps before spending resources."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S6_Q2",
        prompt="True or False: A protocol outline should include controls and measurement checkpoints.",
        qtype="tf",
        options=["True", "False"],
        correct_index=0,
        explanation=(
            "True. Controls (negative/positive) and checkpoints (size, PDI, zeta potential, release tests) "
            "are essential for trustworthy interpretation."
        ),
        points=1,
    ),
]

# Section 7 — AI Co-Designer (Scenario/Policy Mode + Explainability + Governance)
QUIZZES["S7"] = [
    QuizQuestion(
        qid="S7_Q1",
        prompt="In Scenario/Policy Mode, the AI Co-Designer is mainly used to:",
        qtype="mcq",
        options=[
            "Generate random nanoparticle designs without any constraints",
            "Explore design choices under constraints (e.g., safety-first, cost-limited, UAE lab capability)",
            "Rewrite student essays",
            "Predict football match results",
        ],
        correct_index=1,
        explanation=(
            "Scenario/Policy Mode lets you state constraints and priorities. The AI proposes options and trade-offs "
            "based on those goals (e.g., safer, cheaper, more target-specific)."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S7_Q2",
        prompt="True or False: Explainability and audit export are important for governance and responsible innovation.",
        qtype="tf",
        options=["True", "False"],
        correct_index=0,
        explanation=(
            "True. Explainability helps humans understand why a recommendation was made. "
            "Audit reports support transparency, review, and institutional alignment."
        ),
        points=2,
    ),
]

# Section 8 — Integrated Workflow + Baseline Comparison
QUIZZES["S8"] = [
    QuizQuestion(
        qid="S8_Q1",
        prompt="What is the purpose of 'AI vs Manual Baseline'?",
        qtype="mcq",
        options=[
            "To prove AI is always better",
            "To compare two approaches and learn where each one is stronger or weaker",
            "To remove the need for human judgment",
            "To generate a CV for the student",
        ],
        correct_index=1,
        explanation=(
            "A baseline comparison is educational: it shows how manual reasoning and AI reasoning differ, "
            "and why a combined approach can be more robust."
        ),
        points=2,
    ),
    QuizQuestion(
        qid="S8_Q2",
        prompt="Short answer: Name ONE reason why a manual baseline remains valuable even when AI is available.",
        qtype="short",
        accepted_answers=[
            "human judgment",
            "domain knowledge",
            "context awareness",
            "verification",
            "accountability",
            "safety review",
            "bias checking",
        ],
        explanation=(
            "Manual baselines help with verification, accountability, context, and detecting AI mistakes or hidden assumptions."
        ),
        points=2,
    ),
]


# =========================
# Total points computed once
# =========================
ALL_QUESTIONS: List[QuizQuestion] = []
for _k, _qs in QUIZZES.items():
    ALL_QUESTIONS.extend(_qs)
TOTAL_POINTS = compute_total_points(ALL_QUESTIONS)


# =========================
# Initialize State
# =========================
_init_state()
st.session_state["tut_total_points"] = TOTAL_POINTS


# =========================
# Header + Progress
# =========================
render_progress_header(total_points=TOTAL_POINTS)

# Reset control row
with st.container():
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 2.3, 1.3])
    with c1:
        if st.button("🔄 Reset tutorial (score + answers)", type="secondary", use_container_width=True):
            reset_tutorial_state()
            st.success("Tutorial reset done. Your score and quiz locks were cleared.")
            st.rerun()
    with c2:
        st.markdown(
            f'<div class="nb-card nb-micro"><span class="nb-badge">Tip</span> Use the left sidebar to navigate pages. '
            f'Come back anytime to continue.</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="nb-card nb-micro">'
            '<span class="nb-badge">How scoring works</span>'
            'Submit each question once. After submission, it is locked (anti double-scoring). '
            'Read explanations to learn even if you got it wrong.'
            "</div>",
            unsafe_allow_html=True,
        )
    with c4:
        elapsed_min = int((time.time() - st.session_state["tut_course_start_ts"]) / 60)
        st.markdown(
            f'<div class="nb-card nb-micro"><span class="nb-badge">Session time</span> ~{elapsed_min} min</div>',
            unsafe_allow_html=True,
        )

st.markdown("")

# =========================
# A Friendly “Course Map”
# =========================
st.markdown(
    """
<div class="nb-card">
<b>🗺️ Course Map (Suggested Learning Path)</b><br>
<span class="nb-badge">1</span> Orientation & expectations<br>
<span class="nb-badge">2</span> Materials & Targets<br>
<span class="nb-badge">3</span> Design Nanoparticle<br>
<span class="nb-badge">4</span> Delivery Simulation (PK/PD-lite)<br>
<span class="nb-badge">5</span> Toxicity & Safety<br>
<span class="nb-badge">6</span> Cost Estimator<br>
<span class="nb-badge">7</span> Protocol Generator<br>
<span class="nb-badge">8</span> AI Co-Designer (scenario/policy, explainability, governance)<br>
<span class="nb-badge">9</span> AI vs Manual Baseline & integrated workflow<br><br>
<i class="nb-muted">This tutorial is written in a UAE-university friendly style: practical, structured, and focused on learning outcomes.</i>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("")


# ======================================================================
# SECTION 0 — Orientation (What you are building & why it matters)
# ======================================================================
with st.expander("0) Orientation — What NanoBio Studio is (and is NOT) ✅", expanded=True):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> By the end of this section, you can explain NanoBio Studio in one paragraph to a classmate:
what it does, why it exists, and what it does <i>not</i> claim to do.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### What NanoBio Studio does (in student language)

NanoBio Studio helps you **think like a nanoparticle designer**. In real research, nanoparticle drug delivery is full of
design choices and trade-offs:

- If you change **size**, you may change circulation, tissue penetration, and clearance.
- If you change **surface charge**, you may change uptake and safety.
- If you change **ligand targeting**, you may improve specificity but increase complexity.
- If you change **release profile**, you may change therapeutic timing.

NanoBio Studio provides a guided way to:

1) **Select materials and biological targets**  
2) **Design a nanoparticle concept** (size/charge/ligand/payload)  
3) **Run simple delivery simulation** (PK/PD-lite to compare curves)  
4) **Estimate heuristic toxicity/safety risk**  
5) **Estimate cost/complexity at early stage**  
6) **Generate a protocol outline** (SOP-style plan)  
7) **Use AI Co-Designer** to explore scenarios, compare baseline, and export governance evidence

### What NanoBio Studio is NOT
- It is not a replacement for lab work, ethics approvals, animal studies, or clinical trials.
- It does not guarantee real-world performance.
- It helps you **learn the logic of design**, and produce a structured, explainable, reviewable plan.

### A healthy mindset (very important)
Treat your outputs as:
- **Hypotheses** (ideas to test)
- **Comparisons** (this option vs that option)
- **Justifications** (why this design is reasonable given goals and constraints)

Not as absolute truth.
"""
    )

    st.markdown(
        """
<div class="nb-callout-warn">
<b>Common student mistake:</b> Treating the simulator outputs as “final answers”.  
✅ Better: use outputs to ask better questions, then refine the design.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Mini exercise (2 minutes)")
    st.markdown(
        """
Write a short explanation (2–3 sentences) as if you are speaking to a supervisor:

- What problem does NanoBio Studio help with?
- What is one key benefit for students?

You can write it in your notebook or in the “Your notes” box at the top.
"""
    )

    st.markdown("### Quick checklist")
    section_check("S0", "chk_1", "I understand what NanoBio Studio does (supportive simulation + analysis).")
    section_check("S0", "chk_2", "I understand what NanoBio Studio does NOT claim (not a replacement for lab validation).")
    section_check("S0", "chk_3", "I will treat results as hypothesis + comparison, not absolute truth.")

    render_quiz_block("Orientation Quiz (Section 0)", QUIZZES["S0"])


# ======================================================================
# SECTION 1 — Materials & Targets
# ======================================================================
with st.expander("1) Materials & Targets — Choosing the building blocks and the destination 🧩", expanded=False):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> You can select a nanoparticle material and a biological target in a way that makes biological sense.
You also know what information you must not ignore (barriers, off-target risk, feasibility).
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### Why this module exists
Before you adjust numbers (size, charge, etc.), you need clarity on two basics:

1) **What is your nanoparticle made of?**  
   Examples (conceptually): lipid-based, polymer-based, inorganic (gold/silica), hybrid.

2) **Where are you trying to deliver the payload?**  
   Examples: tumor tissue, liver, lung tissue, immune cells, specific receptor such as EGFR.

A good design starts with a realistic *route* from injection → blood → tissue → cells → target.

### How to use it (student steps)
In the app, open **Materials & Targets** and:

1) Browse the materials list (or upload your own library if enabled).
2) Select a target tissue/cell/receptor.
3) Read the provided metadata (if available): typical challenges, barriers, special notes.
4) Keep your choice simple for the first run (learning first, sophistication later).

### What to look for
- Does your target have known barriers? (Example: brain targets often face BBB challenges.)
- Is your target highly expressed or rare?
- Is your material known to be biocompatible or controversial?

### Common mistakes (and how to fix them)
**Mistake A: Choosing a target with no delivery pathway**  
Fix: write the route in one sentence. Example: “IV injection → blood → tumor tissue via EPR + ligand binding”.

**Mistake B: Forgetting off-target risk**  
Fix: ask “Where else could this particle go?” Liver and spleen are common accumulation sites.

**Mistake C: Using too many fancy materials too early**  
Fix: start with a standard approach for learning, then increase complexity.

### Mini exercise: Build a target statement
Create a target statement like:
- “We aim to deliver payload X to target Y using material Z, because …”

Example:
- “We aim to deliver a small-molecule payload to tumor tissue using a lipid nanoparticle, because lipid carriers are common and can support controlled release.”
"""
    )

    st.markdown(
        """
<div class="nb-callout-good">
<b>Practical UAE-university tip:</b> When working on projects, always write a 1–2 line “design intent” that your instructor can review quickly.
It improves grading clarity and reduces confusion in teamwork.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Checkpoints")
    section_check("S1", "chk_1", "I selected one material and one target (not too many at once).")
    section_check("S1", "chk_2", "I can describe the delivery route in one sentence.")
    section_check("S1", "chk_3", "I considered at least one barrier or off-target risk.")

    st.markdown("### Mini practice (optional)")
    st.markdown(
        """
Try this: pick one target and list **two obstacles** to reaching it.

Examples of obstacles:
- immune clearance
- liver/spleen uptake
- poor tissue penetration
- receptor scarcity
- instability in blood
"""
    )

    render_quiz_block("Materials & Targets Quiz (Section 1)", QUIZZES["S1"])


# ======================================================================
# SECTION 2 — Design Nanoparticle
# ======================================================================
with st.expander("2) Design Nanoparticle — Turning an idea into a controlled concept 🧪", expanded=False):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> You can adjust key nanoparticle parameters and explain how each parameter changes behavior and risk.
You also know how to avoid “random tuning”.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### Why this module exists
This is where NanoBio Studio becomes a real learning tool:
you will adjust controllable parameters and see how choices influence simulation, safety, and cost.

Core design knobs (typical):
- **Size** (nm)
- **Surface charge** (zeta potential direction/magnitude)
- **Ligand / targeting** (none vs specific)
- **Payload** (drug type, dose assumptions)
- **Release behavior** (fast vs slow)
- Sometimes: **PDI**, **stealth/steric stabilization**, etc.

### How to use it (a safe student workflow)
Use this simple rule:

> Change **one major parameter at a time**, then observe the effect.

Recommended order for beginners:
1) Start with a reasonable baseline size (mid-range).
2) Keep charge moderate (avoid extremes).
3) Add ligand only after you understand baseline behavior.
4) Adjust release profile after delivery curves make sense.

### What to look for (meaningful learning signals)
- If you reduce size: do you see changes in delivery speed/clearance?
- If you increase charge magnitude: do you see safety score change?
- If you add ligand: do you see tissue uptake improve in simulation (if modeled)?
- Does your design still look feasible and not overly complex?

### Common mistakes (student-friendly)
**Mistake A: “Everything at maximum”**  
Some students increase targeting, charge, dose, and complexity all at once.
Result: unsafe + expensive + unrealistic.

Fix:
- Choose ONE priority (e.g., safety-first)
- Make other parameters moderate

**Mistake B: Not recording what changed**  
Fix: Write a small log in your notes:
- “Design v1: size=..., charge=..., ligand=..., release=...”
- “Design v2: changed size only…”

**Mistake C: Confusing ligand with “magic”**  
Ligand helps targeting but does not guarantee success. It can also increase immune recognition and cost.

### Mini exercise: Baseline vs improved design
1) Create a baseline design (simple, moderate parameters).
2) Create an “improved” design that changes only ONE variable.
3) Predict what will happen before you simulate:
   - “If I make it smaller, I expect …”
   - “If I add ligand, I expect …”
"""
    )

    st.markdown(
        """
<div class="nb-callout-warn">
<b>Important:</b> A “good design” is not the most complex design.
A good design is a balanced one that matches a goal and can be justified.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Checkpoints")
    section_check("S2", "chk_1", "I created a baseline design with moderate parameters.")
    section_check("S2", "chk_2", "I changed only one key parameter to see its effect.")
    section_check("S2", "chk_3", "I wrote a short prediction before simulating (what I expect to happen).")

    st.markdown("### Practical examples (non-technical)")
    st.markdown(
        """
- **Safety-first student design:** moderate size, mild charge, minimal ligand complexity.
- **Targeting-first design:** add ligand, but keep charge mild and dose controlled.
- **Cost-limited design:** avoid rare materials, avoid too many synthesis steps.
"""
    )

    render_quiz_block("Design Nanoparticle Quiz (Section 2)", QUIZZES["S2"])


# ======================================================================
# SECTION 3 — Delivery Simulation (PK/PD-lite)
# ======================================================================
with st.expander("3) Delivery Simulation (PK/PD-lite) — Reading curves like a scientist 📈", expanded=False):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> You can interpret plasma vs tissue curves, and explain what changes might improve delivery.
You also learn how not to over-interpret a simplified model.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### Why this module exists
In drug delivery, **time matters**.
Even if a payload reaches tissue, it must reach it:
- in the right amount
- at the right time
- for long enough

A simplified PK/PD-lite simulator helps students compare “design A vs design B” based on concentration curves.

### Typical outputs you see
- **Plasma concentration curve** (blood exposure)
- **Tissue concentration curve** (target exposure)
- Sometimes: release profile, decay, or retention assumptions

### How to use it (student steps)
1) Choose a design you built in the previous module.
2) Run the simulation.
3) Observe:
   - Peak level (how high)
   - Time to peak (how fast)
   - Area under curve (overall exposure)
   - Tissue vs plasma balance

### What to look for (interpretation guide)
If tissue stays low:
- uptake might be weak
- targeting may not be effective
- size/charge may be suboptimal
- barriers may dominate

If plasma stays high for long:
- could indicate long circulation (good sometimes)
- could also indicate slow clearance (risk depends on toxicity)

If curves are unstable or weird:
- your parameters may be unrealistic
- check inputs (dose too high, extreme values, etc.)

### Common mistakes
**Mistake A: “The curve is high so it must be best.”**  
Not always. High plasma may mean off-target risk.

**Mistake B: Forgetting the target**  
A tumor-targeted system should ideally show improved tissue exposure vs baseline.

**Mistake C: Treating simplified simulation as real human trial**  
This is a conceptual simulator. Use it to learn comparative reasoning, not to claim clinical results.

### Mini exercise: Curve reading practice
After running two designs:
- Which design improved tissue exposure the most?
- Which design increased plasma exposure (possible off-target)?
Write one sentence conclusion:
- “Design B increases tissue exposure but also increases plasma exposure; we should verify safety next.”
"""
    )

    st.markdown(
        """
<div class="nb-callout-good">
<b>Instructor-friendly tip:</b> When you submit assignments, include a screenshot of the curves and a 2–3 bullet interpretation.
This shows understanding and earns marks.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Checkpoints")
    section_check("S3", "chk_1", "I ran the simulation for at least one design.")
    section_check("S3", "chk_2", "I compared two designs (baseline vs modified).")
    section_check("S3", "chk_3", "I wrote a short interpretation of plasma vs tissue curves.")

    render_quiz_block("Delivery Simulation Quiz (Section 3)", QUIZZES["S3"])


# ======================================================================
# SECTION 4 — Toxicity & Safety
# ======================================================================
with st.expander("4) Toxicity & Safety — Thinking responsibly (and professionally) 🛡️", expanded=False):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> You can explain why safety scoring exists, what inputs influence risk, and how to reduce risk logically.
You also learn to talk about safety in a professional way (not fear-based, but evidence-based).
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### Why this module exists
In real research, safety is not optional.
Even if a design delivers well, it can fail due to toxicity, immune response, or off-target accumulation.

NanoBio Studio uses **heuristic risk scoring** to teach safety thinking early:
- size extremes can cause clearance issues or tissue damage risk
- extreme charge can cause non-specific binding and cell stress
- high dose increases risk
- high PDI (wide distribution) may increase unpredictability
- lack of stabilization can cause aggregation

### How to use it (student workflow)
1) Run safety scoring for your baseline design.
2) Run safety scoring for your modified design.
3) Compare:
   - Which factor increased risk?
   - Which change reduces risk with minimal loss of performance?

### What to look for (good student habits)
- Identify the top 1–2 contributors to risk (don’t chase everything at once).
- Make a targeted fix:
  - reduce dose slightly
  - avoid extreme charge
  - aim for reasonable PDI
  - add stabilization if appropriate

### Common mistakes
**Mistake A: Ignoring safety because “it’s just a student project.”**  
In UAE universities and research culture, safety mindset is strongly valued.

**Mistake B: Thinking “safe = no effect.”**  
A good design is safe *and* effective. Balance is the skill.

**Mistake C: Comparing scores without context**  
A score is a signal. You still need reasoning:
- why risk changes
- what is the trade-off

### Mini exercise: Safety improvement plan
Write a small safety plan:
- “Risk contributors: ________”
- “Change we will try: ________”
- “Expected outcome: lower risk score with minimal loss of tissue delivery”
"""
    )

    st.markdown(
        """
<div class="nb-callout-warn">
<b>Professional language tip:</b> Avoid absolute claims like “This is safe.”  
Better: “This design shows a lower heuristic risk score under the current assumptions; further validation is needed.”
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Checkpoints")
    section_check("S4", "chk_1", "I ran safety scoring for baseline and modified design.")
    section_check("S4", "chk_2", "I identified 1–2 drivers of risk.")
    section_check("S4", "chk_3", "I proposed a clear change to reduce risk.")

    render_quiz_block("Toxicity & Safety Quiz (Section 4)", QUIZZES["S4"])


# ======================================================================
# SECTION 5 — Cost Estimator
# ======================================================================
with st.expander("5) Cost Estimator — Thinking like a project leader 💰", expanded=False):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> You can interpret cost results correctly as relative complexity, and explain what increases cost.
You can also suggest a cost-limited design strategy.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### Why this module exists
In real life, the “best design on paper” can fail if it is:
- too expensive to produce
- too complex to scale
- too difficult to control quality

For students, cost estimation teaches an important mindset:
**innovation must also be feasible**.

### How to use it (student steps)
1) Run cost estimation for your baseline design.
2) Run cost estimation for your modified design (especially if you added a ligand or complex material).
3) Compare:
   - Did complexity increase a lot?
   - Is the improvement in delivery worth the extra complexity?

### What to look for
- Is the cost/complexity index rising because you added steps or rare materials?
- Is it rising because tighter size control is assumed?
- Does your design still fit the “scenario” you are working under (e.g., university lab capability)?

### Common mistakes
**Mistake A: Treating cost estimator as exact AED pricing**  
At early stage, it’s an index for comparison.

**Mistake B: Ignoring cost completely**  
In government-funded or industry-linked projects, cost feasibility matters.

**Mistake C: Making the design too “luxury”**  
Students sometimes choose rare materials and complex layers without justification.

### Mini exercise: Cost-limited strategy
Imagine your lab has limited capability (typical student setting).
Write two choices that keep cost/complexity under control:
- keep materials common
- avoid multi-layer complexity
- avoid extreme precision requirements
"""
    )

    st.markdown(
        """
<div class="nb-callout-good">
<b>UAE context:</b> When presenting to sponsors or institutions, the ability to explain feasibility and scaling is highly respected.
Cost thinking is part of professional research maturity.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Checkpoints")
    section_check("S5", "chk_1", "I ran cost estimation for baseline and modified designs.")
    section_check("S5", "chk_2", "I can explain why cost/complexity changed.")
    section_check("S5", "chk_3", "I suggested at least one cost-limiting design decision.")

    render_quiz_block("Cost Estimator Quiz (Section 5)", QUIZZES["S5"])


# ======================================================================
# SECTION 6 — Protocol Generator
# ======================================================================
with st.expander("6) Protocol Generator — Turning design into an experiment plan 🧾", expanded=False):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> You can generate a protocol outline and understand what it contains: steps, checkpoints, controls, and measurements.
You also learn how to use protocols to communicate professionally.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### Why this module exists
A nanoparticle “design” is not enough.
In research, you need a plan to test it.

The Protocol Generator helps you create an SOP-style outline:
- preparation steps
- synthesis outline (high-level)
- characterization checkpoints (size, PDI, charge)
- release testing steps
- safety considerations
- documentation

### How to use it (student steps)
1) Confirm your design settings first (size/charge/ligand/payload).
2) Open Protocol Generator.
3) Generate the protocol outline.
4) Read it carefully and ask:
   - What measurements are included?
   - Are controls mentioned?
   - Do the steps match my design complexity?

### What to look for (quality checklist)
A good protocol outline usually includes:
- materials list
- step sequence
- at least 2–3 checkpoints
- controls (negative/positive)
- data recording (tables, file names, logs)

### Common mistakes
**Mistake A: Exporting protocol without reading**  
Fix: highlight 3 checkpoints and explain them.

**Mistake B: No controls**  
Fix: add at least one control (e.g., blank nanoparticle without payload).

**Mistake C: No acceptance criteria**  
Fix: define acceptable ranges (e.g., target size range, acceptable PDI threshold).

### Mini exercise: Protocol review
After generating a protocol:
- Identify 3 checkpoints.
- For each checkpoint, write:
  - what you measure
  - why you measure it
  - what “good” might look like
"""
    )

    st.markdown(
        """
<div class="nb-callout-warn">
<b>Reminder:</b> Protocol generator is an educational assistant. Real labs must follow institutional SOPs, safety standards, and approvals.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Checkpoints")
    section_check("S6", "chk_1", "I generated a protocol outline and reviewed it.")
    section_check("S6", "chk_2", "I identified at least 3 checkpoints/measurements.")
    section_check("S6", "chk_3", "I ensured controls and recording steps are included or added notes about them.")

    render_quiz_block("Protocol Generator Quiz (Section 6)", QUIZZES["S6"])


# ======================================================================
# SECTION 7 — AI Co-Designer
# ======================================================================
with st.expander("7) AI Co-Designer — Scenario mode, explainability, and governance 🤖📋", expanded=False):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> You can use AI responsibly to explore options under constraints, compare reasoning, and generate explainable evidence.
You also learn to treat AI suggestions as proposals to review, not commands to follow.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### Why AI Co-Designer exists
Manual design is powerful, but it can be slow.
AI can help you:
- explore more options quickly
- consider trade-offs you might miss
- explain design choices in a structured way
- generate audit/governance documentation for review

But in professional settings (including UAE research institutions), AI must be used responsibly:
- explainability matters
- auditability matters
- human review matters

### Core components you’ll see
**1) Scenario / Policy Mode**  
You tell the AI:
- the goal (e.g., safety-first, cost-limited, targeting-first)
- constraints (e.g., materials available in a university lab)
- what you care about most (rank priorities)

**2) AI Exploration Summary**  
A structured summary of options, trade-offs, and recommendations.

**3) AI vs Manual Baseline**  
A comparison: what you did manually vs what AI suggests.

**4) Explainability**  
The “why” behind suggestions:
- which factors were considered
- which trade-offs exist
- why a certain design is suggested

**5) Audit & Governance Export**  
A report you can show to supervisors or reviewers:
- scenario constraints
- assumptions
- rationale
- outputs

### How to use it (student-safe workflow)
1) Start with manual design (baseline).
2) Open AI Co-Designer.
3) Choose a scenario:
   - “Safety-first student lab”
   - “Cost-limited scale”
   - “Targeting priority”
4) Read AI output carefully.
5) Compare against baseline and ask:
   - What did AI change?
   - Is the change justified?
   - Does it introduce new safety or cost problems?
6) Export governance report if required by your coursework.

### Common mistakes
**Mistake A: Copy-paste AI output without thinking**  
Fix: rewrite the recommendation in your own words and justify it.

**Mistake B: Asking AI vague questions**  
Fix: provide constraints and goals. Example:
- “Design for tumor targeting, but keep safety moderate and avoid expensive rare materials.”

**Mistake C: Treating AI as a final authority**  
Fix: treat AI as a brainstorming partner. Final decision is human-reviewed.

### Mini exercise: Scenario writing
Write a scenario prompt in your own words:
- “We are a student lab in UAE. We want safe, feasible nanoparticles for target X, with limited budget. Propose 2 options and explain trade-offs.”
"""
    )

    st.markdown(
        """
<div class="nb-callout-good">
<b>Governance mindset:</b> The goal is not to “prove AI is right”.
The goal is to show transparent reasoning, review, and responsible decision-making.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Checkpoints")
    section_check("S7", "chk_1", "I ran AI Co-Designer in at least one scenario.")
    section_check("S7", "chk_2", "I compared AI suggestion against my manual baseline.")
    section_check("S7", "chk_3", "I can explain one AI trade-off in my own words (not copy-paste).")
    section_check("S7", "chk_4", "I understand why audit/export can be important in universities and government-funded programs.")

    render_quiz_block("AI Co-Designer Quiz (Section 7)", QUIZZES["S7"])


# ======================================================================
# SECTION 8 — Integrated Workflow + AI vs Manual Baseline
# ======================================================================
with st.expander("8) Full Workflow — From idea to protocol + baseline comparison 🧭", expanded=False):
    st.markdown(
        """
<div class="nb-note">
<b>Learning outcome:</b> You can perform the full flow in the app and produce a clean “student deliverable”:
design summary + simulation interpretation + safety + cost + protocol + AI baseline comparison.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
### The full NanoBio Studio student workflow (recommended)
Follow this sequence (and keep your work clean):

**Step 1 — Materials & Targets**
- choose material + target
- write 1–2 sentence target statement

**Step 2 — Design Nanoparticle**
- build baseline design
- change one variable to create a second design

**Step 3 — Delivery Simulation**
- simulate both designs
- compare tissue vs plasma

**Step 4 — Toxicity & Safety**
- compare risk scores
- identify top risk drivers

**Step 5 — Cost Estimator**
- compare complexity/cost index
- justify if complexity increase is worth it

**Step 6 — Protocol Generator**
- generate protocol outline
- highlight checkpoints and controls

**Step 7 — AI Co-Designer**
- run scenario mode
- compare AI suggestions vs manual baseline
- export governance report if needed

### What a good student submission looks like
A good submission is short but meaningful. For example:
- a small table of design parameters
- 1–2 screenshots of curves + interpretation
- safety and cost comparison (2–3 bullets)
- protocol excerpt + checkpoints
- AI baseline comparison summary (what changed and why)

### Common mistakes
**Mistake A: Submitting too many designs**  
Fix: submit 2 designs: baseline and improved.

**Mistake B: No interpretation**  
Fix: always write “what it means”.

**Mistake C: No trade-off discussion**  
Fix: include at least one trade-off:
- “More targeting increases cost; we chose moderate targeting due to feasibility.”

### Mini exercise: One-page report structure
Try writing your report as:
1) Target statement
2) Baseline design
3) Modified design
4) Simulation interpretation
5) Safety + cost notes
6) Protocol highlights
7) AI baseline comparison
"""
    )

    st.markdown(
        """
<div class="nb-callout-good">
<b>Excellent habit:</b> Treat your work like a mini research memo. Clear structure often matters as much as the final numbers.
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Checkpoints")
    section_check("S8", "chk_1", "I completed the full workflow at least once (baseline + modified).")
    section_check("S8", "chk_2", "I created a clean summary of results (not messy screenshots only).")
    section_check("S8", "chk_3", "I can explain at least one trade-off clearly.")
    section_check("S8", "chk_4", "I understand why manual baseline remains valuable even with AI.")

    render_quiz_block("Integrated Workflow Quiz (Section 8)", QUIZZES["S8"])


# ======================================================================
# Wrap-up Panel — Certificate-style completion & study tips
# ======================================================================
st.markdown("")
st.markdown(
    """
<div class="nb-card">
<b>🏁 Wrap-up</b><br>
You now have a full guided understanding of NanoBio Studio modules — manual design and AI co-design — with responsible interpretation.
</div>
""",
    unsafe_allow_html=True,
)

earned = int(st.session_state["tut_earned_points"])
pct = 0.0 if TOTAL_POINTS <= 0 else earned / TOTAL_POINTS

col1, col2 = st.columns([1.35, 1.65])
with col1:
    st.markdown('<div class="nb-card">', unsafe_allow_html=True)
    st.markdown("### Your learning progress")
    st.progress(min(1.0, max(0.0, pct)))
    st.markdown(f"- **Score:** {earned} / {TOTAL_POINTS}")
    st.markdown(f"- **Completion:** {int(pct * 100)}%")
    if pct >= 0.85:
        st.success("Excellent — you are ready to present NanoBio Studio confidently.")
    elif pct >= 0.6:
        st.info("Good progress — review sections where you missed quiz points.")
    else:
        st.warning("Keep going — open each section, do the mini exercises, and complete quizzes.")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="nb-card">', unsafe_allow_html=True)
    st.markdown("### Study tips (UAE university-friendly)")
    st.markdown(
        """
- **Don’t rush to AI first.** Start with a manual baseline so you understand the logic.
- **Use one-variable changes** when learning (size only, charge only, ligand only).
- **Always interpret curves** in words: “tissue low vs plasma high” must mean something.
- **Speak professionally**: “under assumptions” / “heuristic risk” / “requires validation”.
- **Keep a clean report format**: target statement → design → results → trade-offs.
"""
    )
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("")
# st.caption(
    # "Tutorial page includes scoring, reset logic, and anti-double-scoring locks per question. "
    # "If you want, I can also add: section-level badges, downloadable completion summary, and instructor mode (answer key export)."
# )
