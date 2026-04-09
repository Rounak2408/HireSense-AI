"""Recruiter: job description + bulk resume upload."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from database.models import Candidate, JobDescription, UploadedFile, User
from services.file_storage import store_upload
from services.jd_processor import process_job_description
from services.resume_parser import parse_resume_bytes
from services.screening_service import ensure_candidate_skills, run_screening_for_job
from ui.components import skill_chips


def render(db: Session, user: User) -> None:
    if user.role != "recruiter":
        st.warning("Recruiter access only.")
        return

    st.markdown("### Upload & screen")
    st.caption("Drop candidate packs, attach the JD, and generate a ranked slate in one pass.")

    title = st.text_input("Role title", placeholder="Senior ML Engineer")
    jd_text = st.text_area("Job description", height=220, placeholder="Paste the full JD…")

    files = st.file_uploader(
        "Resumes (PDF/DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        help="Drag & drop supported",
    )

    existing = (
        db.query(JobDescription)
        .filter(JobDescription.user_id == user.id)
        .order_by(JobDescription.created_at.desc())
        .all()
    )
    job_options = {f"{j.title} (#{j.id})": j.id for j in existing}
    pick = st.selectbox("Active job context", options=list(job_options.keys()) or ["—"])

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        do_save = st.button("Save job & ingest resumes", type="primary", use_container_width=True)
    with col_b:
        append_files = st.button("Add resumes to selected job", use_container_width=True)
    with col_c:
        only_rescreen = st.button("Re-score selected job", use_container_width=True)

    if do_save:
        if not jd_text.strip():
            st.error("Job description is required.")
        else:
            with st.spinner("Structuring JD and ingesting resumes…"):
                proc = process_job_description(jd_text, title or None)
                job = JobDescription(
                    user_id=user.id,
                    title=(title or proc.title_guess or "Untitled Role")[:500],
                    raw_text=proc.raw_text,
                    extracted_skills=proc.required_skills,
                )
                db.add(job)
                db.commit()
                db.refresh(job)
                _ingest_files(db, user, job.id, files)
                run_screening_for_job(db, job.id)
            st.success("Job saved, resumes parsed, screening complete.")
            st.session_state["selected_job_id"] = job.id
            st.rerun()

    if append_files:
        if pick == "—":
            st.error("Select a job first.")
        elif not files:
            st.error("Upload at least one resume.")
        else:
            jid = job_options[pick]
            with st.spinner("Parsing new candidates…"):
                _ingest_files(db, user, jid, files)
                run_screening_for_job(db, jid)
            st.success("Resumes added and re-ranked.")
            st.session_state["selected_job_id"] = jid
            st.rerun()

    if only_rescreen:
        if pick == "—":
            st.error("No job to rescore.")
        else:
            jid = job_options[pick]
            with st.spinner("Recomputing matches…"):
                run_screening_for_job(db, jid)
            st.success("Ranking refreshed.")
            st.session_state["selected_job_id"] = jid
            st.rerun()

    if pick != "—":
        jid = job_options[pick]
        st.session_state["selected_job_id"] = jid
        job = db.query(JobDescription).filter(JobDescription.id == jid).first()
        if job:
            st.markdown("#### Extracted JD skills")
            skill_chips(list(job.extracted_skills or []))


def _ingest_files(db: Session, user: User, job_id: int, files) -> None:
    if not files:
        return
    for f in files:
        data = f.getvalue()
        parsed = parse_resume_bytes(data, f.name)
        cand = Candidate(
            job_description_id=job_id,
            created_by_user_id=user.id,
            name=parsed.name,
            email=parsed.email,
            phone=parsed.phone,
            education=parsed.education,
            experience=parsed.experience,
            raw_text=parsed.raw_text,
            years_experience=parsed.years_experience,
        )
        db.add(cand)
        db.commit()
        db.refresh(cand)
        rel = store_upload(user.id, data, f.name)
        uf = UploadedFile(
            user_id=user.id,
            original_filename=f.name,
            stored_path=rel,
            mime_type=f.type,
            related_entity="candidate",
            related_id=cand.id,
        )
        db.add(uf)
        db.commit()
        ensure_candidate_skills(db, cand, parsed.skills)
