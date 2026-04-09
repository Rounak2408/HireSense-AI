"""Lazy-loaded spaCy pipeline for entity-assisted parsing."""

from __future__ import annotations

from typing import Any

_nlp: Any = None


def get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            _nlp = spacy.blank("en")
    return _nlp


def extract_person_names(text: str, max_names: int = 3) -> list[str]:
    if not text:
        return []
    nlp = get_nlp()
    doc = nlp(text[:6000])
    names: list[str] = []
    for ent in doc.ents:
        if ent.label_ == "PERSON" and ent.text.strip():
            cleaned = ent.text.strip()
            if cleaned not in names:
                names.append(cleaned)
        if len(names) >= max_names:
            break
    return names


def extract_orgs(text: str, limit: int = 5) -> list[str]:
    if not text:
        return []
    nlp = get_nlp()
    doc = nlp(text[:8000])
    out: list[str] = []
    for ent in doc.ents:
        if ent.label_ in ("ORG", "GPE") and ent.text.strip():
            t = ent.text.strip()
            if t not in out:
                out.append(t)
        if len(out) >= limit:
            break
    return out
