"""Persist screening runs: score candidates and store ScreeningResult rows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from database.models import Candidate, CandidateSkill, JobDescription, ScreeningResult
from services.matching_engine import assign_ranks, score_candidate


def run_screening_for_job(db: Session, job_id: int) -> list[ScreeningResult]:
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise ValueError("Job not found")

    jd_skills = list(job.extracted_skills or [])
    candidates = db.query(Candidate).filter(Candidate.job_description_id == job_id).all()

    scored_payload: list[dict] = []
    for c in candidates:
        cand_skills = [s.skill_name for s in c.skills]
        if not cand_skills:
            cand_skills = []
        payload = score_candidate(
            cand_skills,
            jd_skills,
            c.raw_text or "",
            c.education,
            c.experience,
            c.years_experience,
        )
        payload["candidate_id"] = c.id
        scored_payload.append(payload)

    ranked = assign_ranks(scored_payload, key="match_score")

    # Remove previous results for this job
    db.query(ScreeningResult).filter(ScreeningResult.job_description_id == job_id).delete()

    results: list[ScreeningResult] = []
    for row in ranked:
        sr = ScreeningResult(
            candidate_id=row["candidate_id"],
            job_description_id=job_id,
            match_score=row["match_score"],
            skill_score=row["skill_score"],
            experience_score=row["experience_score"],
            education_score=row["education_score"],
            rank=row.get("rank"),
            matched_skills=row.get("matched_skills"),
            missing_skills=row.get("missing_skills"),
            shortlist=bool(row.get("shortlist")),
            breakdown=row.get("breakdown"),
        )
        db.add(sr)
        results.append(sr)
    db.commit()
    for r in results:
        db.refresh(r)
    return results


def ensure_candidate_skills(db: Session, candidate: Candidate, skills: list[str]) -> None:
    existing = {s.skill_name for s in candidate.skills}
    for sk in skills:
        if sk not in existing:
            db.add(CandidateSkill(candidate_id=candidate.id, skill_name=sk, source="resume"))
            existing.add(sk)
    db.commit()
