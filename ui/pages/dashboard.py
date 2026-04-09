"""Dashboard home — recruiter, admin, or candidate."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from database.models import JobDescription, PublicResumeSubmission, User
from services.analytics_service import resume_analysis_history, screening_history
from services.insights_service import cohort_skill_stats
from ui.components import empty_state, kpi_card, page_header, skill_chips


def render(db: Session, user: User) -> None:
    if user.role == "admin":
        _render_admin_public_intake(db)
        return

    page_header(
        "Command center",
        "A high-signal view of pipeline health, shortlists, and role quality.",
        pill="HireSense Intelligence",
    )
    if user.role == "recruiter":
        _render_recruiter_dashboard(db, user)
        return
    _render_candidate_dashboard(db, user)


def _render_recruiter_dashboard(db: Session, user: User) -> None:
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
            "Go to **Upload** -> paste JD -> upload resumes -> click **Save job & ingest**.",
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
                kpi_card(
                    "Slate trend",
                    stats.get("trend", "flat").replace("-", " ").title(),
                    None,
                    tone="warning" if stats.get("trend") == "polarized" else "neutral",
                )

            st.markdown("##### Most matched skills")
            skill_chips([s for s, _ in (stats.get("top_matched") or [])], limit=18)
            st.markdown("##### Most common gaps")
            skill_chips([s for s, _ in (stats.get("top_missing") or [])], limit=18)
        else:
            empty_state("No role context", "Create a role on Upload to unlock KPI insights.", "Upload -> Save job & ingest resumes.")

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
    _render_public_intake_cards(db, can_moderate=False, keyword_key="hr_keyword_filter", status_key="hr_status_filter")


def _render_admin_public_intake(db: Session) -> None:
    page_header(
        "Public Intake Command Center",
        "Review direct candidate submissions and update final screening status.",
        pill="Admin Moderation",
    )
    rows = (
        db.query(PublicResumeSubmission)
        .order_by(PublicResumeSubmission.created_at.desc())
        .limit(200)
        .all()
    )
    total = len(rows)
    shortlisted = sum(1 for r in rows if r.status == "shortlisted")
    under_review = sum(1 for r in rows if r.status == "under_review")
    rejected = sum(1 for r in rows if r.status == "rejected")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Submissions", str(total), "All", tone="neutral")
    with c2:
        kpi_card("Shortlisted", str(shortlisted), "Ready", tone="positive" if shortlisted else "neutral")
    with c3:
        kpi_card("Under review", str(under_review), "Pending", tone="warning" if under_review else "neutral")
    with c4:
        kpi_card("Rejected", str(rejected), "Filtered", tone="neutral")
    st.markdown("#### Public intake inbox")
    _render_public_intake_cards(db, can_moderate=True, keyword_key="admin_keyword_filter", status_key="admin_status_filter")


def _render_public_intake_cards(db: Session, *, can_moderate: bool, keyword_key: str, status_key: str) -> None:
    kf1, kf2 = st.columns([1.4, 1.0], gap="medium")
    keyword_filter = kf1.text_input("Keyword filter", placeholder="react, python, sql", key=keyword_key)
    status_filter = kf2.selectbox("Status", options=["all", "under_review", "rejected", "shortlisted"], key=status_key)

    rows = (
        db.query(PublicResumeSubmission)
        .order_by(PublicResumeSubmission.created_at.desc())
        .limit(160)
        .all()
    )
    if status_filter != "all":
        rows = [r for r in rows if r.status == status_filter]
    if keyword_filter.strip():
        keys = [k.strip().lower() for k in keyword_filter.replace("\n", ",").split(",") if k.strip()]
        rows = [r for r in rows if any(k in (r.role_keywords or "").lower() or k in " ".join(r.extracted_skills or []).lower() for k in keys)]

    if not rows:
        st.caption("No public submissions found for current filter.")
        return

    for r in rows[:80]:
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
        if not can_moderate:
            continue
        a1, a2, a3 = st.columns(3)
        if a1.button("Mark shortlisted", key=f"mark_shortlisted_{r.id}", use_container_width=True):
            r.status = "shortlisted"
            r.candidate_notice = "Your profile has been shortlisted by HR."
            db.commit()
            st.rerun()
        if a2.button("Mark under review", key=f"mark_under_review_{r.id}", use_container_width=True):
            r.status = "under_review"
            r.candidate_notice = "Your profile is under HR review."
            db.commit()
            st.rerun()
        if a3.button("Mark rejected", key=f"mark_rejected_{r.id}", use_container_width=True):
            r.status = "rejected"
            r.candidate_notice = "You are currently not fit for this role."
            db.commit()
            st.rerun()


def _render_candidate_dashboard(db: Session, user: User) -> None:
    st.caption("Understand fit before you apply. Sharper resumes win shortlists.")
    rows = resume_analysis_history(db, user.id, limit=12)

    recent_match = rows[0]["match_percent"] if rows else 0.0
    best_match = max((r["match_percent"] for r in rows), default=0.0)
    strong_count = sum(1 for r in rows if (r.get("match_percent") or 0) >= 72.0)
    analyses_count = len(rows)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Analyses run", str(analyses_count), "History", tone="positive" if analyses_count else "neutral")
    with c2:
        kpi_card("Recent match", f"{recent_match:.1f}%" if analyses_count else "—", "Latest", tone="neutral")
    with c3:
        kpi_card("Best match", f"{best_match:.1f}%" if analyses_count else "—", "Peak", tone="positive" if best_match >= 72 else "neutral")
    with c4:
        kpi_card("Strong reports", str(strong_count), "72%+", tone="positive" if strong_count else "neutral")

    left, right = st.columns([1.2, 1.0], gap="large")
    with left:
        st.markdown("#### Recent resume intelligence reports")
        if not rows:
            empty_state(
                "Your resume intelligence starts here",
                "Use **Resume Checker** to generate a premium match report (skills, experience, education), gap analysis, and actionable suggestions.",
                "Navigate to **Resume checker** and analyze a target JD.",
            )
        else:
            for r in rows[:6]:
                tone = "ok" if (r.get("match_percent") or 0) >= 72 else ("warn" if (r.get("match_percent") or 0) >= 55 else "bad")
                st.markdown(
                    f"""
                    <div class="hs-card">
                      <span class="hs-badge {tone}">{r.get("strength") or "Report"}</span>
                      <h4 style="margin-top:0.55rem;">Match score: {float(r.get("match_percent") or 0):.1f}%</h4>
                      <div class="hs-muted">{r.get("created_at")} · Analysis ID #{r.get("id")}</div>
                      <div class="hs-muted" style="margin-top:.35rem;">{r.get("preview_jd") or "—"}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with right:
        st.markdown("#### Profile improvement lane")
        st.markdown(
            """
            <div class="hs-card">
              <span class="hs-badge">Action Plan</span>
              <h4 style="margin-top:0.55rem;">How to increase shortlisting chances</h4>
              <div class="hs-muted">Use these quick wins before your next application.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        skill_chips(
            [
                "Quantified impact bullets",
                "Role-matched keywords",
                "Project depth",
                "ATS-safe headings",
                "Outcome-focused summaries",
                "Domain-specific stack proof",
            ],
            limit=12,
        )
        st.markdown("#### This week")
        st.markdown(
            """
- Quantify wins (latency, revenue, accuracy)
- Mirror the JD’s stack without keyword stuffing
- Surface leadership examples if the JD signals seniority
"""
        )
