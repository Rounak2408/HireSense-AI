"""
HireSense AI — premium resume screening & candidate intelligence platform.
Run: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from database import init_db
from database.models import PublicResumeSubmission, User
from database.session import SessionLocal
from services import auth_service
from services.resume_parser import parse_resume_bytes
from ui.components import brand_header, mobile_wall
from ui.pages import analytics, candidates, dashboard, history, resume_checker, upload_screening
from ui.theme import inject_theme, theme_toggle
from utils.text_utils import normalize_skill

st.set_page_config(
    page_title="HireSense AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "theme" not in st.session_state:
    st.session_state.theme = "dark"


def get_db() -> Session:
    return SessionLocal()


def require_init() -> None:
    try:
        init_db()
    except Exception as exc:  # pragma: no cover - connection errors at runtime
        st.error(f"Database initialization failed: {exc}")
        st.stop()


def auth_shell() -> User | None:
    require_init()
    st.markdown(
        """
        <div class="hs-auth-shell">
          <div class="hs-auth-glow"></div>
          <div class="hs-auth-kicker">HireSense AI</div>
          <h1>Log in</h1>
          <p>Log in to your account and continue your hiring intelligence workflow.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left_pad, center, right_pad = st.columns([1, 1.15, 1], gap="large")
    with center:
        st.markdown('<div class="hs-auth-card hs-auth-centered">', unsafe_allow_html=True)
        st.markdown('<div class="hs-auth-brand-line">HireSense</div>', unsafe_allow_html=True)
        auth_mode = st.radio(
            "Auth mode",
            options=["Log in", "Sign up"],
            horizontal=True,
            key="auth_mode_switch",
            label_visibility="collapsed",
        )
        db = get_db()
        try:
            if auth_mode == "Log in":
                u = st.text_input("Email / Username", key="l_user", placeholder="Enter your email address")
                p = st.text_input("Password", type="password", key="l_pass", placeholder="Enter your password")
                if st.button("Sign in", type="primary"):
                    user = auth_service.authenticate(db, u, p)
                    if not user:
                        st.error("Invalid credentials.")
                    else:
                        st.session_state.user_id = user.id
                        st.session_state.username = user.username
                        st.session_state.role = user.role
                        st.session_state.full_name = user.full_name or user.username
                        st.rerun()
            else:
                email = st.text_input("Email", key="s_mail", placeholder="you@company.com")
                username = st.text_input("Choose username", key="s_user", placeholder="choose a workspace username")
                full = st.text_input("Full name (optional)", key="s_fn", placeholder="your full name")
                role = st.selectbox("Role", options=["recruiter", "candidate"])
                p1 = st.text_input("Password", type="password", key="s_p1", placeholder="create a secure password")
                p2 = st.text_input("Confirm password", type="password", key="s_p2", placeholder="re-enter password")
                if st.button("Create account"):
                    if not email or not username or not p1:
                        st.error("Email, username, and password are required.")
                    elif p1 != p2:
                        st.error("Passwords do not match.")
                    elif auth_service.get_user_by_email(db, email) or auth_service.get_user_by_username(db, username):
                        st.error("User already exists.")
                    else:
                        auth_service.create_user(db, email=email, username=username, password=p1, role=role, full_name=full or None)
                        st.success("Account created — please sign in.")
        finally:
            st.markdown("</div>", unsafe_allow_html=True)
            db.close()
        _guest_resume_preview()
    return None


def _guest_resume_preview() -> None:
    st.markdown("### Quick ATS Preview")
    st.caption("Upload a resume and get an instant ATS-friendly score preview.")
    file = st.file_uploader(
        "Upload resume for ATS preview",
        type=["pdf", "docx"],
        key="guest_resume_upload",
        label_visibility="collapsed",
    )
    if not file:
        return
    try:
        parsed = parse_resume_bytes(file.getvalue(), file.name)
    except Exception as exc:
        st.error(f"Could not parse resume: {exc}")
        return

    ats_score, suggestions = _guest_ats_score_and_suggestions(parsed)
    project_count = _project_count_from_parsed(parsed)
    st.markdown('<div class="hs-auth-preview-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3, gap="medium")
    c1.metric("ATS Friendly Score", f"{ats_score:.1f}%")
    c2.metric("Skills Extracted", len(parsed.skills or []))
    c3.metric("Projects in Resume", project_count)
    st.markdown('<div class="hs-preview-chip">Limited Preview</div>', unsafe_allow_html=True)
    st.caption("Login to unlock full report, risk panel, and recruiter insights.")
    st.markdown("**Top improvement suggestions (preview)**")
    for tip in suggestions[:2]:
        st.markdown(f"- {tip}")
    for tip in suggestions[2:]:
        st.markdown(f'<div class="hs-locked-suggestion">- {tip}</div>', unsafe_allow_html=True)
    st.info("Please log in to unlock full analysis.", icon="🔒")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    _public_candidate_intake()


def _guest_ats_score_and_suggestions(parsed) -> tuple[float, list[str]]:
    has_education = 1.0 if parsed.education else 0.0
    has_experience = 1.0 if parsed.experience else 0.0
    has_projects = 1.0 if getattr(parsed, "projects", None) else 0.0
    skills_count = len(parsed.skills or [])
    highlights_count = len(getattr(parsed, "project_highlights", []) or [])

    section_score = ((has_education + has_experience + has_projects) / 3.0) * 100.0
    skill_score = min(100.0, skills_count * 5.5)
    project_score = min(100.0, 30.0 + highlights_count * 14.0) if has_projects else 25.0
    ats_score = (section_score * 0.35) + (skill_score * 0.45) + (project_score * 0.20)

    suggestions: list[str] = []
    if not parsed.education:
        suggestions.append("Add an Education section with degree, college, and graduation year.")
    if not parsed.experience:
        suggestions.append("Add role-wise experience bullets with measurable outcomes.")
    if not has_projects:
        suggestions.append("Add a Projects section with stack, role, and impact.")
    if skills_count < 12:
        suggestions.append("Increase job-relevant keywords (current skills coverage is low).")
    if highlights_count < 2:
        suggestions.append("Add quantified project impact (latency %, users, accuracy, revenue/time saved).")
    suggestions.append("Use ATS-friendly headings: Summary, Skills, Experience, Projects.")
    suggestions.append("Replace generic lines with measurable impact bullets.")

    # Keep deterministic unique order.
    deduped: list[str] = []
    seen: set[str] = set()
    for tip in suggestions:
        if tip not in seen:
            seen.add(tip)
            deduped.append(tip)
    return max(0.0, min(100.0, ats_score)), deduped[:6]


def _project_count_from_parsed(parsed) -> int:
    names = getattr(parsed, "project_names", []) or []
    if names:
        return len(names)
    project_text = getattr(parsed, "projects", None) or ""
    if not project_text.strip():
        return 0
    lines = [ln.strip() for ln in project_text.splitlines() if ln.strip()]
    heading_like = [ln for ln in lines if len(ln.split()) <= 8 and ":" in ln]
    if heading_like:
        return min(10, len(heading_like))
    # Fallback heuristic when project headings are not explicit.
    return max(1, min(10, len(lines) // 3))


def _public_candidate_intake() -> None:
    st.markdown("### Quick Apply Intake (Shareable)")
    st.caption("Candidates can directly submit resume for HR pre-screening.")
    name = st.text_input("Candidate Name", key="public_name", placeholder="Full name")
    email = st.text_input("Candidate Email", key="public_email", placeholder="name@email.com")
    keywords = st.text_area(
        "Role Keywords (from HR)",
        key="public_keywords",
        placeholder="react, typescript, api, sql, aws",
        height=90,
    )
    resume = st.file_uploader(
        "Upload Resume (PDF/DOCX)",
        type=["pdf", "docx"],
        key="public_resume",
    )
    if st.button("Submit for HR Screening", type="primary", key="public_submit"):
        if not name.strip() or not email.strip() or not keywords.strip() or not resume:
            st.error("Please fill name, email, keywords, and resume.")
            return
        try:
            parsed = parse_resume_bytes(resume.getvalue(), resume.name)
            ats, _ = _guest_ats_score_and_suggestions(parsed)
            match = _keyword_match_percent(parsed.skills or [], keywords)
            status = "rejected" if match < 30.0 else "under_review"
            notice = (
                "You are currently not fit for this role (match below 30%)."
                if status == "rejected"
                else "Your profile has been submitted to HR for review."
            )
            db = get_db()
            try:
                row = PublicResumeSubmission(
                    candidate_name=name.strip(),
                    candidate_email=email.strip().lower(),
                    role_keywords=keywords.strip(),
                    extracted_skills=parsed.skills or [],
                    keyword_match_percent=round(match, 2),
                    ats_preview_score=round(ats, 2),
                    status=status,
                    candidate_notice=notice,
                    original_filename=resume.name,
                )
                db.add(row)
                db.commit()
            finally:
                db.close()
            if status == "rejected":
                st.error(f"🔔 {notice}")
            else:
                st.success(f"✅ {notice}")
        except Exception as exc:
            st.error(f"Submission failed: {exc}")


def _keyword_match_percent(candidate_skills: list[str], keywords_text: str) -> float:
    raw_keys = [k.strip().lower() for k in keywords_text.replace("\n", ",").split(",") if k.strip()]
    key_set = {normalize_skill(k) for k in raw_keys}
    skill_set = {normalize_skill(s) for s in candidate_skills if s}
    if not key_set:
        return 0.0
    matched = len(key_set & skill_set)
    return (matched / len(key_set)) * 100.0


def main_app(user: User) -> None:
    brand_header()
    theme_toggle()
    inject_theme()
    mobile_wall()
    st.sidebar.text_input("Quick search", placeholder="Search candidate / skill / JD", key="hs_sidebar_search")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Signed in as {user.full_name or user.username}")
    st.sidebar.caption(f"Role: {user.role}")
    if st.sidebar.button("Sign out"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.session_state.theme = "dark"
        st.rerun()

    if user.role == "recruiter":
        st.sidebar.caption("Recruiter workspace")
        nav = st.sidebar.radio(
            "Navigate",
            options=[
                "Overview · Dashboard",
                "Intake · Upload",
                "Pipeline · Candidates",
                "Insights · Analytics",
                "Intelligence · Resume checker",
                "Archive · History",
            ],
        )
    else:
        st.sidebar.caption("Candidate workspace")
        nav = st.sidebar.radio(
            "Navigate",
            options=["Overview · Dashboard", "Intelligence · Resume checker", "Archive · History"],
        )

    db = get_db()
    try:
        if nav.endswith("Dashboard"):
            dashboard.render(db, user)
        elif nav.endswith("Upload"):
            upload_screening.render(db, user)
        elif nav.endswith("Candidates"):
            candidates.render(db, user)
        elif nav.endswith("Analytics"):
            analytics.render(db, user)
        elif nav.endswith("Resume checker"):
            resume_checker.render(db, user)
        elif nav.endswith("History"):
            history.render(db, user)
    finally:
        db.close()


def load_user() -> User | None:
    if "user_id" not in st.session_state:
        return None
    db = get_db()
    try:
        return db.query(User).filter(User.id == st.session_state.user_id).first()
    finally:
        db.close()


def main() -> None:
    st.session_state.setdefault("theme", "dark")
    user = load_user()
    if not user:
        brand_header()
        theme_toggle()
        inject_theme()
        mobile_wall()
        auth_shell()
        return
    main_app(user)


if __name__ == "__main__":
    main()
