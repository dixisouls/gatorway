"""Prerequisite text -> AND-of-OR groups, concurrent-OK codes and non-course warnings (ARCHITECTURE.md 2.1)."""
import re

_LEAD = re.compile(r"^\s*pre[\s-]*requisites?\s*[:.]\s*", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _find(code: str, clause: str):
    m = re.search(re.escape(code).replace(r"\ ", r"\s+") + r"(\*?)", clause)
    return m


def build_prereq_groups(text, codes):
    """Return (groups, concurrent_ok). groups: list of lists of codes (AND of ORs)."""
    codes = list(dict.fromkeys(codes or []))
    if not codes:
        return [], []
    text = _LEAD.sub("", _norm(text))
    concurrent = set()
    placed = {}  # code -> (clause_index, start, end)
    clauses = [c for c in re.split(r";", text)]
    for ci, clause in enumerate(clauses):
        for code in codes:
            if code in placed:
                continue
            m = _find(code, clause)
            if m:
                placed[code] = (ci, m.start(), m.end())
                if m.group(1) == "*" or re.search(r"concurren", clause[: m.start()], re.I):
                    concurrent.add(code)
    groups = []
    unplaced = [c for c in codes if c not in placed]
    for ci, clause in enumerate(clauses):
        inclause = sorted((placed[c][1], placed[c][2], c) for c in codes if c in placed and placed[c][0] == ci)
        if not inclause:
            continue
        seps = []
        for (s1, e1, _), (s2, e2, _) in zip(inclause, inclause[1:]):
            gap = clause[e1:s2].strip().lower()
            gap = re.sub(r"\*", "", gap)
            if re.fullmatch(r"(,\s*)?(or|/)|or", gap) or gap == "/":
                seps.append("or")
            elif re.fullmatch(r"(,\s*)?and|&", gap):
                seps.append("and")
            else:
                seps.append("comma" if gap in ("", ",") else "other")
        names = [c for _, _, c in inclause]
        if seps and "and" not in seps and "other" not in seps and set(seps) <= {"comma", "or"} and seps[-1] == "or" and "or" in seps and all(s in ("comma",) for s in seps[:-1]):
            groups.append(names)  # "A, B, or C" -> any of
            continue
        cur = [names[0]]
        for s, c in zip(seps, names[1:]):
            if s == "or":
                cur.append(c)
            else:
                groups.append(cur)
                cur = [c]
        groups.append(cur)
    groups += [[c] for c in unplaced]
    return groups, sorted(concurrent)


def non_course_conditions(text, codes):
    """Clauses (split on ';') that mention none of the known course codes, e.g. 'permission of the instructor'."""
    text = _LEAD.sub("", _norm(text))
    out = []
    for clause in text.split(";"):
        clause = clause.strip(" .")
        if len(clause) < 4 or any(_find(c, clause) for c in (codes or [])):
            continue
        out.append(clause)
    return out
