import json

from astrid.anthropic_adapter import AnthropicModelAdapter
from astrid.tooling import ToolDefinition, ToolRegistry


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
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
    assert captured["body"]["max_tokens"] > 0
