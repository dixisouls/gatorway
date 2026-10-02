import pytest

from gatorway.auth.security import is_sfsu_email


@pytest.mark.parametrize("email,ok", [
    ("jane@sfsu.edu", True), ("Jane.Doe@MAIL.SFSU.EDU", True), ("  a@sfsu.edu ", True),
    ("jane@evilsfsu.edu", False), ("jane@sfsu.edu.evil.com", False), ("jane@gmail.com", False),
    ("@sfsu.edu", False), ("jane@@sfsu.edu", False), ("jane smith@sfsu.edu", False), ("", False),
])
def test_sfsu_email_check(email, ok):
    assert is_sfsu_email(email) is ok
