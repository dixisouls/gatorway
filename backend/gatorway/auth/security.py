"""The SFSU email rule."""
from __future__ import annotations

import re

# sfsu.edu itself or any subdomain (students use mail.sfsu.edu); never evilsfsu.edu or sfsu.edu.evil.com
_SFSU_EMAIL = re.compile(r"^[^@\s]+@([a-z0-9-]+\.)*sfsu\.edu$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_sfsu_email(email: str) -> bool:
    return bool(_SFSU_EMAIL.fullmatch(normalize_email(email)))
