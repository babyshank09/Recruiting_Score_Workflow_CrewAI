import asyncio
import os
import re
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st
from pydantic import BaseModel, Field
from uuid import uuid4

from crewai.flow.flow import Flow, listen, or_, router, start

from recruiter_score_flow.constants.constants import JOB_DESCRIPTION
from recruiter_score_flow.crews.recruiting_response_crew.recruiting_response_crew import (
    RecruitingResponseCrew,
)
from recruiter_score_flow.crews.recruiting_score_crew.recruiting_score_crew import (
    RecruitingScoreCrew,
)
from recruiter_score_flow.schema.schema import Candidate, CandidateScore, ScoredCandidate
from recruiter_score_flow.utils.candidate_utils import combine_candidates_with_scores


class RecruitingScoreState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    candidates: List[Candidate] = []
    candidate_score: List[CandidateScore] = []
    hydrated_candidates: List[ScoredCandidate] = []
    scoring_feedback: str = " "


class RecruitingScoreFlow(Flow[RecruitingScoreState]):
    initial_state = RecruitingScoreState

    @start()
    def load_candidates(self):
        csv_filepath = Path(__file__).parent / "database" / "candidates.csv"
        df = pd.read_csv(csv_filepath)
        candidates = []
        for row in df.to_dict(orient="records"):
            row["id"] = str(row["id"])
            candidates.append(Candidate(**row))
        self.state.candidates = candidates

    @listen(or_(load_candidates, "scored_candidates_feedback"))
    async def score_candidates(self):
        tasks = []

        async def score_single_candidate(candidate: Candidate):
            result = await RecruitingScoreCrew().crew().kickoff_async(
                inputs={
                    "candidate_id": candidate.id,
                    "name": candidate.name,
                    "bio": candidate.bio,
                    "job_description": st.session_state.job_description,
                    "additional_instructions": self.state.scoring_feedback,
                }
            )
            self.state.candidate_score.append(result.pydantic)

        for candidate in self.state.candidates:
            tasks.append(asyncio.create_task(score_single_candidate(candidate)))

        await asyncio.gather(*tasks)

    @listen("generate_emails")
    async def write_and_save_emails(self):
        top_ids = {c.id for c in self.state.hydrated_candidates[:3]}
        output_dir = Path(__file__).parent / "output" / "email_responses"
        output_dir.mkdir(parents=True, exist_ok=True)

        async def write_email(candidate):
            result = await (
                RecruitingResponseCrew()
                .crew()
                .kickoff_async(
                    inputs={
                        "candidate_id": candidate.id,
                        "name": candidate.name,
                        "bio": candidate.bio,
                        "proceed_with_candidate": candidate.id in top_ids,
                    }
                )
            )
            safe_name = re.sub(r"[^a-zA-Z0-9_\- ]", "", candidate.name)
            file_path = output_dir / f"{safe_name}.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(result.raw)
            return f"Email saved for {candidate.name}"

        tasks = [asyncio.create_task(write_email(c)) for c in self.state.hydrated_candidates]
        await asyncio.gather(*tasks)


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


st.set_page_config(
    page_title="Recruiting Score Flow",
    page_icon="📂",
    layout="wide",
)

defaults = {
    "stage": "init",
    "flow": None,
    "top_3": [],
    "email_results": [],
    "scoring_feedback": "",
    "log": [],
    "job_description": JOB_DESCRIPTION,   # pre-filled from constants
    "csv_saved": False,                   # tracks whether CSV has been written to disk
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def log(msg: str):
    st.session_state.log.append(msg)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("Settings & Inputs")
    # st.caption("Powered by CrewAI + Streamlit")
    # st.divider() 


    st.subheader("📋 Job Description")
    job_desc_input = st.text_area(
        label="Edit the job description",
        value=st.session_state.job_description,
        height=200,
        key="job_desc_textarea",
        help="Pre-filled from constants.py — edit freely before running.",
    )
    st.session_state.job_description = job_desc_input

    st.divider()

    st.subheader("📂 Candidates CSV")

    uploaded_file = st.file_uploader(
        label="Upload the candidates csv file",
        type=["csv"],
        help="Must contain columns: id, name, email, bio, skills",
    )

    if uploaded_file is not None:
        try:
            preview_df = pd.read_csv(uploaded_file)
            # st.caption(f"✅ {len(preview_df)} candidates detected. Displaying prevview of first 5 rows:")
            # st.dataframe(preview_df.head(5), use_container_width=True, hide_index=True)

            db_dir = Path(__file__).parent / "database"
            db_dir.mkdir(parents=True, exist_ok=True)
            csv_path = db_dir / "candidates.csv"

            uploaded_file.seek(0)
            csv_path.write_bytes(uploaded_file.read())

            st.session_state.csv_saved = True
            st.success(f"Saved → `database/candidates.csv`")

        except Exception as e:
            st.error(f"❌ Could not read CSV: {e}")
            st.session_state.csv_saved = False
    else:
        existing_csv = Path(__file__).parent / "database" / "candidates.csv"
        if existing_csv.exists():
            st.caption("ℹ️ Using existing `database/candidates.csv`")
            st.session_state.csv_saved = True
        else:
            st.warning("Upload a candidates CSV to proceed.")
            st.session_state.csv_saved = False

    st.divider()

    # if st.session_state.log:
    #     st.subheader("📝 Activity Log")
    #     for entry in st.session_state.log[-20:]:
    #         st.caption(entry)
    #     st.divider()

    if st.button("🔄 Reset Everything", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 0 – Init / Load & Score
# ══════════════════════════════════════════════════════════════════════════════
st.title("📂 Recruiting Score Workflow") 
st.caption("An AI-powered workflow application to score candidates and generate personalized emails")
st.divider() 

with st.expander("ℹ️ About this app", expanded=False): 
    st.write(
        """
        This app demonstrates a recruiting workflow where candidates are scored against a job description using AI, then personalized emails are generated for the top candidates. 

        **Steps:**
        1. Upload a CSV of candidates (or use the default one).
        2. Click "Run Scoring" to have the AI evaluate each candidate against the job description.
        3. Review the top candidates and optionally provide feedback to re-score.
        4. Generate personalized emails for all candidates based on their scores.

        All data is stored locally in the `database` and `output` folders for easy access.
        """
    )
st.divider() 

if st.session_state.stage == "init":
    st.info("Step 1: Load & Score Candidates")

    if not st.session_state.job_description.strip():
        st.warning("⚠️ Please enter a job description in the sidebar.")
        st.stop()

    if not st.session_state.csv_saved:
        st.warning("⚠️ Please upload a candidates CSV in the sidebar.")
        st.stop()

    st.write("Click **Run Scoring** to load candidates and score them against the job description.")

    csv_path = Path(__file__).parent / "database" / "candidates.csv"
    preview_df = pd.read_csv(csv_path)
    with st.expander(f"👁️ Preview: {len(preview_df)} candidates loaded", expanded=False):
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

    if st.button("▶️ Run Scoring", type="primary", use_container_width=True):
        with st.spinner("Loading candidates and running AI scoring… this may take a minute."):
            try:
                flow = RecruitingScoreFlow()
                flow.state.scoring_feedback = st.session_state.scoring_feedback

                flow.load_candidates()
                log(f"Loaded {len(flow.state.candidates)} candidates.")

                run_async(flow.score_candidates())
                log(f"Scored {len(flow.state.candidate_score)} candidates.")

                flow.state.hydrated_candidates = combine_candidates_with_scores(
                    flow.state.candidates, flow.state.candidate_score
                )
                sorted_candidates = sorted(
                    flow.state.hydrated_candidates, key=lambda c: c.score, reverse=True
                )
                top_3 = sorted_candidates[:3]

                # Save output files for top-3
                output_dir = Path(__file__).parent / "output" / "selected_candidates"
                output_dir.mkdir(parents=True, exist_ok=True)
                for c in top_3:
                    data = (
                        f"ID: {c.id}\nName: {c.name}\nEmail: {c.email}\n"
                        f"Bio: {c.bio}\nSkills: {c.skills}\n"
                        f"Score: {c.score}\nReason: {c.reason}"
                    )
                    with open(output_dir / f"{c.name}.txt", "w") as f:
                        f.write(data)

                st.session_state.flow = flow
                st.session_state.top_3 = top_3
                st.session_state.stage = "scored"
                log("Scoring complete. Awaiting human review.")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error during scoring: {e}")
                st.exception(e)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 – Human-in-the-Loop review
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "scored":
    st.info("Step 2: Human Review")

    flow: RecruitingScoreFlow = st.session_state.flow
    top_3: List[ScoredCandidate] = st.session_state.top_3

    st.subheader("🏆 Top 3 Candidates")
    cols = st.columns(3)
    for i, (col, candidate) in enumerate(zip(cols, top_3)):
        with col:
            st.metric(label=candidate.name, value=f"Score: {candidate.score}")
            st.caption(f"**ID:** {candidate.id}")
            with st.expander("📄 Reason"):
                st.write(candidate.reason)

    st.divider()

    with st.expander("📊 Full Candidate Leaderboard", expanded=False):
        all_sorted = sorted(
            flow.state.hydrated_candidates, key=lambda c: c.score, reverse=True
        )
        rows = [
            {"Rank": i + 1, "Name": c.name, "Score": c.score, "Reason": c.reason}
            for i, c in enumerate(all_sorted)
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("⚡ Choose an Action")

    action = st.radio(
        "What would you like to do?",
        options=[
            "Proceed to write emails to the candidates",
            "Redo scoring with additional feedback",
            "Quit",
        ],
        index=0,
        horizontal=True,
    )

    if action == "Redo scoring with additional feedback":
        feedback = st.text_area(
            "Provide additional feedback for scoring:",
            placeholder="e.g. Prefer candidates with 5+ years in Python and prior startup experience.",
            height=100,
        )
        if st.button("🔁 Re-run Scoring", type="primary"):
            if not feedback.strip():
                st.warning("Please enter feedback before re-running.")
            else:
                st.session_state.scoring_feedback = feedback
                st.session_state.flow.state.scoring_feedback = feedback
                st.session_state.flow.state.candidate_score = []
                st.session_state.stage = "init"
                log(f"Re-scoring with feedback: {feedback[:80]}…")
                st.rerun()

    elif action == "Quit":
        if st.button("🛑 Confirm Quit"):
            st.warning("Application stopped. Refresh the page to restart.")
            st.stop()

    else:  
        if st.button("✉️ Generate Emails", type="primary"):
            with st.spinner("Writing personalised emails for all candidates…"):
                try:
                    run_async(flow.write_and_save_emails())
                    log("Emails generated and saved.")
                    st.session_state.stage = "emails_done"
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error generating emails: {e}")
                    st.exception(e)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 – Emails done
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.stage == "emails_done":
    st.success("✅ Workflow Completed: Emails successfully generated")
    st.info("All candidate emails have been written and saved to `output/email_responses/`.")

    output_dir = Path(__file__).parent / "output" / "email_responses"
    email_files = sorted(output_dir.glob("*.txt")) if output_dir.exists() else []

    if email_files:
        st.subheader("📨 Preview Emails")
        selected = st.selectbox(
            "Select a candidate to preview:",
            options=[f.stem for f in email_files],
        )
        if selected:
            file_path = output_dir / f"{selected}.txt"
            content = file_path.read_text(encoding="utf-8")
            st.text_area("Email Content", value=content, height=300)
            st.download_button(
                label="⬇️ Download Email",
                data=content,
                file_name=f"{selected}.txt",
                mime="text/plain",
            )
    else:
        st.info("No email files found in `output/email_responses/`.")

    st.divider()
    st.info("Click **Reset Everything** in the sidebar to start a new run.")
