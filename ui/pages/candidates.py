"""Candidate ranking, comparison, exports."""

from __future__ import annotations

from datetime import datetime

import streamlit as st
from sqlalchemy.orm import Session

from database.models import Candidate, JobDescription, User
from services.analytics_service import candidate_rankings
from services.export_service import ranked_candidates_csv, screening_report_text
from services.insights_service import build_smart_insights, cohort_skill_stats, job_summary
from ui.components import empty_state, insight_cards, kpi_card, page_header, progress_pct, skill_chips


def render(db: Session, user: User) -> None:
    if user.role != "recruiter":
        st.warning("Recruiter access only.")
        return

    page_header(
        "Candidates",
        "Ranked slate, side-by-side comparisons, and recruiter-ready exports.",
        pill="Recruiter Mode",
    )
    jobs = (
        db.query(JobDescription)
        .filter(JobDescription.user_id == user.id)
        .order_by(JobDescription.created_at.desc())
        .all()
    )
    if not jobs:
        empty_state(
            "No roles yet",
            "Candidate rankings appear after you create a job description and upload resumes.",
            "Go to **Upload** → paste JD → upload resumes → click **Save job & ingest resumes**.",
        )
        return

    labels = {f"{j.title} (#{j.id})": j.id for j in jobs}
    keys = list(labels.keys())
    default_id = st.session_state.get("selected_job_id")
    default_label = next((k for k, v in labels.items() if v == default_id), keys[0])
    idx = keys.index(default_label) if default_label in keys else 0
    choice = st.selectbox("Job", options=keys, index=idx)
    job_id = labels[choice]
    st.session_state["selected_job_id"] = job_id

    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    with st.expander("Job description & extracted requirements", expanded=False):
        st.text_area("JD text", job.raw_text if job else "", height=220, disabled=True, key="jd_view")
        st.caption("Skills inferred from the JD lexicon + NLP patterns")
        skill_chips(list((job.extracted_skills if job else []) or []))
    rows = candidate_rankings(db, job_id)
    if not rows:
        empty_state(
            "No screening results yet",
            "This role has no ranked slate. Add resumes to this role (or re-score) from Upload.",
            "Upload → select this job → **Add resumes to selected job** → (optional) **Re-score selected job**.",
        )
        return

    for i, r in enumerate(rows, start=1):
        if r.get("rank") is None:
            r["rank"] = i

    summ = job_summary(db, job_id)
    stats = cohort_skill_stats(db, job_id)
    st.markdown("#### Role pulse")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Candidates", str(summ.get("candidate_count", 0)), "Indexed", tone="neutral")
    with k2:
        kpi_card("Average match", str(summ.get("avg_match", 0)), "Cohort", tone="neutral")
    with k3:
        kpi_card("Top score", str(summ.get("top_score", 0)), "Peak", tone="positive" if (summ.get("top_score", 0) or 0) >= 72 else "neutral")
    with k4:
        kpi_card("Slate trend", stats.get("trend", "flat").replace("-", " ").title(), None, tone="warning" if stats.get("trend") == "polarized" else "neutral")

    st.markdown("#### Smart insights")
    insights = build_smart_insights(db, job_id)
    insight_cards(insights)

    st.markdown("#### Ranked slate")
    show = st.slider("Show top N", min_value=5, max_value=min(50, len(rows)), value=min(15, len(rows)))
    filter_q = st.text_input("Search name/email", "")

    filtered = [r for r in rows if filter_q.lower() in (r.get("name") or "").lower() or filter_q.lower() in (r.get("email") or "").lower()]
    view = filtered[:show]

    if not view:
        empty_state("No matches", "No candidates match your search filter.", "Clear the search box to see the full slate.")
        return

    for r in view:
        badge = "Shortlist" if r.get("shortlist") else "Candidate"
        with st.expander(f"#{r.get('rank')} {r.get('name')} · {r.get('match_score')}% match", expanded=False):
            st.markdown(f"<span class='hs-pill'><strong>{badge}</strong> · {r.get('email') or '—'}</span>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                progress_pct("Skills", r.get("skill_score", 0), "Weighted lexicon coverage vs JD")
            with c2:
                progress_pct("Experience", r.get("experience_score", 0), "Tenure & relevance signals")
            with c3:
                progress_pct("Education", r.get("education_score", 0), "Degree & field alignment")
            st.caption("Matched skills")
            skill_chips(r.get("matched_skills") or [], limit=30)
            st.caption("Gaps")
            skill_chips(r.get("missing_skills") or [], limit=30)

    st.markdown("#### Side-by-side compare")
    id_to_label = {r["candidate_id"]: f"#{r.get('rank')} {r['name']}" for r in rows}
    pick = st.multiselect("Pick up to 4 candidates", options=list(id_to_label.keys()), format_func=lambda i: id_to_label.get(i, str(i)), max_selections=4)
    if pick:
        chosen = [next((x for x in rows if x["candidate_id"] == cid), None) for cid in pick]
        chosen = [c for c in chosen if c]
        if chosen:
            # Winner highlights per dimension
            def _best(key: str) -> float:
                return max((float(r.get(key) or 0) for r in chosen), default=0.0)

            best_match = _best("match_score")
            best_skill = _best("skill_score")
            best_exp = _best("experience_score")
            best_edu = _best("education_score")

            cols = st.columns(len(chosen))
            for col, row in zip(cols, chosen):
                cid = row["candidate_id"]
                c = db.query(Candidate).filter(Candidate.id == cid).first()
                with col:
                    crown = " (Top)" if float(row.get("match_score") or 0) == best_match else ""
                    st.markdown(
                        f"""
                        <div class="hs-card">
                          <span class="hs-badge">Compare</span>
                          <h4 style="margin-top:0.55rem;">{row.get("name")}{crown}</h4>
                          <div class="hs-muted">{row.get("email") or "—"}</div>
                          <div style="height:0.65rem;"></div>
                          <div class="hs-pill"><strong>Match</strong> {row.get("match_score")}%</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.metric("Skills", f"{row.get('skill_score'):.1f}%", delta="Best" if float(row.get("skill_score") or 0) == best_skill else None)
                    st.metric("Experience", f"{row.get('experience_score'):.1f}%", delta="Best" if float(row.get("experience_score") or 0) == best_exp else None)
                    st.metric("Education", f"{row.get('education_score'):.1f}%", delta="Best" if float(row.get("education_score") or 0) == best_edu else None)
                    with st.expander("Strengths & gaps", expanded=False):
                        st.caption("Matched")
                        skill_chips(row.get("matched_skills") or [], limit=18)
                        st.caption("Missing")
                        skill_chips(row.get("missing_skills") or [], limit=18)
                    if c:
                        st.text_area(
                            "Experience excerpt",
                            (c.experience or "")[:700],
                            height=180,
                            disabled=True,
                            key=f"exp_{cid}",
                        )

            st.markdown("##### Comparison matrix")
            st.dataframe(
                [
                    {
                        "candidate": r.get("name"),
                        "match": r.get("match_score"),
                        "skills": r.get("skill_score"),
                        "experience": r.get("experience_score"),
                        "education": r.get("education_score"),
                        "shortlist": r.get("shortlist"),
                    }
                    for r in chosen
                ],
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("#### Export")
    st.caption("Export a recruiter-ready ranked slate (CSV) or a text report with insights for sharing.")
    ec1, ec2 = st.columns(2)
    with ec1:
        csv_bytes = ranked_candidates_csv(rows)
        st.session_state.setdefault("last_export", {})
        st.download_button(
            label="Download ranked CSV",
            data=csv_bytes,
            file_name=f"hiresense_ranked_job_{job_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        if st.button("Mark CSV exported", use_container_width=True):
            st.session_state["last_export"][f"job_{job_id}_csv"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            st.toast("Export status saved.")
    with ec2:
        report = screening_report_text(job.title if job else "Role", rows, insights)
        st.download_button(
            label="Download insight report",
            data=report.encode("utf-8"),
            file_name=f"hiresense_report_job_{job_id}.txt",
            mime="text/plain",
            use_container_width=True,
        )
        if st.button("Mark report exported", use_container_width=True):
            st.session_state["last_export"][f"job_{job_id}_report"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            st.toast("Export status saved.")

    last = st.session_state.get("last_export", {})
    if last:
        st.caption(
            f"Last exported — CSV: {last.get(f'job_{job_id}_csv','—')} · Report: {last.get(f'job_{job_id}_report','—')}"
        )

    st.markdown("#### Raw table")
    st.dataframe(
        [
            {
                "rank": r.get("rank"),
                "name": r.get("name"),
                "email": r.get("email"),
                "match": r.get("match_score"),
                "skills": r.get("skill_score"),
                "exp": r.get("experience_score"),
                "edu": r.get("education_score"),
                "shortlist": r.get("shortlist"),
            }
            for r in rows
        ],
        use_container_width=True,
        hide_index=True,
    )
