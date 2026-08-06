"""
AI Co-Designer — Policy-Aware Optimization

STATUS: NOT OPERATIONAL (quarantined under DECISION 7, Phase 2 Step 1)
=====================================================================
This screen previously displayed a complete, convincing optimisation report in
which **every result was fabricated**. No optimisation ever ran. Specifically it
showed:

  * five "Mock candidate designs" ranked by fixed scores
    94.2 / 91.5 / 89.8 / 87.3 / 84.9 -- constants, identical for every input;
  * a "why these were suggested" rationale assembled from static text;
  * mock parameter distributions and a fabricated Pareto front;
  * fabricated headline metrics ("Best Overall Score 94.2/100",
    "Feasible Designs 387/500", "+5.1 vs baseline");
  * fabricated feature-importance and parameter-sensitivity curves;
  * a fabricated AUDIT TRAIL with a hard-coded timestamp and fabricated
    constraint-violation counts -- governance evidence for a run that never
    happened.

Root cause: the real optimiser (`ai_engine`) is un-importable (DEFECT-D7 --
`ai_engine/__init__.py` imports a `nanobio_studio.*` package layout that does
not exist), so its `optuna` dependency is reachable by nothing.

Per DECISION 7 the fabricated output is removed rather than displayed, and this
page now shows a clearly labelled non-operational status. The feature remains
part of the intended platform and returns once the engine is repaired and
tested -- separately authorised work, explicitly NOT part of Step 1.

The pre-correction file is preserved verbatim, clearly labelled as synthetic
demonstration data, at:

    legacy_streamlit/quarantined/7_AI_Co_Designer.legacy.py

It lives outside `pages/` so Streamlit will not route to it.
"""

import streamlit as st

# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
st.set_page_config(page_title="NanoBio Studio - AI Co-Designer", layout="wide")

st.title("🤖 AI Co-Designer — Policy-Aware Optimization")

# ---------------------------------------------------------------------------
# Authentication gate (unchanged from the rest of the application)
# ---------------------------------------------------------------------------
if not st.session_state.get("logged_in"):
    st.warning("⚠️ Please log in first")
    st.info("You need to be logged in to access this page.")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔐 Go to Login", type="primary", use_container_width=True):
            st.query_params.clear()
            st.switch_page("Login.py")

    st.stop()

# ---------------------------------------------------------------------------
# Non-operational status (DECISION 7.5)
# ---------------------------------------------------------------------------

st.error(
    "### AI Co-Designer is not yet operational\n\n"
    "This feature cannot currently generate optimised nanoparticle designs."
)

st.markdown(
    """
The optimisation engine that powers this screen is not available in this build,
so **no candidate designs, scores, rankings, or trade-off curves can be
produced**.

Earlier versions of this page displayed a full set of results — ranked
candidates, score metrics, sensitivity charts and an audit trail. **None of it
came from an optimisation run.** The values were fixed placeholders that did not
change with your design inputs. They have been removed rather than shown as
results, so that placeholder numbers cannot be mistaken for findings, cited, or
saved alongside real simulation records.
"""
)

st.info(
    "**What still works.** Every other part of the platform is unaffected. "
    "Disease selection, design parameters, simulation, safety assessment and "
    "report generation all continue to run normally, and their results are "
    "produced by real calculations."
)

with st.expander("Why is it unavailable? (technical detail)"):
    st.markdown(
        """
The optimisation package (`ai_engine`) cannot be loaded. Its package
initialiser imports modules under a `nanobio_studio.*` path that does not exist
in this repository, so importing it fails immediately. Because nothing can
import it, the `optuna` optimisation library it depends on is never reached.

This was identified during the scientific migration audit and is tracked as
**DEFECT-D6** (fabricated results presented as optimisation output) and
**DEFECT-D7** (optimiser un-importable).
"""
    )

with st.expander("What will it do when restored?"):
    st.markdown(
        """
The AI Co-Designer remains part of the planned platform. Restoring it requires,
at minimum:

1. repairing the `ai_engine` package so it imports;
2. running real Optuna optimisation over declared objective functions and
   constraints;
3. fixed random seeds wherever reproducibility is achievable;
4. provenance for every candidate — which run produced it, under which
   objectives, weights and constraints;
5. persisting optimisation runs so results can be audited and reproduced;
6. generating explanations from actual parameter and objective contributions,
   never from static text;
7. tests proving results come from execution rather than constants.

Until all of that is in place and reviewed, no candidate designs will be shown.
"""
    )

st.divider()

st.caption(
    "Research use only. When this feature is restored, its outputs will remain "
    "computational research-planning results: not experimentally validated, not "
    "clinically validated, not regulatory approval predictions, and not a "
    "substitute for wet-lab testing. NanoBio Studio positions AI as a "
    "transparent research co-designer, not an oracle."
)
