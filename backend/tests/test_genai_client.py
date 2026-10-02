import pytest

from gatorway.config import Settings
from gatorway.llm.client import gemini_configured, make_genai_client


def test_vertex_mode_uses_adc_with_project_and_location():
    s = Settings(_env_file=None, google_genai_use_vertexai=True, google_cloud_project="p1", google_cloud_location="us-central1")
    assert gemini_configured(s)
    c = make_genai_client(s)
    assert c.vertexai is True


def test_api_key_mode_is_used_when_vertex_is_off():
    s = Settings(_env_file=None, gemini_api_key="k")
    assert gemini_configured(s)
    assert make_genai_client(s).vertexai is False


def test_nothing_configured_is_reported_not_guessed():
    s = Settings(_env_file=None)
    assert not gemini_configured(s)
    with pytest.raises(RuntimeError, match="GOOGLE_GENAI_USE_VERTEXAI"):
        make_genai_client(s)


def test_vertex_without_a_project_is_rejected():
    s = Settings(_env_file=None, google_genai_use_vertexai=True)
    assert not gemini_configured(s)
