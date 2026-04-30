from astrid.agent_loop import run_agent_turn
from astrid.tooling import ToolDefinition, ToolRegistry, ToolResult
from astrid.types import AgentStep, ChatMessage, ModelAdapter, StepDiagnostics


class ScriptedModel(ModelAdapter):
    def __init__(self, steps: list[AgentStep | BaseException]) -> None:
        self._steps = steps
        self.calls = 0

    def next(self, messages: list[ChatMessage]) -> AgentStep:
        step = self._steps[self.calls]
        self.calls += 1
        if isinstance(step, BaseException):
            raise step
        return step


def test_agent_turn_executes_tool_and_returns_assistant() -> None:
    def run_echo(input_data: dict, _context) -> ToolResult:
        return ToolResult(ok=True, output=f"echo:{input_data['text']}")

    registry = ToolRegistry(
        [
            ToolDefinition(
                name="echo",
                description="echo tool",
                input_schema={"type": "object"},
                validator=lambda value: value,
                run=run_echo,
            )
        ]
    )
    model = ScriptedModel(
        [
            AgentStep(
                type="tool_calls",
                calls=[{"id": "1", "toolName": "echo", "input": {"text": "hi"}}],
            ),
            AgentStep(type="assistant", content="done"),
        ]
    )

    messages = run_agent_turn(
        model=model,
        tools=registry,
        messages=[{"role": "system", "content": "sys"}],
        cwd=".",
    )

    assert messages[-1] == {"role": "assistant", "content": "done"}
    assert any(message["role"] == "tool_result" for message in messages)


def test_agent_turn_emits_callbacks() -> None:
    events: list[tuple[str, str]] = []

    def run_echo(input_data: dict, _context) -> ToolResult:
        return ToolResult(ok=True, output=f"echo:{input_data['text']}")

    registry = ToolRegistry(
        [
            ToolDefinition(
                name="echo",
                description="echo tool",
                input_schema={"type": "object"},
                validator=lambda value: value,
                run=run_echo,
            )
        ]
    )
    model = ScriptedModel(
        [
            AgentStep(type="tool_calls", content="working", contentKind="progress", calls=[{"id": "1", "toolName": "echo", "input": {"text": "hi"}}]),
            AgentStep(type="assistant", content="done"),
        ]
    )

    run_agent_turn(
        model=model,
        tools=registry,
        messages=[{"role": "system", "content": "sys"}],
        cwd=".",
        on_tool_start=lambda name, _input: events.append(("start", name)),
        on_tool_result=lambda name, _output, _error: events.append(("result", name)),
        on_assistant_message=lambda content: events.append(("assistant", content)),
        on_progress_message=lambda content: events.append(("progress", content)),
    )

    assert ("progress", "working") in events
    assert ("start", "echo") in events
    assert ("result", "echo") in events
    assert ("assistant", "done") in events
    assert ("progress", "Planning the next step") in events
    assert ("progress", "Received result from echo") in events


def test_agent_turn_retries_empty_response_then_continues() -> None:
    model = ScriptedModel(
        [
            AgentStep(type="assistant", content=""),
            AgentStep(type="assistant", content="done"),
        ]
    )
    registry = ToolRegistry([])

    messages = run_agent_turn(
        model=model,
        tools=registry,
        messages=[{"role": "system", "content": "sys"}],
        cwd=".",
    )

    assert messages[-1] == {"role": "assistant", "content": "done"}
    assert any(
        message["role"] == "user" and "last response was empty" in message["content"]
        for message in messages
    )


def test_agent_turn_handles_recoverable_pause_turn() -> None:
    model = ScriptedModel(
        [
            AgentStep(
                type="assistant",
                content="",
                diagnostics=StepDiagnostics(stopReason="pause_turn", ignoredBlockTypes=["thinking"]),
            ),
            AgentStep(type="assistant", content="done"),
        ]
    )
    registry = ToolRegistry([])
    progress_events: list[str] = []

    messages = run_agent_turn(
        model=model,
        tools=registry,
        messages=[{"role": "system", "content": "sys"}],
        cwd=".",
        on_progress_message=progress_events.append,
    )

    assert messages[-1] == {"role": "assistant", "content": "done"}
    assert any("pause_turn" in event for event in progress_events)


def test_agent_turn_emits_adapting_progress_after_tool_result() -> None:
    def run_echo(input_data: dict, _context) -> ToolResult:
        return ToolResult(ok=True, output=f"echo:{input_data['text']}")

    registry = ToolRegistry(
        [
            ToolDefinition(
                name="echo",
                description="echo tool",
                input_schema={"type": "object"},
                validator=lambda value: value,
                run=run_echo,
            )
        ]
    )
    model = ScriptedModel(
        [
            AgentStep(type="tool_calls", calls=[{"id": "1", "toolName": "echo", "input": {"text": "hi"}}]),
            AgentStep(type="assistant", content="done"),
        ]
    )
    progress_events: list[str] = []

    run_agent_turn(
        model=model,
        tools=registry,
        messages=[{"role": "system", "content": "sys"}],
        cwd=".",
        on_progress_message=progress_events.append,
    )

    assert "Planning the next step" in progress_events
    assert "Received result from echo" in progress_events
    assert "Adapting after the latest tool result" in progress_events


def test_agent_turn_recovers_from_timeout_after_file_write(tmp_path) -> None:
    def run_write_file(input_data: dict, _context) -> ToolResult:
        target = tmp_path / input_data["path"]
        target.write_text(input_data["content"], encoding="utf-8")
        return ToolResult(ok=True, output=f"wrote:{target.name}")

    registry = ToolRegistry(
        [
            ToolDefinition(
                name="write_file",
                description="write file tool",
                input_schema={"type": "object"},
                validator=lambda value: value,
                run=run_write_file,
            )
        ]
    )
    model = ScriptedModel(
        [
            AgentStep(
                type="tool_calls",
                calls=[{"id": "1", "toolName": "write_file", "input": {"path": "index.html", "content": "partial"}}],
            ),
            TimeoutError("read operation timed out"),
            AgentStep(type="assistant", content="done"),
        ]
    )
    progress_events: list[str] = []

    messages = run_agent_turn(
        model=model,
        tools=registry,
        messages=[{"role": "system", "content": "sys"}],
        cwd=".",
        on_progress_message=progress_events.append,
    )

    assert messages[-1] == {"role": "assistant", "content": "done"}
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "partial"
    assert model.calls == 3
    assert any("timeout" in message["content"].lower() for message in messages if message["role"] == "assistant_progress")
    assert any("timeout" in event.lower() for event in progress_events)
    assert any("Tool duration: write_file elapsed_seconds=" in event for event in progress_events)


def test_agent_turn_emits_model_usage_progress() -> None:
    model = ScriptedModel(
        [
            AgentStep(
                type="assistant",
                content="done",
                diagnostics=StepDiagnostics(inputTokens=10, outputTokens=5),
            )
        ]
    )
    progress_events: list[str] = []

    messages = run_agent_turn(
        model=model,
        tools=ToolRegistry([]),
        messages=[{"role": "system", "content": "sys"}],
        cwd=".",
        on_progress_message=progress_events.append,
    )

    assert messages[-1] == {"role": "assistant", "content": "done"}
    assert "Model usage: input_tokens=10 output_tokens=5 total_tokens=15" in progress_events
    assert any(
        message["role"] == "assistant_progress" and "total_tokens=15" in message["content"]
        for message in messages
    )


def test_agent_turn_returns_fallback_after_repeated_empty_responses() -> None:
    model = ScriptedModel(
        [
            AgentStep(type="assistant", content=""),
            AgentStep(type="assistant", content=""),
            AgentStep(type="assistant", content=""),
        ]
    )
    registry = ToolRegistry([])

    messages = run_agent_turn(
        model=model,
        tools=registry,
        messages=[{"role": "system", "content": "sys"}],
        cwd=".",
    )

    assert "empty response" in messages[-1]["content"].lower()


def test_tool_registry_dispose_calls_disposer() -> None:
    disposed: list[bool] = []
    registry = ToolRegistry([], disposer=lambda: disposed.append(True))

    registry.dispose()

    assert disposed == [True]
