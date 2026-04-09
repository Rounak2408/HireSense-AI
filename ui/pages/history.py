"""History — screenings & personal analyses."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from database.models import User
from services.analytics_service import resume_analysis_history, screening_history


def render(db: Session, user: User) -> None:
    st.markdown("### History")
    tab_a, tab_b = st.tabs(["Role screenings", "Resume analyses"])
    with tab_a:
        if user.role != "recruiter":
            st.info("Screening history is available to recruiter accounts.")
        else:
            hist = screening_history(db, user.id, limit=60)
            if not hist:
                st.caption("No jobs yet.")
            for h in hist:
                with st.expander(f"{h['title']} · {h['created_at']}"):
                    st.write(f"Candidates: {h['candidates']} · Best score: {h['best_score']}")
    with tab_b:
        rows = resume_analysis_history(db, user.id, limit=40)
        if not rows:
            st.caption("No personal analyses yet — try Resume Checker.")
        for r in rows:
            with st.expander(f"{r['match_percent']}% · {r['strength']} · {r['created_at']}"):
                st.caption(r["preview_jd"])
