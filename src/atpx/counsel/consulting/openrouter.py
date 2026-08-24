import os
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import cast

from openai import (
    APIConnectionError,
    APIStatusError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from openai.types.shared_params import ResponseFormatJSONSchema
from pydantic import JsonValue

from ...models.consultation import Consultation
from ...models.lane import Message, ModelLane, Schema

_ENDPOINT = "https://openrouter.ai/api/v1"
_KEY_LINE = "OPENROUTER_API_KEY="
_MAX_TOKENS = 8000
_REASONING_MAX_TOKENS = 24000
_RETRIES = 3
_TIMEOUT = 180.0


def api_key(root: Path) -> str:
    """The OpenRouter key, the environment first and the workspace `.env` second.

    The environment wins so any workspace works under an activated session
    without duplicating the secret per repo; the `.env` fallback keeps
    single-workspace use zero-setup. Read fresh and never logged.

    root: the workspace root holding the fallback `.env` file.
    """
    if exported := os.environ.get("OPENROUTER_API_KEY"):
        return exported
    try:
        lines = (root / ".env").read_text().splitlines()
    except FileNotFoundError as error:
        raise RuntimeError(f"no .env under {root} holding a {_KEY_LINE} line") from error
    for line in lines:
        if line.startswith(_KEY_LINE):
            return line.removeprefix(_KEY_LINE).strip().strip('"')
    raise RuntimeError(f"{root / '.env'} has no {_KEY_LINE} line")


def consult(
    messages: Sequence[Message], schema: Schema, lane: ModelLane, root: Path
) -> Consultation:
    """Ask one lane for one strict-JSON reply through OpenRouter, synchronously.

    messages: the chat messages, system first.
    schema: the JSON schema the reply must satisfy.
    lane: the model and sampling policy to consult.
    root: the workspace root whose `.env` holds the key.
    """
    return OpenRouter(lane, root).reply(messages, schema)


class OpenRouter:
    """One strict-JSON consultation through OpenRouter, via the official OpenAI client.

    The request shape is measured protocol: `max_tokens` 8000 (24000 for
    reasoning lanes, whose thinking otherwise starves the reply of its budget),
    throughput-sorted
    provider routing with fallbacks allowed, and a strict `json_schema` response
    format, carried in `extra_body` since the official client has no vocabulary
    of its own for OpenRouter's provider and reasoning fields. The lane's
    reasoning policy picks the degradation ladder: a reasoning lane never
    mentions the field and only drops its sampling on a 400, while the measured
    reasoning-off ladder opens disabled with the lane's sampling, then minimal
    effort without temperature on a 400, then neither. The client's own
    retries stay off (`max_retries=0`); this class owns every retry itself so
    the measured backoff stays exact, and exhaustion records an explicit failed
    consultation rather than raising.
    """

    def __init__(self, lane: ModelLane, root: Path) -> None:
        """lane: the model and sampling policy to consult.

        root: the workspace root whose `.env` holds the key.
        """
        self.lane = lane
        self.client = OpenAI(
            api_key=api_key(root),
            base_url=_ENDPOINT,
            timeout=lane.timeout or _TIMEOUT,
            max_retries=0,
        )
        opening: Schema = (
            {"reasoning": {"effort": lane.effort}, **lane.sampling()}
            if lane.effort
            else dict(lane.sampling())
        )
        self.variants: list[Schema] = (
            [opening, {}]
            if lane.reasoning
            else [
                {"reasoning": {"enabled": False}, **lane.sampling()},
                {"reasoning": {"effort": "minimal"}},
                {},
            ]
        )

    def reply(self, messages: Sequence[Message], schema: Schema) -> Consultation:
        """The consultation for one message exchange, after any degradations and retries.

        Each call runs its own fresh degradation and retry state, so one
        instance is safe to reuse across independent consultations.

        messages: the chat messages, system first.
        schema: the JSON schema the reply must satisfy.
        """
        self.start = time.monotonic()
        self.step = 0
        self.retries = 0
        self.outcome: Consultation | None = None
        while self.outcome is None:
            self.__attempt(messages, schema)
        return self.outcome

    def __answered(self, completion: ChatCompletion) -> Consultation:
        """Shape one reply into a consultation record.

        OpenRouter can carry an application error inside a 200 body, which the
        client parses as a choice-less completion, so that comes back as a
        failed consultation rather than a crash mid-episode.
        """
        if not completion.choices:
            return self.__failed(f"error body: {completion.model_dump_json()[:500]}")
        usage = completion.usage
        details = usage.completion_tokens_details if usage else None
        return Consultation(
            content=completion.choices[0].message.content or "",
            model=completion.model or self.lane.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            reasoning_tokens=(details.reasoning_tokens if details else None) or 0,
            elapsed=time.monotonic() - self.start,
        )

    def __attempt(self, messages: Sequence[Message], schema: Schema) -> None:
        """One request with the current degradation variant, routed to its outcome."""
        body: dict[str, JsonValue] = {
            "provider": {"sort": "throughput", "allow_fallbacks": True},
            **self.variants[self.step],
        }
        try:
            completion = self.client.chat.completions.create(
                model=self.lane.model,
                messages=cast(Iterable[ChatCompletionMessageParam], messages),
                max_tokens=self.lane.max_tokens
                or (_REASONING_MAX_TOKENS if self.lane.reasoning else _MAX_TOKENS),
                response_format=cast(
                    ResponseFormatJSONSchema,
                    {
                        "type": "json_schema",
                        "json_schema": {"name": "reply", "strict": True, "schema": schema},
                    },
                ),
                extra_body=body,
            )
        except BadRequestError as error:
            return self.__degraded(error)
        except (RateLimitError, InternalServerError) as error:
            return self.__retried(f"HTTP {error.status_code}")
        except APIStatusError as error:
            return self.__stopped(error)
        except APIConnectionError as error:
            return self.__retried("transport failure", detail=f": {error}")
        self.outcome = self.__answered(completion)

    def __degraded(self, error: BadRequestError) -> None:
        """Advance to the next reasoning variant, or fail once every variant is spent."""
        if self.step + 1 < len(self.variants):
            self.step += 1
            return
        self.outcome = self.__failed(f"HTTP 400: {error.response.text[:500]}")

    def __failed(self, error: str) -> Consultation:
        """The explicit failure record when the lane cannot answer."""
        return Consultation(
            content="",
            model=self.lane.model,
            elapsed=time.monotonic() - self.start,
            error=error,
        )

    def __retried(self, cause: str, *, detail: str = "") -> None:
        """Sleep before the next try, or record the failure once retries exhaust.

        cause: what failed, opening the exhaustion message.
        detail: trailing context appended after the try count.
        """
        self.retries += 1
        if self.retries > _RETRIES:
            self.outcome = self.__failed(f"{cause} after {self.retries} tries{detail}")
            return
        time.sleep(2.0 * self.retries)

    def __stopped(self, error: APIStatusError) -> None:
        """Fail immediately on a status this client never retries or degrades."""
        self.outcome = self.__failed(f"HTTP {error.status_code}: {error.response.text[:500]}")
