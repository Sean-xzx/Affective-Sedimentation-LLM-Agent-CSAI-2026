from __future__ import annotations
import json, logging, os, re, time
from dataclasses import dataclass
from typing import Callable, Literal
import openai
from openai import OpenAI
from sprint.schema import load_config
Choice = Literal["A", "B"]
_LOG = logging.getLogger(__name__)
_REDACT = (
    (re.compile(r"Bearer\s+\S+", re.I), "Bearer [REDACTED]"),
    (re.compile(r"(?:api[_-]?key|authorization)\s*[:=]\s*\S+", re.I), "[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "[REDACTED]"),
)
class ProviderError(Exception):
    def __init__(self, code: str, message: str, *, raw_response: str | None = None, retry_count: int = 0, prompt_tokens: int | None = None, completion_tokens: int | None = None, total_tokens: int | None = None):
        super().__init__(message); self.code, self.raw_response, self.retry_count = code, raw_response, retry_count
        self.prompt_tokens, self.completion_tokens, self.total_tokens = prompt_tokens, completion_tokens, total_tokens
class SchemaError(ProviderError):
    pass
class TransportError(ProviderError):
    pass
@dataclass(frozen=True)
class CompletionResult:
    choice: Choice
    raw_response: str
    requested_model: str
    returned_model: str | None
    response_id: str | None
    latency_ms: int
    retry_count: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
def _usage_fields(response: object) -> dict[str, int | None]:
    u = getattr(response, "usage", None)
    if u is None: return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    return {"prompt_tokens": getattr(u, "prompt_tokens", None), "completion_tokens": getattr(u, "completion_tokens", None), "total_tokens": getattr(u, "total_tokens", None)}
def sanitize_log_message(text: str) -> str:
    out = text
    for pattern, repl in _REDACT:
        out = pattern.sub(repl, out)
    return out
def parse_choice(raw: str) -> Choice:
    _e = SchemaError("invalid_choice_json", 'response must be exactly {"choice":"A"} or {"choice":"B"}', raw_response=raw)
    try: obj = json.loads(raw.strip())
    except json.JSONDecodeError: raise _e
    if not isinstance(obj, dict) or set(obj) != {"choice"} or obj["choice"] not in ("A", "B"): raise _e
    return obj["choice"]
def _response_search_metadata(obj: object) -> object | None:
    for attr in ("search_info", "search_results", "web_search"):
        if getattr(obj, attr, None) is not None:
            return getattr(obj, attr)
    return None
def extract_message_content(response: object) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        raise SchemaError("empty_choices", "response has no choices")
    message = choices[0].message
    if message is None:
        raise SchemaError("missing_message", "response choice has no message")
    if getattr(message, "reasoning_content", None) is not None:
        raise SchemaError("reasoning_content", "response contains reasoning_content", raw_response=str(message.reasoning_content))
    if getattr(message, "tool_calls", None) is not None:
        raise SchemaError("tool_calls", "response contains tool_calls", raw_response=str(message.tool_calls))
    for obj in (response, message):
        if (search_meta := _response_search_metadata(obj)) is not None:
            raise SchemaError("search_metadata", "response contains search metadata", raw_response=str(search_meta))
    return message.content or ""
def is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return True
    if isinstance(exc, openai.RateLimitError):
        return True
    if isinstance(exc, openai.InternalServerError):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
        return True
    return False
def deterministic_backoff_seconds(retry_index: int) -> float:
    return float(min(8, 2 ** retry_index))
def build_chat_create_kwargs(cfg: dict[str, object], prompt: str) -> dict[str, object]:
    assert cfg["tools"] == "off"
    assert cfg["search"] == "off"
    assert cfg["request_seed"] is None
    assert cfg["enable_thinking"] is False
    return {
        "model": cfg["agent_model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg["temperature"],
        "top_p": cfg["top_p"],
        "max_tokens": cfg["max_tokens"],
        "response_format": cfg["response_format"],
        "tool_choice": "none",
        "extra_body": {"enable_thinking": cfg["enable_thinking"], "enable_search": False},
    }
def make_client(config: dict[str, object] | None = None) -> OpenAI:
    cfg = config or load_config()
    if not (key := os.environ.get("DASHSCOPE_API_KEY")): raise EnvironmentError("DASHSCOPE_API_KEY not set")
    base = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
    return OpenAI(api_key=key, base_url=base, timeout=float(cfg["timeout_seconds"]))
def complete_choice(
    prompt: str,
    *,
    config: dict[str, object] | None = None,
    client: OpenAI | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> CompletionResult:
    cfg = config or load_config()
    api = client or make_client(cfg)
    params = build_chat_create_kwargs(cfg, prompt)
    max_retries = int(cfg["max_retries"])
    last_transport: TransportError | None = None
    for attempt in range(max_retries + 1):
        started = time.perf_counter()
        try:
            response = api.chat.completions.create(**params)
            usage = _usage_fields(response)
            try:
                raw = extract_message_content(response)
                choice = parse_choice(raw)
            except SchemaError as exc:
                raise SchemaError(exc.code, str(exc), raw_response=exc.raw_response, retry_count=attempt, **usage) from exc
            latency_ms = int((time.perf_counter() - started) * 1000)
            return CompletionResult(choice=choice, raw_response=f'{{"choice":"{choice}"}}', requested_model=str(cfg["agent_model"]), returned_model=getattr(response, "model", None),
                response_id=getattr(response, "id", None), latency_ms=latency_ms, retry_count=attempt, **usage)
        except SchemaError:
            raise
        except Exception as exc:
            if not is_retryable_error(exc) or attempt >= max_retries:
                code = "transport_exhausted" if attempt >= max_retries and is_retryable_error(exc) else "transport_error"
                msg = sanitize_log_message(str(exc))
                _LOG.warning("qwen transport failure attempt=%s code=%s", attempt, code)
                if is_retryable_error(exc) and attempt >= max_retries:
                    raise TransportError(code, msg, retry_count=attempt) from exc
                raise TransportError(code, msg, retry_count=attempt) from exc
            last_transport = TransportError("transport_retry", sanitize_log_message(str(exc)), retry_count=attempt)
            _LOG.warning("qwen retryable error attempt=%s", attempt)
            sleep(deterministic_backoff_seconds(attempt))
    raise last_transport or TransportError("transport_exhausted", "request failed", retry_count=max_retries)
