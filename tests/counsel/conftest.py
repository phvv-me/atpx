import pytest


@pytest.fixture(autouse=True)
def isolated_key_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip the session's exported OpenRouter key so tests control both key paths.

    An activated env exports `OPENROUTER_API_KEY`, and `api_key` prefers the
    environment, so without this every consult test would silently use the
    real key instead of the fixture's.
    """
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
