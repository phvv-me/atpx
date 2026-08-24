import json
from pathlib import Path

import httpx
import pytest
import respx
from httpx import Response
from pydantic import JsonValue

from atpx import Lanes, ModelLane, consult
from atpx.counsel.consulting import api_key

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
_V4FLASH = "deepseek/deepseek-v4-flash-0731"
_LUNA = "openai/gpt-5.6-luna"
_MAX_TOKENS = 8000
_TEMPERATURE = "temperature"
_REASONING = "reasoning"

_SCHEMA: dict[str, JsonValue] = {"type": "object", "properties": {"probe": {"type": "string"}}}
_MESSAGES: list[dict[str, JsonValue]] = [{"role": "user", "content": "prove it"}]


def reply_body(content: str = '{"probe": "import sys"}') -> dict[str, JsonValue]:
    """A well-formed OpenRouter completion body."""
    return {
        "model": _V4FLASH,
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "completion_tokens_details": {"reasoning_tokens": 2},
        },
    }


@pytest.fixture
def keyed_root(tmp_path: Path) -> Path:
    """A root whose .env carries an OpenRouter key."""
    (tmp_path / ".env").write_text("OTHER=1\nOPENROUTER_API_KEY=sk-test-123\n")
    return tmp_path


def sent(route: respx.Route, call: int):
    """The JSON body of one recorded request, untyped so asserts can index freely."""
    return json.loads(route.calls[call].request.content)


def test_api_key_reads_the_env_line(keyed_root: Path) -> None:
    assert api_key(keyed_root) == "sk-test-123"


def test_api_key_prefers_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-exported")
    assert api_key(tmp_path) == "sk-exported"


def test_api_key_fails_loudly_without_the_line(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="no .env"):
        api_key(tmp_path)
    (tmp_path / ".env").write_text("OTHER=1\n")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        api_key(tmp_path)


@respx.mock
def test_consult_measures_usage_from_the_reply(keyed_root: Path) -> None:
    respx.post(_ENDPOINT).mock(return_value=Response(200, json=reply_body()))
    consultation = consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root)
    assert consultation.ok and consultation.content == '{"probe": "import sys"}'
    assert consultation.prompt_tokens == 11 and consultation.completion_tokens == 7
    assert consultation.reasoning_tokens == 2 and consultation.elapsed > 0


@respx.mock
def test_consult_sends_the_measured_request_body(keyed_root: Path) -> None:
    route = respx.post(_ENDPOINT).mock(return_value=Response(200, json=reply_body()))
    consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root)
    body = sent(route, 0)
    assert body["max_tokens"] == _MAX_TOKENS
    assert body["provider"] == {"sort": "throughput", "allow_fallbacks": True}
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body[_REASONING] == {"enabled": False}
    assert body[_TEMPERATURE] == 1.0 and body["top_p"] == 0.95
    assert route.calls[0].request.headers["authorization"] == "Bearer sk-test-123"


@respx.mock
def test_consult_falls_back_to_minimal_effort_on_400(keyed_root: Path) -> None:
    route = respx.post(_ENDPOINT).mock(
        side_effect=[Response(400), Response(200, json=reply_body())]
    )
    consultation = consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root)
    assert consultation.ok
    retry = sent(route, 1)
    assert retry[_REASONING] == {"effort": "minimal"}
    assert _TEMPERATURE not in retry and "top_p" not in retry


@respx.mock
def test_consult_drops_reasoning_entirely_on_a_second_400(keyed_root: Path) -> None:
    route = respx.post(_ENDPOINT).mock(
        side_effect=[Response(400), Response(400), Response(200, json=reply_body())]
    )
    assert consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root).ok
    bare = sent(route, 2)
    assert _REASONING not in bare and _TEMPERATURE not in bare


@respx.mock
def test_consult_reports_a_terminal_400_instead_of_raising(keyed_root: Path) -> None:
    respx.post(_ENDPOINT).mock(return_value=Response(400, text="bad request"))
    consultation = consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root)
    assert not consultation.ok and "HTTP 400" in consultation.error


@respx.mock
def test_consult_reports_an_unretriable_status_instead_of_raising(keyed_root: Path) -> None:
    respx.post(_ENDPOINT).mock(return_value=Response(403, text="forbidden"))
    consultation = consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root)
    assert not consultation.ok and "HTTP 403" in consultation.error


@respx.mock
def test_consult_retries_transients_then_fails_explicitly(
    keyed_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    naps: list[float] = []
    monkeypatch.setattr("time.sleep", naps.append)
    route = respx.post(_ENDPOINT).mock(return_value=Response(503))
    consultation = consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root)
    assert not consultation.ok and "HTTP 503" in consultation.error
    assert len(route.calls) == 4 and naps == [2.0, 4.0, 6.0]


@respx.mock
def test_consult_recovers_after_a_429(keyed_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    respx.post(_ENDPOINT).mock(side_effect=[Response(429), Response(200, json=reply_body())])
    assert consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root).ok


@respx.mock
def test_consult_flags_an_error_inside_a_200_body(keyed_root: Path) -> None:
    respx.post(_ENDPOINT).mock(return_value=Response(200, json={"error": {"message": "nope"}}))
    consultation = consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root)
    assert not consultation.ok and "error body" in consultation.error


@respx.mock
def test_consult_reports_transport_exhaustion(
    keyed_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    respx.post(_ENDPOINT).mock(side_effect=httpx.ConnectError("down"))
    consultation = consult(_MESSAGES, _SCHEMA, Lanes().prover, keyed_root)
    assert not consultation.ok and "transport failure" in consultation.error


@respx.mock
def test_a_reasoning_lane_never_mentions_the_reasoning_field(keyed_root: Path) -> None:
    route = respx.post(_ENDPOINT).mock(return_value=Response(200, json=reply_body()))
    consult(_MESSAGES, _SCHEMA, ModelLane(model=_LUNA, reasoning=True), keyed_root)
    body = sent(route, 0)
    assert _REASONING not in body and _TEMPERATURE not in body
    assert body["max_tokens"] == 24000


@respx.mock
def test_a_reasoning_lane_drops_sampling_on_a_400(keyed_root: Path) -> None:
    route = respx.post(_ENDPOINT).mock(
        side_effect=[Response(400), Response(200, json=reply_body())]
    )
    lane = ModelLane(model=_LUNA, temperature=0.7, reasoning=True)
    assert consult(_MESSAGES, _SCHEMA, lane, keyed_root).ok
    assert sent(route, 0)[_TEMPERATURE] == 0.7
    retry = sent(route, 1)
    assert _REASONING not in retry and _TEMPERATURE not in retry


@respx.mock
def test_an_effort_lane_names_its_reasoning_effort(keyed_root: Path) -> None:
    route = respx.post(_ENDPOINT).mock(return_value=Response(200, json=reply_body()))
    lane = ModelLane(model=_LUNA, reasoning=True, effort="xhigh")
    consult(_MESSAGES, _SCHEMA, lane, keyed_root)
    assert sent(route, 0)[_REASONING] == {"effort": "xhigh"}


@respx.mock
def test_a_pro_lane_carries_its_own_token_budget(keyed_root: Path) -> None:
    route = respx.post(_ENDPOINT).mock(return_value=Response(200, json=reply_body()))
    lane = ModelLane(model=_LUNA, reasoning=True, timeout=900, max_tokens=32000)
    consult(_MESSAGES, _SCHEMA, lane, keyed_root)
    assert sent(route, 0)["max_tokens"] == 32000
