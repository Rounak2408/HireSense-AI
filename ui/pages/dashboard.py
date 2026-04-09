"""Dashboard home — recruiter or candidate."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from database.models import JobDescription, PublicResumeSubmission, User
from services.analytics_service import screening_history
from services.insights_service import cohort_skill_stats
from ui.components import empty_state, kpi_card, page_header, skill_chips


def render(db: Session, user: User) -> None:
    page_header(
        "Command center",
        "A high-signal view of pipeline health, shortlists, and role quality.",
        pill="HireSense Intelligence",
    )
    if user.role == "recruiter":
        hist = screening_history(db, user.id, limit=8)
        active_roles = len(hist)
        total_cands = sum(h.get("candidates") or 0 for h in hist)
        best = max((h.get("best_score") or 0 for h in hist), default=0)
        past = db.query(JobDescription).filter(JobDescription.user_id == user.id).count()

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi_card("Active roles", str(active_roles), "Live", tone="positive" if active_roles else "neutral")
        with k2:
            kpi_card("Candidates indexed", str(total_cands), "Parsed", tone="positive" if total_cands else "neutral")
        with k3:
            kpi_card("Best match (recent)", f"{best:.1f}" if best else "—", "Peak", tone="positive" if best >= 72 else "neutral")
        with k4:
            kpi_card("JDs stored", str(past), "History", tone="neutral")

        st.markdown("#### Active roles")
        if not hist:
            empty_state(
                "No roles yet",
                "Create a role by pasting a job description, then upload candidate resumes to generate an instantly ranked slate.",
                "Go to **Upload** → paste JD → upload resumes → click **Save job & ingest**.",
            )
            return

        left, right = st.columns([1.2, 1.0])
        with left:
            st.markdown("##### Recent screenings")
            for h in hist[:6]:
                best_score = h.get("best_score")
                bs = f"{best_score:.1f}" if isinstance(best_score, (int, float)) else "—"
                st.markdown(
                    f"""
                    <div class="hs-card">
                      <span class="hs-badge">Role</span>
                      <h4 style="margin-top:0.55rem;">{h["title"]}</h4>
                      <div class="hs-muted">{h["candidates"]} candidates · best match {bs} · ID #{h["job_id"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with right:
            latest = (
                db.query(JobDescription)
                .filter(JobDescription.user_id == user.id)
                .order_by(JobDescription.created_at.desc())
                .first()
            )
            st.markdown("##### Role quality snapshot")
            if latest:
                stats = cohort_skill_stats(db, latest.id)
                st.markdown(f"<div class='hs-pill'><strong>Latest role:</strong> {latest.title}</div>", unsafe_allow_html=True)
                st.caption("What’s working, what’s missing, and how strong this slate is.")
                b1, b2, b3 = st.columns(3)
                with b1:
                    kpi_card("Avg match", f"{stats.get('avg', 0)}", "Cohort", tone="neutral")
                with b2:
                    qb = stats.get("quality_bands", {})
                    kpi_card("Strong profiles", str(qb.get("high", 0)), "72%+", tone="positive" if qb.get("high", 0) else "neutral")
                with b3:
                    kpi_card("Slate trend", stats.get("trend", "flat").replace("-", " ").title(), None, tone="warning" if stats.get("trend") == "polarized" else "neutral")

                st.markdown("##### Most matched skills")
                skill_chips([s for s, _ in (stats.get("top_matched") or [])], limit=18)
                st.markdown("##### Most common gaps")
                skill_chips([s for s, _ in (stats.get("top_missing") or [])], limit=18)
            else:
                empty_state("No role context", "Create a role on Upload to unlock KPI insights.", "Upload → Save job & ingest resumes.")

        st.markdown("#### JD skill radar (latest role)")
        last = (
            db.query(JobDescription)
            .filter(JobDescription.user_id == user.id)
            .order_by(JobDescription.created_at.desc())
            .first()
        )
        if last and last.extracted_skills:
            skill_chips(list(last.extracted_skills))
        elif last:
            st.info("No structured skills yet — paste a richer JD on Upload.")

        st.markdown("#### Public intake inbox")
        kf1, kf2 = st.columns([1.4, 1.0], gap="medium")
        keyword_filter = kf1.text_input(
            "HR keyword filter",
            placeholder="react, python, sql",
            key="hr_keyword_filter",
        )
        status_filter = kf2.selectbox(
            "Status",
            options=["all", "under_review", "rejected", "shortlisted"],
            key="hr_status_filter",
        )

        rows = (
            db.query(PublicResumeSubmission)
            .order_by(PublicResumeSubmission.created_at.desc())
            .limit(120)
            .all()
        )
        if status_filter != "all":
            rows = [r for r in rows if r.status == status_filter]
        if keyword_filter.strip():
            keys = [k.strip().lower() for k in keyword_filter.replace("\n", ",").split(",") if k.strip()]
            rows = [
                r for r in rows
                if any(k in (r.role_keywords or "").lower() or k in " ".join(r.extracted_skills or []).lower() for k in keys)
            ]

        if not rows:
            st.caption("No public submissions found for current filter.")
        else:
            for r in rows[:40]:
                tone = "ok" if r.status == "shortlisted" else ("bad" if r.status == "rejected" else "warn")
                st.markdown(
                    f"""
                    <div class="hs-card">
                      <span class="hs-badge {tone}">{r.status.replace('_',' ').title()}</span>
                      <h4 style="margin-top:0.55rem;">{r.candidate_name} · {r.candidate_email}</h4>
                      <div class="hs-muted">Keyword match: {r.keyword_match_percent:.1f}% · ATS: {r.ats_preview_score:.1f}% · Resume: {r.original_filename or "—"}</div>
                      <div class="hs-muted" style="margin-top:.3rem;">Notice: {r.candidate_notice or "—"}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        return

    # candidate
    st.caption("Understand fit before you apply. Sharper resumes win shortlists.")
    empty_state(
        "Your resume intelligence starts here",
        "Use **Resume Checker** to generate a premium match report (skills, experience, education), gap analysis, and actionable suggestions.",
        "Navigate to **Resume checker** and analyze a target JD.",
    )
    st.markdown("#### This week")
    st.markdown(
        """
- Quantify wins (latency, revenue, accuracy)
- Mirror the JD’s stack without keyword stuffing
- Surface leadership examples if the JD signals seniority
"""
    )
