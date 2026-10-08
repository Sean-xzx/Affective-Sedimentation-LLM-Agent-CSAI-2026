from __future__ import annotations
from types import SimpleNamespace
import httpx
import openai
import pytest
from sprint.provider_qwen import (
    CompletionResult,
    SchemaError,
    TransportError,
    build_chat_create_kwargs,
    complete_choice,
    deterministic_backoff_seconds,
    extract_message_content,
    is_retryable_error,
    parse_choice,
    sanitize_log_message,
)
from sprint.schema import load_config
def _http_error(status: int, message: str) -> openai.APIStatusError:
    req = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    resp = httpx.Response(status, request=req)
    if status == 429:
        return openai.RateLimitError(message, response=resp, body=None)
    if status >= 500:
        return openai.InternalServerError(message, response=resp, body=None)
    return openai.APIStatusError(message, response=resp, body=None)
def _message(content: str | None, **extra):
    return SimpleNamespace(content=content, **extra)
def _response(
    content: str | None,
    *,
    model: str = "qwen3.7-flash-2026-07-15",
    response_id: str = "resp-1",
    message_extra: dict | None = None,
    response_extra: dict | None = None,
):
    msg = _message(content, **(message_extra or {}))
    return SimpleNamespace(
        id=response_id,
        model=model,
        choices=[SimpleNamespace(message=msg)],
        **(response_extra or {}),
    )
class FakeCompletions:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0
        self.last_kwargs = None
    def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
class FakeClient:
    def __init__(self, outcomes):
        self.chat = SimpleNamespace(completions=FakeCompletions(outcomes))
def test_parse_choice_accepts_exact_json_only():
    assert parse_choice('{"choice":"A"}') == "A"
    assert parse_choice('{"choice":"B"}') == "B"
    assert parse_choice('\n{"choice":"A"}\n') == "A"
    assert parse_choice(' {"choice" : "B"} ') == "B"
    assert parse_choice('{\n"choice": "A"\n}') == "A"
@pytest.mark.parametrize(
    "raw,code",
    [
        ("not json", "invalid_choice_json"),
        ('{"choice":"C"}', "invalid_choice_json"),
        ('{"choice":"A","extra":1}', "invalid_choice_json"),
        ('["A"]', "invalid_choice_json"),
    ],
)
def test_parse_choice_rejects_non_exact_json(raw, code):
    with pytest.raises(SchemaError) as exc:
        parse_choice(raw)
    assert exc.value.code == code
    assert exc.value.raw_response == raw
def test_build_chat_create_kwargs_match_config():
    cfg = load_config()
    kwargs = build_chat_create_kwargs(cfg, "prompt body")
    assert kwargs["model"] == "qwen3.7-flash-2026-07-15"
    assert kwargs["temperature"] == 0
    assert kwargs["top_p"] == 1
    assert kwargs["max_tokens"] == 16
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["tool_choice"] == "none"
    assert kwargs["extra_body"] == {"enable_thinking": False, "enable_search": False}
    assert kwargs["messages"] == [{"role": "user", "content": "prompt body"}]
    assert "seed" not in kwargs
    assert "tools" not in kwargs
def test_build_chat_create_kwargs_rejects_bad_config():
    cfg = dict(load_config())
    cfg["tools"] = "on"
    with pytest.raises(AssertionError):
        build_chat_create_kwargs(cfg, "prompt")
def test_build_chat_create_kwargs_rejects_enable_thinking():
    cfg = dict(load_config())
    cfg["enable_thinking"] = True
    with pytest.raises(AssertionError):
        build_chat_create_kwargs(cfg, "prompt")
def test_extract_message_content_rejects_side_channels():
    with pytest.raises(SchemaError, match="reasoning_content"):
        extract_message_content(_response('{"choice":"A"}', message_extra={"reasoning_content": "hidden"}))
    with pytest.raises(SchemaError, match="reasoning_content"):
        extract_message_content(_response('{"choice":"A"}', message_extra={"reasoning_content": ""}))
    with pytest.raises(SchemaError, match="tool_calls"):
        extract_message_content(_response('{"choice":"A"}', message_extra={"tool_calls": [{"id": "1"}]}))
    with pytest.raises(SchemaError, match="tool_calls"):
        extract_message_content(_response('{"choice":"A"}', message_extra={"tool_calls": []}))
    with pytest.raises(SchemaError, match="search metadata"):
        extract_message_content(_response('{"choice":"A"}', response_extra={"search_info": {"q": "x"}}))
    with pytest.raises(SchemaError, match="search metadata"):
        extract_message_content(_response('{"choice":"A"}', response_extra={"search_info": {}}))
    with pytest.raises(SchemaError, match="search metadata"):
        extract_message_content(_response('{"choice":"A"}', response_extra={"search_results": []}))
    with pytest.raises(SchemaError, match="search metadata"):
        extract_message_content(_response('{"choice":"A"}', response_extra={"web_search": ""}))
    with pytest.raises(SchemaError, match="search metadata"):
        extract_message_content(_response('{"choice":"A"}', message_extra={"search_info": {}}))
    with pytest.raises(SchemaError, match="search metadata"):
        extract_message_content(_response('{"choice":"A"}', message_extra={"search_results": []}))
def test_extract_message_content_rejects_empty_or_missing_message():
    with pytest.raises(SchemaError, match="no choices"):
        extract_message_content(SimpleNamespace(choices=[]))
    with pytest.raises(SchemaError, match="no message"):
        extract_message_content(SimpleNamespace(choices=[SimpleNamespace(message=None)]))
def test_complete_choice_stores_canonical_raw_response():
    client = FakeClient([_response('\n {"choice":"A"} \n')])
    result = complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert result.raw_response == '{"choice":"A"}'
    assert result.choice == "A"

def test_complete_choice_success():
    client = FakeClient([_response('{"choice":"A"}', response_extra={"usage": SimpleNamespace(prompt_tokens=10, completion_tokens=2, total_tokens=12)})])
    result = complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert isinstance(result, CompletionResult)
    assert result.choice == "A"
    assert result.retry_count == 0
    assert result.prompt_tokens == 10 and result.completion_tokens == 2 and result.total_tokens == 12
    assert result.requested_model == "qwen3.7-flash-2026-07-15"
    assert client.chat.completions.calls == 1

def test_complete_choice_null_usage_when_absent():
    client = FakeClient([_response('{"choice":"A"}')])
    result = complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert result.prompt_tokens is None and result.completion_tokens is None and result.total_tokens is None

def test_complete_choice_schema_fail_preserves_usage():
    usage = SimpleNamespace(prompt_tokens=7, completion_tokens=1, total_tokens=8)
    client = FakeClient([_response("bad", response_extra={"usage": usage})])
    with pytest.raises(SchemaError) as exc:
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert exc.value.prompt_tokens == 7 and exc.value.completion_tokens == 1 and exc.value.total_tokens == 8
def test_complete_choice_retries_429_then_succeeds():
    client = FakeClient([_http_error(429, "rate limit"), _response('{"choice":"B"}')])
    sleeps: list[float] = []
    result = complete_choice("hello", config=load_config(), client=client, sleep=sleeps.append)
    assert result.choice == "B"
    assert result.retry_count == 1
    assert client.chat.completions.calls == 2
    assert sleeps == [deterministic_backoff_seconds(0)]
def test_complete_choice_retries_5xx_then_succeeds():
    client = FakeClient([_http_error(500, "server"), _http_error(500, "server"), _response('{"choice":"A"}')])
    result = complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert result.choice == "A"
    assert result.retry_count == 2
    assert client.chat.completions.calls == 3
def test_complete_choice_no_retry_on_bad_json():
    client = FakeClient([_response("Choose A because ...")])
    with pytest.raises(SchemaError, match='exactly {"choice":"A"}'):
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert client.chat.completions.calls == 1
def test_complete_choice_no_retry_on_reasoning_content():
    client = FakeClient([_response('{"choice":"A"}', message_extra={"reasoning_content": "think"})])
    with pytest.raises(SchemaError, match="reasoning_content"):
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert client.chat.completions.calls == 1
def test_complete_choice_no_retry_on_empty_reasoning_content():
    client = FakeClient([_response('{"choice":"A"}', message_extra={"reasoning_content": ""})])
    with pytest.raises(SchemaError, match="reasoning_content"):
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert client.chat.completions.calls == 1
def test_complete_choice_no_retry_on_empty_tool_calls():
    client = FakeClient([_response('{"choice":"A"}', message_extra={"tool_calls": []})])
    with pytest.raises(SchemaError, match="tool_calls"):
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert client.chat.completions.calls == 1
def test_complete_choice_no_retry_on_empty_search_metadata():
    client = FakeClient([_response('{"choice":"A"}', response_extra={"search_info": {}})])
    with pytest.raises(SchemaError, match="search metadata"):
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert client.chat.completions.calls == 1
    client = FakeClient([_response('{"choice":"A"}', message_extra={"search_results": []})])
    with pytest.raises(SchemaError, match="search metadata"):
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert client.chat.completions.calls == 1
def test_complete_choice_no_retry_on_schema_fail():
    client = FakeClient([_response('{"choice":"C"}')])
    with pytest.raises(SchemaError, match='exactly {"choice":"A"}'):
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert client.chat.completions.calls == 1
def test_complete_choice_exhausts_transport_retries():
    client = FakeClient([_http_error(429, "rate limit")] * 4)
    with pytest.raises(TransportError) as exc:
        complete_choice("hello", config=load_config(), client=client, sleep=lambda _: None)
    assert exc.value.code == "transport_exhausted"
    assert exc.value.retry_count == 3
    assert client.chat.completions.calls == 4
def test_is_retryable_error_classification():
    assert is_retryable_error(openai.APITimeoutError("t"))
    req = httpx.Request("POST", "https://example.com/v1/chat/completions")
    assert is_retryable_error(openai.APIConnectionError(request=req))
    assert is_retryable_error(_http_error(429, "r"))
    assert is_retryable_error(_http_error(500, "i"))
    assert not is_retryable_error(_http_error(400, "b"))
def test_sanitize_log_message_redacts_secrets():
    msg = "Authorization: Bearer sk-testsecret123 api_key=abc123"
    clean = sanitize_log_message(msg)
    assert "sk-testsecret" not in clean
    assert "abc123" not in clean
    assert "[REDACTED]" in clean
def test_deterministic_backoff_sequence():
    assert [deterministic_backoff_seconds(i) for i in range(4)] == [1.0, 2.0, 4.0, 8.0]
