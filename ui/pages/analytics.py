"""Analytics — distributions & skill gaps."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy.orm import Session

from database.models import JobDescription, User
from services.analytics_service import candidate_rankings
from services.insights_service import cohort_skill_stats
from ui.components import empty_state, page_header, skill_chips


def render(db: Session, user: User) -> None:
    if user.role not in {"recruiter", "admin"}:
        st.warning("Recruiter access only.")
        return

    page_header(
        "Analytics",
        "Match distribution, cohort strength, and gap analysis across your slate.",
        pill="Insights",
    )

    jobs = (
        db.query(JobDescription)
        .filter(JobDescription.user_id == user.id)
        .order_by(JobDescription.created_at.desc())
        .all()
    )
    if not jobs:
        empty_state(
            "No analytics yet",
            "Analytics unlock after you screen candidates for a role.",
            "Go to **Upload** → create role → upload resumes → screen.",
        )
        return
    labels = {f"{j.title} (#{j.id})": j.id for j in jobs}
    choice = st.selectbox("Job", options=list(labels.keys()))
    job_id = labels[choice]

    rows = candidate_rankings(db, job_id)
    if not rows:
        empty_state(
            "No screening results",
            "This role has no scored candidates yet.",
            "Upload resumes and re-score the role from **Upload**.",
        )
        return

    df = pd.DataFrame(rows)
    tmpl = "plotly_dark" if st.session_state.get("theme") == "dark" else "plotly_white"

    stats = cohort_skill_stats(db, job_id)
    st.markdown("#### Cohort callouts")
    ca, cb = st.columns([1.1, 0.9])
    with ca:
        st.markdown(
            "<div class='hs-card'><span class='hs-badge'>Signal</span>"
            "<h4 style='margin-top:0.55rem;'>Top gaps</h4>"
            "<div class='hs-muted'>Skills missing most frequently across the slate.</div></div>",
            unsafe_allow_html=True,
        )
        skill_chips([s for s, _ in (stats.get("top_missing") or [])], limit=18)
    with cb:
        st.markdown(
            "<div class='hs-card'><span class='hs-badge'>Signal</span>"
            "<h4 style='margin-top:0.55rem;'>Shortlist strengths</h4>"
            "<div class='hs-muted'>Skills that show up repeatedly among top candidates.</div></div>",
            unsafe_allow_html=True,
        )
        skill_chips([s for s, _ in (stats.get("shortlist_strengths") or [])], limit=18)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(df.head(15), x="name", y="match_score", color="shortlist", title="Top matches")
        fig.update_layout(template=tmpl, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.box(df, y="match_score", points="all", title="Match score spread")
        fig2.update_layout(template=tmpl, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    # Skill gap aggregation
    from collections import Counter

    miss = Counter()
    hit = Counter()
    for r in rows:
        for s in r.get("missing_skills") or []:
            miss[s] += 1
        for s in r.get("matched_skills") or []:
            hit[s] += 1
    top_miss = miss.most_common(12)
    top_hit = hit.most_common(12)
    if top_miss:
        dm = pd.DataFrame(top_miss, columns=["skill", "missing_count"])
        fig3 = px.bar(dm, x="skill", y="missing_count", title="Most common gaps across slate")
        fig3.update_layout(template=tmpl, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3, use_container_width=True)
    if top_hit:
        dh = pd.DataFrame(top_hit, columns=["skill", "matched_count"])
        fig4 = px.bar(dh, x="skill", y="matched_count", title="Strongest shared skills")
        fig4.update_layout(template=tmpl, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("#### Score components (averages)")
    st.dataframe(
        pd.DataFrame(
            {
                "avg_skill": [df["skill_score"].mean()],
                "avg_experience": [df["experience_score"].mean()],
                "avg_education": [df["education_score"].mean()],
            }
        ),
        hide_index=True,
    )
