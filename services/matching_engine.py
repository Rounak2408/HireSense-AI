"""Weighted scoring, similarity, and ranking for candidates vs JD."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from utils.text_utils import normalize_skill, normalize_text, tokenize_words

# Weights sum to 1.0
WEIGHT_SKILLS = 0.45
WEIGHT_EXPERIENCE = 0.25
WEIGHT_EDUCATION = 0.12
WEIGHT_PROJECTS = 0.18


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _text_overlap_score(resume: str, jd: str) -> float:
    r = set(tokenize_words(resume))
    j = set(tokenize_words(jd))
    return _jaccard(r, j)


def _education_score(education: str | None, jd_text: str) -> float:
    if not education:
        return 35.0
    ed = education.lower()
    jd = jd_text.lower()
    score = 45.0
    degree_signals = ["bachelor", "master", "mba", "phd", "b.s", "m.s", "b.tech", "m.tech"]
    for d in degree_signals:
        if d in ed:
            score += 10
    stem = ["computer", "engineering", "statistics", "mathematics", "science", "information"]
    if any(s in ed for s in stem):
        score += 10
    if any(k in jd for k in ["phd", "master", "mba", "degree"]):
        score += min(20, _text_overlap_score(ed, jd) * 40)
    return max(0.0, min(100.0, score))


def _experience_score_candidate(
    experience: str | None,
    years: float | None,
    jd_text: str,
    required_skill_count: int,
) -> float:
    base = 40.0
    if years is not None:
        # Soft target: roles asking for many hard skills expect seniority
        target = 2.0 + min(4.0, required_skill_count * 0.35)
        diff = years - target
        base += max(-25.0, min(35.0, diff * 8.0))
    overlap = _text_overlap_score(experience or "", jd_text)
    base += overlap * 35.0
    if re.search(r"\b(senior|lead|principal|manager|director)\b", jd_text, re.I):
        base += 8.0 if (years or 0) >= 4 else -5.0
    return max(0.0, min(100.0, base))


def _project_score(project_text: str | None, jd_skills: list[str], jd_text: str) -> tuple[float, dict[str, Any]]:
    if not project_text:
        return 28.0, {
            "project_count_estimate": 0,
            "skill_overlap_ratio": 0.0,
            "impact_signal_count": 0,
            "complexity_signal_count": 0,
            "note": "No clear project section detected.",
        }

    ptext = project_text.lower()
    normalized_project_tokens = {normalize_skill(tok) for tok in tokenize_words(project_text)}
    jd_set = {normalize_skill(s) for s in jd_skills if s}

    direct_hits = [s for s in jd_set if s in ptext or s in normalized_project_tokens]
    overlap_ratio = (len(direct_hits) / len(jd_set)) if jd_set else 0.5

    impact_signals = re.findall(
        r"\b(\d+%|\d+x|reduced|improved|increased|optimized|decreased|saved|latency|throughput|accuracy)\b",
        ptext,
        re.I,
    )
    complexity_signals = re.findall(
        r"\b(api|microservice|architecture|pipeline|ci/cd|docker|kubernetes|aws|gcp|azure|scalable|distributed|realtime)\b",
        ptext,
        re.I,
    )
    project_count_est = len(re.findall(r"\b(project|capstone|application|platform|system)\b", ptext, re.I))

    score = 32.0
    score += overlap_ratio * 42.0
    score += min(14.0, len(impact_signals) * 2.4)
    score += min(12.0, len(set(complexity_signals)) * 2.2)
    if re.search(r"\b(project|portfolio)\b", jd_text, re.I):
        score += min(6.0, overlap_ratio * 10.0)

    return max(0.0, min(100.0, score)), {
        "project_count_estimate": project_count_est,
        "project_skill_hits": sorted(set(direct_hits)),
        "skill_overlap_ratio": round(overlap_ratio, 3),
        "impact_signal_count": len(impact_signals),
        "complexity_signal_count": len(set(complexity_signals)),
    }


def score_candidate(
    candidate_skills: list[str],
    jd_skills: list[str],
    resume_text: str,
    education: str | None,
    experience: str | None,
    years_experience: float | None,
    project_text: str | None = None,
) -> dict[str, Any]:
    jd_set = {normalize_skill(s) for s in jd_skills}
    cand_set = {normalize_skill(s) for s in candidate_skills}
    matched = sorted(jd_set & cand_set)
    missing = sorted(jd_set - cand_set)

    if jd_set:
        skill_ratio = len(matched) / len(jd_set)
    else:
        skill_ratio = _jaccard(cand_set, cand_set)  # 1.0 if no JD skills

    skill_score = 100.0 * skill_ratio
    exp_score = _experience_score_candidate(
        experience, years_experience, resume_text, len(jd_set) or len(cand_set) or 1
    )
    edu_score = _education_score(education, resume_text)
    proj_score, project_meta = _project_score(project_text, jd_skills, resume_text)

    match = (
        WEIGHT_SKILLS * skill_score
        + WEIGHT_EXPERIENCE * exp_score
        + WEIGHT_EDUCATION * edu_score
        + WEIGHT_PROJECTS * proj_score
    )

    # Boost for breadth when JD is skill-heavy
    if len(jd_set) >= 6 and skill_ratio >= 0.65:
        match = min(100.0, match + 3.0)

    strength = "Low"
    if match >= 72:
        strength = "High"
    elif match >= 48:
        strength = "Medium"

    return {
        "match_score": round(match, 2),
        "skill_score": round(skill_score, 2),
        "experience_score": round(exp_score, 2),
        "education_score": round(edu_score, 2),
        "project_score": round(proj_score, 2),
        "matched_skills": matched,
        "missing_skills": missing,
        "strength": strength,
        "breakdown": {
            "weights": {
                "skills": WEIGHT_SKILLS,
                "experience": WEIGHT_EXPERIENCE,
                "education": WEIGHT_EDUCATION,
                "projects": WEIGHT_PROJECTS,
            },
            "jd_skill_count": len(jd_set),
            "candidate_skill_count": len(cand_set),
            "project_analysis": project_meta,
        },
    }


def suggest_improvements(
    missing: list[str],
    jd_text: str,
    project_score: float | None = None,
    project_meta: dict[str, Any] | None = None,
) -> list[str]:
    tips: list[str] = []
    if missing[:5]:
        tips.append(
            "Prioritize evidence for: " + ", ".join(missing[:5])
            + ("…" if len(missing) > 5 else "")
        )
    if any(m in {"docker", "kubernetes"} for m in missing):
        tips.append("Add measurable cloud/DevOps impact (deployments, SLAs, latency).")
    if any(m in {"python", "sql"} for m in missing):
        tips.append("Surface quantified outcomes tied to core stack (Python/SQL).")
    if project_score is not None and project_score < 55:
        tips.append("Expand project section with role, stack, and measurable outcomes for each project.")
    if project_meta and int(project_meta.get("impact_signal_count", 0)) == 0:
        tips.append("Add impact metrics in projects (latency %, accuracy %, revenue/time saved).")
    if project_meta and int(project_meta.get("complexity_signal_count", 0)) <= 1:
        tips.append("Highlight architecture depth: APIs, deployment, scale, and production constraints.")
    if not tips and missing:
        tips.append("Mirror JD keywords in your impact bullets without stuffing.")
    if not tips:
        tips.append("Tighten executive summary to reflect top 3 JD outcomes.")
    return tips[:6]


def assign_ranks(results: list[dict[str, Any]], key: str = "match_score") -> list[dict[str, Any]]:
    sorted_r = sorted(results, key=lambda x: x.get(key, 0), reverse=True)
    for i, row in enumerate(sorted_r, start=1):
        row["rank"] = i
        row["shortlist"] = i <= max(3, min(8, len(sorted_r) // 3 or 1))
    return sorted_r
