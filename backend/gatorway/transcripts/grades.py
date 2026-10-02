"""Which transcript grades count as 'passed' (credit earned)."""
PASSING = {"A", "A-", "A+", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "CR", "P", "RD"}


def is_passing(grade: str | None) -> bool:
    """False for F, W, WU, NC, I, IP, AU, blanks. 'In progress' is not passed."""
    return (grade or "").strip().upper().replace(" ", "") in PASSING
