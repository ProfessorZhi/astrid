from astrid.tty_app import (
    TtyAppArgs,
    ScreenState,
    _is_multi_agent_candidate,
    _apply_tool_result_visual_state,
    _build_agent_prompt_region,
    _busy_animation_interval,
    _idle_poll_interval,
    _render_throttle_interval,
    _build_screen_simple,
    _handle_normal_mode_wheel,
    _handle_normal_mode_key,
    _render_agent_frame_update,
    _should_record_progress_entries,
    _should_skip_agent_frame_update,
    _should_start_windows_wheel_fallback,
    _win_build_input_mode,
    _win_translate_console_mouse_event,
    _format_history,
    _handle_input,
    _handle_companion_command,
    _drain_next_queued_turn,
    _render_queued_turn_preview,
    _render_welcome_pet_block,
    _render_screen_simple,
    _get_renderable_transcript_entries,
    _mark_unfinished_tools,
    _save_transcript,
    _win_build_mouse_fallback_title,
    _win_call_next_hook_ex,
    _win_drain_mouse_fallback_events,
    _win_titles_match,
    summarize_tool_input,
    summarize_tool_output,
)
from astrid.tui.buddy_state import build_buddy_profile
from astrid.tui.input_parser import KeyEvent
from astrid.mock_model import MockModelAdapter
from astrid.permissions import PermissionManager
from astrid.prompt import build_system_prompt
from astrid.tools import create_default_tool_registry
from astrid.tui.chrome import strip_ansi
from astrid.tui.transcript import format_transcript_text
from astrid.tui.types import TranscriptEntry
from astrid.tui.input_parser import WheelEvent, parse_input_chunk
from io import StringIO
from pathlib import Path
import queue
import time

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def _clear_codex_terminal_env(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_SHELL", raising=False)
    monkeypatch.delenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", raising=False)


def test_summarize_tool_output_prefers_first_meaningful_line() -> None:
    output = "\n\nFILE: README.md\nOFFSET: 0\nEND: 100"
    assert summarize_tool_output("read_file", output).startswith("FILE: README.md")


def test_summarize_tool_output_truncates_long_lines() -> None:
    output = "x" * 400
    summary = summarize_tool_output("run_command", output)
    assert len(summary) < 200
    assert summary.endswith("...")


def test_win_translate_console_mouse_event_maps_wheel_directions() -> None:
    assert _win_translate_console_mouse_event(0x0004, 0x00780000) == WheelEvent(direction="up")
    assert _win_translate_console_mouse_event(0x0004, 0xFF880000) == WheelEvent(direction="down")
    assert _win_translate_console_mouse_event(0x0001, 0x00000000) is None


def test_win_build_input_mode_preserves_quick_edit_when_mouse_capture_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "tui")
    monkeypatch.delenv("ASTRID_ENABLE_MOUSE", raising=False)

    mode = _win_build_input_mode(0x0040)

    assert (mode & 0x0010) == 0
    assert mode & 0x0080
    assert mode & 0x0200
    assert mode & 0x0040


def test_win_build_input_mode_enables_mouse_and_disables_quick_edit_when_requested(monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "tui")
    monkeypatch.setenv("ASTRID_ENABLE_MOUSE", "1")

    mode = _win_build_input_mode(0x0040)

    assert mode & 0x0010
    assert mode & 0x0080
    assert mode & 0x0200
    assert (mode & 0x0040) == 0


def test_win_build_mouse_fallback_title_adds_unique_marker() -> None:
    title = _win_build_mouse_fallback_title("PowerShell", pid=4321)

    assert title == "PowerShell [astrid-wheel:4321]"


def test_win_titles_match_accepts_wrapped_foreground_title() -> None:
    assert _win_titles_match(
        "PowerShell [astrid-wheel:4321]",
        "Windows Terminal - PowerShell [astrid-wheel:4321]",
    )
    assert not _win_titles_match(
        "PowerShell [astrid-wheel:4321]",
        "Windows Terminal - Other tab",
    )


def test_win_titles_match_accepts_different_base_titles_with_same_marker() -> None:
    assert _win_titles_match(
        "PowerShell [astrid-wheel:4321]",
        "Astrid Tui Verify [astrid-wheel:4321]",
    )


def test_win_drain_mouse_fallback_events_returns_pending_wheels() -> None:
    pending: queue.SimpleQueue[WheelEvent] = queue.SimpleQueue()
    pending.put(WheelEvent(direction="up"))
    pending.put(WheelEvent(direction="down"))

    assert _win_drain_mouse_fallback_events(pending) == [
        WheelEvent(direction="up"),
        WheelEvent(direction="down"),
    ]
    assert _win_drain_mouse_fallback_events(pending) == []


def test_shell_mode_skips_windows_mouse_fallback(monkeypatch) -> None:
    monkeypatch.setattr("astrid.tty_app.sys.platform", "win32")
    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "shell")

    from astrid.tty_app import _maybe_start_windows_mouse_wheel_fallback

    assert _maybe_start_windows_mouse_wheel_fallback() is None


def test_win_call_next_hook_ex_passes_pointer_sized_lparam() -> None:
    captured: dict[str, object] = {}

    class _FakeUser32:
        def CallNextHookEx(self, hook, n_code, w_param, l_param):
            captured["args"] = (hook, n_code, w_param, l_param)
            return 123

    result = _win_call_next_hook_ex(_FakeUser32(), 1, 2, 2**40)

    assert result == 123
    assert captured["args"] == (None, 1, 2, 2**40)


def test_parse_input_chunk_maps_ctrl_v_to_key_event() -> None:
    parsed = parse_input_chunk("\x16")

    assert parsed.events == [KeyEvent(name="v", ctrl=True, meta=False)]


def test_handle_normal_mode_key_pastes_clipboard_text(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[], input="hello ", cursor_offset=6)
    rerenders: list[str] = []

    monkeypatch.setattr("astrid.tty_app._read_clipboard_text", lambda: "world")

    handled = _handle_normal_mode_key(
        args,
        state,
        KeyEvent(name="v", ctrl=True, meta=False),
        [],
        lambda: rerenders.append("render"),
    )

    assert handled is True
    assert state.input == "hello world"
    assert state.cursor_offset == len("hello world")
    assert rerenders == ["render"]


def test_render_agent_frame_update_only_rewrites_prompt_region() -> None:
    transcript = [
        TranscriptEntry(id=1, kind="user", body="hello"),
        TranscriptEntry(id=2, kind="assistant", body="world"),
    ]

    first, first_ids, first_prompt_lines = _render_agent_frame_update(
        transcript,
        (),
        "astrid> hi",
        previous_prompt_line_count=0,
    )
    second, second_ids, second_prompt_lines = _render_agent_frame_update(
        transcript,
        first_ids,
        "astrid> hi there",
        previous_prompt_line_count=first_prompt_lines,
    )

    assert "hello" in first
    assert "world" in first
    assert first.endswith("astrid> hi")
    assert second.startswith("\r\x1b[J")
    assert "hello" not in second
    assert "world" not in second
    assert second.endswith("astrid> hi there")
    assert second_ids == first_ids
    assert second_prompt_lines == 1


def test_render_agent_frame_update_appends_only_new_transcript_entries() -> None:
    initial = [
        TranscriptEntry(id=1, kind="user", body="hello"),
        TranscriptEntry(id=2, kind="assistant", body="world"),
    ]
    expanded = initial + [
        TranscriptEntry(id=3, kind="user", body="next"),
        TranscriptEntry(id=4, kind="assistant", body="reply"),
    ]

    _, rendered_ids, prompt_lines = _render_agent_frame_update(
        initial,
        (),
        "astrid> ",
        previous_prompt_line_count=0,
    )
    rendered, next_ids, next_prompt_lines = _render_agent_frame_update(
        expanded,
        rendered_ids,
        "astrid> ",
        previous_prompt_line_count=prompt_lines,
    )

    assert rendered.startswith("\r\x1b[J")
    assert "hello" not in rendered
    assert "world" not in rendered
    assert "next" in rendered
    assert "reply" in rendered
    assert rendered.endswith("astrid> ")
    assert next_ids == (1, 2, 3, 4)
    assert next_prompt_lines == 1


def test_render_agent_frame_update_rewrites_full_bottom_region() -> None:
    transcript = [TranscriptEntry(id=1, kind="assistant", body="ready")]

    first, first_ids, first_prompt_lines = _render_agent_frame_update(
        transcript,
        (),
        "astrid> /\n/help\nstatus: waiting",
        previous_prompt_line_count=0,
    )
    second, second_ids, second_prompt_lines = _render_agent_frame_update(
        transcript,
        first_ids,
        "astrid> hi",
        previous_prompt_line_count=first_prompt_lines,
    )

    assert first.endswith("astrid> /\n/help\nstatus: waiting")
    assert first_prompt_lines == 3
    assert second.startswith("\r\x1b[2A\x1b[J")
    assert "/help" not in second
    assert "status: waiting" not in second
    assert second.endswith("astrid> hi")
    assert second_ids == first_ids
    assert second_prompt_lines == 1


def test_build_agent_prompt_region_includes_footer_status() -> None:
    state = ScreenState(history=[], input="/", cursor_offset=1, status="Running /help...")

    rendered = strip_ansi(_build_agent_prompt_region(state))

    assert "astrid>" in rendered
    assert "/help" in rendered
    assert "Running /help..." in rendered


def test_build_agent_prompt_region_includes_busy_spinner_line() -> None:
    state = ScreenState(
        history=[],
        input="",
        cursor_offset=0,
        is_busy=True,
        busy_verb="Inspecting",
        current_action_summary="Scanning files",
        animation_frame=1,
    )

    rendered = strip_ansi(_build_agent_prompt_region(state))

    assert "Inspecting..." in rendered
    assert "Scanning files" in rendered
    assert "progress" not in rendered


def test_agent_mode_keeps_windows_wheel_fallback_enabled() -> None:
    assert _should_start_windows_wheel_fallback("agent") is True
    assert _should_start_windows_wheel_fallback("tui") is True
    assert _should_start_windows_wheel_fallback("shell") is False


def test_agent_mode_reuses_tui_animation_and_polling() -> None:
    assert _busy_animation_interval("agent") == 0.25
    assert _busy_animation_interval("tui") == 0.25
    assert _idle_poll_interval("agent") == 0.05
    assert _idle_poll_interval("tui") == 0.05
    assert _render_throttle_interval("agent") == 0.016
    assert _render_throttle_interval("tui") == 0.016


def test_shell_mode_disables_periodic_animation_repaints() -> None:
    assert _busy_animation_interval("shell") is None
    assert _idle_poll_interval("shell") >= 0.1
    assert _render_throttle_interval("shell") >= 0.05


def test_codex_terminal_uses_shell_mode_for_tty_loop(monkeypatch) -> None:
    from astrid.tty_app import _terminal_mode_label
    from astrid.tui.screen import _terminal_mode

    monkeypatch.setenv("CODEX_SHELL", "1")
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)

    assert _terminal_mode() == "shell"
    assert _terminal_mode_label() == "shell mode"
    assert _busy_animation_interval(_terminal_mode()) is None
    assert _render_throttle_interval(_terminal_mode()) >= 0.05


def test_terminal_mode_label_treats_agent_as_tui_for_users(monkeypatch) -> None:
    from astrid.tty_app import _terminal_mode_label

    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "agent")

    assert _terminal_mode_label() == "tui mode"


def test_should_skip_agent_frame_update_only_when_visible_state_matches() -> None:
    assert _should_skip_agent_frame_update((1, 2), (1, 2), "astrid> hi", "astrid> hi") is True
    assert _should_skip_agent_frame_update((1, 2, 3), (1, 2), "astrid> hi", "astrid> hi") is False
    assert _should_skip_agent_frame_update((1, 2), (1, 2), "astrid> hi there", "astrid> hi") is False


def test_build_screen_simple_keeps_prompt_visible_while_scrolling_transcript(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[
            TranscriptEntry(id=1, kind="assistant", body="\n".join(f"line {i}" for i in range(30)))
        ],
        input="hello",
        cursor_offset=5,
    )
    state.transcript_scroll_offset = 0

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 10))

    rendered = strip_ansi(_build_screen_simple(args, state))

    assert "line 29" in rendered
    assert "line 23" in rendered
    assert "astrid>" in rendered
    assert "hello" in rendered


def test_build_screen_simple_keeps_prompt_in_document_flow_when_not_scrolled(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[
            TranscriptEntry(id=1, kind="assistant", body="\n".join(f"line {i}" for i in range(30)))
        ],
        input="hello",
        cursor_offset=5,
        status="Running",
    )
    state.transcript_scroll_offset = 0

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 12))

    rendered = strip_ansi(_build_screen_simple(args, state))
    lines = rendered.splitlines()
    assert lines[-3].startswith(" astrid>")
    assert lines[-1] == " Running"


def test_build_screen_simple_without_footer_keeps_prompt_after_content(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[
            TranscriptEntry(id=1, kind="assistant", body="\n".join(f"line {i}" for i in range(30)))
        ],
        input="hello",
        cursor_offset=5,
    )
    state.transcript_scroll_offset = 0

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 12))

    rendered = strip_ansi(_build_screen_simple(args, state))
    lines = rendered.splitlines()

    assert lines[-1].startswith(" astrid>")


def test_build_screen_simple_does_not_pad_short_transcript_to_terminal_height(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[TranscriptEntry(id=1, kind="assistant", body="short reply")],
        input="hello",
        cursor_offset=5,
    )

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 16))

    rendered = strip_ansi(_build_screen_simple(args, state))
    lines = rendered.splitlines()

    assert len(lines) < 16
    assert lines[-1].startswith(" astrid>")


def test_build_screen_simple_scrolls_prompt_out_of_view_with_document(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[
            TranscriptEntry(id=1, kind="assistant", body="\n".join(f"line {i}" for i in range(40)))
        ],
        input="hello",
        cursor_offset=5,
        status="Running",
    )
    state.transcript_scroll_offset = 10

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 16))

    rendered = strip_ansi(_build_screen_simple(args, state))
    lines = rendered.splitlines()

    assert len(lines) == 16
    assert all(not line.startswith("astrid>") for line in lines)
    assert "Running" not in lines


def test_build_screen_simple_no_longer_renders_dedicated_bottom_region_separator(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[TranscriptEntry(id=1, kind="assistant", body="\n".join(f"line {i}" for i in range(20)))],
        input="hello",
        cursor_offset=5,
        status="Running",
    )
    state.transcript_scroll_offset = 0

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 16))

    rendered = strip_ansi(_build_screen_simple(args, state))
    lines = rendered.splitlines()
    assert all(set(line) != {"-"} for line in lines if line)


def test_inline_mode_does_not_record_progress_entries() -> None:
    assert _should_record_progress_entries("agent") is False
    assert _should_record_progress_entries("tui") is False
    assert _should_record_progress_entries("shell") is False


def test_handle_normal_mode_wheel_scrolls_agent_mode_both_directions(monkeypatch) -> None:
    from astrid.tty_app import _handle_normal_mode_wheel

    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[
            TranscriptEntry(id=1, kind="assistant", body="\n".join(f"line {i}" for i in range(24)))
        ],
    )
    rerenders: list[str] = []
    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "agent")
    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 8))

    handled_up = _handle_normal_mode_wheel(args, state, WheelEvent(direction="up"), lambda: rerenders.append("up"))
    assert handled_up is True
    assert state.transcript_scroll_offset > 0

    handled_down = _handle_normal_mode_wheel(args, state, WheelEvent(direction="down"), lambda: rerenders.append("down"))
    assert handled_down is True
    assert state.transcript_scroll_offset == 0
    assert rerenders == ["up", "down"]


def test_format_history_shows_recent_entries_with_numbers() -> None:
    rendered = _format_history(["/help", "build parser", "/cmd pytest -q"], limit=2)
    assert rendered == "2. build parser\n3. /cmd pytest -q"


def test_save_transcript_writes_plain_text(tmp_path) -> None:
    state_entries = [
        TranscriptEntry(id=1, kind="user", body="hello"),
        TranscriptEntry(id=2, kind="assistant", body="world"),
    ]
    permissions = PermissionManager(str(tmp_path), prompt=lambda request: {"decision": "allow_once"})

    path = _save_transcript(
        type("State", (), {"transcript": state_entries})(),
        str(tmp_path),
        permissions,
        "logs/session.txt",
    )

    assert path.endswith("logs\\session.txt") or path.endswith("logs/session.txt")
    assert (tmp_path / "logs" / "session.txt").read_text(encoding="utf-8") == "you\n  hello\n\n---\n\nassistant\n  world"


def test_format_transcript_text_uses_clean_separator() -> None:
    rendered = format_transcript_text(
        [
            TranscriptEntry(id=1, kind="user", body="one"),
            TranscriptEntry(id=2, kind="assistant", body="two"),
        ]
    )

    assert "\n\n---\n\n" in rendered


def test_summarize_tool_input_formats_patch_file() -> None:
    summary = summarize_tool_input(
        "patch_file",
        {"path": "demo.txt", "replacements": [{"search": "a", "replace": "b"}, {"search": "c", "replace": "d"}]},
    )

    assert summary == "patch_file path=demo.txt replacements=2"


def test_mark_unfinished_tools_marks_running_entries_as_errors() -> None:
    state = type(
        "State",
        (),
        {
            "transcript": [TranscriptEntry(id=1, kind="tool", body="running", toolName="run_command", status="running")],
            "recent_tools": [],
            "pending_tool_runs": {"run_command": [{"entry": "placeholder"}]},
            "active_tool": "run_command",
        },
    )()

    count = _mark_unfinished_tools(state)

    assert count == 1
    assert state.transcript[0].status == "error"
    assert "did not report a final result" in state.transcript[0].body
    assert state.recent_tools == [{"name": "run_command", "status": "error"}]
    assert state.pending_tool_runs == {}
    assert state.active_tool is None


def test_error_tool_entry_stays_expanded_for_visibility() -> None:
    entry = TranscriptEntry(id=1, kind="tool", body="boom", toolName="run_command", status="running")
    _apply_tool_result_visual_state(entry, "run_command", "boom", is_error=True)

    assert entry.status == "error"
    assert entry.collapsed is False
    assert entry.collapsedSummary is None


def test_success_tool_entry_collapses_to_summary() -> None:
    entry = TranscriptEntry(id=1, kind="tool", body="running", toolName="read_file", status="running")
    _apply_tool_result_visual_state(entry, "read_file", "FILE: README.md\nhello", is_error=False)

    assert entry.status == "success"
    assert entry.collapsed is True
    assert entry.collapsedSummary == "FILE: README.md"
    assert entry.collapsePhase == 3


def test_handle_input_runs_multi_agent_flow_and_records_summary() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                },
            ),
        }
    ]
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=messages,
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(
        args,
        state,
        lambda: None,
        submitted_raw_input="Please do a multi-agent review and implementation pass for Astrid TUI, split search and implementation, then review the result.",
    )

    assert should_exit is False

    for _ in range(200):
        result = state.agent_result or {}
        if result.get("done"):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("multi-agent background run did not finish")

    assert state.orchestration is not None
    assert state.orchestration.task_state.value == "done"
    assert len(state.orchestration.workers) == 3
    assert [worker.name for worker in state.orchestration.workers.values()] == ["Russell", "Knuth", "Hegel"]
    assert any(entry.kind == "orchestration" for entry in state.transcript)
    assert any(
        entry.kind == "assistant" and entry.body.startswith("Multi-agent summary")
        for entry in state.transcript
    )


def test_handle_input_multi_agent_can_finish_natural_language_workspace_task(tmp_path: Path) -> None:
    cwd = str(tmp_path)
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                },
            ),
        }
    ]
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=messages,
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(
        args,
        state,
        lambda: None,
        submitted_raw_input="Please use multi-agent to create hello.txt with hello world in it.",
    )

    assert should_exit is False

    for _ in range(200):
        result = state.agent_result or {}
        if result.get("done"):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("multi-agent background run did not finish")

    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "hello world"
    assert state.orchestration is not None
    assert state.orchestration.task_state.value == "done"


def test_handle_input_refreshes_system_prompt_with_new_skill(tmp_path: Path) -> None:
    cwd = str(tmp_path)
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                },
            ),
        }
    ]
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=messages,
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    skill_file = tmp_path / ".astrid" / "skills" / "late" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("# Late\n\nLive prompt skill\n", encoding="utf-8")

    should_exit = _handle_input(
        args,
        state,
        lambda: None,
        submitted_raw_input="hello",
    )

    assert should_exit is False
    assert "late: Live prompt skill" in args.messages[0]["content"]

    for _ in range(200):
        result = state.agent_result or {}
        if result.get("done"):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("single-agent background run did not finish")


def test_handle_input_queues_next_turn_while_busy(tmp_path: Path) -> None:
    cwd = str(tmp_path)
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[], is_busy=True)

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="next task")

    assert should_exit is False
    assert state.queued_inputs == ["next task"]
    assert state.status == "Queued next turn (1)"


def test_drain_next_queued_turn_starts_follow_up_turn(tmp_path: Path) -> None:
    cwd = str(tmp_path)
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                },
            ),
        }
    ]
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=messages,
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[], queued_inputs=["write a quick summary"])

    handled = _drain_next_queued_turn(args, state, lambda: None)

    assert handled is True
    assert state.queued_inputs == []
    assert any(entry.kind == "user" and entry.body == "write a quick summary" for entry in state.transcript)
    assert state.agent_result is not None


def test_render_queued_turn_preview_shows_count_suffix() -> None:
    state = ScreenState(queued_inputs=["first queued", "second queued"])

    rendered = strip_ansi(_render_queued_turn_preview(state))

    assert "next turn:" in rendered
    assert "first queued" in rendered
    assert "(+1)" in rendered


def test_handle_input_pet_next_cycles_species_and_renders_preview() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet next")

    assert should_exit is False
    assert state.companion_species == "goose"
    assert state.companion_enabled is True
    assert state.transcript[-1].kind == "assistant"
    assert "goose buddy" in state.transcript[-1].body


def test_handle_input_pet_switch_sets_requested_species() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet switch robot")

    assert should_exit is False
    assert state.companion_species == "robot"
    assert state.companion_enabled is True
    assert "robot buddy" in state.transcript[-1].body


def test_buddy_profile_can_follow_selected_species() -> None:
    profile = build_buddy_profile("demo-seed", species_override="goose")
    assert profile.bones.species == "goose"


def test_render_welcome_pet_block_uses_solid_builtin_pet_for_builtin_species() -> None:
    state = ScreenState(history=[])
    profile = build_buddy_profile("demo-seed", species_override="duck")

    block = _render_welcome_pet_block(state, profile)

    assert "\u2588" in block
    assert "<(o )___" not in block
    assert "Duck" in block


def test_render_welcome_pet_block_ignores_busy_animation_frame() -> None:
    state = ScreenState(history=[])
    profile = build_buddy_profile("demo-seed", species_override="duck")

    state.animation_frame = 0
    first = _render_welcome_pet_block(state, profile)
    state.animation_frame = 1
    second = _render_welcome_pet_block(state, profile)

    assert first == second


def test_handle_input_pet_switch_unknown_species_reports_error() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet switch unknown")

    assert should_exit is False
    assert state.transcript[-1].kind == "assistant"
    assert "Unknown buddy 'unknown'" in state.transcript[-1].body


def test_handle_input_pet_hide_and_show_toggle_welcome_buddy() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet hide")

    assert should_exit is False
    assert state.companion_enabled is False
    assert "Buddy hidden" in state.transcript[-1].body

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet show")

    assert should_exit is False
    assert state.companion_enabled is True
    assert "Duck" in state.transcript[-1].body


def test_handle_input_pet_pet_triggers_buddy_reaction() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet pet")

    assert should_exit is False
    assert state.buddy_runtime.reaction_text == "Much appreciated"
    assert state.buddy_runtime.pet_until > 0
    assert "hearts" in state.transcript[-1].body


def test_handle_input_pet_profile_shows_current_buddy_traits() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet profile")

    assert should_exit is False
    body = state.transcript[-1].body
    assert "name:" in body
    assert "species:" in body
    assert "rarity:" in body
    assert "hat:" in body


def test_handle_input_pet_import_loads_local_image_as_custom_pet(tmp_path: Path) -> None:
    cwd = str(tmp_path.resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    image_path = tmp_path / "pet.png"
    Image.new("RGBA", (8, 8), (255, 120, 80, 255)).save(image_path)
    state = ScreenState(history=[])

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input=f"/pet import {image_path}")

    assert should_exit is False
    assert state.imported_pet_name == "pet"
    assert state.imported_pet_ansi
    assert state.imported_pet_ascii
    assert state.imported_pet_active is False
    assert "imported pet" in state.transcript[-1].body
    assert "save" in state.transcript[-1].body.lower()


def test_handle_input_pet_mode_switches_render_mode() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet mode ascii")

    assert should_exit is False
    assert state.imported_pet_mode == "ascii"
    assert "ascii" in state.transcript[-1].body


def test_handle_companion_command_import_keeps_pet_as_non_persisted_draft(monkeypatch, tmp_path: Path) -> None:
    saved: dict[str, object] = {}
    monkeypatch.setattr("astrid.tty_app.save_pet_settings", lambda payload: saved.update(payload))
    image_path = tmp_path / "pet.png"
    Image.new("RGBA", (8, 8), (40, 180, 255, 255)).save(image_path)
    state = ScreenState(history=[])

    result = _handle_companion_command(state, f"/pet import {image_path}")

    assert result is not None
    assert saved == {}
    assert "importedPetName" not in saved


def test_handle_companion_command_can_save_and_reuse_preset_pet(monkeypatch, tmp_path: Path) -> None:
    library: dict[str, dict[str, str]] = {}
    monkeypatch.setattr("astrid.tty_app._load_custom_pet_library", lambda: dict(library))
    monkeypatch.setattr("astrid.tty_app._save_custom_pet_library", lambda payload: library.clear() or library.update(payload))
    monkeypatch.setattr("astrid.tty_app.save_pet_settings", lambda payload: None)

    image_path = tmp_path / "asuna.png"
    Image.new("RGBA", (8, 8), (220, 120, 180, 255)).save(image_path)
    state = ScreenState(history=[])

    import_result = _handle_companion_command(state, f"/pet import {image_path}")
    save_result = _handle_companion_command(state, "/pet save asuna")

    assert import_result is not None
    assert "asuna" in save_result
    assert "asuna" in library

    state.imported_pet_name = None
    state.imported_pet_source = None
    state.imported_pet_ansi = None
    state.imported_pet_ascii = None

    use_result = _handle_companion_command(state, "/pet use asuna")

    assert use_result is not None
    assert state.imported_pet_name == "asuna"
    assert state.imported_pet_active is True
    assert "preset pet" in use_result


def test_handle_companion_command_can_remove_preset_pet(monkeypatch) -> None:
    library: dict[str, dict[str, str]] = {"asuna": {"source": "x", "ansi": "ansi", "ascii": "ascii"}}
    monkeypatch.setattr("astrid.tty_app._load_custom_pet_library", lambda: dict(library))
    monkeypatch.setattr("astrid.tty_app._save_custom_pet_library", lambda payload: library.clear() or library.update(payload))
    monkeypatch.setattr("astrid.tty_app.save_pet_settings", lambda payload: None)
    state = ScreenState(history=[])
    state.imported_pet_name = "asuna"
    state.imported_pet_ansi = "ansi"
    state.imported_pet_ascii = "ascii"
    state.imported_pet_active = True

    result = _handle_companion_command(state, "/pet remove asuna")

    assert "Removed preset pet" in result
    assert "asuna" not in library
    assert state.imported_pet_name is None
    assert state.imported_pet_active is False


def test_welcome_uses_builtin_buddy_when_import_is_only_a_draft(tmp_path: Path) -> None:
    image_path = tmp_path / "pet.png"
    Image.new("RGBA", (8, 8), (255, 120, 80, 255)).save(image_path)
    state = ScreenState(history=[])
    profile = build_buddy_profile("demo-seed", species_override="duck")

    _handle_companion_command(state, f"/pet import {image_path}")
    welcome = _render_welcome_pet_block(state, profile)

    assert "Duck" in welcome
    assert "imported pet" not in welcome


def test_welcome_uses_custom_pet_after_pet_use(monkeypatch) -> None:
    library: dict[str, dict[str, str]] = {"asuna": {"source": "x", "ansi": "ansi-sprite", "ascii": "ascii-sprite"}}
    monkeypatch.setattr("astrid.tty_app._load_custom_pet_library", lambda: dict(library))
    monkeypatch.setattr("astrid.tty_app.save_pet_settings", lambda payload: None)
    state = ScreenState(history=[])
    profile = build_buddy_profile("demo-seed", species_override="duck")

    _handle_companion_command(state, "/pet use asuna")
    welcome = _render_welcome_pet_block(state, profile)

    assert "asuna imported pet" in welcome


def test_render_screen_simple_shows_welcome_workbench_for_fresh_session(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])
    output = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = output.getvalue()
    assert "Welcome back" in rendered
    assert "tips" in rendered
    assert "recent" in rendered


def test_render_screen_simple_rotates_welcome_tips_with_animation_frame(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])
    output_a = StringIO()
    output_b = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))

    monkeypatch.setattr("astrid.tty_app.sys.stdout", output_a)
    state.welcome_tip_index = 0
    _render_screen_simple(args, state)

    monkeypatch.setattr("astrid.tty_app.sys.stdout", output_b)
    state.welcome_tip_index = 1
    _render_screen_simple(args, state)

    assert "Run /pet next to switch buddies" in output_a.getvalue()
    assert "Try a multi-agent prompt" in output_b.getvalue()


def test_render_screen_simple_welcome_uses_runtime_model_name(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime={"model": "claude-sonnet-4-20250514"},
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])
    output = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = output.getvalue()
    assert "claude-sonnet-4-20250514" in rendered


def test_render_screen_simple_welcome_shows_shell_mode_label(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])
    output = StringIO()

    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "shell")
    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = strip_ansi(output.getvalue())
    assert "welcome · shell mode" in rendered
    assert "Mode: shell. PowerShell keeps native scrollback." not in rendered


def test_render_screen_simple_welcome_shows_tui_mode_hint(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])
    output = StringIO()

    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = strip_ansi(output.getvalue())
    assert "welcome · tui mode" in rendered
    assert "Mode: tui. Astrid owns the screen and scroll." not in rendered


def test_handle_normal_mode_wheel_scrolls_welcome_view(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[TranscriptEntry(id=1, kind="welcome", body="\n".join(f"line {i}" for i in range(12)))],
    )
    rerenders: list[str] = []

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 8))
    monkeypatch.setattr(
        "astrid.tty_app._build_welcome_workbench",
        lambda *_args, **_kwargs: "\n".join(f"line {i}" for i in range(12)),
    )

    handled = _handle_normal_mode_wheel(
        args,
        state,
        WheelEvent(direction="up"),
        lambda: rerenders.append("render"),
    )

    assert handled is True
    assert state.transcript_scroll_offset > 0
    assert rerenders == ["render"]


def test_build_screen_simple_applies_welcome_scroll_offset(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])
    state.transcript_scroll_offset = 2

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (80, 8))
    monkeypatch.setattr(
        "astrid.tty_app._build_welcome_workbench",
        lambda *_args, **_kwargs: "\n".join(f"line {i}" for i in range(8)),
    )

    rendered = strip_ansi(_build_screen_simple(args, state))

    assert "line 0" not in rendered
    assert "line 7" in rendered
    assert "scroll 2/" in rendered
    assert "line 5" in rendered or "line 6" in rendered


def test_handle_input_keeps_single_welcome_entry_once_first_message_starts(monkeypatch, tmp_path: Path) -> None:
    cwd = str(tmp_path)
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                },
            ),
        }
    ]
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=messages,
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="hello")

    assert should_exit is False

    for _ in range(200):
        result = state.agent_result or {}
        if result.get("done"):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("single-agent background run did not finish")

    assert any(entry.kind == "user" and entry.body == "hello" for entry in state.transcript)
    welcome_entries = [entry for entry in state.transcript if entry.kind == "welcome"]
    assert len(welcome_entries) == 1


def test_handle_input_drops_progress_entries_after_final_answer(monkeypatch, tmp_path: Path) -> None:
    cwd = str(tmp_path)
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                },
            ),
        }
    ]
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=messages,
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    def _fake_run_agent_turn(**kwargs):
        kwargs["on_progress_message"]("Planning the next step")
        kwargs["on_assistant_message"]("Final answer")
        return kwargs["messages"] + [{"role": "assistant", "content": "Final answer"}]

    monkeypatch.setattr("astrid.tty_app.run_agent_turn", _fake_run_agent_turn)

    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="who are you")

    assert should_exit is False

    for _ in range(200):
        result = state.agent_result or {}
        if result.get("done"):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("single-agent background run did not finish")

    assert all(entry.kind != "progress" for entry in state.transcript)
    assert any(entry.kind == "assistant" and entry.body == "Final answer" for entry in state.transcript)


def test_render_screen_simple_keeps_compact_welcome_after_first_message(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=["hello"],
        transcript=[
            TranscriptEntry(id=1, kind="welcome", body="Welcome back\nTips for getting started"),
            TranscriptEntry(id=2, kind="user", body="hello"),
            TranscriptEntry(id=3, kind="assistant", body="Hi there"),
        ],
    )
    output = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = strip_ansi(output.getvalue())
    assert "Welcome back" in rendered
    assert "tips" in rendered
    assert "hello" in rendered
    assert "Hi there" in rendered


def test_get_renderable_transcript_entries_dedupes_multiple_welcome_entries() -> None:
    state = ScreenState(
        transcript=[
            TranscriptEntry(id=1, kind="welcome", body="welcome a"),
            TranscriptEntry(id=2, kind="welcome", body="welcome b"),
        ]
    )

    rendered = _get_renderable_transcript_entries(state)

    assert rendered == []
    assert len([entry for entry in state.transcript if entry.kind == "welcome"]) == 1
    assert state.transcript[0].body == "welcome a"


def test_render_screen_simple_hides_completed_progress_history(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=["你是谁"],
        transcript=[
            TranscriptEntry(id=1, kind="user", body="你是谁"),
            TranscriptEntry(
                id=2,
                kind="progress",
                body="Planning the next step",
                phaseVerb="Transfiguring",
                actionSummary="Planning the next step",
            ),
            TranscriptEntry(id=3, kind="assistant", body="我是 Astrid"),
        ],
    )
    output = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = strip_ansi(output.getvalue())
    assert "Planning the next step" not in rendered
    assert "我是 Astrid" in rendered


def test_startup_randomizes_builtin_welcome_pet(monkeypatch) -> None:
    monkeypatch.setattr("astrid.tty_app.load_pet_settings", lambda: {"companionEnabled": True})
    monkeypatch.setattr("astrid.tty_app.random.choice", lambda species: "robot")

    state = ScreenState(history=[])
    from astrid.tty_app import _apply_startup_pet_state

    _apply_startup_pet_state(state)

    assert state.companion_species == "robot"
    assert state.imported_pet_active is False


def test_startup_keeps_active_imported_pet_instead_of_randomizing(monkeypatch) -> None:
    monkeypatch.setattr(
        "astrid.tty_app.load_pet_settings",
        lambda: {
            "companionEnabled": True,
            "companionSpecies": "duck",
            "importedPetName": "asuna",
            "importedPetSource": "x",
            "importedPetAnsi": "ansi-sprite",
            "importedPetAscii": "ascii-sprite",
            "importedPetMode": "ansi",
            "importedPetActive": True,
        },
    )
    monkeypatch.setattr("astrid.tty_app.random.choice", lambda species: "robot")

    state = ScreenState(history=[])
    from astrid.tty_app import _apply_startup_pet_state

    _apply_startup_pet_state(state)

    assert state.companion_species == "duck"
    assert state.imported_pet_active is True
    assert state.imported_pet_name == "asuna"


def test_multi_agent_candidate_requires_explicit_coordination_signal() -> None:
    assert (
        _is_multi_agent_candidate(
            "https://github.com/Textualize/textual 把这个仓库clone到 F:\\funnyskills\\fromgithub"
        )
        is False
    )
    assert (
        _is_multi_agent_candidate(
            "请执行 git status --short 然后把结果告诉我"
        )
        is False
    )
    assert (
        _is_multi_agent_candidate(
            "Please do a multi-agent review and implementation pass, split search and implementation, then review the result."
        )
        is True
    )


def test_render_screen_simple_shows_buddy_overlay_in_active_view(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[TranscriptEntry(id=1, kind="user", body="hello")],
    )
    state.buddy_runtime.reaction_text = "Need your approval"
    state.buddy_runtime.reaction_until = 9999999999.0
    output = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = output.getvalue()
    assert "Need your approval" in rendered
    assert "says:" in rendered


def test_render_screen_simple_shows_busy_thinking_line_for_single_agent_turn(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[TranscriptEntry(id=1, kind="user", body="你好")],
        is_busy=True,
        current_action_summary="run_command git status --short",
    )
    output = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = strip_ansi(output.getvalue())
    assert "你好" in rendered
    assert "Transfiguring..." in rendered
    assert "run_command git status --short" in rendered
    assert "[=>" not in rendered


def test_render_screen_simple_keeps_busy_line_visible_when_progress_is_visible(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[
            TranscriptEntry(id=1, kind="user", body="你好"),
            TranscriptEntry(
                id=2,
                kind="progress",
                body="Planning the next step",
                phaseVerb="Transfiguring",
                actionSummary="Planning the next step",
            ),
        ],
        is_busy=True,
        busy_verb="Transfiguring",
        current_action_summary="Planning the next step",
    )
    output = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = strip_ansi(output.getvalue())
    assert rendered.count("Planning the next step") == 1
    assert "progress" not in rendered
    assert "Transfiguring..." in rendered
    assert "[=>" not in rendered


def test_render_screen_simple_animates_busy_thinking_line_frames(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[TranscriptEntry(id=1, kind="user", body="hello")],
        is_busy=True,
    )
    output_a = StringIO()
    output_b = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))

    monkeypatch.setattr("astrid.tty_app.sys.stdout", output_a)
    state.animation_frame = 0
    _render_screen_simple(args, state)

    monkeypatch.setattr("astrid.tty_app.sys.stdout", output_b)
    state.animation_frame = 1
    _render_screen_simple(args, state)

    rendered_a = strip_ansi(output_a.getvalue())
    rendered_b = strip_ansi(output_b.getvalue())
    assert "Transfiguring..." in rendered_a
    assert "Transfiguring..." in rendered_b
    assert rendered_a != rendered_b


def test_render_screen_simple_uses_full_clear_and_no_duplicate_busy_footer(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        transcript=[TranscriptEntry(id=1, kind="user", body="hello")],
        is_busy=True,
        status="Running write_file...",
    )
    output_a = StringIO()
    output_b = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))

    monkeypatch.setattr("astrid.tty_app.sys.stdout", output_a)
    state.animation_frame = 0
    _render_screen_simple(args, state)

    monkeypatch.setattr("astrid.tty_app.sys.stdout", output_b)
    state.animation_frame = 1
    _render_screen_simple(args, state)

    raw_rendered_a = output_a.getvalue()
    rendered_a = strip_ansi(raw_rendered_a)
    rendered_b = strip_ansi(output_b.getvalue())
    assert raw_rendered_a.startswith("\x1b[2J\x1b[H")
    assert rendered_a.count("Running write_file...") == 1
    assert rendered_a != rendered_b


def test_render_screen_simple_shows_busy_layout_without_transcript(monkeypatch) -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=[],
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(
        history=[],
        is_busy=True,
        status="Inspecting workspace...",
        current_action_summary="walking project files",
    )
    output = StringIO()

    monkeypatch.setattr("astrid.tty_app._get_terminal_size", lambda: (100, 40))
    monkeypatch.setattr("astrid.tty_app.sys.stdout", output)

    _render_screen_simple(args, state)

    rendered = strip_ansi(output.getvalue())
    assert "Transfiguring..." in rendered or "Inspecting" in rendered
    assert "walking project files" in rendered
    assert "msg or /help" in rendered


def test_multi_agent_flow_updates_buddy_runtime_reaction() -> None:
    cwd = str(Path(".").resolve())
    permissions = PermissionManager(cwd, prompt=lambda request: {"decision": "allow_once"})
    tools = create_default_tool_registry(cwd, runtime=None)
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                },
            ),
        }
    ]
    args = TtyAppArgs(
        runtime=None,
        tools=tools,
        model=MockModelAdapter(),
        messages=messages,
        cwd=cwd,
        permissions=permissions,
    )
    state = ScreenState(history=[])

    should_exit = _handle_input(
        args,
        state,
        lambda: None,
        submitted_raw_input="Please do a multi-agent review and implementation pass for Astrid TUI, split search and implementation, then review the result.",
    )

    assert should_exit is False
    assert state.buddy_runtime.reaction_text in {
        "Crew assembling",
        "Russell is on it",
        "Double-checking the patch",
        "Stitching the results together",
        "Review complete",
    }


def test_tty_app_keeps_single_welcome_render_definition_set() -> None:
    source = Path("astrid/tty_app.py").read_text(encoding="utf-8")

    assert source.count("def _build_welcome_workbench(") == 1
    assert source.count("def _render_screen(") == 1
    assert source.count("def _render_screen_simple(") == 1
    assert "_legacy_duplicate" not in source
