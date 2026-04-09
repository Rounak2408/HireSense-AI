"""
Seed PostgreSQL with demo recruiter account, job description, and synthetic candidates.
Run: python scripts/seed_sample_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.models import Candidate, CandidateSkill, JobDescription, User
from database.session import SessionLocal, init_db
from services import auth_service
from services.screening_service import run_screening_for_job


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        if auth_service.get_user_by_username(db, "demo_recruiter"):
            print("Already seeded (demo_recruiter exists).")
            return

        recruiter = auth_service.create_user(
            db,
            email="demo@hiresense.ai",
            username="demo_recruiter",
            password="ChangeMe!123",
            role="recruiter",
            full_name="Alex Rivera",
        )

        jd_text = """
        Senior Backend Engineer — HireSense Labs

        We need a senior backend engineer with Python, FastAPI, PostgreSQL, Docker,
        and AWS. Experience with Kubernetes, CI/CD, and machine learning pipelines
        is a plus. 4+ years building distributed systems. Strong SQL and system design.
        """

        job = JobDescription(
            user_id=recruiter.id,
            title="Senior Backend Engineer",
            raw_text=jd_text,
            extracted_skills=[
                "python",
                "fastapi",
                "postgres",
                "docker",
                "aws",
                "kubernetes",
                "sql",
                "machine learning",
            ],
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        profiles = [
            dict(
                name="Jamie Chen",
                email="jamie.chen@example.com",
                skills=["python", "django", "postgres", "docker", "aws", "sql"],
                education="M.S. Computer Science, State University",
                experience="Backend engineer 5 years building APIs and data services.",
                years=5.0,
            ),
            dict(
                name="Sam Patel",
                email="sam.patel@example.com",
                skills=["python", "flask", "mysql", "kubernetes", "aws"],
                education="B.S. Information Systems",
                experience="Cloud-focused engineer with 3 years shipping microservices.",
                years=3.0,
            ),
            dict(
                name="Riley Nguyen",
                email="riley.nguyen@example.com",
                skills=["java", "spring", "postgres", "docker", "sql"],
                education="B.Tech Computer Engineering",
                experience="4 years enterprise integrations and REST APIs.",
                years=4.0,
            ),
        ]

        for p in profiles:
            cand = Candidate(
                job_description_id=job.id,
                created_by_user_id=recruiter.id,
                name=p["name"],
                email=p["email"],
                phone=None,
                education=p["education"],
                experience=p["experience"],
                raw_text=f"{p['experience']}\nSkills: {', '.join(p['skills'])}",
                years_experience=p["years"],
            )
            db.add(cand)
            db.commit()
            db.refresh(cand)
            for sk in p["skills"]:
                db.add(CandidateSkill(candidate_id=cand.id, skill_name=sk, source="seed"))

        db.commit()
        run_screening_for_job(db, job.id)
        print("Seed complete. Login as demo_recruiter / ChangeMe!123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
