"""General-education helpers (pure). Courses carry their GE area in `attributes`, under the current label ("4: Social/Behavioral
Sciences") and the older letter scheme ("D1: Social Sciences"). Area 2 (math) has no labelled courses in the catalog."""
from __future__ import annotations

import re

GE_ATTRIBUTES = {
    "1A": ("1A:", "A2:"), "1B": ("1B:", "A3:"), "1C": ("1C:", "A1:"),
    "3A": ("3A:", "C1:"), "3B": ("3B:", "C2:", "C3 or C2:"),
    "4": ("4:", "D1:", "D2:", "D3:"),
    "5A": ("5A:", "B1:"), "5B": ("5B:", "B2:"), "5C": ("5C:", "B3:"),
    "6": ("6:", "GE-F:"),
}
GE_GROUPS = {"1": ("1A", "1B", "1C"), "3": ("3A", "3B"), "5": ("5A", "5B", "5C")}
UPPER_DIVISION = 300


def ge_tokens(label: str) -> list[str]:
    """The GE areas a roadmap row names: 'GE Area 5UD or 2UD: ...' -> ['5UD', '2UD']. Empty if it is not a GE row."""
    if not re.match(r"\s*GE\b", label or "", re.I):
        return []
    head = label.split(":")[0]
    return [m.upper() for m in re.findall(r"\b([1-6][A-C]?(?:UD)?)\b", head, re.I)]


def ge_prefixes(areas: list[str]) -> tuple[set[str], bool]:
    """(attribute prefixes that satisfy these areas, whether the row wants upper-division courses)."""
    prefixes: set[str] = set()
    upper = False
    for raw in areas:
        token = raw.strip().upper()
        if token.endswith("UD"):
            upper, token = True, token[:-2]
        for base in GE_GROUPS.get(token, (token,)):
            prefixes.update(GE_ATTRIBUTES.get(base, ()))
    return prefixes, upper


def has_ge_courses(areas: list[str]) -> bool:
    return bool(ge_prefixes(areas)[0])


def counts_for_ge(attributes: list[str], number_int: int | None, areas: list[str]) -> bool:
    """Does a course with these attributes count for a row naming these areas? A "UD" row takes upper-division courses, the others lower."""
    prefixes, upper = ge_prefixes(areas)
    if not prefixes or not any(a.startswith(p) for a in attributes or [] for p in prefixes):
        return False
    return (number_int is not None and number_int >= UPPER_DIVISION) == upper
