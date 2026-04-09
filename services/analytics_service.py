"""Dashboard analytics queries."""

from __future__ import annotations

from sqlalchemy.orm import Session

from database.models import Candidate, JobDescription, ScreeningResult, UserResumeAnalysis


def screening_history(db: Session, user_id: int, limit: int = 50) -> list[dict]:
    jobs = (
        db.query(JobDescription)
        .filter(JobDescription.user_id == user_id)
        .order_by(JobDescription.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for j in jobs:
        n = db.query(Candidate).filter(Candidate.job_description_id == j.id).count()
        top = (
            db.query(ScreeningResult)
            .filter(ScreeningResult.job_description_id == j.id)
            .order_by(ScreeningResult.match_score.desc())
            .first()
        )
        out.append(
            {
                "job_id": j.id,
                "title": j.title,
                "created_at": j.created_at,
                "candidates": n,
                "best_score": top.match_score if top else None,
            }
        )
    return out


def candidate_rankings(db: Session, job_id: int) -> list[dict]:
    rows = (
        db.query(ScreeningResult, Candidate)
        .join(Candidate, Candidate.id == ScreeningResult.candidate_id)
        .filter(ScreeningResult.job_description_id == job_id)
        .order_by(ScreeningResult.match_score.desc())
        .all()
    )
    result: list[dict] = []
    for sr, c in rows:
        result.append(
            {
                "rank": sr.rank,
                "name": c.name or "Unknown",
                "email": c.email,
                "match_score": sr.match_score,
                "skill_score": sr.skill_score,
                "experience_score": sr.experience_score,
                "education_score": sr.education_score,
                "shortlist": sr.shortlist,
                "matched_skills": sr.matched_skills or [],
                "missing_skills": sr.missing_skills or [],
                "candidate_id": c.id,
            }
        )
    return result


def resume_analysis_history(db: Session, user_id: int, limit: int = 30) -> list[dict]:
    items = (
        db.query(UserResumeAnalysis)
        .filter(UserResumeAnalysis.user_id == user_id)
        .order_by(UserResumeAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "match_percent": a.match_percent,
            "strength": a.strength,
            "created_at": a.created_at,
            "preview_jd": (a.job_description_text[:120] + "…")
            if len(a.job_description_text) > 120
            else a.job_description_text,
        }
        for a in items
    ]
