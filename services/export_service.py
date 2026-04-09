"""CSV / report export helpers."""

from __future__ import annotations

import csv
import io
from typing import Any


def ranked_candidates_csv(rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    fieldnames = [
        "rank",
        "name",
        "email",
        "match_score",
        "skill_score",
        "experience_score",
        "education_score",
        "shortlist",
        "matched_skills",
        "missing_skills",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        flat = dict(r)
        flat["matched_skills"] = ";".join(flat.get("matched_skills") or [])
        flat["missing_skills"] = ";".join(flat.get("missing_skills") or [])
        writer.writerow(flat)
    return output.getvalue().encode("utf-8")


def screening_report_text(job_title: str, rows: list[dict[str, Any]], insights: list[dict]) -> str:
    lines = [
        "HireSense AI — Screening Report",
        f"Role: {job_title}",
        "",
        "Ranked candidates:",
    ]
    for r in rows[:25]:
        lines.append(
            f"  #{r.get('rank') or ''} {r.get('name')} — match {r.get('match_score')}% "
            f"(shortlist: {r.get('shortlist')})"
        )
    lines.append("")
    lines.append("Insights:")
    for ins in insights:
        lines.append(f"  • {ins.get('title')}: {ins.get('detail')}")
    return "\n".join(lines)
