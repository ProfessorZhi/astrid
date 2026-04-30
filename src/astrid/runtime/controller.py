from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from astrid.core.agent_loop import run_agent_turn as default_run_agent_turn
from astrid.state.history import save_history_entries as default_save_history_entries
from astrid.runtime.local_tool_shortcuts import parse_local_tool_shortcut
from astrid.core.prompt import build_system_prompt as default_build_system_prompt
from astrid.core.tooling import ToolContext
from astrid.tui.types import TranscriptEntry


LocalCommandHandler = Callable[[str, Any], str | None]
TranscriptSaver = Callable[[str], str]
OutputWriter = Callable[[str], None]
RunAgentTurn = Callable[..., list[dict[str, str]]]
BuildSystemPrompt = Callable[..., str]
SaveHistoryEntries = Callable[[list[str], str], None]


@dataclass
class RuntimeTurnCallbacks:
    """UI callbacks for one model turn.

    RuntimeController owns turn lifecycle and permission boundaries. Frontends
    may supply these callbacks to render progress in their own style.
    """

    on_assistant_message: Callable[[str], None] | None = None
    on_progress_message: Callable[[str], None] | None = None
    on_tool_start: Callable[[str, dict[str, Any]], None] | None = None
    on_tool_result: Callable[[str, str, bool], None] | None = None


def append_transcript(transcript: list[TranscriptEntry], **kwargs: Any) -> None:
    transcript.append(TranscriptEntry(id=len(transcript) + 1, **kwargs))


def _preview(value: Any, *, limit: int = 500) -> str:
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > limit:
        return text[:limit] + "... [truncated]"
    return text


class RuntimeController:
    """UI-neutral wrapper around one Astrid user turn.

    Frontends should call this controller instead of embedding turn execution,
    tool progress rendering, history updates, and transcript bookkeeping.
    """

    def __init__(
        self,
        *,
        cwd: str,
        permissions: Any,
        transcript: list[TranscriptEntry],
        tools: Any,
        messages: list[dict[str, str]],
        history: list[str],
        model: Any,
        max_tool_steps: int | None,
        advanced_memory_mgr: Any,
        context_mgr: Any,
        logger: Any,
        local_command_handler: LocalCommandHandler,
        transcript_saver: TranscriptSaver,
        output_writer: OutputWriter | None = None,
        run_agent_turn_fn: RunAgentTurn = default_run_agent_turn,
        build_system_prompt_fn: BuildSystemPrompt = default_build_system_prompt,
        save_history_entries_fn: SaveHistoryEntries = default_save_history_entries,
    ) -> None:
        self.cwd = cwd
        self.permissions = permissions
        self.transcript = transcript
        self.tools = tools
        self.messages = messages
        self.history = history
        self.model = model
        self.max_tool_steps = max_tool_steps
        self.advanced_memory_mgr = advanced_memory_mgr
        self.context_mgr = context_mgr
        self.logger = logger
        self.local_command_handler = local_command_handler
        self.transcript_saver = transcript_saver
        self.output_writer = output_writer or print
        self._run_agent_turn = run_agent_turn_fn
        self._build_system_prompt = build_system_prompt_fn
        self._save_history_entries = save_history_entries_fn

    def handle_user_input(
        self,
        user_input: str,
        *,
        callbacks: RuntimeTurnCallbacks | None = None,
    ) -> list[dict[str, str]] | None:
        if user_input == "/exit":
            return None
        if user_input.startswith("/transcript-save "):
            output_path = user_input[len("/transcript-save ") :].strip()
            if not output_path:
                self.output_writer("Usage: /transcript-save <path>")
                return self.messages
            saved_path = self.transcript_saver(output_path)
            self.output_writer(f"Saved transcript to {saved_path}")
            return self.messages

        local_result = self.local_command_handler(user_input, self.tools)
        if local_result is not None:
            append_transcript(self.transcript, kind="user", body=user_input)
            append_transcript(self.transcript, kind="assistant", body=local_result)
            self.output_writer(local_result)
            return self.messages

        shortcut = parse_local_tool_shortcut(user_input)
        if shortcut is not None:
            append_transcript(self.transcript, kind="user", body=user_input)
            result = self.tools.execute(
                shortcut["toolName"],
                shortcut["input"],
                context=ToolContext(cwd=self.cwd, permissions=self.permissions),
            )
            append_transcript(
                self.transcript,
                kind="tool",
                body=result.output,
                toolName=shortcut["toolName"],
                status="success" if result.ok else "error",
            )
            self.output_writer(result.output)
            return self.messages

        return self.execute_agent_turn(user_input, callbacks=callbacks)

    def execute_agent_turn(
        self,
        user_input: str,
        *,
        callbacks: RuntimeTurnCallbacks | None = None,
        record_user_transcript: bool = True,
        record_history: bool = True,
        emit_output: bool = True,
    ) -> list[dict[str, str]]:
        """Execute one model turn behind the UI-neutral runtime boundary."""
        if record_user_transcript:
            append_transcript(self.transcript, kind="user", body=user_input)
        self.messages.append({"role": "user", "content": user_input})
        if record_history:
            self.history.append(user_input)
            self._save_history_entries(self.history, self.cwd)
        if hasattr(self.tools, "refresh_capabilities"):
            self.tools.refresh_capabilities()
        self.messages[0] = {
            "role": "system",
            "content": self._build_system_prompt(
                self.cwd,
                self.permissions.get_summary(),
                {
                    "skills": self.tools.get_skills(),
                    "mcpServers": self.tools.get_mcp_servers(),
                    "advanced_memory_context": (
                        self.advanced_memory_mgr.format_context_for_prompt(max_tokens=5000)
                        if self.advanced_memory_mgr is not None
                        else ""
                    ),
                },
            ),
        }
        self.permissions.begin_turn()

        def _on_progress(content: str) -> None:
            if callbacks and callbacks.on_progress_message:
                callbacks.on_progress_message(content)
                return
            append_transcript(self.transcript, kind="assistant", body=content)
            if emit_output:
                self.output_writer(f"[progress] {content}")

        def _on_tool_start(tool_name: str, input_data: dict[str, Any]) -> None:
            if callbacks and callbacks.on_tool_start:
                callbacks.on_tool_start(tool_name, input_data)
                return
            body = _preview(input_data)
            append_transcript(
                self.transcript,
                kind="tool",
                body=f"input: {body}",
                toolName=tool_name,
                status="running",
            )
            if emit_output:
                self.output_writer(f"[tool:start] {tool_name} {body}")

        def _on_tool_result(tool_name: str, output: str, is_error: bool) -> None:
            if callbacks and callbacks.on_tool_result:
                callbacks.on_tool_result(tool_name, output, is_error)
                return
            status = "error" if is_error else "success"
            body = _preview(output, limit=1200)
            append_transcript(
                self.transcript,
                kind="tool",
                body=body,
                toolName=tool_name,
                status=status,
            )
            if emit_output:
                self.output_writer(f"[tool:{status}] {tool_name}\n{body}")

        try:
            self.messages = self._run_agent_turn(
                model=self.model,
                tools=self.tools,
                messages=self.messages,
                cwd=self.cwd,
                permissions=self.permissions,
                context_manager=self.context_mgr,
                max_steps=self.max_tool_steps or 50,
                on_assistant_message=callbacks.on_assistant_message if callbacks else None,
                on_progress_message=_on_progress,
                on_tool_start=_on_tool_start,
                on_tool_result=_on_tool_result,
            )
        finally:
            self.permissions.end_turn()
        if self.context_mgr:
            stats = self.context_mgr.get_stats()
            self.logger.debug("After turn: %d tokens (%.0f%%)", stats.total_tokens, stats.usage_percentage)
        last_assistant = next((message for message in reversed(self.messages) if message["role"] == "assistant"), None)
        if last_assistant and not callbacks:
            append_transcript(self.transcript, kind="assistant", body=last_assistant["content"])
            if emit_output:
                self.output_writer(last_assistant["content"])
        return self.messages

    def run_permission_turn(self, fn: Callable[[], Any]) -> Any:
        """Run a custom runtime operation inside one permission turn."""
        self.permissions.begin_turn()
        try:
            return fn()
        finally:
            self.permissions.end_turn()

    def begin_permission_turn(self) -> None:
        """Begin a custom runtime turn that is orchestrated outside agent_loop."""
        self.permissions.begin_turn()

    def end_permission_turn(self) -> None:
        """End a custom runtime turn that is orchestrated outside agent_loop."""
        self.permissions.end_turn()
