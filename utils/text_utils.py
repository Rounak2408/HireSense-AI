"""Text normalization and lightweight extraction helpers."""

from __future__ import annotations

import re
from typing import Iterable

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)
_PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{8,14}\d")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}", text.lower())


def extract_emails(text: str) -> list[str]:
    return list(dict.fromkeys(_EMAIL_RE.findall(text or "")))


def extract_phones(text: str) -> list[str]:
    raw = _PHONE_RE.findall(text or "")
    phones = [str(m).strip() for m in raw]
    return [p for p in phones if 10 <= len(re.sub(r"\D", "", p)) <= 15][:3]


def normalize_skill(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[\s_]+", " ", s)
    synonyms = {
        "postgresql": "postgres",
        "k8s": "kubernetes",
        "tf": "tensorflow",
        "js": "javascript",
        "ts": "typescript",
        "ml": "machine learning",
    }
    return synonyms.get(s, s)


SECTION_PATTERNS = [
    re.compile(r"(?im)^\s*(education|academic)\b[^\n]*\n"),
    re.compile(r"(?im)^\s*(experience|work history|employment|professional experience)\b[^\n]*\n"),
    re.compile(r"(?im)^\s*(skills|technical skills|core competencies)\b[^\n]*\n"),
    re.compile(r"(?im)^\s*(projects|certifications)\b[^\n]*\n"),
]


def chunk_sections(text: str) -> dict[str, str]:
    """Split resume-like text into coarse sections by common headers."""
    if not text:
        return {}
    lines = text.splitlines()
    sections: dict[str, str] = {}
    current = "header"
    buf: list[str] = []
    for line in lines:
        header_hit = None
        for pat in SECTION_PATTERNS:
            if pat.search(line):
                header_hit = pat.pattern
                break
        if header_hit:
            if buf:
                sections[current] = "\n".join(buf).strip()
            current = line.strip()[:80]
            buf = []
        else:
            buf.append(line)
    if buf:
        sections[current] = "\n".join(buf).strip()
    return sections
