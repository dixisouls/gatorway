import pytest

from gatorway.api.state import build_state, check_auth
from gatorway.config import Settings


def test_the_firebase_project_id_is_required_to_start():
    with pytest.raises(RuntimeError, match="FIREBASE_PROJECT_ID"):
        check_auth(Settings(_env_file=None, firebase_project_id=""))
    check_auth(Settings(_env_file=None, firebase_project_id="my-project"))


def test_build_state_checks_the_auth_config_before_touching_any_service():
    with pytest.raises(RuntimeError, match="FIREBASE_PROJECT_ID"):
        build_state(Settings(_env_file=None))


def test_the_redactor_is_chosen_by_setting_and_the_real_one_is_the_default():
    from gatorway.api.state import build_redactor
    from gatorway.transcripts.pii import GlinerRedactor
    from gatorway.transcripts.redact import StubRedactor

    assert Settings(_env_file=None).redactor == "gliner"
    assert isinstance(build_redactor(Settings(_env_file=None, redactor="stub")), StubRedactor)
    assert isinstance(build_redactor(Settings(_env_file=None)), GlinerRedactor)  # lazy: the model loads on first use, not here
    with pytest.raises(ValueError):
        build_redactor(Settings(_env_file=None, redactor="nope"))
