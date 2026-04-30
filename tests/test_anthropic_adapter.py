import json

from astrid.integrations.anthropic_adapter import AnthropicModelAdapter
from astrid.runtime.config import DEFAULT_MAX_OUTPUT_TOKENS
from astrid.core.tooling import ToolDefinition, ToolRegistry


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TimeoutThenResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self._reads = 0

    def read(self) -> bytes:
        self._reads += 1
        if self._reads == 1:
            raise TimeoutError("read operation timed out")
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolDefinition(
                name="read_file",
                description="Read file",
                input_schema={"type": "object"},
                validator=lambda value: value,
                run=lambda _input, _context: None,
            )
        ]
    )


def test_anthropic_adapter_parses_tool_use(monkeypatch) -> None:
    payload = {
        "stop_reason": "tool_use",
        "content": [
            {"type": "text", "text": "<progress>thinking</progress>"},
            {"type": "tool_use", "id": "tool-1", "name": "read_file", "input": {"path": "README.md"}},
        ],
    }
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=60: DummyResponse(payload))
    adapter = AnthropicModelAdapter(
        {"model": "claude", "baseUrl": "https://api.anthropic.com", "authToken": "x"},
        _tool_registry(),
    )

    step = adapter.next([{"role": "system", "content": "sys"}, {"role": "user", "content": "read me"}])

    assert step.type == "tool_calls"
    assert step.content == "thinking"
    assert step.contentKind == "progress"
    assert step.calls[0]["toolName"] == "read_file"


def test_anthropic_adapter_parses_final_text(monkeypatch) -> None:
    payload = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "<final>done</final>"}],
    }
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=60: DummyResponse(payload))
    adapter = AnthropicModelAdapter(
        {"model": "claude", "baseUrl": "https://api.anthropic.com", "authToken": "x"},
        _tool_registry(),
    )

    step = adapter.next([{"role": "system", "content": "sys"}, {"role": "user", "content": "finish"}])

    assert step.type == "assistant"
    assert step.content == "done"
    assert step.kind == "final"


def test_anthropic_adapter_sends_default_max_tokens_when_runtime_omits_it(monkeypatch) -> None:
    payload = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "<final>done</final>"}],
    }
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=60):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return DummyResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    adapter = AnthropicModelAdapter(
        {"model": "claude", "baseUrl": "https://api.anthropic.com", "authToken": "x", "maxOutputTokens": None},
        _tool_registry(),
    )

    step = adapter.next([{"role": "system", "content": "sys"}, {"role": "user", "content": "finish"}])

    assert step.type == "assistant"
    assert captured["body"]["max_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS


def test_anthropic_adapter_uses_runtime_timeout(monkeypatch) -> None:
    payload = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "<final>done</final>"}],
    }
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=60):
        captured["timeout"] = timeout
        return DummyResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    adapter = AnthropicModelAdapter(
        {
            "model": "claude",
            "baseUrl": "https://api.anthropic.com",
            "authToken": "x",
            "modelTimeoutSeconds": 240,
        },
        _tool_registry(),
    )

    adapter.next([{"role": "system", "content": "sys"}, {"role": "user", "content": "finish"}])

    assert captured["timeout"] == 240


def test_anthropic_adapter_retries_read_timeout(monkeypatch) -> None:
    payload = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "<final>done after retry</final>"}],
    }
    calls = 0

    def _fake_urlopen(request, timeout=60):
        nonlocal calls
        calls += 1
        if calls == 1:
            return TimeoutThenResponse(payload)
        return DummyResponse(payload)

    monkeypatch.setenv("ASTRID_MAX_RETRIES", "1")
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    adapter = AnthropicModelAdapter(
        {"model": "claude", "baseUrl": "https://api.anthropic.com", "authToken": "x"},
        _tool_registry(),
    )

    step = adapter.next([{"role": "system", "content": "sys"}, {"role": "user", "content": "finish"}])

    assert calls == 2
    assert step.type == "assistant"
    assert step.content == "done after retry"


def test_anthropic_adapter_records_token_usage(monkeypatch) -> None:
    payload = {
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 123, "output_tokens": 45},
        "content": [{"type": "text", "text": "<final>done</final>"}],
    }

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=60: DummyResponse(payload))
    adapter = AnthropicModelAdapter(
        {"model": "claude", "baseUrl": "https://api.anthropic.com", "authToken": "x"},
        _tool_registry(),
    )

    step = adapter.next([{"role": "system", "content": "sys"}, {"role": "user", "content": "finish"}])

    assert step.diagnostics is not None
    assert step.diagnostics.inputTokens == 123
    assert step.diagnostics.outputTokens == 45
