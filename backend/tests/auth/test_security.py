import pytest

from gatorway.auth.security import (create_access_token, decode_access_token, hash_password, is_sfsu_email, verify_password)


@pytest.mark.parametrize("email,ok", [
    ("jane@sfsu.edu", True), ("Jane.Doe@MAIL.SFSU.EDU", True), ("  a@sfsu.edu ", True),
    ("jane@evilsfsu.edu", False), ("jane@sfsu.edu.evil.com", False), ("jane@gmail.com", False),
    ("@sfsu.edu", False), ("jane@@sfsu.edu", False), ("jane smith@sfsu.edu", False), ("", False),
])
def test_sfsu_email_check(email, ok):
    assert is_sfsu_email(email) is ok


def test_password_and_token_roundtrip():
    h = hash_password("s3cret-pass")
    assert verify_password(h, "s3cret-pass") and not verify_password(h, "nope") and not verify_password("garbage", "x")
    tok = create_access_token(42, "k"*32, 5)
    assert decode_access_token(tok, "k"*32) == 42 and decode_access_token(tok, "o"*32) is None and decode_access_token("x.y.z", "k"*32) is None


def test_expired_token_rejected():
    from datetime import datetime, timedelta, timezone
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    assert decode_access_token(create_access_token(1, "k"*32, 1, now=old), "k"*32) is None
