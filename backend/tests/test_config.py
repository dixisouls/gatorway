from gatorway.config import Settings


def test_defaults_match_docker_compose():
    s = Settings(_env_file=None)
    assert s.database_url.endswith("/gatorway") and s.test_database_url.endswith("/gatorway_test")
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.embed_dim == 768


def test_gemini_tool_allowlist_is_parsed_from_a_comma_list(monkeypatch):
    monkeypatch.setenv("GEMINI_TOOLS", "a, b ,c")
    assert Settings(_env_file=None).gemini_tool_set == {"a", "b", "c"}


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:1/2")
    assert Settings(_env_file=None).redis_url == "redis://example:1/2"
