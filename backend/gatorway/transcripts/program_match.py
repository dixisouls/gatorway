"""Match the degree printed on a transcript ("B.S. Computer Science") to our programs ("Bachelor of Science in Computer Science").
Deterministic and local: abbreviations are expanded, then word overlap and string similarity decide; the student confirms the result."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_STOP = {"in", "of", "the", "and", "a", "an", "degree", "program", "major", "with", "for", "department"}
_ABBREVIATIONS = [
    (r"\bb\.?\s?s\.?\b", "bachelor of science"), (r"\bb\.?\s?a\.?\b", "bachelor of arts"), (r"\bb\.?\s?f\.?\s?a\.?\b", "bachelor of fine arts"),
    (r"\bm\.?\s?s\.?\b", "master of science"), (r"\bm\.?\s?a\.?\b", "master of arts"), (r"\bm\.?\s?f\.?\s?a\.?\b", "master of fine arts"),
    (r"\bm\.?\s?b\.?\s?a\.?\b", "master of business administration"),
]
_LEVELS = {"bachelor": "undergraduate", "master": "graduate", "minor": "minor", "certificate": "certificate", "credential": "credential"}
_DEGREE_WORDS = {"bachelor", "master", "science", "arts", "fine", "business", "administration", "minor", "certificate", "credential"}
MIN_SCORE = 0.5
LIMIT = 3


def _tokens(text: str) -> list[str]:
    t = (text or "").lower().replace("&", " and ")
    for pattern, full in _ABBREVIATIONS:
        t = re.sub(pattern, f" {full} ", t)
    return [w for w in re.findall(r"[a-z]+", t) if w not in _STOP]


def _level_hint(tokens: list[str]) -> str | None:
    return next((_LEVELS[w] for w in tokens if w in _LEVELS), None)


def rank_programs(raw: str | None, programs: list[dict], limit: int = LIMIT, min_score: float = MIN_SCORE) -> list[dict]:
    """The programs that best fit the printed degree, best first, each with a 0-1 `score`. Empty when nothing is plausible."""
    wanted = _tokens(raw or "")
    if not [w for w in wanted if w not in _DEGREE_WORDS]:  # only degree words ("B.S.") and no field of study: nothing to match
        return []
    want_set, hint = set(wanted), _level_hint(wanted)
    scored = []
    for p in programs:
        have = _tokens(p["title"])
        have_set = set(have)
        union = want_set | have_set
        jaccard = len(want_set & have_set) / len(union) if union else 0.0
        similarity = SequenceMatcher(None, " ".join(sorted(want_set)), " ".join(sorted(have_set))).ratio()
        score = 0.65 * jaccard + 0.35 * similarity
        if hint:
            score += 0.1 if p.get("level") == hint else -0.3
        elif p.get("level") == "undergraduate":
            score += 0.04  # no degree word printed: a bare major most likely means the bachelor's
        if score >= min_score:
            scored.append({**p, "score": round(min(score, 1.0), 3)})
    return sorted(scored, key=lambda p: -p["score"])[:limit]
