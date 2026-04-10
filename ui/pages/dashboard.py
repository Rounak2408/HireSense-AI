"""Premium recruiter dashboard for resume intelligence."""

from __future__ import annotations

from datetime import datetime
import time

import streamlit as st
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from database.models import PublicResumeSubmission, User, UserResumeAnalysis
from services.jd_processor import process_job_description
from services.matching_engine import score_candidate, suggest_improvements
from services.resume_parser import parse_resume_bytes
from ui.components import empty_state, kpi_card, page_header, skill_chips


def render(db: Session, user: User) -> None:
    if user.role == "admin":
        _render_admin_public_intake(db)
        return
    _render_workspace(db, user)


def _render_workspace(db: Session, user: User) -> None:
    st.session_state.setdefault("ws_result", None)
    st.session_state.setdefault("ws_running", False)
    st.session_state.setdefault("ws_jd_text", "")
    st.session_state.setdefault("ws_resume_upload_key", 0)
    st.session_state.setdefault("ws_last_analysis_id", None)

    sid = _parse_shared_analysis_query_id(st.query_params)
    if sid is not None:
        row = (
            db.query(UserResumeAnalysis)
            .filter(UserResumeAnalysis.id == sid, UserResumeAnalysis.user_id == user.id)
            .first()
        )
        if row:
            st.session_state.ws_result = _result_dict_from_row(row)
            st.session_state.ws_jd_text = row.job_description_text or ""
            st.session_state.ws_last_analysis_id = row.id
            st.toast("Opened shared analysis from link.", icon="🔗")
        else:
            st.warning("That shared analysis was not found or you do not have access.")
        try:
            del st.query_params["shared_analysis"]
        except Exception:
            pass

    result = st.session_state.get("ws_result")
    st.session_state.setdefault("ws_bookmarked", False)
    st.session_state.setdefault("ws_notes", "")
    _inject_premium_results_css()

    page_header(
        "Recruiter Intelligence Workspace",
        "Premium AI screening hub for JD intelligence, candidate fit, ATS diagnostics, and hiring recommendations.",
        pill="HireSense AI",
    )

    _hero_section(db, user, result)

    share_url = st.session_state.get("_share_url")
    if share_url:
        st.caption("Shareable analysis link")
        st.code(share_url, language=None)

    st.markdown("### Analysis Workspace")
    jd_col, resume_col = st.columns([1.15, 1.0], gap="large")
    with jd_col:
        st.markdown("#### Job Description Intelligence")
        jd_text, jd_skills = _jd_input_card()
        jd_word_count = len((jd_text or "").split())
        jd_quality = "High" if jd_word_count >= 120 else ("Medium" if jd_word_count >= 60 else "Low")
        qc1, qc2, qc3 = st.columns(3)
        qc1.metric("Word count", str(jd_word_count))
        qc2.metric("Quality signal", jd_quality)
        if qc3.button("Optimize JD", use_container_width=True):
            st.toast("AI JD optimizer prepared suggestions. Apply and rerun analysis.", icon="✨")
        if jd_skills:
            st.caption("Auto-detected tags")
            skill_chips(jd_skills[:18], limit=18)

    with resume_col:
        st.markdown("#### Candidate Resume Upload")
        resume_file, parsed_preview = _resume_upload_card()
        if parsed_preview:
            st.success("Resume parsed successfully")
            p1, p2, p3 = st.columns(3)
            p1.metric("Candidate", parsed_preview.name or "Unknown")
            p2.metric("Projects", str(len(getattr(parsed_preview, "project_names", []) or [])))
            p3.metric("Experience", f"{float(parsed_preview.years_experience or 0):.1f} yrs")
        else:
            st.info("Drop a PDF/DOCX to unlock parse preview and recruiter diagnostics.", icon="📄")

    st.markdown("### Sticky Analysis CTA")
    c1, c2, c3 = st.columns([1.4, 1.2, 1.1])
    ready = resume_file is not None and bool(jd_text.strip())
    with c1:
        st.markdown('<div class="hs-badge">Parsing → Skill Matching → ATS → Final Evaluation</div>', unsafe_allow_html=True)
    with c2:
        st.button("View Reports", use_container_width=True, key="ws_view_reports_sticky")
    with c3:
        trigger = st.button(
            "Analyze Candidate Fit →",
            type="primary",
            use_container_width=True,
            disabled=not ready,
            key="ws_analyze_fit_primary",
        )

    if trigger:
        st.session_state.ws_running = True
        st.rerun()

    if st.session_state.get("ws_running") and ready:
        progress = st.progress(0.0)
        stage = st.empty()
        steps = ["Parsing resume", "Skill matching", "ATS scoring", "Final evaluation"]
        for idx, label in enumerate(steps, start=1):
            stage.caption(f"{idx}/4 · {label}")
            progress.progress(idx / 4)
            time.sleep(0.1)
        parsed = parse_resume_bytes(resume_file.getvalue(), resume_file.name)
        jd = process_job_description(jd_text)
        score = score_candidate(
            parsed.skills,
            jd.required_skills,
            parsed.raw_text,
            parsed.education,
            parsed.experience,
            parsed.years_experience,
            parsed.projects,
        )
        suggestions = suggest_improvements(
            score.get("missing_skills") or [],
            jd_text,
            score.get("project_score"),
            (score.get("breakdown") or {}).get("project_analysis"),
        )
        ats = _ats_score(score, parsed)
        result = {
            "resume_name": resume_file.name,
            "parsed_name": parsed.name or "Unknown",
            "parsed": parsed,
            "jd_text": jd_text,
            "jd_skills": jd.required_skills,
            "score": score,
            "ats": ats,
            "suggestions": suggestions,
            "created_at": datetime.utcnow(),
            "toggles": {},
        }
        st.session_state.ws_result = result
        st.session_state.ws_running = False
        st.session_state.ws_last_analysis_id = _persist_analysis_row(db, user, result)
        st.success("Analysis completed.")
        st.rerun()

    st.markdown("---")
    result = st.session_state.get("ws_result")
    if not result:
        _premium_empty_state()
        _history_table(db, user)
        return

    rows = (
        db.query(UserResumeAnalysis)
        .filter(UserResumeAnalysis.user_id == user.id)
        .order_by(UserResumeAnalysis.created_at.desc())
        .limit(60)
        .all()
    )
    _render_results_page(db, user, result, rows)


def _resume_upload_card():
    st.markdown("#### Resume Upload")
    st.caption("Drop your latest resume to extract skills, experience, projects, and ATS signals.")
    resume_file = st.file_uploader(
        "Drop resume",
        type=["pdf", "docx"],
        key=f"ws_resume_file_{st.session_state.get('ws_resume_upload_key', 0)}",
        help="Accepted formats: PDF / DOCX",
    )
    parsed_preview = None
    if not resume_file:
        st.markdown(
            """
            <div class="hs-card hs-empty-illustrated">
              <div class="hs-badge">Onboarding Hint</div>
              <h4 style="margin-top:.45rem;">Upload resume to begin analysis</h4>
              <div class="hs-muted">Drag & drop your latest resume to unlock ATS scoring, fit breakdown, and recruiter recommendations.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return None, None

    try:
        parsed_preview = parse_resume_bytes(resume_file.getvalue(), resume_file.name)
    except Exception as exc:
        st.error(f"Resume parse failed: {exc}")
        return resume_file, None

    st.success(f"Resume parsed successfully: {resume_file.name}")
    st.markdown('<div class="hs-file-preview-chip">File Ready · AI Parse Complete</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Candidate", parsed_preview.name or "Unknown")
    m2.metric("Experience", f"{float(parsed_preview.years_experience or 0):.1f} yrs")
    m3.metric("Skills", str(len(parsed_preview.skills or [])))
    m4.metric("Projects", str(len(getattr(parsed_preview, "project_names", []) or [])))

    r1, r2 = st.columns(2)
    if r1.button("Replace File", use_container_width=True, key="ws_replace_resume"):
        st.session_state.ws_resume_upload_key += 1
        st.session_state.ws_result = None
        st.rerun()
    if r2.button("Remove File", use_container_width=True, key="ws_remove_resume"):
        st.session_state.ws_resume_upload_key += 1
        st.session_state.ws_result = None
        st.rerun()
    return resume_file, parsed_preview


def _jd_input_card():
    st.markdown("#### Job Description Input")
    st.session_state.setdefault("ws_jd_text", "")

    # Apply deferred actions before the ws_jd_text widget is instantiated.
    if st.session_state.pop("ws_jd_clear_pending", False):
        st.session_state.ws_jd_text = ""
    if st.session_state.pop("ws_jd_sample_pending", False):
        st.session_state.ws_jd_text = (
            "We are hiring a Senior Frontend Engineer with React, TypeScript, Next.js, API integration, SQL literacy, "
            "and performance optimization experience. Candidate should drive measurable user and business impact."
        )

    jd_file = st.file_uploader("Optional JD upload", type=["txt", "md"], key="ws_jd_file")
    if jd_file is not None:
        try:
            file_bytes = jd_file.getvalue()
            file_sig = f"{jd_file.name}:{len(file_bytes)}"
            if st.session_state.get("ws_jd_file_sig") != file_sig:
                st.session_state.ws_jd_file_sig = file_sig
                st.session_state.ws_jd_text = file_bytes.decode("utf-8", errors="ignore")
                st.rerun()
        except Exception:
            st.warning("Unable to parse JD file, please paste text manually.")

    jd_text = st.text_area(
        "Paste JD",
        key="ws_jd_text",
        height=210,
        placeholder="Paste the target job description to compare required skills, experience, and keywords.",
    )
    url_input = st.text_input("Import from URL (optional)", key="ws_jd_url", placeholder="https://job-posting-url")
    if url_input.strip():
        st.caption("URL captured. Paste key role details below for best accuracy.")

    c1, c2 = st.columns(2)
    if c1.button("Clear JD", use_container_width=True, key="ws_clear_jd"):
        st.session_state.ws_jd_clear_pending = True
        st.rerun()
    if c2.button("Use Sample JD", use_container_width=True, key="ws_sample_jd"):
        st.session_state.ws_jd_sample_pending = True
        st.rerun()

    jd_skills = []
    if jd_text.strip():
        try:
            jd_skills = process_job_description(jd_text).required_skills or []
        except Exception:
            jd_skills = []
    if jd_skills:
        st.caption("Detected JD skills / keywords")
        skill_chips(jd_skills[:16], limit=16)
    return jd_text, jd_skills


def _analysis_control_card(*, resume_ready: bool, jd_ready: bool):
    st.markdown("#### Analysis Control Engine")
    ready = resume_ready and jd_ready
    confidence = "High" if ready else ("Medium" if resume_ready or jd_ready else "Low")
    st.markdown(
        f"""
        <div class="hs-readiness-grid">
          <div><strong>Resume uploaded</strong><br/>{"✅" if resume_ready else "❌"}</div>
          <div><strong>JD loaded</strong><br/>{"✅" if jd_ready else "❌"}</div>
          <div><strong>Match readiness</strong><br/>{"✅ Ready" if ready else "❌ Incomplete"}</div>
          <div><strong>AI confidence</strong><br/>{confidence}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    t1, t2 = st.columns(2)
    ats_mode = t1.toggle("ATS mode", value=True, key="ws_toggle_ats")
    recruiter_summary = t2.toggle("Recruiter summary", value=True, key="ws_toggle_summary")
    t3, t4 = st.columns(2)
    gap_scan = t3.toggle("Keyword gap analysis", value=True, key="ws_toggle_gap")
    relevance_scan = t4.toggle("Skill relevance scan", value=True, key="ws_toggle_relevance")

    run_btn = st.button(
        "Run Resume Intelligence",
        type="primary",
        use_container_width=True,
        disabled=not ready,
        key="ws_run_intelligence",
    )
    st.button("Preview Match Inputs", use_container_width=True, key="ws_preview_inputs")
    return run_btn, ats_mode, recruiter_summary, gap_scan, relevance_scan


def _hero_section(db: Session, user: User, result: dict | None) -> None:
    rows = (
        db.query(UserResumeAnalysis)
        .filter(UserResumeAnalysis.user_id == user.id)
        .order_by(UserResumeAnalysis.created_at.desc())
        .limit(200)
        .all()
    )
    analyzed = len(rows)
    avg_match = (sum(float(r.match_percent or 0.0) for r in rows) / analyzed) if analyzed else 0.0
    shortlisted = (sum(1 for r in rows if float(r.match_percent or 0.0) >= 72) / analyzed * 100.0) if analyzed else 0.0
    st.markdown(
        """
        <div class="hs-workspace-headline">
          <div class="hs-workspace-kicker">Recruiter Intelligence Workspace</div>
          <div class="hs-workspace-subline">Screen faster with modular inputs, AI scoring, risk signals, and decision-ready recommendation panels.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Candidates analyzed", str(analyzed))
    s2.metric("Avg match score", f"{avg_match:.1f}%")
    s3.metric("Shortlisted %", f"{shortlisted:.1f}%")
    s4.metric("Current report", "Ready" if result else "Not started")
    b1, b2, b3 = st.columns([1.2, 1.2, 1.2])
    if b1.button("New Analysis", type="primary", use_container_width=True):
        st.session_state.ws_result = None
        st.session_state.ws_jd_text = ""
        st.session_state.ws_last_analysis_id = None
        st.session_state.ws_resume_upload_key += 1
        st.rerun()
    b2.button("View Reports", use_container_width=True, key="ws_view_reports_hero")
    if result:
        b3.download_button(
            "Export Report",
            data=_export_report_blob(result),
            file_name=f"hiresense-analysis-{datetime.utcnow().strftime('%Y%m%d-%H%M')}.txt",
            mime="text/plain",
            use_container_width=True,
            key="ws_export_report_hero",
        )
    else:
        b3.button("Export Report", disabled=True, use_container_width=True)


def _premium_empty_state() -> None:
    st.markdown(
        """
        <div class="hs-card hs-empty-illustrated">
          <div class="hs-badge">Onboarding</div>
          <h4 style="margin-top:.45rem;">No report generated yet</h4>
          <div class="hs-muted">1) Paste a strong JD → 2) Upload candidate resume → 3) Click Analyze Candidate Fit.</div>
          <div class="hs-muted" style="margin-top:.4rem;">You will instantly unlock scorecards, gaps, risk signals, and AI recommendation.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _inject_premium_results_css() -> None:
    # Standalone premium CSS (works even if global theme injection is off).
    st.markdown(
        """
        <style>
        /* Layout */
        .block-container { padding-top: 1.0rem !important; max-width: 1200px !important; }
        h1, h2, h3, h4 { letter-spacing: -0.015em; }

        /* Premium cards */
        .hs-prem-card {
          border-radius: 16px;
          border: 1px solid rgba(148,163,184,0.18);
          background: rgba(2, 6, 23, 0.35);
          box-shadow: 0 18px 45px rgba(0,0,0,0.35);
          padding: 14px 14px;
          position: relative;
          overflow: hidden;
        }
        .hs-prem-card::before{
          content:"";
          position:absolute; inset:0;
          background: radial-gradient(800px 240px at 20% 0%, rgba(124,58,237,.22), rgba(79,70,229,0) 55%),
                      radial-gradient(700px 260px at 90% 30%, rgba(34,211,238,.14), rgba(79,70,229,0) 60%);
          pointer-events:none;
        }
        .hs-strip {
          border-radius: 18px;
          border: 1px solid rgba(148,163,184,0.18);
          background: linear-gradient(135deg, rgba(124,58,237,.18), rgba(79,70,229,.10), rgba(2,6,23,.35));
          box-shadow: 0 18px 45px rgba(0,0,0,0.32);
          padding: 14px 14px;
        }
        .hs-kicker { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: rgba(148,163,184,.95); font-weight: 700; }
        .hs-muted { color: rgba(148,163,184,.92); font-size: 13px; }
        .hs-divider { height: 1px; background: rgba(148,163,184,0.14); margin: 10px 0 12px 0; }

        /* Badges */
        .hs-badge2 {
          display:inline-flex; align-items:center; gap:6px;
          padding: 6px 10px;
          border-radius: 999px;
          border: 1px solid rgba(148,163,184,0.18);
          background: rgba(15, 23, 42, 0.55);
          font-size: 12px; font-weight: 700;
        }
        .hs-badge2.ok { color:#a7f3d0; border-color: rgba(16,185,129,0.35); }
        .hs-badge2.warn { color:#fde68a; border-color: rgba(245,158,11,0.35); }
        .hs-badge2.bad { color:#fecaca; border-color: rgba(239,68,68,0.35); }

        /* Buttons */
        .stButton > button[kind="primary"]{
          border-radius: 14px !important;
          background: linear-gradient(120deg, #7c3aed, #4f46e5) !important;
          border: none !important;
          box-shadow: 0 14px 34px rgba(79,70,229,0.35) !important;
          font-weight: 800 !important;
        }
        .stButton > button{ border-radius: 14px !important; }

        /* Progress */
        div[role="progressbar"] > div { border-radius: 999px !important; }

        /* Reduce clutter */
        footer { visibility: hidden; height: 0; }

        /* Mobile responsiveness */
        @media (max-width: 900px){
          .block-container { padding: 0.75rem 0.75rem 1.25rem 0.75rem !important; max-width: 100% !important; }
          /* Streamlit columns -> stack */
          div[data-testid="stHorizontalBlock"]{ flex-direction: column !important; gap: 0.75rem !important; }
          div[data-testid="stHorizontalBlock"] > div{ width: 100% !important; min-width: 100% !important; }
          /* Tabs list scroll */
          .stTabs [data-baseweb="tab-list"]{ overflow-x: auto; white-space: nowrap; }
          /* Metric cards breathing room */
          div[data-testid="stMetric"]{ border-radius: 14px !important; }
          /* Decision strip spacing */
          .hs-strip{ padding: 12px 12px; }
        }

        @media (max-width: 640px){
          .hs-kicker{ font-size: 11px; }
          .hs-muted{ font-size: 12px; }
          .hs-badge2{ font-size: 11px; padding: 5px 9px; }
          .stButton > button{ min-height: 42px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_results_page(db: Session, user: User, result: dict, rows: list[UserResumeAnalysis]) -> None:
    st.markdown("## Resume Intelligence Results")
    st.caption("Decision-ready recruiter dashboard — scan summary, validate risks, then deep dive.")

    prev = rows[1] if len(rows) > 1 else None
    deltas = _compute_deltas(result, prev)

    with st.container():
        render_decision_strip(result, deltas)

    st.markdown("### Insights Grid")
    left, right = st.columns([1.15, 1.0], gap="large")
    with left:
        render_match_intelligence(result)
        st.markdown('<div class="hs-divider"></div>', unsafe_allow_html=True)
        render_resume_health(result)
        st.markdown('<div class="hs-divider"></div>', unsafe_allow_html=True)
        render_skills(result)
    with right:
        render_strengths(result)
        st.markdown('<div class="hs-divider"></div>', unsafe_allow_html=True)
        render_risks(result)
        st.markdown('<div class="hs-divider"></div>', unsafe_allow_html=True)
        render_recommendations(result)
        st.markdown('<div class="hs-divider"></div>', unsafe_allow_html=True)
        render_charts(result)

    st.markdown("### Deep Analysis")
    t1, t2, t3, t4 = st.tabs(["Project Analysis", "Feedback Board", "Resume Extract (Raw)", "Archive / History"])
    with t1:
        render_project_analysis(result)
    with t2:
        render_feedback_board(result)
    with t3:
        render_resume_extract(result)
    with t4:
        _render_history_picker(db, user, rows)

    st.markdown("---")
    _notes_and_assistant(result)


def _compute_deltas(result: dict, prev: UserResumeAnalysis | None) -> dict[str, str | None]:
    sc = result.get("score", {})
    cur = {
        "match": float(sc.get("match_score", 0.0)),
        "ats": float(result.get("ats", 0.0)),
        "skills": float(sc.get("skill_score", 0.0)),
        "exp": float(sc.get("experience_score", 0.0)),
    }
    if not prev:
        return {k: None for k in cur}
    # Best-effort mapping: historical rows store these in their columns.
    prev_vals = {
        "match": float(prev.match_percent or 0.0),
        "ats": float(prev.skill_score or 0.0),  # legacy column; still useful as delta signal
        "skills": float(prev.skill_score or 0.0),
        "exp": float(prev.experience_score or 0.0),
    }
    out: dict[str, str] = {}
    for k, v in cur.items():
        dv = v - prev_vals.get(k, 0.0)
        sign = "↑" if dv >= 0 else "↓"
        out[k] = f"{sign} {abs(dv):.1f}%"
    return out


def _tone_for_score(score: float) -> str:
    if score >= 78:
        return "ok"
    if score >= 58:
        return "warn"
    return "bad"


def _final_decision(match: float, ats: float, missing_count: int) -> str:
    if match >= 82 and ats >= 65 and missing_count <= 5:
        return "Shortlist"
    if match >= 60:
        return "Hold"
    return "Reject"


def render_decision_strip(result: dict, deltas: dict[str, str | None]) -> None:
    sc = result.get("score", {})
    match = float(sc.get("match_score", 0.0))
    ats = float(result.get("ats", 0.0))
    skills = float(sc.get("skill_score", 0.0))
    exp = float(sc.get("experience_score", 0.0))
    missing = len(sc.get("missing_skills") or [])
    decision = _final_decision(match, ats, missing)
    tone = _tone_for_score(match)

    st.markdown(
        f"""
        <div class="hs-strip">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
            <div>
              <div class="hs-kicker">Decision Summary</div>
              <div class="hs-muted">Match, ATS, skills and experience — optimized for 5-second scan.</div>
            </div>
            <span class="hs-badge2 {tone}">Final Decision · {decision}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Match Score", f"{match:.1f}%", deltas.get("match"))
    m2.metric("ATS Score", f"{ats:.1f}%", deltas.get("ats"))
    m3.metric("Skill Match", f"{skills:.1f}%", deltas.get("skills"))
    m4.metric("Experience Fit", f"{exp:.1f}%", deltas.get("exp"))
    m5.metric("Decision", decision, "Recruiter")

    a1, a2, a3, a4 = st.columns([1, 1, 1, 1])
    if a1.button("Shortlist", use_container_width=True, key="ws_act_shortlist"):
        st.toast("Marked as shortlisted (session).", icon="✅")
    if a2.button("Hold", use_container_width=True, key="ws_act_hold"):
        st.toast("Marked as hold (session).", icon="🟨")
    if a3.button("Reject", use_container_width=True, key="ws_act_reject"):
        st.toast("Marked as rejected (session).", icon="🛑")
    a4.download_button(
        "Export Report",
        data=_export_report_blob(result),
        file_name=f"hiresense-analysis-{datetime.utcnow().strftime('%Y%m%d-%H%M')}.txt",
        mime="text/plain",
        use_container_width=True,
        key="ws_export_report_strip",
    )


def render_match_intelligence(result: dict) -> None:
    sc = result.get("score", {})
    st.markdown("#### Match Intelligence")
    st.caption("Core alignment signals (progress view).")
    items = [
        ("Skill alignment", float(sc.get("skill_score", 0.0))),
        ("Experience alignment", float(sc.get("experience_score", 0.0))),
        ("Education", float(sc.get("education_score", 0.0))),
        ("Project match", float(sc.get("project_score", 0.0))),
    ]
    for label, val in items:
        st.write(f"**{label}**")
        st.progress(max(0.0, min(1.0, val / 100.0)))
        st.caption(f"{val:.1f}%")


def render_resume_health(result: dict) -> None:
    sc = result.get("score", {})
    ats = float(result.get("ats", 0.0))
    keyword_cov = min(100.0, float(sc.get("skill_score", 0.0)) * 1.08)
    missing = (sc.get("missing_skills") or [])[:12]
    st.markdown("#### Resume Health / ATS Review")
    c1, c2 = st.columns(2)
    c1.metric("ATS Score", f"{ats:.1f}%")
    c2.metric("Keyword match %", f"{keyword_cov:.1f}%")
    st.caption("Missing keywords")
    skill_chips(missing or ["No critical missing keyword"], limit=12)


def _group_skills(skills: list[str]) -> dict[str, list[str]]:
    front = {"react", "next.js", "typescript", "javascript", "html", "css", "tailwind", "redux"}
    back = {"python", "node", "node.js", "java", "go", "django", "flask", "fastapi", "sql", "postgresql"}
    tools = {"aws", "docker", "kubernetes", "git", "ci/cd", "ci cd", "linux", "gcp", "azure"}
    out = {"Frontend": [], "Backend": [], "Tools": [], "Other": []}
    for s in skills:
        n = (s or "").lower().strip()
        if any(k in n for k in front):
            out["Frontend"].append(s)
        elif any(k in n for k in back):
            out["Backend"].append(s)
        elif any(k in n for k in tools):
            out["Tools"].append(s)
        else:
            out["Other"].append(s)
    return {k: v for k, v in out.items() if v}


def render_skills(result: dict) -> None:
    sc = result.get("score", {})
    matched = sc.get("matched_skills") or []
    grouped = _group_skills(matched[:30])
    st.markdown("#### Skills Breakdown")
    st.caption("Grouped for faster scanning.")
    cols = st.columns(3)
    keys = ["Frontend", "Backend", "Tools"]
    for i, k in enumerate(keys):
        with cols[i]:
            st.markdown(f"**{k}**")
            skill_chips(grouped.get(k, [])[:12] or ["—"], limit=12)
    if grouped.get("Other"):
        st.markdown("**Other**")
        skill_chips(grouped["Other"][:14], limit=14)


def render_strengths(result: dict) -> None:
    sc = result.get("score", {})
    match = float(sc.get("match_score", 0.0))
    st.markdown("#### Candidate Strengths")
    strengths = []
    ms = (sc.get("matched_skills") or [])[:6]
    if ms:
        strengths.append(f"✅ Strong alignment on: {', '.join(ms)}")
    if match >= 75:
        strengths.append("✅ Overall match score is high for this role.")
    if float(sc.get("project_score", 0.0)) >= 70:
        strengths.append("✅ Projects appear relevant to role requirements.")
    if not strengths:
        strengths = ["✅ Strengths will appear after a full analysis run."]
    for s in strengths[:5]:
        st.success(s)


def render_risks(result: dict) -> None:
    sc = result.get("score", {})
    match = float(sc.get("match_score", 0.0))
    ats = float(result.get("ats", 0.0))
    missing = len(sc.get("missing_skills") or [])
    st.markdown("#### Risk Signals")
    if match < 55:
        st.error("High · Overall fit is low for this role.")
    elif match < 70:
        st.warning("Medium · Fit is moderate; validate critical requirements.")
    else:
        st.success("Low · Fit looks strong; proceed to shortlist review.")
    if ats < 60:
        st.warning("Medium · ATS compatibility may block shortlisting.")
    if missing >= 8:
        st.error("High · Many JD keywords missing — risk of mismatch.")


def render_recommendations(result: dict) -> None:
    st.markdown("#### Recommendations Board")
    recs = (result.get("suggestions") or [])[:8]
    if not recs:
        recs = [
            "Add quantified impact bullets in Experience.",
            "Strengthen project descriptions with measurable outcomes.",
            "Improve ATS keyword coverage with role-aligned skills.",
        ]
    for r in recs[:6]:
        st.info(f"• {r}")


def render_charts(result: dict) -> None:
    st.markdown("#### Visual Analytics")
    sc = result.get("score", {})
    values = {
        "Match": float(sc.get("match_score", 0.0)),
        "ATS": float(result.get("ats", 0.0)),
        "Skills": float(sc.get("skill_score", 0.0)),
        "Experience": float(sc.get("experience_score", 0.0)),
        "Education": float(sc.get("education_score", 0.0)),
        "Projects": float(sc.get("project_score", 0.0)),
    }
    fig = go.Figure(
        data=[
            go.Bar(
                x=list(values.keys()),
                y=list(values.values()),
                marker=dict(
                    color=["#7c3aed", "#4f46e5", "#06b6d4", "#10b981", "#f59e0b", "#a78bfa"],
                    line=dict(color="rgba(255,255,255,0.18)", width=1),
                ),
                hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        height=280,
        margin=dict(l=8, r=8, t=16, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(range=[0, 100], gridcolor="rgba(148,163,184,0.12)", zeroline=False),
        xaxis=dict(tickfont=dict(size=12)),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_project_analysis(result: dict) -> None:
    sc = result.get("score", {})
    bd = sc.get("breakdown") or {}
    relevance = float(sc.get("project_score", 0.0))
    complexity = float((bd.get("project_complexity") or (relevance * 0.82)) if isinstance(bd, dict) else relevance * 0.82)
    impact = float((bd.get("project_impact") or (relevance * 0.74)) if isinstance(bd, dict) else relevance * 0.74)
    st.markdown("#### Project Analysis")
    st.markdown('<div class="hs-prem-card">', unsafe_allow_html=True)
    st.caption("Relevance, complexity and impact — normalized signals.")
    for label, val, icon in [
        ("Relevance", relevance, "🟩"),
        ("Complexity", complexity, "🟦"),
        ("Impact", impact, "🟨"),
    ]:
        st.write(f"**{icon} {label}**")
        st.progress(max(0.0, min(1.0, val / 100.0)))
        st.caption(f"{val:.1f}%")
    st.markdown("</div>", unsafe_allow_html=True)


def render_feedback_board(result: dict) -> None:
    sc = result.get("score", {})
    strengths = (sc.get("matched_skills") or [])[:6]
    gaps = (sc.get("missing_skills") or [])[:6]
    recs = (result.get("suggestions") or [])[:6]
    st.markdown("#### Resume Feedback Board")
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.success("**Strengths**")
        for s in strengths[:5] or ["Good baseline alignment detected."]:
            st.write(f"- {s}")
    with c2:
        st.info("**Improvements**")
        for r in recs[:5] or ["Add measurable outcomes and role-aligned keywords."]:
            st.write(f"- {r}")
    with c3:
        st.error("**Critical Fixes**")
        for g in gaps[:5] or ["No critical gaps detected."]:
            st.write(f"- {g}")


def render_resume_extract(result: dict) -> None:
    st.markdown("#### Resume Experience (as in resume)")
    parsed = result.get("parsed")
    if not parsed:
        st.info("Resume extract is not available for saved/shared reports.", icon="ℹ️")
        return
    exp_text = (getattr(parsed, "experience", None) or "").strip()
    edu_text = (getattr(parsed, "education", None) or "").strip()
    proj_text = (getattr(parsed, "projects", None) or "").strip()

    c1, c2 = st.columns([1.0, 1.0], gap="large")
    with c1:
        st.caption("Experience")
        st.text_area(
            "Experience (parsed)",
            value=exp_text if exp_text else "No explicit Experience section detected in the resume.",
            height=240,
            key="ws_resume_exp_raw",
        )
        st.caption("Education")
        st.text_area(
            "Education (parsed)",
            value=edu_text if edu_text else "No explicit Education section detected in the resume.",
            height=140,
            key="ws_resume_edu_raw",
        )
    with c2:
        st.caption("Projects")
        st.text_area(
            "Projects (parsed)",
            value=proj_text if proj_text else "No explicit Projects section detected in the resume.",
            height=240,
            key="ws_resume_proj_raw",
        )
        years = float(getattr(parsed, "years_experience", 0.0) or 0.0)
        st.metric("Estimated years experience", f"{years:.1f} yrs")


def _render_history_picker(db: Session, user: User, rows: list[UserResumeAnalysis]) -> None:
    st.markdown("#### Archive / History")
    if not rows:
        st.caption("No past analyses yet.")
        return
    options = {f"Report #{r.id} · {r.created_at.strftime('%Y-%m-%d %H:%M')} · {float(r.match_percent or 0):.1f}%": r for r in rows}
    pick = st.selectbox("Select past analysis", options=list(options.keys()), index=0, key="ws_history_pick")
    row = options[pick]
    preview = _result_dict_from_row(row)
    sc = preview.get("score", {})
    st.markdown('<div class="hs-prem-card">', unsafe_allow_html=True)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Match", f"{float(sc.get('match_score', 0)):.1f}%")
    p2.metric("Skills", f"{float(sc.get('skill_score', 0)):.1f}%")
    p3.metric("Experience", f"{float(sc.get('experience_score', 0)):.1f}%")
    p4.metric("Strength", str(row.strength))
    st.caption("Missing keywords preview")
    skill_chips((sc.get("missing_skills") or [])[:12] or ["—"], limit=12)
    st.markdown("</div>", unsafe_allow_html=True)


def _results_dashboard(result: dict) -> None:
    # Backward compat: keep call sites working; new UI lives in _render_results_page.
    del result
    return


def _comparison_and_timeline(db: Session, user: User, result: dict) -> None:
    # Backward compat.
    del db, user, result
    return


def _notes_and_assistant(result: dict) -> None:
    st.markdown("### Recruiter Notes & AI Assistant")
    n1, n2 = st.columns([1.15, 1.0], gap="large")
    with n1:
        st.markdown("#### Recruiter Notes Panel")
        notes = st.text_area(
            "Private notes",
            key="ws_notes",
            height=150,
            placeholder="Add interview notes, salary expectations, concerns, and next steps...",
        )
        if st.button("Save Notes", use_container_width=True):
            st.toast("Recruiter notes saved in session.", icon="📝")
        st.caption(f"Notes length: {len((notes or '').strip())} chars")
    with n2:
        st.markdown("#### AI Chat Assistant")
        st.caption("Ask for quick coaching prompts and recruiter summaries.")
        q = st.text_input("Ask AI", key="ws_ai_q", placeholder="Summarize top risks in 3 bullet points")
        if st.button("Generate Response", use_container_width=True, key="ws_ai_respond"):
            base = result.get("score", {})
            missing = ", ".join((base.get("missing_skills") or [])[:5]) or "None"
            st.markdown(
                f"""
                <div class="hs-card">
                  <div class="hs-muted"><strong>AI:</strong> Candidate fit is {float(base.get('match_score', 0)):.1f}%.
                  Top missing skills: {missing}. Suggested recruiter action: {_strength_label(float(base.get('match_score', 0)))}.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if q.strip():
            st.caption("Prompt captured. Click Generate Response.")


def _live_status_panel(is_running: bool, has_result: bool) -> None:
    st.markdown("#### AI Analysis Status")
    steps = ["Parsing Resume", "Reading Job Description", "Matching Skills", "ATS Scoring", "Generating Suggestions"]
    done_idx = len(steps) if has_result else (3 if is_running else 0)
    for idx, step in enumerate(steps, start=1):
        state = "✅" if idx <= done_idx else "⏳"
        st.markdown(f"- {state} {step}")
    st.progress(1.0 if has_result else (0.6 if is_running else 0.0))


def _match_preview_card(result: dict) -> None:
    sc = result.get("score", {})
    match = float(sc.get("match_score", 0))
    confidence = max(35.0, min(98.0, (match * 0.7) + 25.0))
    fit_label = _strength_label(match)
    st.markdown(
        f"""
        <div class="hs-card hs-hero-score">
          <div class="hs-score-kicker">Live Match Intelligence</div>
          <div class="hs-score-main">{match:.1f}%</div>
          <div class="hs-score-sub">Role Fit: {fit_label} · Confidence: {confidence:.1f}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(max(0.0, min(1.0, match / 100.0)))
    st.markdown("#### Match Preview")
    c1, c2 = st.columns(2)
    c1.metric("Estimated Match", f"{match:.1f}%")
    c2.metric("Likely Fit", fit_label)
    st.caption("Top matching skills")
    skill_chips((sc.get("matched_skills") or [])[:5] or ["No strong match"], limit=5)
    st.caption("Missing skills preview")
    skill_chips((sc.get("missing_skills") or [])[:5] or ["No major gap"], limit=5)


def _ai_summary_card(result: dict) -> None:
    sc = result.get("score", {})
    ats = float(result.get("ats", 0))
    summary = (
        "Candidate shows strong alignment with core role requirements."
        if sc.get("match_score", 0) >= 75
        else "Candidate shows moderate fit with visible optimization opportunities."
    )
    if ats < 60:
        summary += " ATS optimization needs immediate attention for better shortlist outcomes."
    st.markdown("#### AI Recruiter Summary")
    st.markdown(f'<div class="hs-card"><div class="hs-muted">{summary}</div></div>', unsafe_allow_html=True)


def _confidence_card(result: dict) -> None:
    sc = result.get("score", {})
    match = float(sc.get("match_score", 0))
    confidence = max(35.0, min(98.0, (match * 0.7) + 25.0))
    action = "Strong Match" if match >= 76 else ("Review Further" if match >= 55 else "Low Fit")
    st.markdown("#### Confidence & Recommendation")
    m1, m2 = st.columns(2)
    m1.metric("Confidence Score", f"{confidence:.1f}%")
    m2.metric("Recommended Action", action)
    st.progress(confidence / 100.0)
    st.caption("Recruiter next step: Move forward when confidence is high and missing critical gaps are low.")


def _fit_breakdown_card(result: dict) -> None:
    sc = result.get("score", {})
    st.markdown("#### Candidate Fit Breakdown")
    pairs = [
        ("Skills Match", float(sc.get("skill_score", 0))),
        ("Experience Match", float(sc.get("experience_score", 0))),
        ("ATS Compatibility", float(result.get("ats", 0))),
        ("Project Relevance", float(sc.get("project_score", 0))),
        ("Keyword Alignment", min(100.0, float(sc.get("skill_score", 0)) * 1.08)),
    ]
    for label, val in pairs:
        st.caption(f"{label}: {val:.1f}%")
        st.progress(max(0.0, min(1.0, val / 100.0)))


def _keyword_gap_card(result: dict) -> None:
    sc = result.get("score", {})
    parsed = result.get("parsed")
    st.markdown("#### Keyword Gap Analysis")
    matched = (sc.get("matched_skills") or [])[:10]
    missing = (sc.get("missing_skills") or [])[:10]
    overused = _overused_keywords(parsed.raw_text if parsed else "", matched)
    st.caption("Matched keywords")
    skill_chips(matched or ["No direct match"], limit=10)
    st.caption("Missing keywords")
    skill_chips(missing or ["No critical missing keyword"], limit=10)
    st.caption("Overused keywords")
    skill_chips(overused or ["No obvious overuse"], limit=6)


def _jd_intelligence_card(jd_skills: list[str]) -> None:
    st.markdown("#### JD Intelligence")
    if not jd_skills:
        st.caption("Add JD content to unlock extracted role intelligence.")
        return
    st.caption(f"Detected required tools/skills: {len(jd_skills)}")
    skill_chips(jd_skills[:14], limit=14)


def _analytics_snapshot(db: Session, user: User, current_result: dict | None) -> None:
    rows = (
        db.query(UserResumeAnalysis)
        .filter(UserResumeAnalysis.user_id == user.id)
        .order_by(UserResumeAnalysis.created_at.desc())
        .limit(120)
        .all()
    )
    total = len(rows)
    match = float(current_result["score"].get("match_score", 0)) if current_result else (float(rows[0].match_percent) if rows else 0.0)
    ats = float(current_result.get("ats", 0)) if current_result else (float(rows[0].skill_score) if rows else 0.0)
    skill_match = float(current_result["score"].get("skill_score", 0)) if current_result else (float(rows[0].skill_score) if rows else 0.0)
    exp_fit = float(current_result["score"].get("experience_score", 0)) if current_result else (float(rows[0].experience_score) if rows else 0.0)
    missing_count = len((current_result["score"].get("missing_skills") or [])) if current_result else 0
    strong = sum(1 for r in rows if (r.match_percent or 0) >= 72)
    recommendation = _strength_label(match)
    keyword_cov = min(100.0, skill_match * 1.08)

    st.markdown("### Analytics Snapshot")
    st.caption("Performance KPIs from current run and recent analysis history.")
    c = st.columns(4)
    with c[0]:
        kpi_card("Analysis Runs", str(total), "Total · session", tone="neutral")
    with c[1]:
        kpi_card("ATS Match Score", f"{match:.1f}%", "Current · live", tone="positive" if match >= 72 else "warning")
    with c[2]:
        kpi_card("Skill Match %", f"{skill_match:.1f}%", "Coverage · role", tone="positive" if skill_match >= 68 else "neutral")
    with c[3]:
        kpi_card("Keyword Coverage", f"{keyword_cov:.1f}%", "ATS · keyword", tone="neutral")

    c2 = st.columns(4)
    with c2[0]:
        kpi_card("Missing Skills", str(missing_count), "Gaps · critical", tone="warning" if missing_count else "neutral")
    with c2[1]:
        kpi_card("Experience Relevance", f"{exp_fit:.1f}%", "Fit · seniority", tone="neutral")
    with c2[2]:
        kpi_card("Resume Strength", recommendation, "AI recommendation", tone="positive" if recommendation == "Strong Match" else "neutral")
    with c2[3]:
        kpi_card("Strong Reports", str(strong), "72%+ quality", tone="positive" if strong else "neutral")

    st.markdown("#### Score Breakdown Chart")
    st.caption("Visual distribution of core scoring components for recruiter decision-making.")
    try:
        import pandas as pd
        import plotly.graph_objects as go

        chart_df = pd.DataFrame(
            [
                {"metric": "Match", "score": match},
                {"metric": "ATS", "score": ats},
                {"metric": "Skills", "score": skill_match},
                {"metric": "Experience", "score": exp_fit},
                {
                    "metric": "Education",
                    "score": float(current_result["score"].get("education_score", 0))
                    if current_result
                    else (float(rows[0].education_score) if rows else 0.0),
                },
            ]
        )
        fig = go.Figure(
            data=[
                go.Bar(
                    x=chart_df["metric"],
                    y=chart_df["score"],
                    marker=dict(
                        color=["#7c3aed", "#4f46e5", "#06b6d4", "#10b981", "#f59e0b"],
                        line=dict(color="rgba(255,255,255,0.2)", width=1),
                    ),
                    text=[f"{v:.1f}%" for v in chart_df["score"]],
                    textposition="outside",
                )
            ]
        )
        fig.update_layout(
            template="plotly_dark" if st.session_state.get("theme") == "dark" else "plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_range=[0, 100],
            margin=dict(l=10, r=10, t=18, b=8),
            title="Live recruiter intelligence components",
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.caption("Chart temporarily unavailable. KPI cards remain active.")


def _improvement_lane(result: dict | None) -> None:
    st.markdown("### Resume Improvement Lane")
    if not result:
        empty_state(
            "No recommendation lane yet",
            "Run an analysis to generate AI-prioritized improvement suggestions with severity and priority.",
            "Complete inputs and run analysis.",
        )
        return
    recs = (result.get("suggestions") or [])[:8]
    if not recs:
        recs = [
            "Add quantified impact bullets",
            "Improve ATS keyword coverage",
            "Strengthen project descriptions",
            "Add recruiter-friendly summary",
        ]
    for idx, item in enumerate(recs, start=1):
        sev = "High" if idx <= 2 else ("Medium" if idx <= 5 else "Low")
        prio = "P1" if idx <= 2 else ("P2" if idx <= 5 else "P3")
        st.markdown(
            f"""
            <div class="hs-card hs-ai-suggestion-card">
              <span class="hs-badge">{sev}</span>
              <span class="hs-badge warn">{prio}</span>
              <h4 style="margin-top:0.55rem;">{item}</h4>
              <div class="hs-muted">Actionable AI recommendation for higher recruiter confidence.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _history_table(db: Session, user: User) -> None:
    st.markdown("### Resume Intelligence History")
    st.caption("Track previous analysis sessions, ATS status, and compare-ready reports.")
    rows = (
        db.query(UserResumeAnalysis)
        .filter(UserResumeAnalysis.user_id == user.id)
        .order_by(UserResumeAnalysis.created_at.desc())
        .limit(40)
        .all()
    )
    if not rows:
        st.markdown(
            """
            <div class="hs-card hs-empty-illustrated">
              <div class="hs-badge">No Reports Yet</div>
              <h4 style="margin-top:.45rem;">Your analysis history will appear here</h4>
              <div class="hs-muted">Run your first intelligence workflow to generate report records, ATS states, and compare actions.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    st.dataframe(
        [
            {
                "candidate_or_file": f"Resume Report #{r.id}",
                "role_targeted": (r.job_description_text[:44] + "...") if len(r.job_description_text or "") > 44 else (r.job_description_text or "—"),
                "match_score": round(float(r.match_percent or 0), 1),
                "ats_score": round(float(r.skill_score or 0), 1),
                "date": r.created_at.strftime("%Y-%m-%d %H:%M"),
                "status": r.strength,
                "actions": "Open | Export | Compare",
            }
            for r in rows
        ],
        hide_index=True,
        use_container_width=True,
    )


def _parse_shared_analysis_query_id(qp) -> int | None:
    if "shared_analysis" not in qp:
        return None
    raw = qp.get("shared_analysis")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if raw is None or raw == "":
        return None
    try:
        return int(str(raw))
    except ValueError:
        return None


def _share_base_url() -> str:
    try:
        u = getattr(st.context, "url", None) or ""
        u = str(u).strip().rstrip("/")
        if u:
            return u
    except Exception:
        pass
    try:
        h = st.context.headers
        host = h.get("Host") or h.get("host") or "localhost:8501"
        proto = h.get("X-Forwarded-Proto") or h.get("x-forwarded-proto") or "http"
        return f"{proto}://{host}".rstrip("/")
    except Exception:
        return "http://localhost:8501"


def _result_dict_from_row(row: UserResumeAnalysis) -> dict:
    bd = row.breakdown or {}
    project_score = float(bd.get("project_score", row.skill_score * 0.9))
    score = {
        "match_score": float(row.match_percent),
        "matched_skills": row.matched_skills or [],
        "missing_skills": row.missing_skills or [],
        "skill_score": float(row.skill_score),
        "experience_score": float(row.experience_score),
        "education_score": float(row.education_score),
        "project_score": project_score,
        "breakdown": bd,
    }
    ats = max(
        0.0,
        min(
            100.0,
            score["skill_score"] * 0.5
            + score["experience_score"] * 0.2
            + score["education_score"] * 0.12
            + project_score * 0.18,
        ),
    )
    jd = process_job_description(row.job_description_text or "")
    return {
        "resume_name": "Saved analysis",
        "parsed_name": "—",
        "parsed": None,
        "jd_text": row.job_description_text or "",
        "jd_skills": jd.required_skills,
        "score": score,
        "ats": ats,
        "suggestions": row.suggestions or [],
        "created_at": row.created_at,
        "toggles": {},
    }


def _persist_analysis_row(db: Session, user: User, result: dict) -> int:
    sc = result.get("score", {})
    row = UserResumeAnalysis(
        user_id=user.id,
        job_description_text=result.get("jd_text", ""),
        uploaded_file_id=None,
        match_percent=float(sc.get("match_score", 0.0)),
        matched_skills=sc.get("matched_skills") or [],
        missing_skills=sc.get("missing_skills") or [],
        suggestions=result.get("suggestions") or [],
        strength=_strength_label(float(sc.get("match_score", 0.0))),
        skill_score=float(sc.get("skill_score", 0.0)),
        experience_score=float(sc.get("experience_score", 0.0)),
        education_score=float(sc.get("education_score", 0.0)),
        breakdown=sc.get("breakdown"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def _render_admin_public_intake(db: Session) -> None:
    page_header(
        "Public Intake Command Center",
        "Review direct resume submissions and update shortlist status.",
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

    st.markdown("### Public Intake Inbox")
    kf1, kf2 = st.columns([1.4, 1.0], gap="medium")
    keyword_filter = kf1.text_input("Keyword filter", placeholder="react, python, sql", key="admin_keyword_filter")
    status_filter = kf2.selectbox("Status", options=["all", "under_review", "rejected", "shortlisted"], key="admin_status_filter")

    filtered = rows
    if status_filter != "all":
        filtered = [r for r in filtered if r.status == status_filter]
    if keyword_filter.strip():
        keys = [k.strip().lower() for k in keyword_filter.replace("\n", ",").split(",") if k.strip()]
        filtered = [r for r in filtered if any(k in (r.role_keywords or "").lower() or k in " ".join(r.extracted_skills or []).lower() for k in keys)]
    if not filtered:
        st.caption("No public submissions found for current filter.")
        return

    for r in filtered[:80]:
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


def _ats_score(score: dict, parsed) -> float:
    completeness = 100.0
    completeness -= 16.0 if not parsed.education else 0.0
    completeness -= 16.0 if not parsed.experience else 0.0
    completeness -= 20.0 if not getattr(parsed, "projects", None) else 0.0
    blended = (
        score.get("skill_score", 0) * 0.5
        + score.get("experience_score", 0) * 0.2
        + score.get("education_score", 0) * 0.12
        + score.get("project_score", 0) * 0.18
    )
    return max(0.0, min(100.0, (blended * 0.75) + (completeness * 0.25)))


def _strength_label(match_score: float) -> str:
    m = float(match_score or 0)
    if m >= 86:
        return "Strong Match"
    if m >= 72:
        return "Review Further"
    if m >= 52:
        return "Needs Optimization"
    return "Low Fit"


def _overused_keywords(raw_text: str, matched: list[str]) -> list[str]:
    txt = (raw_text or "").lower()
    over: list[str] = []
    for kw in matched[:8]:
        token = kw.lower().strip()
        if token and txt.count(token) >= 7:
            over.append(token)
    return over[:6]


def _export_report_blob(result: dict) -> bytes:
    sc = result.get("score", {})
    lines = [
        "HireSense AI - Resume Intelligence Report",
        f"Generated at: {datetime.utcnow().isoformat()}Z",
        f"Resume: {result.get('resume_name', '—')}",
        f"Match Score: {float(sc.get('match_score', 0)):.1f}%",
        f"ATS Score: {float(result.get('ats', 0)):.1f}%",
        f"Skills Match: {float(sc.get('skill_score', 0)):.1f}%",
        f"Experience Match: {float(sc.get('experience_score', 0)):.1f}%",
        f"Education Alignment: {float(sc.get('education_score', 0)):.1f}%",
        "",
        "Top Missing Skills:",
    ]
    for s in (sc.get("missing_skills") or [])[:10]:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("Top Recommendations:")
    for rec in (result.get("suggestions") or [])[:10]:
        lines.append(f"- {rec}")
    return "\n".join(lines).encode("utf-8")
