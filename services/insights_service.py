"""Aggregate insights across candidates and screenings."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from database.models import Candidate, JobDescription, ScreeningResult


def cohort_skill_stats(db: Session, job_id: int) -> dict[str, Any]:
    results = (
        db.query(ScreeningResult)
        .filter(ScreeningResult.job_description_id == job_id)
        .order_by(ScreeningResult.match_score.desc())
        .all()
    )
    if not results:
        return {
            "count": 0,
            "avg": 0,
            "trend": "flat",
            "top_missing": [],
            "top_matched": [],
            "shortlist_strengths": [],
            "quality_bands": {"high": 0, "mid": 0, "low": 0},
        }

    missing_counter: Counter[str] = Counter()
    matched_counter: Counter[str] = Counter()

    scores = [float(r.match_score) for r in results]
    top = results[: max(3, len(results) // 3)]

    for r in results:
        for s in r.missing_skills or []:
            missing_counter[s] += 1
        for s in r.matched_skills or []:
            matched_counter[s] += 1

    # Quality bands
    bands = {"high": 0, "mid": 0, "low": 0}
    for s in scores:
        if s >= 72:
            bands["high"] += 1
        elif s >= 48:
            bands["mid"] += 1
        else:
            bands["low"] += 1

    # Trend heuristic: compare top-third avg vs bottom-third avg
    n = len(scores)
    top_slice = scores[: max(2, n // 3)]
    bottom_slice = scores[-max(2, n // 3) :]
    top_avg = sum(top_slice) / len(top_slice)
    bot_avg = sum(bottom_slice) / len(bottom_slice)
    trend = "flat"
    if top_avg - bot_avg >= 12:
        trend = "polarized"
    elif top_avg - bot_avg >= 6:
        trend = "top-heavy"

    # Shortlist strengths: what shortlisted candidates share
    shortlist_hits: Counter[str] = Counter()
    for r in top:
        for s in r.matched_skills or []:
            shortlist_hits[s] += 1

    return {
        "count": len(results),
        "avg": round(sum(scores) / len(scores), 1),
        "trend": trend,
        "top_missing": missing_counter.most_common(8),
        "top_matched": matched_counter.most_common(8),
        "shortlist_strengths": shortlist_hits.most_common(6),
        "quality_bands": bands,
    }


def build_smart_insights(db: Session, job_id: int) -> list[dict[str, Any]]:
    stats = cohort_skill_stats(db, job_id)
    if stats["count"] == 0:
        return [
            {
                "title": "No screenings yet",
                "detail": "Upload resumes and run screening to unlock cohort insights.",
                "tone": "neutral",
            }
        ]

    insights: list[dict[str, Any]] = []

    shortlist = stats.get("shortlist_strengths") or []
    if shortlist:
        skills = " + ".join(s.title() for s, _ in shortlist[:2])
        insights.append(
            {
                "title": f"Shortlist strengths: {skills}",
                "detail": "High match candidates repeatedly surface these capabilities.",
                "tone": "positive",
            }
        )

    miss = stats.get("top_missing") or []
    if miss:
        top_gap = miss[0][0].title()
        gap_share = int(round(100 * (miss[0][1] / max(1, stats["count"]))))
        insights.append(
            {
                "title": f"Most common gap: {top_gap}",
                "detail": f"Missing in ~{gap_share}% of candidates in this slate.",
                "tone": "warning",
            }
        )

    bands = stats.get("quality_bands") or {}
    if bands:
        insights.append(
            {
                "title": "Candidate quality distribution",
                "detail": f"High: {bands.get('high',0)} · Improving: {bands.get('mid',0)} · Weak: {bands.get('low',0)}",
                "tone": "neutral",
            }
        )

    if stats.get("trend") in {"top-heavy", "polarized"}:
        tone = "warning" if stats["trend"] == "polarized" else "neutral"
        insights.append(
            {
                "title": "Quality trend",
                "detail": "This slate is top-heavy (few strong profiles) — use comparison to balance stack depth vs seniority."
                if stats["trend"] == "top-heavy"
                else "This slate is polarized — strong profiles are strong, but the tail is very weak. Consider sourcing for the gaps.",
                "tone": tone,
            }
        )

    if len(insights) < 2:
        insights.append(
            {
                "title": "Skill coverage is polarized",
                "detail": "Use comparison view to balance seniority vs stack depth.",
                "tone": "neutral",
            }
        )

    return insights[:5]


def job_summary(db: Session, job_id: int) -> dict[str, Any]:
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        return {}
    n_candidates = db.query(Candidate).filter(Candidate.job_description_id == job_id).count()
    results = db.query(ScreeningResult).filter(ScreeningResult.job_description_id == job_id).all()
    scores = [r.match_score for r in results]
    return {
        "job_title": job.title,
        "skills_required": len(job.extracted_skills or []),
        "candidate_count": n_candidates,
        "avg_match": round(sum(scores) / len(scores), 1) if scores else 0,
        "top_score": round(max(scores), 1) if scores else 0,
    }
