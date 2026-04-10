"""Resume parsing from PDF and DOCX."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import pdfplumber

from services.nlp_service import extract_person_names
from services.skill_extractor import extract_skills_from_text
from utils.text_utils import chunk_sections, extract_emails, extract_phones, normalize_text


@dataclass
class ParsedResume:
    raw_text: str
    name: str | None
    email: str | None
    phone: str | None
    education: str | None
    experience: str | None
    projects: str | None
    project_names: list[str]
    project_highlights: list[str]
    skills: list[str]
    years_experience: float | None


_YEAR_RANGE_RE = re.compile(
    r"((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|present|current|now)",
    re.I,
)
_YEAR_SINGLE_RE = re.compile(r"(?:19|20)\d{2}")


def _estimate_years_experience(text: str) -> float | None:
    if not text:
        return None
    current_year = datetime.utcnow().year
    spans: list[tuple[int, int]] = []
    for m in _YEAR_RANGE_RE.finditer(text):
        start_raw, end_raw = m.group(1), m.group(2)
        try:
            start_year = int(start_raw)
        except Exception:
            continue
        if re.match(r"present|current|now", (end_raw or "").lower()):
            end_year = current_year
        else:
            try:
                end_year = int(end_raw)
            except Exception:
                continue
        if end_year < start_year:
            start_year, end_year = end_year, start_year
        spans.append((start_year, end_year))
    if spans:
        total_years = sum(max(0, hi - lo) for lo, hi in spans)
        return max(0.5, min(30.0, total_years * 0.7))
    # fallback: count year mentions in experience-like chunk
    years = [int(y) for y in _YEAR_SINGLE_RE.findall(text)]
    if len(years) >= 2:
        return max(0.5, min(30.0, (max(years) - min(years)) * 0.6))
    return None


def _read_pdf(data: bytes) -> str:
    parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:20]:
                t = page.extract_text() or ""
                if t:
                    parts.append(t)
    except Exception:
        parts = []
    if parts:
        return "\n".join(parts)
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(data))
        for page in reader.pages[:20]:
            t = page.extract_text() or ""
            if t:
                parts.append(t)
    except Exception:
        return ""
    return "\n".join(parts)


def _read_docx(data: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def _clean_resume_text(raw: str) -> str:
    """Normalize noisy whitespace while preserving line boundaries for section parsing."""
    if not raw:
        return ""
    lines = [normalize_text(line.replace("\xa0", " ")) for line in raw.splitlines()]
    cleaned = [line for line in lines if line]
    return "\n".join(cleaned)


def _extract_project_text(sections: dict[str, str], raw: str) -> str | None:
    project_keys = [k for k in sections if re.search(r"project|case study|portfolio", k, re.I)]
    if project_keys:
        text = "\n".join(sections[k] for k in project_keys if sections.get(k)).strip()
        return text or None

    # Fallback: look for project-like phrases in raw resume text.
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    hits = [
        ln
        for ln in lines
        if re.search(
            r"\b(project|built|developed|designed|implemented|deployed|capstone|portfolio)\b",
            ln,
            re.I,
        )
    ]
    if not hits:
        return None
    return "\n".join(hits[:12]).strip() or None


def _project_highlights(project_text: str | None) -> list[str]:
    if not project_text:
        return []
    lines = [ln.strip(" -•\t") for ln in project_text.splitlines() if ln.strip()]
    # Prefer concise, meaningful project bullets.
    ranked = sorted(
        lines,
        key=lambda ln: (
            bool(re.search(r"\d|%|x|latency|accuracy|reduced|improved|saved|optimized", ln, re.I)),
            len(ln),
        ),
        reverse=True,
    )
    out: list[str] = []
    for ln in ranked:
        if len(ln) < 18:
            continue
        if ln not in out:
            out.append(ln[:220])
        if len(out) >= 4:
            break
    return out


def _extract_project_names(project_text: str | None, highlights: list[str]) -> list[str]:
    if not project_text:
        return []

    names: list[str] = []
    lines = [ln.strip(" -•\t") for ln in project_text.splitlines() if ln.strip()]
    title_like = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 +/&().,\-]{2,90}$")

    for ln in lines:
        # Pattern: "Project Name: details..."
        if ":" in ln:
            left = ln.split(":", 1)[0].strip()
            if 2 <= len(left.split()) <= 8 and title_like.match(left):
                names.append(left)
                continue

        # Pattern: "XYZ built/developed/implemented..."
        m = re.match(
            r"^([A-Za-z0-9][A-Za-z0-9 +/&().,\-]{2,80}?)\s+(built|developed|designed|implemented|created|deployed)\b",
            ln,
            re.I,
        )
        if m:
            candidate = m.group(1).strip(" -|,")
            if 1 <= len(candidate.split()) <= 9:
                names.append(candidate)

    if not names:
        # Fallback from highlights.
        for ln in highlights:
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9 +/&().,\-]{3,80}?)\s+(built|developed|designed|implemented)\b", ln, re.I)
            if m:
                names.append(m.group(1).strip(" -|,"))

    deduped: list[str] = []
    seen: set[str] = set()
    for n in names:
        key = normalize_text(n).lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(n[:90])
        if len(deduped) >= 6:
            break
    return deduped


def _guess_name(text: str, email: str | None) -> str | None:
    lines = [normalize_text(x) for x in text.splitlines() if normalize_text(x)]
    if not lines:
        return None
    if email:
        local = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        if 3 <= len(local) <= 40:
            return local
    names = extract_person_names("\n".join(lines[:12]))
    if names:
        return names[0]
    head = lines[0]
    if 2 <= len(head.split()) <= 4 and head.isalpha() is False:
        if re.match(r"^[A-Z][a-z]+(\s[A-Z][a-z]+){0,3}$", head):
            return head
    if 2 <= len(head.split()) <= 5:
        return head
    return None


def parse_resume_bytes(data: bytes, filename: str) -> ParsedResume:
    name_lower = (filename or "").lower()
    if name_lower.endswith(".pdf"):
        raw = _read_pdf(data)
    elif name_lower.endswith(".docx"):
        raw = _read_docx(data)
    elif name_lower.endswith(".doc"):
        raise ValueError("Legacy .doc is not supported. Please save as .docx or PDF.")
    else:
        raise ValueError("Unsupported file type. Use PDF or DOCX.")

    raw = _clean_resume_text(raw)
    emails = extract_emails(raw)
    phones = extract_phones(raw)
    sections = chunk_sections(raw)
    edu = sections.get("education") or sections.get("academic") or None
    exp_keys = [k for k in sections if re.search(r"experience|employment|work", k, re.I)]
    experience = "\n".join(sections[k] for k in exp_keys if sections.get(k)) or None
    projects = _extract_project_text(sections, raw)
    project_highlights = _project_highlights(projects)
    project_names = _extract_project_names(projects, project_highlights)
    skill_blob = sections.get("skills") or ""
    skills = extract_skills_from_text(raw + "\n" + skill_blob)
    name = _guess_name(raw, emails[0] if emails else None)
    years = _estimate_years_experience(experience or raw)

    return ParsedResume(
        raw_text=raw,
        name=name,
        email=emails[0] if emails else None,
        phone=phones[0] if phones else None,
        education=edu,
        experience=experience or None,
        projects=projects,
        project_names=project_names,
        project_highlights=project_highlights,
        skills=skills,
        years_experience=years,
    )


def parse_resume_path(path: str | Path) -> ParsedResume:
    p = Path(path)
    return parse_resume_bytes(p.read_bytes(), p.name)
