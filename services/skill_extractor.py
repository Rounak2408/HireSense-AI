"""Extract skills from text using lexicon + regex boundaries."""

from __future__ import annotations

import re

from services.skills_lexicon import SKILL_PHRASES, SKILL_SINGLES
from utils.text_utils import normalize_skill


def extract_skills_from_text(text: str) -> list[str]:
    if not text:
        return []
    lower = text.lower()
    found: list[str] = []

    for phrase in SKILL_PHRASES:
        p = phrase.lower().replace(" ", r"\s+")
        p = p.replace("/", r"/")
        if re.search(rf"(?<![a-z0-9]){p}(?![a-z0-9])", lower):
            found.append(normalize_skill(phrase))

    words = set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#]*", lower))
    for w in words:
        if w in SKILL_SINGLES or normalize_skill(w) in SKILL_SINGLES:
            found.append(normalize_skill(w))

    order: dict[str, None] = {}
    for s in found:
        order.setdefault(s, None)
    return list(order.keys())
