"""Job description processing: skill extraction and structuring."""

from __future__ import annotations

from dataclasses import dataclass

from services.skill_extractor import extract_skills_from_text


@dataclass
class ProcessedJD:
    raw_text: str
    required_skills: list[str]
    title_guess: str | None


def process_job_description(text: str, title: str | None = None) -> ProcessedJD:
    t = (text or "").strip()
    skills = extract_skills_from_text(t)
    tg = title.strip() if title else None
    return ProcessedJD(raw_text=t, required_skills=skills, title_guess=tg)
