"""Premium resume intelligence workspace for recruiters and candidates."""

from __future__ import annotations

import hashlib
import json
import time

import streamlit as st
from sqlalchemy.orm import Session

from database.models import UploadedFile, User, UserResumeAnalysis
from services.file_storage import store_upload
from services.jd_processor import process_job_description
from services.matching_engine import score_candidate, suggest_improvements
from services.resume_parser import parse_resume_bytes
from ui.components import empty_state, progress_pct, skill_chips


def render(db: Session, user: User) -> None:
    st.session_state.setdefault("rc_result", None)
    st.session_state.setdefault("rc_decision", "Pending review")

    _hero_header(user)
    jd_text, file, analyze = _analysis_workspace()
    current_signature = _input_signature(jd_text, file)

    # Prevent stale analytics when JD/resume changes.
    if st.session_state.get("rc_result") and current_signature:
        prev_sig = st.session_state["rc_result"].get("input_signature")
        if prev_sig and prev_sig != current_signature:
            st.session_state.rc_result = None
            st.info("New resume/JD detected. Click **Analyze Candidate Fit** to generate fresh analytics.")

    if analyze:
        if not jd_text.strip():
            st.error("Paste hiring requirements before analysis.")
        elif not file:
            st.error("Drop candidate resume before analysis.")
        else:
            result = _run_analysis_pipeline(db, user, jd_text, file)
            if result:
                result["input_signature"] = current_signature
                st.session_state.rc_result = result
                st.toast("Report generated successfully.", icon="✅")
                st.rerun()

    result = st.session_state.get("rc_result")
    if not result:
        _premium_empty_state()
        return

    _summary_strip(result["score"], result["strength"], result["parsed"])
    _history_save_bar(db, user, result)
    _dashboard_layout(result)


def _hero_header(user: User) -> None:
    ts = time.strftime("%d %b %Y, %I:%M %p")
    st.markdown(
        f"""
        <div class="hs-hero">
          <div>
            <div class="hs-kicker">HireSense AI · Recruiter Intelligence Workspace</div>
            <h1>Resume Intelligence</h1>
            <p>AI-powered evaluation for ATS readiness, project depth, skill fit, and hiring confidence.</p>
            <div style="display:flex;gap:.5rem;flex-wrap:wrap;">
              <span class="hs-pill">Smart analysis</span>
              <span class="hs-pill">Last analyzed: {ts}</span>
              <span class="hs-pill">Team: Talent Ops</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    qa1, qa2, qa3 = st.columns([1, 1, 1.4])
    qa1.button("New analysis", use_container_width=True, key="new_analysis_btn")
    qa2.button("Open history", use_container_width=True, key="open_history_btn")
    qa3.caption(f"Signed in as {user.full_name or user.username}")


def _analysis_workspace() -> tuple[str, object, bool]:
    st.session_state.setdefault("rc_upload_key", 0)
    st.markdown("### Analysis Workspace")
    left, right = st.columns([1.45, 1.0], gap="large")

    with left:
        st.markdown("**Paste hiring requirements**")
        st.caption("Tip: Include must-have stack, role seniority, and expected business outcomes.")
        jd_text = st.text_area(
            "Job description",
            label_visibility="collapsed",
            placeholder="Example: 3+ years React/TypeScript, API integration, performance optimization, production deployment ownership.",
            height=220,
        )
    with right:
        st.markdown("**Drop candidate resume**")
        st.caption("AI compares skills, projects, experience, and ATS readiness.")
        file = st.file_uploader(
            "Resume upload",
            label_visibility="collapsed",
            type=["pdf", "docx"],
            help="PDF or DOCX, up to ~25 MB.",
            key=f"rc_upload_{st.session_state.rc_upload_key}",
        )
        if file:
            st.success(f"Uploaded: {file.name}")
            a1, a2 = st.columns(2)
            if a1.button("Replace file", key="replace_file_btn", use_container_width=True):
                st.session_state.rc_upload_key += 1
                st.rerun()
            if a2.button("Remove file", key="remove_file_btn", use_container_width=True):
                st.session_state.rc_upload_key += 1
                st.rerun()
    analyze = st.button("Analyze Candidate Fit", type="primary", use_container_width=True)
    return jd_text, file, analyze


def _run_analysis_pipeline(db: Session, user: User, jd_text: str, file) -> dict | None:
    steps = [
        "Parsing resume",
        "Extracting skills",
        "Evaluating ATS quality",
        "Matching job description",
        "Generating insights",
    ]
    p = st.progress(0.0, text="Starting analysis...")
    for i, step in enumerate(steps, start=1):
        time.sleep(0.08)
        p.progress(i / len(steps), text=f"{step}...")

    try:
        data = file.getvalue()
        parsed = parse_resume_bytes(data, file.name)
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
        tips = suggest_improvements(
            score["missing_skills"],
            jd_text,
            score.get("project_score"),
            (score.get("breakdown") or {}).get("project_analysis"),
        )
        strength_label = _premium_strength_label(score.get("match_score", 0))
        rel = store_upload(user.id, data, file.name)
        uf = UploadedFile(
            user_id=user.id,
            original_filename=file.name,
            stored_path=rel,
            mime_type=file.type,
            related_entity="resume_analysis",
            related_id=None,
        )
        db.add(uf)
        db.commit()
        db.refresh(uf)

        row = UserResumeAnalysis(
            user_id=user.id,
            job_description_text=jd.raw_text,
            uploaded_file_id=uf.id,
            match_percent=score["match_score"],
            matched_skills=score["matched_skills"],
            missing_skills=score["missing_skills"],
            suggestions=tips,
            strength=strength_label,
            skill_score=score["skill_score"],
            experience_score=score["experience_score"],
            education_score=score["education_score"],
            breakdown=score.get("breakdown"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        p.empty()
        return {
            "parsed": parsed,
            "score": score,
            "tips": tips,
            "strength": strength_label,
            "jd_skills": jd.required_skills,
            "jd_text": jd_text,
            "uploaded_file_id": uf.id,
            "history_saved_id": row.id,
            "history_saved_at": str(row.created_at),
        }
    except Exception as exc:
        p.empty()
        st.error(f"Analysis failed: {exc}")
        return None


def _summary_strip(score: dict, strength_label: str, parsed) -> None:
    ats_score = _ats_score(score, parsed)
    risk = _risk_level(score)
    recommendation = _recommendation(score, ats_score)

    st.markdown("### Recruiter Decision Panel")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Overall Match", f"{score['match_score']:.1f}%")
    c2.metric("Candidate Fit", strength_label)
    c3.metric("ATS Compatibility", f"{ats_score:.1f}%")
    c4.metric("Risk Level", risk)
    c5.metric("Recommendation", recommendation)

    a1, a2, a3, a4 = st.columns(4)
    if a1.button("Shortlist", use_container_width=True):
        st.session_state.rc_decision = "Shortlisted"
        st.toast("Candidate moved to shortlist.", icon="✅")
    if a2.button("Hold", use_container_width=True):
        st.session_state.rc_decision = "On Hold"
    if a3.button("Reject", use_container_width=True):
        st.session_state.rc_decision = "Rejected"
    report_blob = json.dumps(
        {
            "match_score": score["match_score"],
            "skill_score": score.get("skill_score"),
            "experience_score": score.get("experience_score"),
            "education_score": score.get("education_score"),
            "project_score": score.get("project_score"),
            "decision": st.session_state.get("rc_decision"),
        },
        indent=2,
    )
    a4.download_button(
        "Export Report",
        data=report_blob,
        file_name="hiresense-report.json",
        mime="application/json",
        use_container_width=True,
    )
    st.caption(f"Current recruiter status: {st.session_state.get('rc_decision')}")


def _history_save_bar(db: Session, user: User, result: dict) -> None:
    st.markdown("### Archive + History")
    c1, c2 = st.columns([1.2, 2.2], gap="large")
    with c1:
        if st.button("Add to Archive + History", use_container_width=True, key="save_to_history_btn"):
            new_id = _save_result_to_history(db, user, result)
            st.session_state.rc_result["manual_history_id"] = new_id
            st.toast("Added to Archive + History.", icon="📌")
    with c2:
        auto_id = result.get("history_saved_id")
        manual_id = result.get("manual_history_id")
        if manual_id:
            st.success(f"Latest manual archive id: #{manual_id}")
        elif auto_id:
            st.caption(f"Auto-saved after analysis (id #{auto_id}). You can still save another snapshot manually.")
        else:
            st.caption("Click the button to archive this report snapshot.")


def _save_result_to_history(db: Session, user: User, result: dict) -> int:
    score = result["score"]
    row = UserResumeAnalysis(
        user_id=user.id,
        job_description_text=result.get("jd_text", ""),
        uploaded_file_id=result.get("uploaded_file_id"),
        match_percent=score["match_score"],
        matched_skills=score.get("matched_skills"),
        missing_skills=score.get("missing_skills"),
        suggestions=result.get("tips"),
        strength=result.get("strength") or _premium_strength_label(score.get("match_score", 0)),
        skill_score=score.get("skill_score", 0.0),
        experience_score=score.get("experience_score", 0.0),
        education_score=score.get("education_score", 0.0),
        breakdown=score.get("breakdown"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return int(row.id)


def _dashboard_layout(result: dict) -> None:
    left, right = st.columns([2.1, 1.0], gap="large")

    with left:
        _match_intelligence_panel(result["score"])
        _resume_health_panel(result["parsed"], result["score"])
        _skills_breakdown(result["score"], result["parsed"])
        _project_analysis_panel(result["parsed"], result["score"])
        _feedback_board(result["parsed"], result["score"], result["jd_skills"])

    with right:
        _candidate_strengths(result["score"], result["parsed"])
        _candidate_risks(result["score"])
        _recommendation_board(result["tips"], result["score"])


def _match_intelligence_panel(score: dict) -> None:
    st.markdown("### Match Intelligence")
    r1, r2 = st.columns([1.1, 1.4], gap="large")
    with r1:
        st.markdown(
            f"""
            <div class="hs-card">
              <div class="hs-muted">Overall Match Score</div>
              <div style="font-size:2.2rem;font-weight:800;margin-top:.35rem;">{score["match_score"]:.1f}%</div>
              <div class="hs-muted" style="margin-top:.3rem;">Recruiter confidence index for role fit decisioning.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        progress_pct("Skill alignment", score["skill_score"], "Coverage against required stack.")
        progress_pct("Experience alignment", score["experience_score"], "Seniority and scope confidence.")
        progress_pct("Education alignment", score["education_score"], "Academic relevance signals.")
        progress_pct("Project alignment", score.get("project_score", 0), "Project quality and impact fit.")
    with r2:
        try:
            import pandas as pd
            import plotly.graph_objects as go

            df = pd.DataFrame(
                [
                    {"metric": "Skills", "score": score["skill_score"]},
                    {"metric": "Experience", "score": score["experience_score"]},
                    {"metric": "Education", "score": score["education_score"]},
                    {"metric": "Projects", "score": score.get("project_score", 0)},
                ]
            )
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=df["metric"],
                        y=df["score"],
                        marker=dict(
                            color=["#7c3aed", "#22d3ee", "#10b981", "#f59e0b"],
                            line=dict(color="rgba(255,255,255,0.24)", width=1),
                        ),
                        text=[f"{x:.1f}%" for x in df["score"]],
                        textposition="outside",
                    )
                ]
            )
            fig.update_layout(
                template="plotly_dark" if st.session_state.get("theme") == "dark" else "plotly_white",
                title="Component score distribution",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_range=[0, 100],
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("Chart unavailable. Core scores are still computed.")


def _resume_health_panel(parsed, score: dict) -> None:
    st.markdown("### Resume Health / ATS Review")
    keyword_density = min(100.0, (len(score.get("matched_skills") or []) / max(1, len(parsed.skills or [1]))) * 100)
    completeness = 100.0
    completeness -= 20.0 if not parsed.education else 0.0
    completeness -= 20.0 if not parsed.experience else 0.0
    completeness -= 20.0 if not getattr(parsed, "projects", None) else 0.0
    bullet_quality = 42.0 + min(40.0, len(getattr(parsed, "project_highlights", []) or []) * 11.0)

    a, b, c = st.columns(3)
    a.metric("ATS readability", f"{_ats_score(score, parsed):.1f}%")
    b.metric("Section completeness", f"{max(0, completeness):.1f}%")
    c.metric("Keyword optimization", f"{keyword_density:.1f}%")
    progress_pct("Bullet quality", bullet_quality, "Impact-oriented, quantified statements.")


def _skills_breakdown(score: dict, parsed) -> None:
    st.markdown("### Skills Breakdown")
    matched = score.get("matched_skills") or []
    missing = score.get("missing_skills") or []
    all_sk = parsed.skills or []
    cat_map = {
        "Frontend": ["react", "next.js", "javascript", "typescript", "html", "css", "tailwind"],
        "Backend": ["python", "java", "node", "express", "django", "fastapi", "api"],
        "Databases": ["sql", "postgres", "mysql", "mongodb", "redis"],
        "Tools": ["git", "jira", "figma", "postman", "docker"],
        "Cloud": ["aws", "azure", "gcp", "kubernetes"],
        "AI/ML": ["machine learning", "tensorflow", "pytorch", "nlp", "llm"],
    }
    cols = st.columns(3)
    for i, (cat, keys) in enumerate(cat_map.items()):
        grp = [s for s in all_sk if any(k in s.lower() for k in keys)]
        with cols[i % 3]:
            st.markdown(f"**{cat}**")
            skill_chips(grp[:8] or ["-"])
    st.code(", ".join(matched[:24]), language="text")
    st.caption("Matched skills (use copy icon).")
    m1, m2 = st.columns(2)
    with m1:
        st.markdown("**Matched vs Missing**")
        skill_chips(matched[:20] or ["No strong matches"])
    with m2:
        st.markdown("**Critical Gaps**")
        skill_chips(missing[:20] or ["No major gaps"])


def _project_analysis_panel(parsed, score: dict) -> None:
    st.markdown("### Project Analysis")
    names = getattr(parsed, "project_names", []) or []
    highlights = getattr(parsed, "project_highlights", []) or []
    if not names and not highlights:
        st.info("No clear project cards detected. Add project titles and impact bullets for stronger recruiter signals.")
        return

    for idx, name in enumerate(names or ["Project insight"], start=1):
        hi = highlights[idx - 1] if idx - 1 < len(highlights) else "Project description available in resume."
        impact_score = min(98, 40 + len([c for c in hi if c.isdigit()]) * 8 + 18)
        complexity_score = min(96, 45 + len([w for w in ["api", "deploy", "architecture", "scale", "auth"] if w in hi.lower()]) * 11)
        recruiter_signal = "Strong" if impact_score >= 70 and complexity_score >= 68 else "Needs Review"
        with st.expander(f"{idx}. {name} · Recruiter signal: {recruiter_signal}", expanded=(idx == 1)):
            p1, p2, p3 = st.columns(3)
            p1.metric("Role relevance", f"{score.get('project_score', 0):.1f}%")
            p2.metric("Impact score", f"{impact_score:.0f}%")
            p3.metric("Complexity score", f"{complexity_score:.0f}%")
            st.markdown(f"**Strength:** {hi}")
            if impact_score < 65:
                st.warning("Concern: Add quantifiable business or technical impact.")
            if complexity_score < 65:
                st.warning("Concern: Mention architecture/deployment depth.")


def _candidate_strengths(score: dict, parsed) -> None:
    st.markdown("### Candidate Strengths")
    strengths = [
        "High skill alignment with role-required stack." if score.get("skill_score", 0) >= 70 else "Solid baseline skill fit for target role.",
        "Project section demonstrates practical application." if score.get("project_score", 0) >= 60 else "Projects present but need stronger impact proof.",
        "Experience narrative aligns with role outcomes." if score.get("experience_score", 0) >= 60 else "Experience exists with moderate role alignment.",
        f"Extracted skills: {min(len(parsed.skills or []), 24)} relevant signals identified.",
    ]
    for item in strengths:
        st.markdown(f"- {item}")


def _candidate_risks(score: dict) -> None:
    st.markdown("### Candidate Risks / Gaps")
    missing = score.get("missing_skills") or []
    risks = [
        "Missing critical skills: " + ", ".join(missing[:4]) if missing else "No major hard-skill misses detected.",
        "Low measurable outcomes in project bullets." if score.get("project_score", 0) < 60 else "Project outcomes mostly acceptable.",
        "ATS optimization may need work." if score.get("skill_score", 0) < 55 else "ATS keyword profile is healthy.",
        "Evidence depth should improve for interview confidence." if score.get("experience_score", 0) < 55 else "Experience confidence acceptable.",
    ]
    for r in risks:
        st.markdown(f"- {r}")


def _feedback_board(parsed, score: dict, jd_skills: list[str]) -> None:
    st.markdown("### Resume Feedback Board")
    issues, add_items, remove_items = _resume_feedback(parsed, score, jd_skills)
    cols = st.columns(3, gap="large")
    with cols[0]:
        st.markdown("**Issues Found (severity)**")
        for i in issues:
            st.error(f"HIGH · {i}") if "No measurable" in i or "missing" in i.lower() else st.warning(f"MEDIUM · {i}")
    with cols[1]:
        st.markdown("**Recommended Additions**")
        for i in add_items:
            st.info(i)
    with cols[2]:
        st.markdown("**What to Remove / Trim**")
        for i in remove_items:
            st.write(f"- {i}")


def _recommendation_board(tips: list[str], score: dict) -> None:
    st.markdown("### Recommendations Board")
    ats = score.get("skill_score", 0)
    shortlist = "Ready" if score.get("match_score", 0) >= 72 and ats >= 60 else "Needs Review"
    interview = "Suitable" if score.get("experience_score", 0) >= 58 else "Potential but verify depth"
    st.markdown(f"- **Shortlist readiness:** {shortlist}")
    st.markdown(f"- **Interview suitability:** {interview}")
    st.markdown(f"- **Role fit summary:** {_premium_strength_label(score.get('match_score', 0))}")
    st.markdown("- **Next step:** Schedule technical round focused on missing skills and architecture ownership.")
    st.markdown("---")
    if not tips:
        st.success("No major gaps detected.")
    else:
        for t in tips[:6]:
            st.markdown(f"- {t}")


def _premium_empty_state() -> None:
    st.markdown(
        """
        <div class="hs-card" style="padding:1.35rem 1.4rem;">
          <div class="hs-kicker">Onboarding</div>
          <h3 style="margin:.15rem 0 .5rem 0;">Start premium candidate analysis</h3>
          <p class="hs-muted" style="margin-bottom:.8rem;">
            Build a recruiter-ready intelligence report in under a minute. HireSense parses resume context,
            evaluates ATS safety, scores role fit, and generates actionable hiring guidance.
          </p>
          <div class="hs-auth-list-item"><span class="hs-auth-dot"></span><span>Step 1: Paste hiring requirements with must-have stack and outcomes.</span></div>
          <div class="hs-auth-list-item"><span class="hs-auth-dot"></span><span>Step 2: Upload candidate resume (PDF/DOCX).</span></div>
          <div class="hs-auth-list-item"><span class="hs-auth-dot"></span><span>Step 3: Run AI analysis and use decision panel for shortlist/hold/reject.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    empty_state(
        "No report generated yet",
        "Your dashboard will populate with fit intelligence, ATS diagnostics, project cards, and recruiter recommendations after first analysis.",
        "Paste JD -> Drop resume -> Click Analyze Candidate Fit.",
    )


def _premium_strength_label(match_score: float) -> str:
    m = float(match_score or 0)
    if m >= 86:
        return "Strong Fit"
    if m >= 72:
        return "Moderate Fit"
    if m >= 52:
        return "Needs Review"
    return "High Risk"


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


def _risk_level(score: dict) -> str:
    missing = len(score.get("missing_skills") or [])
    m = score.get("match_score", 0)
    if m >= 75 and missing <= 4:
        return "Low"
    if m >= 55 and missing <= 8:
        return "Medium"
    return "High"


def _recommendation(score: dict, ats_score: float) -> str:
    if score.get("match_score", 0) >= 74 and ats_score >= 65:
        return "Shortlist"
    if score.get("match_score", 0) >= 55:
        return "Hold"
    return "Reject"


def _input_signature(jd_text: str, file) -> str:
    if not jd_text and not file:
        return ""
    hasher = hashlib.md5()
    hasher.update((jd_text or "").strip().encode("utf-8", errors="ignore"))
    if file is not None:
        hasher.update((getattr(file, "name", "") or "").encode("utf-8", errors="ignore"))
        try:
            hasher.update(file.getvalue() or b"")
        except Exception:
            pass
    return hasher.hexdigest()


def _resume_feedback(parsed, score: dict, jd_skills: list[str]) -> tuple[list[str], list[str], list[str]]:
    issues: list[str] = []
    add_items: list[str] = []
    remove_items: list[str] = []

    highlights = getattr(parsed, "project_highlights", []) or []
    project_names = getattr(parsed, "project_names", []) or []
    project_meta = (score.get("breakdown") or {}).get("project_analysis") or {}
    missing = score.get("missing_skills") or []

    if not project_names:
        issues.append("Project names are not clearly written as headings.")
        add_items.append("Add clear headings like: 'Project: Real-Time Chat App'.")
    if len(highlights) < 2:
        issues.append("Project bullets are too few or unclear.")
        add_items.append("Write 3-4 bullets per project (problem, approach, impact).")
    if int(project_meta.get("impact_signal_count", 0)) == 0:
        issues.append("No measurable impact found in project descriptions.")
        add_items.append("Add numbers: latency -35%, accuracy 92%, users 5k+, etc.")
    if int(project_meta.get("complexity_signal_count", 0)) <= 1:
        issues.append("Low architecture depth signals.")
        add_items.append("Mention APIs, database design, auth, deployment, scaling.")
    if missing[:3]:
        issues.append("Key JD skills are missing from resume wording.")
        add_items.append("Include evidence for: " + ", ".join(missing[:3]))

    generic_words = ("good", "hardworking", "responsible", "team player", "interactive features")
    for line in highlights:
        if any(w in line.lower() for w in generic_words):
            remove_items.append("Replace generic lines like '" + line[:60] + "...' with specific impact.")
            break
    if len(highlights) > 4:
        remove_items.append("Trim repetitive project bullets; keep strongest 3-4 bullets.")
    remove_items.append("Avoid long paragraphs; use concise bullet points.")

    if not issues:
        issues.append("No major project issues detected.")
    if not add_items:
        add_items.append("Keep current structure and add one stronger metrics bullet.")
    if not remove_items:
        remove_items.append("No major content removal needed.")
    return issues[:5], add_items[:5], remove_items[:5]
