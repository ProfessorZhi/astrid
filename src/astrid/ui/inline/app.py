from __future__ import annotations

from collections.abc import Callable
import subprocess
import sys

from astrid.ui.common.frontend import FrontendRuntime
from astrid.ui.common.text_input import normalize_cli_input
from astrid.ui.common.welcome import render_startup_welcome
from astrid.ui.inline.bottom_pane import InlineInputBuffer
from astrid.ui.inline.rendering import (
    render_assistant_message,
    render_permission_panel,
    render_paste_preview,
    render_mode_line,
    render_prompt,
    render_status_line,
    render_tool_result,
    render_tool_start,
    render_warning_line,
)
from astrid.runtime.controller import RuntimeTurnCallbacks, append_transcript


def render_inline_intro(runtime: FrontendRuntime) -> str:
    summary = runtime.controller.permissions.get_summary()
    mode = next((line for line in summary if line.startswith("permission mode:")), "permission mode: default")
    warning = ""
    if "bypassPermissions" in mode:
        warning = "\n" + render_warning_line("WARNING: bypassPermissions is high risk and bypasses Astrid policy prompts.")
    welcome = render_startup_welcome(cwd=runtime.cwd, controller=runtime.controller, mode="inline")
    return f"{welcome}\n{render_mode_line(mode, high_risk='bypassPermissions' in mode)}{warning}\n"


def render_inline_permission_prompt(request: dict) -> str:
    return render_permission_panel(request)


class InlineTuiFrontend:
    """Codex-style inline TUI MVP.

    This keeps transcript history in native terminal scrollback and delegates
    all turn execution to RuntimeController.
    """

    name = "inline"

    def __init__(
        self,
        *,
        input_reader: Callable[[str], str] | None = None,
        intro: str | None = None,
    ) -> None:
        self.input_reader = input_reader
        self.intro = intro

    def run(self, runtime: FrontendRuntime) -> list[dict[str, str]] | None:
        print(self.intro if self.intro is not None else render_inline_intro(runtime))
        read_input = self.input_reader or read_inline_input
        original_prompt = getattr(runtime.controller.permissions, "prompt", None)
        runtime.controller.permissions.prompt = self._make_permission_prompt(read_input)
        messages = runtime.controller.messages
        try:
            while True:
                try:
                    raw_input = read_input(render_prompt())
                except EOFError:
                    break
                user_input = normalize_cli_input(raw_input)
                if not user_input:
                    continue
                if "\n" in user_input:
                    line_count = user_input.count("\n") + 1
                    print(render_paste_preview(1, line_count - 1))
                next_messages = runtime.controller.handle_user_input(
                    user_input,
                    callbacks=self._make_turn_callbacks(runtime),
                )
                if next_messages is None:
                    break
                messages = next_messages
        finally:
            runtime.controller.permissions.prompt = original_prompt
        return messages

    def _make_permission_prompt(self, read_input: Callable[[str], str]) -> Callable[[dict], dict]:
        def _prompt(request: dict) -> dict:
            print(render_inline_permission_prompt(request))
            choices = request.get("choices", [])
            default = choices[0] if choices else {"decision": "allow_once"}
            try:
                answer = read_input("approval> ").strip()
            except EOFError:
                return {"decision": "deny_once"}
            if answer in {"", "\r", "\n"}:
                return {"decision": default.get("decision", "allow_once")}
            if answer == "\x1b":
                return {"decision": "deny_once"}
            for choice in choices:
                if answer == str(choice.get("key", "")):
                    return {"decision": choice.get("decision", "allow_once")}
            return {"decision": "deny_once"}

        return _prompt

    def _make_turn_callbacks(self, runtime: FrontendRuntime) -> RuntimeTurnCallbacks:
        progress_state = {"last": ""}

        def _rewrite_status(text: str) -> None:
            progress_state["last"] = text
            sys.stdout.write("\r\x1b[2K" + text)
            sys.stdout.flush()

        def _finish_status() -> None:
            if progress_state["last"]:
                sys.stdout.write("\r\x1b[2K")
                sys.stdout.flush()
                progress_state["last"] = ""

        def _assistant(content: str) -> None:
            _finish_status()
            append_transcript(runtime.transcript, kind="assistant", body=content)
            print(render_assistant_message(content))

        def _progress(content: str) -> None:
            append_transcript(runtime.transcript, kind="progress", body=content)
            _rewrite_status(render_status_line(content))

        def _tool_start(tool_name: str, input_data: dict) -> None:
            append_transcript(
                runtime.transcript,
                kind="tool",
                body=f"input: {input_data}",
                toolName=tool_name,
                status="running",
            )
            _rewrite_status(render_tool_start(tool_name))

        def _tool_result(tool_name: str, output: str, is_error: bool) -> None:
            _finish_status()
            status = "error" if is_error else "success"
            append_transcript(
                runtime.transcript,
                kind="tool",
                body=output,
                toolName=tool_name,
                status=status,
            )
            print(render_tool_result(tool_name, output, is_error))

        return RuntimeTurnCallbacks(
            on_assistant_message=_assistant,
            on_progress_message=_progress,
            on_tool_start=_tool_start,
            on_tool_result=_tool_result,
        )


def _read_clipboard_text() -> str:
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _redraw_prompt(prompt: str, buffer: InlineInputBuffer) -> None:
    sys.stdout.write("\r\x1b[2K" + prompt + buffer.display_text)
    sys.stdout.flush()


def _read_inline_input_windows(prompt: str) -> str:
    import msvcrt

    buffer = InlineInputBuffer()
    sys.stdout.write(prompt)
    sys.stdout.flush()
    while True:
        char = msvcrt.getwch()
        if char in {"\r", "\n"}:
            sys.stdout.write("\n")
            sys.stdout.flush()
            return buffer.submit()
        if char == "\x03":
            raise KeyboardInterrupt
        if char == "\x04":
            raise EOFError
        if char == "\x08":
            buffer.backspace()
            _redraw_prompt(prompt, buffer)
            continue
        if char == "\x16":
            pasted = _read_clipboard_text()
            if pasted:
                buffer.insert_paste(pasted)
                _redraw_prompt(prompt, buffer)
            continue
        if char in {"\x00", "\xe0"}:
            # Consume extended key code.
            if msvcrt.kbhit():
                msvcrt.getwch()
            continue
        buffer.insert_text(char)
        sys.stdout.write(char)
        sys.stdout.flush()


def read_inline_input(prompt: str) -> str:
    if sys.platform == "win32" and sys.stdin.isatty():
        return _read_inline_input_windows(prompt)
    return input(prompt)


def run_inline_tui_app(**kwargs):
    runtime = kwargs.get("frontend_runtime")
    if isinstance(runtime, FrontendRuntime):
        return InlineTuiFrontend().run(runtime)
    raise NotImplementedError("inline TUI is planned but not implemented yet")
