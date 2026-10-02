import pytest

from gatorway.api.state import build_state, check_secrets
from gatorway.config import Settings


@pytest.mark.parametrize("secret", ["dev-only-secret-change-me-0123456789abcdef", "change-me-to-a-long-random-string-0123456789", "short", ""])
def test_default_placeholder_or_short_jwt_secrets_are_refused(secret):
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        check_secrets(Settings(_env_file=None, jwt_secret=secret))


def test_a_long_random_secret_is_accepted():
    check_secrets(Settings(_env_file=None, jwt_secret="k" * 48))


def test_build_state_checks_the_secret_before_touching_any_service():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        build_state(Settings(_env_file=None))
