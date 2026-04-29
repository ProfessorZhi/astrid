"""Astrid TTY Application.

This module implements the full-screen terminal user interface for Astrid,
including:
- Real-time transcript rendering with tool output collapsing
- Interactive permission approval prompts
- Background agent thread management
- Keyboard event handling and command routing
- Session persistence and autosave
"""

from __future__ import annotations

import logging
import os
import queue
import random
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, TextIO

from astrid.agent_loop import run_agent_turn
from astrid.background_tasks import list_background_tasks
from astrid.cli_commands import (
    SLASH_COMMANDS,
    find_matching_slash_commands,
    try_handle_local_command,
)
from astrid.config import load_pet_settings, save_pet_settings
from astrid.cost_tracker import CostTracker
from astrid.history import load_history_entries, save_history_entries
from astrid.local_tool_shortcuts import parse_local_tool_shortcut
from astrid.orchestration import (
    OrchestratorState,
    TaskRuntimeState,
    WorkerRole,
    WorkerRuntimeState,
    archive_worker,
    create_runtime,
    get_phase_label,
    get_phase_verb,
    mark_review_required,
    mark_worker_reported,
    request_spawn,
    sample_spinner_verb,
)
from astrid.permissions import PermissionManager
from astrid.prompt import build_system_prompt
from astrid.sub_agents import AgentType, SubAgentManager
from astrid.session import (
    AutosaveManager,
    SessionData,
    create_new_session,
    format_session_list,
    format_session_resume,
    get_latest_session,
    list_sessions,
    load_session,
    save_session,
)
from astrid.state import AppState, Store, create_app_store, format_app_state_summary
from astrid.tooling import ToolContext, ToolRegistry
from astrid.tui.chrome import (
    _cached_terminal_size,
    get_permission_prompt_max_scroll_offset,
    render_banner,
    render_footer_bar,
    render_panel,
    render_permission_prompt,
    render_slash_menu,
    render_status_line,
    render_tool_panel,
    render_welcome_workbench,
    string_display_width,
    SUBTLE,
    RESET,
)
from astrid.tui.buddy import (
    BUDDY_SPECIES,
    cycle_buddy_species,
    normalize_buddy_species,
    render_buddy_block,
    render_buddy_overlay,
)
from astrid.tui.pet_import import import_pet_sprite
from astrid.tui.buddy_state import BuddyProfile, BuddyRuntimeState, build_buddy_profile
from astrid.tui.welcome_hero import render_welcome_hero_profile_block
from astrid.tui.input import render_input_prompt
from astrid.tui.input_parser import (
    KeyEvent,
    ParsedInputEvent,
    TextEvent,
    WheelEvent,
    parse_input_chunk,
)
from astrid.tui.screen import (
    clear_screen,
    enter_alternate_screen,
    exit_alternate_screen,
    hide_cursor,
    _should_capture_mouse,
    _should_use_alternate_screen,
    _terminal_mode,
    show_cursor,
)
from astrid.tui.theme import theme
from astrid.tui.transcript import (
    _SIMPLE_SEPARATOR_LINES,
    _render_transcript_lines,
    get_transcript_max_scroll_offset,
    get_transcript_window_size,
    render_transcript,
    render_transcript_simple,
    render_transcript_simple_windowed,
)
from astrid.tui.types import OrchestrationWorker, TranscriptEntry
from astrid.types import ChatMessage, ModelAdapter
from astrid.workspace import resolve_tool_path

# ---------------------------------------------------------------------------
# Terminal size 鈥?use unified cache from chrome module
# ---------------------------------------------------------------------------

# Alias to the single canonical implementation in chrome.py
_get_terminal_size = _cached_terminal_size


# ---------------------------------------------------------------------------
# Throttled renderer
# ---------------------------------------------------------------------------

class _ThrottledRenderer:
    """Coalesces rapid rerender() calls into at most one actual render per interval.

    THREAD SAFETY: The actual render function (_render_fn) is ONLY executed on
    the thread that calls ``flush()`` or ``force()``.  ``request()`` never
    invokes the render function directly 鈥?it only marks a pending flag.  This
    ensures that background threads (agent, collapse timer) can safely call
    ``request()`` without writing to stdout concurrently with the main UI
    thread.
    """

    __slots__ = ("_render_fn", "_min_interval", "_pending", "_last_render_time", "_lock")

    def __init__(self, render_fn: Callable[[], None], min_interval: float = 0.033) -> None:
        self._render_fn = render_fn
        self._min_interval = min_interval  # ~30 fps cap (sufficient for terminal UI)
        self._pending = False
        self._last_render_time: float = 0.0
        self._lock = threading.Lock()

    def request(self) -> None:
        """Mark that a rerender is needed.

        This method is safe to call from any thread.  It never invokes the
        render function 鈥?the actual render happens on the next ``flush()``
        call from the main event loop.
        """
        with self._lock:
            self._pending = True

    def flush(self) -> None:
        """Execute a pending render if the throttle interval has elapsed.

        Must be called from the main UI thread only.
        """
        now = time.monotonic()
        with self._lock:
            if not self._pending:
                return
            elapsed = now - self._last_render_time
            if elapsed < self._min_interval:
                return  # Still within throttle window 鈥?defer
            self._pending = False
            self._last_render_time = now
        self._render_fn()

    def force(self) -> None:
        """Unconditionally render now, ignoring throttle.

        Must be called from the main UI thread only.
        """
        with self._lock:
            self._pending = False
            self._last_render_time = time.monotonic()
        self._render_fn()


def _busy_animation_interval(terminal_mode: str) -> float | None:
    """Return the spinner cadence for the active terminal mode."""
    if terminal_mode == "shell":
        return None
    return 0.25


def _idle_poll_interval(terminal_mode: str) -> float:
    """Return the main-loop idle sleep interval for the active terminal mode."""
    if terminal_mode == "shell":
        return 0.1
    return 0.05


def _render_throttle_interval(terminal_mode: str) -> float:
    """Return the rerender throttle interval for the active terminal mode."""
    if terminal_mode == "shell":
        return 0.08
    return 0.016


def _should_skip_agent_frame_update(
    transcript_ids: tuple[int, ...],
    rendered_ids: tuple[int, ...],
    prompt_body: str,
    previous_prompt_body: str,
) -> bool:
    """Skip redundant inline redraws when nothing visible changed."""
    return transcript_ids == rendered_ids and prompt_body == previous_prompt_body


def _should_record_progress_entries(terminal_mode: str) -> bool:
    """Return True when progress updates should be appended into transcript."""
    return False


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class TtyAppArgs:
    runtime: dict | None
    tools: ToolRegistry
    model: ModelAdapter
    messages: list[ChatMessage]
    cwd: str
    permissions: PermissionManager


@dataclass
class PendingApproval:
    request: dict[str, Any]
    resolve: Callable[[dict[str, Any]], None]
    details_expanded: bool = False
    details_scroll_offset: int = 0
    selected_choice_index: int = 0
    feedback_mode: bool = False
    feedback_input: str = ""


@dataclass
class AggregatedEditProgress:
    entry_id: int
    tool_name: str
    path: str
    total: int = 1
    completed: int = 0
    errors: int = 0
    last_output: str = ""


@dataclass
class ScreenState:
    input: str = ""
    cursor_offset: int = 0
    queued_inputs: list[str] = field(default_factory=list)
    transcript: list[TranscriptEntry] = field(default_factory=list)
    transcript_scroll_offset: int = 0
    selected_slash_index: int = 0
    status: str | None = None
    active_tool: str | None = None
    recent_tools: list[dict[str, str]] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    history_index: int = 0
    history_draft: str = ""
    next_entry_id: int = 1
    pending_approval: PendingApproval | None = None
    is_busy: bool = False
    # Session persistence
    session: SessionData | None = None
    autosave: AutosaveManager | None = None
    # State management (Zustand-style)
    app_state: Store[AppState] | None = None
    # Cost tracking
    cost_tracker: CostTracker | None = None
    # Background agent thread
    agent_thread: Any = None
    agent_result: dict | None = None
    agent_lock: Any = None
    tool_start_time: float | None = None
    orchestration: OrchestratorState | None = None
    orchestration_entry_id: int | None = None
    sub_agent_manager: SubAgentManager | None = None
    companion_enabled: bool = True
    companion_species: str = "duck"
    animation_frame: int = 0
    buddy_profile: BuddyProfile | None = None
    buddy_runtime: BuddyRuntimeState = field(default_factory=BuddyRuntimeState)
    imported_pet_name: str | None = None
    imported_pet_source: str | None = None
    imported_pet_ansi: str | None = None
    imported_pet_ascii: str | None = None
    imported_pet_mode: str = "ansi"
    imported_pet_active: bool = False
    busy_verb: str = "Transfiguring"
    current_action_summary: str | None = None
    wheel_debug_last_direction: str | None = None
    wheel_debug_event_count: int = 0
    wheel_debug_fallback_active: bool = False
    wheel_debug_fallback_hook: bool = False
    wheel_debug_session_title: str | None = None
    wheel_debug_foreground_title: str | None = None
    wheel_debug_raw_callback_count: int = 0
    wheel_debug_matched_callback_count: int = 0
    wheel_debug_callback_foreground_title: str | None = None
    welcome_tip_index: int = 0
    welcome_tip_rotated_at: float = 0.0


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def _get_session_stats(args: TtyAppArgs, state: ScreenState) -> dict[str, int]:
    """Get current session statistics.
    
    Returns a dict with transcript, message, skill, and MCP server counts.
    """
    return {
        "transcriptCount": len(state.transcript),
        "messageCount": len(args.messages),
        "skillCount": len(args.tools.get_skills()),
        "mcpCount": len(args.tools.get_mcp_servers()),
    }


def _push_transcript_entry(state: ScreenState, **kwargs: Any) -> int:
    """Create and append a new transcript entry.
    
    Returns the unique entry ID for later updates.
    """
    entry_id = state.next_entry_id
    state.next_entry_id += 1
    state.transcript.append(TranscriptEntry(id=entry_id, **kwargs))
    return entry_id


def _find_transcript_entry(state: ScreenState, entry_id: int) -> TranscriptEntry | None:
    for entry in state.transcript:
        if entry.id == entry_id:
            return entry
    return None


def _is_multi_agent_candidate(input_text: str) -> bool:
    lowered = input_text.lower()
    explicit_keywords = (
        "multi-agent",
        "multi agent",
        "subagent",
        "sub-agent",
        "parallel",
        "orchestr",
        "并行",
        "多agent",
        "多 agent",
        "多智能体",
    )
    paired_workflows = (
        "review and implementation",
        "search and implementation",
        "split search and implementation",
        "implement and review",
        "explore and review",
        "审查和实现",
        "搜索和实现",
    )
    if any(keyword in lowered for keyword in explicit_keywords):
        return True
    if any(keyword in lowered for keyword in paired_workflows):
        return True
    if _looks_like_single_step_execution_task(input_text):
        return False
    return False


_SINGLE_AGENT_BUSY_SPINNER_FRAMES: tuple[str, ...] = ("◜", "◠", "◝", "◞", "◡", "◟")
_SINGLE_AGENT_DEFAULT_VERB = "Transfiguring"
_SCREEN_CLEAR = "\x1b[2J\x1b[H"
_CLEAR_LINE = "\x1b[2K"
_CURSOR_SAVE = "\x1b7"
_CURSOR_RESTORE = "\x1b8"


def _strip_screen_clear_prefix(frame: str) -> str:
    if frame.startswith(_SCREEN_CLEAR):
        return frame[len(_SCREEN_CLEAR):]
    return frame


class _LineDiffScreenWriter:
    """Write terminal frames by updating only rows whose text changed."""

    def __init__(self, output: TextIO) -> None:
        self._output = output
        self._previous_lines: list[str] = []
        self._has_frame = False

    def reset(self) -> None:
        self._previous_lines = []
        self._has_frame = False

    def render(self, frame: str, *, force_full: bool = False) -> str:
        content = _strip_screen_clear_prefix(frame)
        next_lines = content.split("\n") if content else [""]
        if force_full or not self._has_frame:
            rendered = _SCREEN_CLEAR + content
            self._output.write(rendered)
            self._previous_lines = next_lines
            self._has_frame = True
            return rendered

        chunks: list[str] = []
        max_lines = max(len(self._previous_lines), len(next_lines))
        for index in range(max_lines):
            previous = self._previous_lines[index] if index < len(self._previous_lines) else ""
            current = next_lines[index] if index < len(next_lines) else ""
            if previous == current:
                continue
            chunks.append(f"\x1b[{index + 1};1H{_CLEAR_LINE}{current}")

        rendered = "".join(chunks)
        if rendered:
            self._output.write(rendered)
        self._previous_lines = next_lines
        return rendered


def _count_rendered_lines(frame: str, width: int) -> int:
    width = max(1, width)
    content = _strip_screen_clear_prefix(frame)
    if not content:
        return 1

    total = 0
    for line in content.split("\n"):
        display_width = string_display_width(line)
        total += max(1, (display_width + width - 1) // width)
    return max(1, total)


def _render_inline_frame(frame: str, previous_line_count: int) -> str:
    content = _strip_screen_clear_prefix(frame)
    if previous_line_count <= 0:
        return f"{_CURSOR_SAVE}{content}"
    return f"{_CURSOR_RESTORE}\x1b[J{content}"


def _render_inline_frame_update(
    frame: str,
    previous_line_count: int,
    width: int,
) -> tuple[str, int]:
    return _render_inline_frame(frame, previous_line_count), _count_rendered_lines(frame, width)


def _clear_prompt_region(previous_line_count: int) -> str:
    if previous_line_count <= 0:
        return ""
    move_up = f"\x1b[{previous_line_count - 1}A" if previous_line_count > 1 else ""
    return f"\r{move_up}\x1b[J"


def _render_agent_frame_update(
    transcript_entries: list[TranscriptEntry],
    previous_transcript_ids: tuple[int, ...],
    prompt_body: str,
    previous_prompt_line_count: int,
) -> tuple[str, tuple[int, ...], int]:
    current_ids = tuple(entry.id for entry in transcript_entries)
    has_prefix = (
        len(previous_transcript_ids) <= len(current_ids)
        and current_ids[: len(previous_transcript_ids)] == previous_transcript_ids
    )
    visible_entries = transcript_entries[len(previous_transcript_ids) :] if has_prefix else transcript_entries

    buf = [_clear_prompt_region(previous_prompt_line_count)]
    if visible_entries:
        transcript_text = render_transcript_simple(visible_entries)
        if transcript_text:
            buf.append(transcript_text)
            if not transcript_text.endswith("\n"):
                buf.append("\n")
            buf.append("\n")
    buf.append(prompt_body)
    return "".join(buf), current_ids, _count_text_lines(prompt_body)


def _should_start_windows_wheel_fallback(terminal_mode: str) -> bool:
    return terminal_mode in {"tui", "agent"} and _should_capture_mouse()


def _should_rotate_welcome_tips() -> bool:
    value = os.environ.get("ASTRID_ROTATE_WELCOME_TIPS", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _render_busy_spinner(frame: int) -> str:
    spinner = _SINGLE_AGENT_BUSY_SPINNER_FRAMES[
        frame % len(_SINGLE_AGENT_BUSY_SPINNER_FRAMES)
    ]
    t = theme()
    return f"{t.progress}{t.bold}{spinner}{t.reset}"


def _render_live_status_line(state: ScreenState) -> str | None:
    t = theme()
    status = state.status
    if state.pending_approval is not None:
        status = "Awaiting approval..."
    elif state.is_busy and not status:
        status = f"{state.busy_verb}..."
    if not status:
        return None
    if state.is_busy or state.pending_approval is not None:
        summary = _truncate_for_display(" ".join((state.current_action_summary or "").split()).strip(), 120)
        if summary:
            return (
                f"{_render_busy_spinner(state.animation_frame)} {t.progress}{status}{t.reset} "
                f"{t.subtle}{summary}{t.reset}"
            )
        return f"{_render_busy_spinner(state.animation_frame)} {t.progress}{status}{t.reset}"
    return f"{t.subtle}{status}{t.reset}"


def _looks_like_single_step_execution_task(input_text: str) -> bool:
    lowered = input_text.lower()
    direct_actions = (
        "git clone",
        "clone ",
        "copy ",
        "move ",
        "rename ",
        "delete ",
        "remove ",
        "download ",
        "install ",
        "run ",
        "execute ",
        "执行",
        "运行",
        "克隆",
        "复制",
        "移动",
        "重命名",
        "删除",
        "下载",
        "安装",
    )
    target_markers = (
        "http://",
        "https://",
        "github.com",
        "git@",
        ":\\",
        "./",
        "../",
        "git ",
        "python ",
        "pytest",
        "npm ",
        "pnpm ",
        "uv ",
        "cargo ",
        "pip ",
    )
    return any(token in lowered for token in direct_actions) and any(
        marker in lowered for marker in target_markers
    )


def _set_single_agent_busy_state(
    state: ScreenState,
    *,
    verb: str | None = None,
    summary: str | None = None,
    status: str | None = None,
) -> None:
    state.busy_verb = verb or _SINGLE_AGENT_DEFAULT_VERB
    state.current_action_summary = summary
    if status is not None:
        state.status = status


def _summarize_progress_update(content: str) -> tuple[str, str]:
    summary = _truncate_for_display(" ".join(content.split()).strip(), 160)
    lowered = summary.lower()
    if any(token in lowered for token in ("review", "validate", "check", "审查", "校验")):
        return "Reviewing", summary
    if any(token in lowered for token in ("search", "scan", "inspect", "read", "grep", "搜索", "扫描", "读取")):
        return "Inspecting", summary
    if any(token in lowered for token in ("command", "tool", "run", "execute", "命令", "工具", "执行")):
        return "Running", summary
    if any(token in lowered for token in ("merge", "combine", "collect", "汇总", "合并")):
        return "Collecting", summary
    return _SINGLE_AGENT_DEFAULT_VERB, summary


def _render_single_agent_busy_line(state: ScreenState) -> str:
    t = theme()
    line = f"{_render_busy_spinner(state.animation_frame)} {t.progress}{t.bold}{state.busy_verb}{t.reset}{t.progress}...{t.reset}"
    summary = state.current_action_summary
    if not summary and state.status and state.status != f"{state.busy_verb}...":
        summary = state.status
    if summary:
        return f"{line}\n  {t.assistant}{summary}{t.reset}"
    return line


def _trim_simple_transcript_for_busy_state(entries: list[TranscriptEntry], state: ScreenState) -> list[TranscriptEntry]:
    if not _should_append_single_agent_busy_line(state):
        return entries
    trimmed = list(entries)
    while trimmed and trimmed[-1].kind == "progress":
        trimmed.pop()
    return trimmed


def _should_append_single_agent_busy_line(state: ScreenState) -> bool:
    return False


def _prune_completed_progress_entries(state: ScreenState) -> None:
    state.transcript = [entry for entry in state.transcript if entry.kind != "progress"]


def _get_renderable_transcript_entries(state: ScreenState) -> list[TranscriptEntry]:
    _dedupe_welcome_entries(state)
    return [
        entry
        for entry in state.transcript
        if entry.kind not in {"progress", "welcome"}
    ]


def _pick_worker_name(role: WorkerRole, index: int) -> tuple[str, str]:
    role_pool: dict[WorkerRole, list[tuple[str, str]]] = {
        WorkerRole.CONTEXT_SCOUT: [
            ("Russell", "teal"),
            ("Hume", "sage"),
            ("Turing", "blue"),
        ],
        WorkerRole.CODE_WORKER: [
            ("Ada", "amber"),
            ("Knuth", "coral"),
            ("Hopper", "violet"),
        ],
        WorkerRole.REVIEW_AGENT: [
            ("Hegel", "blue"),
            ("Popper", "teal"),
            ("Godel", "violet"),
        ],
    }
    options = role_pool[role]
    return options[index % len(options)]


def _to_orchestration_workers(runtime: OrchestratorState) -> list[OrchestrationWorker]:
    status_map = {
        WorkerRuntimeState.QUEUED: "queued",
        WorkerRuntimeState.RUNNING: "running",
        WorkerRuntimeState.REPORTING: "reporting",
        WorkerRuntimeState.BLOCKED: "blocked",
        WorkerRuntimeState.ARCHIVED: "done",
        WorkerRuntimeState.FAILED: "failed",
        WorkerRuntimeState.CANCELLED: "failed",
    }
    return [
        OrchestrationWorker(
            name=worker.name,
            role=worker.role.value,
            mission=worker.mission,
            status=status_map.get(worker.state, "queued"),
            colorKey=worker.color,
            latestEvent=worker.latest_event,
            spinnerVerb=worker.spinner_verb,
        )
        for worker in runtime.workers.values()
    ]


def _sync_orchestration_entry(state: ScreenState) -> None:
    runtime = state.orchestration
    if runtime is None:
        return
    phase_elapsed = max(0.0, time.monotonic() - runtime.phase_started_at)

    workers = _to_orchestration_workers(runtime)
    if state.orchestration_entry_id is None:
        state.orchestration_entry_id = _push_transcript_entry(
            state,
            kind="orchestration",
            body=runtime.narrative,
            narrativeLine=runtime.narrative,
            phaseLabel=get_phase_label(runtime.task_state),
            phaseVerb=get_phase_verb(runtime.task_state, state.animation_frame, phase_elapsed),
            animationFrame=state.animation_frame,
            workers=workers,
        )
        return

    entry = _find_transcript_entry(state, state.orchestration_entry_id)
    if entry is None:
        state.orchestration_entry_id = None
        _sync_orchestration_entry(state)
        return

    entry.body = runtime.narrative
    entry.narrativeLine = runtime.narrative
    entry.phaseLabel = get_phase_label(runtime.task_state)
    entry.phaseVerb = get_phase_verb(runtime.task_state, state.animation_frame, phase_elapsed)
    entry.animationFrame = state.animation_frame
    entry.workers = workers
    if runtime.task_state == TaskRuntimeState.DONE:
        state.buddy_runtime.reaction_text = "Review complete"
        state.buddy_runtime.reaction_until = time.monotonic() + 6.0


def _set_buddy_reaction(state: ScreenState, text: str, *, duration: float = 5.0) -> None:
    state.buddy_runtime.reaction_text = text
    state.buddy_runtime.reaction_until = time.monotonic() + duration


def _render_buddy_profile_summary(state: ScreenState) -> str:
    if state.imported_pet_name and (state.imported_pet_ansi or state.imported_pet_ascii):
        return "\n".join(
            (
                f"name: {state.imported_pet_name}",
                "species: imported",
                f"status: {'active' if state.imported_pet_active else 'draft'}",
                f"mode: {state.imported_pet_mode}",
                f"source: {state.imported_pet_source or 'unknown'}",
            )
        )
    profile = _ensure_buddy_profile(state, state.companion_species)
    return "\n".join(
        (
            f"name: {profile.soul.name}",
            f"persona: {profile.soul.persona}",
            f"species: {profile.bones.species}",
            f"rarity: {profile.bones.rarity}",
            f"eye: {profile.bones.eye}",
            f"hat: {profile.bones.hat}",
            f"shiny: {'yes' if profile.bones.shiny else 'no'}",
        )
    )


def _persist_pet_state(state: ScreenState) -> None:
    existing = load_pet_settings()
    save_pet_settings(
        {
            "customPets": existing.get("customPets", {}),
            "companionEnabled": state.companion_enabled,
            "companionSpecies": state.companion_species,
            "importedPetName": state.imported_pet_name,
            "importedPetSource": state.imported_pet_source,
            "importedPetAnsi": state.imported_pet_ansi,
            "importedPetAscii": state.imported_pet_ascii,
            "importedPetMode": state.imported_pet_mode,
            "importedPetActive": state.imported_pet_active,
        }
    )


def _load_custom_pet_library() -> dict[str, dict[str, str]]:
    pet_settings = load_pet_settings()
    custom = pet_settings.get("customPets", {})
    return custom if isinstance(custom, dict) else {}


def _save_custom_pet_library(custom_pets: dict[str, dict[str, str]]) -> None:
    save_pet_settings({"customPets": custom_pets})


def _apply_startup_pet_state(state: ScreenState) -> None:
    pet_settings = load_pet_settings()
    state.companion_enabled = bool(pet_settings.get("companionEnabled", state.companion_enabled))

    state.imported_pet_name = pet_settings.get("importedPetName")
    state.imported_pet_source = pet_settings.get("importedPetSource")
    state.imported_pet_ansi = pet_settings.get("importedPetAnsi")
    state.imported_pet_ascii = pet_settings.get("importedPetAscii")
    if pet_settings.get("importedPetMode") in {"ansi", "ascii"}:
        state.imported_pet_mode = str(pet_settings["importedPetMode"])
    state.imported_pet_active = bool(pet_settings.get("importedPetActive", False))

    if state.imported_pet_active:
        if pet_settings.get("companionSpecies"):
            state.companion_species = normalize_buddy_species(str(pet_settings["companionSpecies"]))
        return

    state.companion_species = random.choice(BUDDY_SPECIES)


def _render_welcome_pet_block(state: ScreenState, profile: BuddyProfile) -> str:
    if state.imported_pet_active and state.imported_pet_name:
        sprite = state.imported_pet_ansi if state.imported_pet_mode == "ansi" else state.imported_pet_ascii
        if sprite:
            return "\n".join(
                (
                    sprite,
                    f"{state.imported_pet_name} imported pet",
                    f"mode {state.imported_pet_mode} · source {state.imported_pet_source or 'unknown'}",
                )
            )
    return render_welcome_hero_profile_block(profile, state.buddy_runtime, 0)


def _handle_companion_command(state: ScreenState, input_text: str) -> str | None:
    if input_text == "/pet":
        return "Usage: /pet show | /pet hide | /pet next | /pet switch <species> | /pet list | /pet pet | /pet profile | /pet import <path-or-url> [--ascii|--ansi] | /pet mode <ascii|ansi> | /pet save <name> | /pet use <name> | /pet remove <name>"

    if input_text == "/pet show" or input_text == "/pet summon":
        state.companion_enabled = True
        _set_buddy_reaction(state, "Welcome back", duration=6.0)
        state.buddy_runtime.summoned_until = time.monotonic() + 4.0
        _persist_pet_state(state)
        profile = _ensure_buddy_profile(state, state.companion_species)
        return _render_welcome_pet_block(state, profile)

    if input_text == "/pet hide":
        state.companion_enabled = False
        _persist_pet_state(state)
        return "Buddy hidden from the welcome screen."

    if input_text == "/pet next":
        state.companion_species = cycle_buddy_species(state.companion_species, 1)
        state.companion_enabled = True
        state.imported_pet_active = False
        if state.buddy_profile is not None:
            state.buddy_profile = build_buddy_profile(f"{state.buddy_profile.soul.name}:{state.companion_species}")
        _persist_pet_state(state)
        return render_buddy_block(state.companion_species, state.animation_frame)

    if input_text.startswith("/pet switch "):
        requested = input_text[len("/pet switch "):].strip().lower()
        if requested not in BUDDY_SPECIES:
            return (
                f"Unknown buddy '{requested}'.\n"
                f"Available buddies: {', '.join(BUDDY_SPECIES)}"
            )
        species = normalize_buddy_species(requested)
        state.companion_species = species
        state.companion_enabled = True
        state.imported_pet_active = False
        if state.buddy_profile is not None:
            state.buddy_profile = build_buddy_profile(f"{state.buddy_profile.soul.name}:{species}")
        _persist_pet_state(state)
        return render_buddy_block(state.companion_species, state.animation_frame)

    if input_text == "/pet list":
        custom = _load_custom_pet_library()
        lines = ["Built-in buddies:", ", ".join(BUDDY_SPECIES)]
        if custom:
            lines.extend(["", "Custom preset pets:", ", ".join(sorted(custom.keys()))])
        return "\n".join(lines)

    if input_text == "/pet pet":
        _set_buddy_reaction(state, "Much appreciated")
        state.buddy_runtime.pet_until = time.monotonic() + 2.5
        return "Buddy perks up with a shower of hearts."

    if input_text == "/pet profile":
        return _render_buddy_profile_summary(state)

    if input_text.startswith("/pet mode "):
        mode = input_text[len("/pet mode "):].strip().lower()
        if mode not in {"ansi", "ascii"}:
            return "Usage: /pet mode <ansi|ascii>"
        state.imported_pet_mode = mode
        _persist_pet_state(state)
        return f"Imported pet render mode set to {mode}."

    if input_text.startswith("/pet save "):
        pet_name = input_text[len("/pet save "):].strip()
        if not pet_name:
            return "Usage: /pet save <name>"
        if not state.imported_pet_name or not (state.imported_pet_ansi or state.imported_pet_ascii):
            return "No imported pet is active. Use /pet import <path-or-url> first."
        custom = _load_custom_pet_library()
        custom[pet_name] = {
            "source": state.imported_pet_source or "",
            "ansi": state.imported_pet_ansi or "",
            "ascii": state.imported_pet_ascii or "",
        }
        _save_custom_pet_library(custom)
        state.imported_pet_name = pet_name
        state.imported_pet_active = False
        _persist_pet_state(state)
        return f"Saved imported pet as preset '{pet_name}'."

    if input_text.startswith("/pet use "):
        pet_name = input_text[len("/pet use "):].strip()
        if not pet_name:
            return "Usage: /pet use <name>"
        custom = _load_custom_pet_library()
        pet = custom.get(pet_name)
        if not pet:
            return f"Unknown preset pet '{pet_name}'. Use /pet list to see saved pets."
        state.imported_pet_name = pet_name
        state.imported_pet_source = str(pet.get("source", ""))
        state.imported_pet_ansi = str(pet.get("ansi", ""))
        state.imported_pet_ascii = str(pet.get("ascii", ""))
        state.imported_pet_active = True
        state.companion_enabled = True
        _set_buddy_reaction(state, f"{pet_name} is back", duration=6.0)
        _persist_pet_state(state)
        return (
            (state.imported_pet_ansi if state.imported_pet_mode == "ansi" else state.imported_pet_ascii)
            + f"\n{pet_name} preset pet"
        )

    if input_text.startswith("/pet remove "):
        pet_name = input_text[len("/pet remove "):].strip()
        if not pet_name:
            return "Usage: /pet remove <name>"
        custom = _load_custom_pet_library()
        if pet_name not in custom:
            return f"Unknown preset pet '{pet_name}'."
        del custom[pet_name]
        _save_custom_pet_library(custom)
        if state.imported_pet_name == pet_name:
            state.imported_pet_name = None
            state.imported_pet_source = None
            state.imported_pet_ansi = None
            state.imported_pet_ascii = None
            state.imported_pet_active = False
            _persist_pet_state(state)
        return f"Removed preset pet '{pet_name}'."

    if input_text.startswith("/pet import "):
        raw = input_text[len("/pet import "):].strip()
        mode = "ansi"
        if raw.endswith(" --ascii"):
            mode = "ascii"
            raw = raw[: -len(" --ascii")].strip()
        elif raw.endswith(" --ansi"):
            raw = raw[: -len(" --ansi")].strip()
        if not raw:
            return "Usage: /pet import <path-or-url> [--ascii|--ansi]"
        try:
            imported = import_pet_sprite(raw)
        except Exception as exc:  # noqa: BLE001
            return f"Failed to import pet: {exc}"
        state.imported_pet_name = imported.name
        state.imported_pet_source = imported.source
        state.imported_pet_ansi = imported.ansi_sprite
        state.imported_pet_ascii = imported.ascii_sprite
        state.imported_pet_mode = mode
        state.imported_pet_active = False
        state.companion_enabled = True
        state.buddy_runtime.reaction_text = None
        state.buddy_runtime.reaction_until = 0.0
        return (
            (imported.ansi_sprite if mode == "ansi" else imported.ascii_sprite)
            + f"\n{imported.name} imported pet draft\nUse /pet save <name> to keep it or /pet use <name> after saving."
        )

    return None


def _set_worker_state(
    state: ScreenState,
    worker_id: str,
    *,
    status: WorkerRuntimeState | None = None,
    latest_event: str | None = None,
) -> None:
    runtime = state.orchestration
    if runtime is None or worker_id not in runtime.workers:
        return
    worker = runtime.workers[worker_id]
    if status is not None:
        worker.state = status
        if status == WorkerRuntimeState.RUNNING and not worker.spinner_verb:
            worker.spinner_verb = sample_spinner_verb(runtime.task_state, worker.name)
        if status == WorkerRuntimeState.RUNNING:
            _set_buddy_reaction(state, f"{worker.name} is on it", duration=4.0)
    if latest_event is not None:
        worker.latest_event = latest_event
    _sync_orchestration_entry(state)


def _begin_orchestration(state: ScreenState, input_text: str) -> OrchestratorState:
    state.orchestration = create_runtime(input_text)
    state.orchestration_entry_id = None
    state.animation_frame = 0
    _set_buddy_reaction(state, "Crew assembling", duration=5.0)
    request_spawn(state.orchestration)
    _sync_orchestration_entry(state)
    state.status = state.orchestration.narrative
    return state.orchestration


def _summarize_worker_result(instance: Any) -> str:
    summary = instance.result_summary or {}
    output = str(summary.get("final_output") or instance.result or "").strip()
    if not output:
        return f"{instance.definition.name} finished with no final output."
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), output)
    return f"{instance.definition.name}: {first_line[:180]}"


def _mark_running_tools_as_error(state: ScreenState, message: str) -> None:
    """Mark all currently running tools as failed with the given error message.
    
    This is used when a turn ends unexpectedly while tools are still running.
    """
    for entry in state.transcript:
        if entry.kind == "tool" and entry.status == "running":
            entry.status = "error"
            entry.body = message
            entry.collapsed = False
            entry.collapsedSummary = None
            entry.collapsePhase = None
            state.recent_tools.append({"name": entry.toolName or "unknown", "status": "error"})
    if any(e.kind == "tool" and e.status == "error" for e in state.transcript):
        state.active_tool = None


def _update_tool_entry(
    state: ScreenState,
    entry_id: int,
    status: str,
    body: str,
) -> None:
    """Update a tool entry's status and output body.
    
    Automatically un-collapses the entry so the new content is visible.
    """
    for entry in state.transcript:
        if entry.id == entry_id and entry.kind == "tool":
            entry.status = status
            entry.body = body
            entry.collapsed = False
            entry.collapsedSummary = None
            entry.collapsePhase = None
            return


def _set_tool_entry_collapse_phase(state: ScreenState, entry_id: int, phase: int) -> None:
    """Set the collapse animation phase for a tool entry."""
    for entry in state.transcript:
        if entry.id == entry_id and entry.kind == "tool" and entry.status != "running":
            entry.collapsePhase = phase
            return


def _collapse_tool_entry(state: ScreenState, entry_id: int, summary: str) -> None:
    """Collapse a tool entry to show only a summary line.
    
    Used for completed tools to reduce visual clutter in the transcript.
    """
    for entry in state.transcript:
        if entry.id == entry_id and entry.kind == "tool" and entry.status != "running":
            entry.collapsePhase = None
            entry.collapsed = True
            entry.collapsedSummary = summary
            return


def _get_running_tool_entries(state: ScreenState) -> list[TranscriptEntry]:
    """Get all transcript entries that are still in 'running' status."""
    return [e for e in state.transcript if e.kind == "tool" and e.status == "running"]


def _finalize_dangling_running_tools(state: ScreenState) -> None:
    """Mark all running tools as errors when a turn ends unexpectedly.
    
    This happens when the model stops responding but tools are still active,
    indicating a potential sync issue or background process.
    """
    running = _get_running_tool_entries(state)
    if running:
        error_message = (
            f"{running[0].body}\n\n"
            "ERROR: Tool did not report a final result before the turn ended. "
            "This usually means the command kept running in the background "
            "or the tool lifecycle got out of sync."
        )
        _mark_running_tools_as_error(state, error_message)
        state.status = f"Previous turn ended with {len(running)} unfinished tool call(s)."


def _summarize_collapsed_tool_body(output: str) -> str:
    line = next(
        (l.strip() for l in output.split("\n") if l.strip()),
        "output collapsed",
    )
    return line[:140] + "..." if len(line) > 140 else line


def _schedule_tool_auto_collapse(
    state: ScreenState,
    entry_id: int,
    output: str,
    rerender: Callable[[], None],
) -> None:
    """Collapse tool output with a brief animation. Optimized to use a single
    combined delay instead of 3 separate sleep+rerender cycles."""
    summary = _summarize_collapsed_tool_body(output)

    def _do_collapse() -> None:
        # Single delay then jump straight to collapsed state
        # (avoids 3 separate rerender() calls for an animation most users barely see)
        time.sleep(0.25)
        _collapse_tool_entry(state, entry_id, summary)
        rerender()

    t = threading.Thread(target=_do_collapse, daemon=True)
    t.start()


def _get_contextual_help(state: ScreenState, args: TtyAppArgs) -> str | None:
    """Return a contextual help hint for busy or approval states."""
    if not state.is_busy and not state.pending_approval:
        return None  # 淇濇寔鐘舵€佹爮绠€娲?
    if state.is_busy and state.active_tool:
        return f"Running {state.active_tool}... (Ctrl+C to cancel)"
    if state.pending_approval:
        return "Approval required. Use arrow keys and Enter to choose."

    return None


def _terminal_mode_label() -> str:
    mode = _terminal_mode()
    if mode == "shell":
        return "shell mode"
    return "tui mode"


def _terminal_mode_hint() -> str:
    label = _terminal_mode_label()
    if label == "shell mode":
        return "Mode: shell. PowerShell keeps native scrollback. Use astrid --tui for full-screen UI."
    if label == "inline mode":
        return "Mode: inline. Astrid owns transcript scrolling in the main screen without using the alt screen."
    return "Mode: tui. Astrid owns the screen and scroll. Use astrid for shell mode on Windows."


# ---------------------------------------------------------------------------
# Tool summarization
# ---------------------------------------------------------------------------


def _truncate_for_display(text: str, max_len: int = 180) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def _summarize_tool_input(tool_name: str, tool_input: Any) -> str:
    if isinstance(tool_input, str):
        return _truncate_for_display(" ".join(tool_input.split()).strip())

    if isinstance(tool_input, dict):
        path = str(tool_input.get("path", "")).strip()
        path_part = f" path={path}" if path else ""

        if tool_name == "patch_file":
            replacements = tool_input.get("replacements")
            count = len(replacements) if isinstance(replacements, list) else 0
            return f"patch_file{path_part} replacements={count}"
        if tool_name == "edit_file":
            return f"edit_file{path_part}"
        if tool_name == "read_file":
            extras: list[str] = []
            if tool_input.get("offset") is not None:
                extras.append(f"offset={tool_input['offset']}")
            if tool_input.get("limit") is not None:
                extras.append(f"limit={tool_input['limit']}")
            return f"read_file{path_part}{' ' + ' '.join(extras) if extras else ''}"
        if tool_name == "run_command":
            cmd = str(tool_input.get("command", "")).strip()
            return f"run_command{' ' + _truncate_for_display(cmd, 120) if cmd else ''}"
        if path:
            return f"{tool_name}{path_part}"

    try:
        return _truncate_for_display(str(tool_input))
    except Exception:
        return _truncate_for_display(repr(tool_input))


def _is_file_edit_tool(tool_name: str) -> bool:
    return tool_name in ("edit_file", "patch_file", "modify_file", "write_file")


def _extract_path_from_tool_input(tool_input: Any) -> str | None:
    if not isinstance(tool_input, dict):
        return None
    value = tool_input.get("path")
    return value if isinstance(value, str) and value.strip() else None


# ---------------------------------------------------------------------------
# Scroll / history / slash
# ---------------------------------------------------------------------------


_FOOTER_LINES = 1

# Cache for chrome overhead so we only re-measure when state changes
_chrome_overhead_cache: dict[str, tuple[tuple, int]] = {}


def _count_text_lines(s: str) -> int:
    """Count screen lines in a rendered string (split on \\n)."""
    return s.count("\n") + 1


def _split_rendered_lines(block: str) -> list[str]:
    if block == "":
        return []
    return block.split("\n")


_SIMPLE_LEFT_GUTTER = " "


def _apply_simple_left_gutter(lines: list[str], gutter: str = _SIMPLE_LEFT_GUTTER) -> list[str]:
    """Add a one-column safety gutter for embedded terminals that clip column 0."""
    return [f"{gutter}{line}" if line else "" for line in lines]


def _get_chrome_overhead(args: TtyAppArgs, state: ScreenState) -> int:
    """Measure the actual line count of header + prompt panels (cached).

    Accounts for compact mode (small terminal): uses single-\\n separators
    instead of double-\\n, saving 2 lines.
    """
    compact = _is_compact_terminal()
    # sep "\n\n" adds 2 blank lines between panels; "\n" adds 1.
    # There are 2 separators (header鈫抰ranscript, transcript鈫抪rompt).
    gaps = 2 if compact else 4
    cache_key = (
        args.cwd,
        getattr(args, "model", None),
        state.input,
        bool(state.pending_approval),
        compact,
    )
    cached = _chrome_overhead_cache.get("key")
    if cached is not None and cached[0] == cache_key:
        return cached[1]

    header_lines = _count_text_lines(_render_header_panel(args, state))
    prompt_lines = _count_text_lines(_render_prompt_panel(state))
    overhead = header_lines + prompt_lines + _FOOTER_LINES + gaps
    _chrome_overhead_cache["key"] = (cache_key, overhead)
    return overhead


def _get_transcript_body_lines(args: TtyAppArgs, state: ScreenState) -> int:
    _, rows = _get_terminal_size()
    rows = max(24, rows)
    # Subtract the actual rendered chrome (header + prompt + footer + gaps)
    # plus 4 lines for the transcript panel frame (top border, title, divider, bottom border)
    transcript_frame = 4
    chrome_overhead = _get_chrome_overhead(args, state) + transcript_frame
    return max(6, rows - chrome_overhead)


def _is_tui_profile_enabled() -> bool:
    value = os.environ.get("ASTRID_TUI_PROFILE", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _record_tui_profile(metrics: dict[str, float | int]) -> None:
    if not _is_tui_profile_enabled():
        return
    logging.getLogger("astrid.tui.profile").info(
        " ".join(f"{key}={value}" for key, value in metrics.items())
    )


def _get_simple_bottom_chrome_lines(state: ScreenState) -> list[str]:
    lines = _split_rendered_lines(_build_simple_prompt_body(state))
    footer_status = _get_simple_footer_status(state)
    if footer_status:
        lines.append("")
        lines.extend(_split_rendered_lines(footer_status))
    return lines


def _get_simple_content_window_size(state: ScreenState, rows: int) -> int:
    bottom_lines = _get_simple_bottom_chrome_lines(state)
    spacer = 1
    return max(1, rows - len(bottom_lines) - spacer)


def _get_simple_transcript_entries(state: ScreenState) -> list[TranscriptEntry]:
    transcript_snapshot = _get_renderable_transcript_entries(state)
    return _trim_simple_transcript_for_busy_state(transcript_snapshot, state)


def _get_simple_welcome_lines(args: TtyAppArgs, state: ScreenState) -> list[str]:
    _sync_welcome_transcript_entry(args, state)
    welcome_entry = _find_welcome_entry(state)
    if welcome_entry is None:
        return []
    return _split_rendered_lines(welcome_entry.body)


def _get_max_transcript_scroll_offset(args: TtyAppArgs, state: ScreenState) -> int:
    _, rows = _get_terminal_size()
    rows = max(8, rows)
    content_window_size = _get_simple_content_window_size(state, rows)
    transcript_entries = _get_simple_transcript_entries(state)
    if transcript_entries:
        return get_transcript_max_scroll_offset(
            transcript_entries,
            content_window_size,
            separator_lines=_SIMPLE_SEPARATOR_LINES,
        )

    content_lines = _get_simple_static_content_lines(args, state)
    return max(0, len(content_lines) - content_window_size)


def _scroll_transcript_by(args: TtyAppArgs, state: ScreenState, delta: int) -> bool:
    max_offset = _get_max_transcript_scroll_offset(args, state)
    next_offset = max(0, min(max_offset, state.transcript_scroll_offset + delta))
    if next_offset == state.transcript_scroll_offset:
        return False
    state.transcript_scroll_offset = next_offset
    return True


def _build_simple_prompt_body(state: ScreenState) -> str:
    compact = _is_compact_terminal()
    commands = _get_visible_commands(state.input)
    prompt_body = render_input_prompt(state.input, state.cursor_offset, compact=compact)
    if commands:
        prompt_body += "\n" + render_slash_menu(
            commands,
            min(state.selected_slash_index, len(commands) - 1),
        )
    queued_preview = _render_queued_turn_preview(state)
    if queued_preview:
        prompt_body += "\n" + queued_preview
    return prompt_body


def _get_simple_footer_status(state: ScreenState) -> str | None:
    return None if _should_append_single_agent_busy_line(state) else _render_live_status_line(state)


def _render_queued_turn_preview(state: ScreenState) -> str:
    if not state.queued_inputs:
        return ""
    preview = _truncate_for_display(" ".join(state.queued_inputs[0].split()).strip(), 96)
    suffix = f" (+{len(state.queued_inputs) - 1})" if len(state.queued_inputs) > 1 else ""
    return f"{SUBTLE}next turn:{RESET} {preview}{SUBTLE}{suffix}{RESET}"


def _get_simple_static_content_lines(args: TtyAppArgs, state: ScreenState) -> list[str]:
    welcome_lines = _get_simple_welcome_lines(args, state)
    if welcome_lines:
        return welcome_lines

    if _should_append_single_agent_busy_line(state):
        return _split_rendered_lines(_render_single_agent_busy_line(state))

    if state.companion_enabled:
        return _split_rendered_lines(
            f"{render_status_line(None)}\n\n"
            f"{render_buddy_block(state.companion_species, 0)}\n\n"
            "Type a message or /help for commands."
        )

    return _split_rendered_lines(f"{render_status_line(None)}\n\nType /help for commands.")


def _slice_content_lines(lines: list[str], scroll_offset: int, window_size: int) -> list[str]:
    window_size = max(1, window_size)
    max_offset = max(0, len(lines) - window_size)
    offset = max(0, min(scroll_offset, max_offset))
    if offset > 0:
        content_window_size = max(1, window_size - 1)
        end = min(len(lines), content_window_size + offset + 1)
        start = max(0, end - content_window_size)
        visible = list(lines[start:end])
        visible.append(f"{SUBTLE}── scroll {offset}/{max_offset} (PgUp/PgDn or scroll)──{RESET}")
        return visible
    end = len(lines)
    start = max(0, end - window_size)
    visible = lines[start:end]
    return visible


def _build_simple_page_flow_document(
    args: TtyAppArgs,
    state: ScreenState,
    *,
    include_scroll_hint: bool,
) -> str:
    parts: list[str] = []
    _sync_welcome_transcript_entry(args, state)
    welcome_entry = _find_welcome_entry(state)
    has_welcome = welcome_entry is not None
    if welcome_entry is not None:
        parts.extend(_split_rendered_lines(welcome_entry.body))
        parts.append("")

    transcript_snapshot = _get_renderable_transcript_entries(state)
    if transcript_snapshot:
        simple_transcript = _trim_simple_transcript_for_busy_state(transcript_snapshot, state)
        if simple_transcript:
            parts.extend(_split_rendered_lines(render_transcript_simple(simple_transcript)))
        profile = _ensure_buddy_profile(state, args.cwd)
        overlay = render_buddy_overlay(profile, state.buddy_runtime)
        if overlay:
            if parts and parts[-1] != "":
                parts.append("")
            parts.extend(_split_rendered_lines(overlay))
    elif _should_append_single_agent_busy_line(state):
        parts.extend(_split_rendered_lines(_render_single_agent_busy_line(state)))
    elif not has_welcome and state.companion_enabled:
        parts.extend(
            _split_rendered_lines(
                f"{render_status_line(None)}\n\n"
                f"{render_buddy_block(state.companion_species, 0)}\n\n"
                "Type a message or /help for commands."
            )
        )
    elif not has_welcome:
        parts.extend(_split_rendered_lines(f"{render_status_line(None)}\n\nType /help for commands."))

    if include_scroll_hint and state.transcript_scroll_offset > 0:
        max_offset = _get_max_transcript_scroll_offset(args, state)
        parts.append(f"{SUBTLE}── scroll {state.transcript_scroll_offset}/{max_offset} (PgUp/PgDn or scroll)──{RESET}")

    if parts and parts[-1] != "":
        parts.append("")
    parts.extend(_split_rendered_lines(_build_simple_prompt_body(state)))

    footer_status = _get_simple_footer_status(state)
    if footer_status:
        parts.append("")
        parts.extend(_split_rendered_lines(footer_status))

    return "\n".join(_apply_simple_left_gutter(parts))


def _build_agent_prompt_region(state: ScreenState) -> str:
    prompt_body = _build_simple_prompt_body(state)
    if _should_append_single_agent_busy_line(state):
        return f"{_render_single_agent_busy_line(state)}\n\n{prompt_body}"
    footer_status = _get_simple_footer_status(state)
    if not footer_status:
        return prompt_body
    return f"{prompt_body}\n\n{footer_status}"


def _enqueue_next_turn(state: ScreenState, input_text: str) -> bool:
    queued_text = input_text.strip()
    if not queued_text:
        return False
    state.queued_inputs.append(queued_text)
    state.status = f"Queued next turn ({len(state.queued_inputs)})"
    return True


def _drain_next_queued_turn(
    args: TtyAppArgs,
    state: ScreenState,
    rerender: Callable[[], None],
) -> bool:
    if state.is_busy or not state.queued_inputs:
        return False
    next_input = state.queued_inputs.pop(0)
    if _handle_input(args, state, rerender, submitted_raw_input=next_input):
        raise SystemExit(0)
    return True


def _jump_transcript_to_edge(args: TtyAppArgs, state: ScreenState, target: str) -> bool:
    next_offset = _get_max_transcript_scroll_offset(args, state) if target == "top" else 0
    if next_offset == state.transcript_scroll_offset:
        return False
    state.transcript_scroll_offset = next_offset
    return True


def _scroll_pending_approval_by(state: ScreenState, delta: int) -> bool:
    pending = state.pending_approval
    if not pending or not pending.details_expanded:
        return False
    max_offset = get_permission_prompt_max_scroll_offset(pending.request, expanded=True)
    next_offset = max(0, min(max_offset, pending.details_scroll_offset + delta))
    if next_offset == pending.details_scroll_offset:
        return False
    pending.details_scroll_offset = next_offset
    return True


def _toggle_pending_approval_expand(state: ScreenState) -> bool:
    pending = state.pending_approval
    if not pending or pending.request.get("kind") != "edit":
        return False
    pending.details_expanded = not pending.details_expanded
    pending.details_scroll_offset = 0
    return True


def _move_pending_approval_selection(state: ScreenState, delta: int) -> bool:
    pending = state.pending_approval
    if not pending or pending.feedback_mode:
        return False
    total = len(pending.request.get("choices", []))
    if total <= 0:
        return False
    pending.selected_choice_index = (pending.selected_choice_index + delta + total) % total
    return True


def _history_up(state: ScreenState) -> bool:
    if not state.history or state.history_index <= 0:
        return False
    if state.history_index == len(state.history):
        state.history_draft = state.input
    state.history_index -= 1
    state.input = state.history[state.history_index] if state.history_index < len(state.history) else ""
    state.cursor_offset = len(state.input)
    return True


def _history_down(state: ScreenState) -> bool:
    if state.history_index >= len(state.history):
        return False
    state.history_index += 1
    state.input = (
        state.history_draft
        if state.history_index == len(state.history)
        else (state.history[state.history_index] if state.history_index < len(state.history) else "")
    )
    state.cursor_offset = len(state.input)
    return True


def _get_visible_commands(input_text: str) -> list[Any]:
    if not input_text.startswith("/"):
        return []
    if input_text == "/":
        return SLASH_COMMANDS
    matches = find_matching_slash_commands(input_text)
    return [cmd for cmd in SLASH_COMMANDS if getattr(cmd, "usage", str(cmd)) in matches]


# ---------------------------------------------------------------------------
# Rendering 鈥?cached header & footer
# ---------------------------------------------------------------------------

# Banner cache: the banner rarely changes (only when cwd, model, or stats change).
_banner_cache: dict[str, tuple[tuple, str]] = {"key": ((), "")}


_COMPACT_ROWS_THRESHOLD = 35  # Use compact UI when terminal rows < this value


def _is_compact_terminal() -> bool:
    """Return True when the terminal is too short for the full UI chrome."""
    _, rows = _get_terminal_size()
    return rows < _COMPACT_ROWS_THRESHOLD


def _render_header_panel(args: TtyAppArgs, state: ScreenState) -> str:
    """Render the top banner panel with model info, cwd, and session stats.
    
    The result is cached to avoid re-rendering when stats haven't changed.
    Uses compact single-line mode when the terminal has fewer than
    _COMPACT_ROWS_THRESHOLD rows so that the transcript area has more space.
    """
    stats = _get_session_stats(args, state)
    compact = _is_compact_terminal()
    show_companion = state.companion_enabled and not state.transcript
    companion_preview = (
        render_buddy_block(state.companion_species, state.animation_frame) if show_companion else None
    )
    cache_key = (
        args.cwd,
        id(args.runtime),
        stats.get("transcriptCount"),
        stats.get("messageCount"),
        stats.get("skillCount"),
        stats.get("mcpCount"),
        _cached_terminal_size(),
        compact,
        state.companion_enabled,
        state.companion_species,
        bool(companion_preview),
    )
    cached = _banner_cache.get("key")
    if cached and cached[0] == cache_key:
        return cached[1]
    result = render_banner(
        args.runtime,
        args.cwd,
        args.permissions.get_summary(),
        stats,
        compact=compact,
        companion_preview=companion_preview,
    )
    _banner_cache["key"] = (cache_key, result)
    return result


# Footer cache: only changes with status, tool/skill state, background tasks
_footer_cache: dict[str, tuple[tuple, str]] = {"key": ((), "")}


def _render_footer_cached(
    status: str | None,
    tools_enabled: bool,
    skills_enabled: bool,
    background_tasks: list[dict[str, Any]],
) -> str:
    """Render the bottom status bar with caching to reduce flicker.
    
    Shows current operation status, tool/skill availability, and background tasks.
    """
    cache_key = (
        status,
        tools_enabled,
        skills_enabled,
        len(background_tasks),
        _cached_terminal_size(),
    )
    cached = _footer_cache.get("key")
    if cached and cached[0] == cache_key:
        return cached[1]
    result = render_footer_bar(status, tools_enabled, skills_enabled, background_tasks)
    _footer_cache["key"] = (cache_key, result)
    return result


def _render_prompt_panel(state: ScreenState) -> str:
    compact = _is_compact_terminal()
    commands = _get_visible_commands(state.input)
    prompt_body = render_input_prompt(state.input, state.cursor_offset, compact=compact)
    if commands:
        prompt_body += "\n" + render_slash_menu(
            commands,
            min(state.selected_slash_index, len(commands) - 1),
        )
    return render_panel("prompt", prompt_body)


def _ensure_buddy_profile(state: ScreenState, seed: str) -> BuddyProfile:
    if state.buddy_profile is None or state.buddy_profile.bones.species != state.companion_species:
        state.buddy_profile = build_buddy_profile(
            f"{seed}:{state.companion_species}",
            species_override=state.companion_species,
        )
    return state.buddy_profile



def _find_welcome_entry(state: ScreenState) -> TranscriptEntry | None:
    for entry in state.transcript:
        if entry.kind == "welcome":
            return entry
    return None


def _dedupe_welcome_entries(state: ScreenState) -> None:
    seen_welcome = False
    deduped: list[TranscriptEntry] = []
    for entry in state.transcript:
        if entry.kind == "welcome":
            if seen_welcome:
                continue
            seen_welcome = True
        deduped.append(entry)
    state.transcript = deduped


def _drop_welcome_entries(state: ScreenState) -> None:
    state.transcript = [entry for entry in state.transcript if entry.kind != "welcome"]


def _has_non_welcome_transcript_entries(state: ScreenState) -> bool:
    return any(entry.kind != "welcome" for entry in state.transcript)


def _sync_welcome_transcript_entry(args: TtyAppArgs, state: ScreenState) -> None:
    _dedupe_welcome_entries(state)
    width, _ = _get_terminal_size()
    welcome_body = _build_welcome_workbench(
        args,
        state,
        width=max(40, width - len(_SIMPLE_LEFT_GUTTER)),
    )
    entry = _find_welcome_entry(state)
    if entry is not None:
        entry.body = welcome_body
        return

    entry_id = state.next_entry_id
    state.next_entry_id += 1
    state.transcript.insert(0, TranscriptEntry(id=entry_id, kind="welcome", body=welcome_body))


def _build_welcome_workbench(args: TtyAppArgs, state: ScreenState, *, width: int) -> str:
    model_name = (
        str(args.runtime.get("model"))
        if isinstance(args.runtime, dict) and args.runtime.get("model")
        else (getattr(args.model, "__class__", None).__name__ if args.model else "unknown")
    )
    tip_cycle = (
        "Run /pet next to switch buddies",
        "Try a multi-agent prompt to watch orchestration",
        "Use /help to browse commands",
    )
    if state.welcome_tip_rotated_at <= 0.0:
        state.welcome_tip_rotated_at = time.monotonic()
    profile = _ensure_buddy_profile(state, args.cwd)
    buddy_block = (
        _render_welcome_pet_block(state, profile)
        if state.companion_enabled
        else "Buddy hidden\nUse /pet show to bring it back."
    )
    recent_items = [item for item in reversed(state.history[-3:])] if state.history else []
    if not recent_items:
        recent_items = ["No recent activity yet"]
    return render_welcome_workbench(
        app_name="codingagent x astrid",
        version=f"welcome · {_terminal_mode_label()}",
        model_name=model_name,
        workspace=args.cwd,
        buddy_block=buddy_block,
        tips=[
            "Type a message to start working",
            tip_cycle[state.welcome_tip_index % len(tip_cycle)],
            "Use /pet switch <species> to browse built-in buddies",
        ],
        recent_items=recent_items,
        width=width,
    )


def _render_screen(args: TtyAppArgs, state: ScreenState) -> None:
    if not _has_non_welcome_transcript_entries(state):
        _sync_welcome_transcript_entry(args, state)
    background_tasks = list_background_tasks()
    compact = _is_compact_terminal()
    sep = "\n" if compact else "\n\n"

    buf: list[str] = []
    buf.append(_SCREEN_CLEAR)
    buf.append(_render_header_panel(args, state))
    buf.append(sep)

    has_skills = len(args.tools.get_skills()) > 0

    if state.pending_approval:
        buf.append(
            render_permission_prompt(
                state.pending_approval.request,
                expanded=state.pending_approval.details_expanded,
                scroll_offset=state.pending_approval.details_scroll_offset,
                selected_choice_index=state.pending_approval.selected_choice_index,
                feedback_mode=state.pending_approval.feedback_mode,
                feedback_input=state.pending_approval.feedback_input,
            )
        )
        buf.append(sep)
        buf.append(
            render_panel(
                "activity",
                render_tool_panel(state.active_tool, state.recent_tools, background_tasks),
            )
        )
        buf.append(sep)
        buf.append(_render_footer_cached(_render_live_status_line(state), True, has_skills, background_tasks))
        sys.stdout.write("".join(buf))
        sys.stdout.flush()
        return

    transcript_snapshot = _get_renderable_transcript_entries(state)
    body_lines = _get_transcript_body_lines(args, state)
    if transcript_snapshot:
        transcript_body = render_transcript(
            transcript_snapshot, state.transcript_scroll_offset, body_lines
        )
        if _should_append_single_agent_busy_line(state):
            transcript_body = f"{transcript_body}\n\n{_render_single_agent_busy_line(state)}"
    else:
        transcript_body = f"{render_status_line(None)}\n\nType /help for commands."
    buf.append(
        render_panel(
            "session feed",
            transcript_body,
            right_title=f"{len(transcript_snapshot)} events",
            min_body_lines=body_lines,
        )
    )
    profile = _ensure_buddy_profile(state, args.cwd)
    overlay = render_buddy_overlay(profile, state.buddy_runtime)
    if overlay:
        buf.append(sep)
        buf.append(render_panel("buddy", overlay))
    buf.append(sep)
    buf.append(_render_prompt_panel(state))
    buf.append(sep)
    buf.append(_render_footer_cached(_render_live_status_line(state), True, has_skills, background_tasks))

    contextual_help = _get_contextual_help(state, args)
    if contextual_help:
        buf.append(f"\n{SUBTLE}{contextual_help}{RESET}")

    sys.stdout.write("".join(buf))
    sys.stdout.flush()


def _build_screen_simple(args: TtyAppArgs, state: ScreenState) -> str:
    total_start = time.perf_counter()
    render_transcript_ms = 0.0
    build_start = time.perf_counter()
    _, rows = _get_terminal_size()
    rows = max(8, rows)

    bottom_lines = _get_simple_bottom_chrome_lines(state)
    content_window_size = _get_simple_content_window_size(state, rows)
    transcript_entries = _get_simple_transcript_entries(state)

    if transcript_entries:
        transcript_start = time.perf_counter()
        content = render_transcript_simple_windowed(
            transcript_entries,
            state.transcript_scroll_offset,
            content_window_size,
        )
        render_transcript_ms = (time.perf_counter() - transcript_start) * 1000
        content_lines = _split_rendered_lines(content)

        welcome_lines = _get_simple_welcome_lines(args, state)
        if welcome_lines:
            welcome_budget = min(len(welcome_lines), max(0, content_window_size - 1))
            if welcome_budget > 0:
                content_lines = welcome_lines[:welcome_budget] + [""] + content_lines
                content_lines = content_lines[-content_window_size:]

        profile = _ensure_buddy_profile(state, args.cwd)
        overlay = render_buddy_overlay(profile, state.buddy_runtime)
        if overlay and len(content_lines) < content_window_size:
            if content_lines and content_lines[-1] != "":
                content_lines.append("")
            remaining = max(0, content_window_size - len(content_lines))
            content_lines.extend(_split_rendered_lines(overlay)[:remaining])
    else:
        static_lines = _get_simple_static_content_lines(args, state)
        content_lines = _slice_content_lines(static_lines, state.transcript_scroll_offset, content_window_size)

    visible = list(content_lines)
    if visible and bottom_lines:
        visible.append("")
    visible.extend(bottom_lines)
    if len(visible) > rows:
        visible = visible[-rows:]

    build_document_ms = (time.perf_counter() - build_start) * 1000
    _record_tui_profile(
        {
            "total_frame_ms": round((time.perf_counter() - total_start) * 1000, 3),
            "build_document_ms": round(build_document_ms, 3),
            "render_transcript_ms": round(render_transcript_ms, 3),
            "terminal_write_ms": 0,
            "transcript_entries": len(transcript_entries),
            "rendered_lines": len(visible),
            "bytes_written": len("\n".join(visible)),
        }
    )
    return _SCREEN_CLEAR + "\n".join(_apply_simple_left_gutter(visible))


def _render_screen_simple(args: TtyAppArgs, state: ScreenState) -> None:
    sys.stdout.write(_build_screen_simple(args, state))
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Cross-platform raw mode stdin
# ---------------------------------------------------------------------------

# Windows msvcrt scan-code 鈫?ANSI escape sequence mapping.
# msvcrt.getwch() returns a two-char sequence for special keys:
#   prefix ('\x00' or '\xe0') + scan-code byte.
# We translate these to the ANSI sequences that input_parser.py already
# understands.
_WIN_SCANCODE_TO_ANSI: dict[int, str] = {
    72: "\x1b[A",    # Up
    80: "\x1b[B",    # Down
    77: "\x1b[C",    # Right
    75: "\x1b[D",    # Left
    71: "\x1b[H",    # Home
    79: "\x1b[F",    # End
    73: "\x1b[5~",   # Page Up
    81: "\x1b[6~",   # Page Down
    83: "\x1b[3~",   # Delete
    82: "\x1b[2~",   # Insert
    # Alt+Arrow (returned with \x00 prefix on some terminals)
    152: "\x1b[1;3A",  # Alt+Up
    160: "\x1b[1;3B",  # Alt+Down
    157: "\x1b[1;3C",  # Alt+Right
    155: "\x1b[1;3D",  # Alt+Left
    # Ctrl+Arrow
    141: "\x1b[1;5A",  # Ctrl+Up
    145: "\x1b[1;5B",  # Ctrl+Down
    116: "\x1b[1;5C",  # Ctrl+Right
    115: "\x1b[1;5D",  # Ctrl+Left
}

_WIN_INPUT_EVENT_KEY = 0x0001
_WIN_INPUT_EVENT_MOUSE = 0x0002
_WIN_MOUSE_WHEELED = 0x0004
_WIN_FILE_TYPE_PIPE = 0x0003
_WIN_ENABLE_MOUSE_INPUT = 0x0010
_WIN_ENABLE_QUICK_EDIT_MODE = 0x0040
_WIN_ENABLE_EXTENDED_FLAGS = 0x0080
_WIN_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200
_WIN_WH_MOUSE_LL = 14
_WIN_WM_MOUSEWHEEL = 0x020A
_WIN_WM_QUIT = 0x0012


def _win_build_input_mode(base_mode: int) -> int:
    mode = base_mode | _WIN_ENABLE_EXTENDED_FLAGS | _WIN_ENABLE_VIRTUAL_TERMINAL_INPUT
    if _should_capture_mouse():
        mode |= _WIN_ENABLE_MOUSE_INPUT
        mode &= ~_WIN_ENABLE_QUICK_EDIT_MODE
    return mode


def _win_build_mouse_fallback_title(base_title: str, pid: int | None = None) -> str:
    label = base_title.strip() or "Astrid"
    return f"{label} [astrid-wheel:{os.getpid() if pid is None else pid}]"


def _win_extract_mouse_fallback_marker(title: str | None) -> str | None:
    if not title:
        return None
    import re

    match = re.search(r"\[astrid-wheel:\d+\]", title, flags=re.IGNORECASE)
    return match.group(0).casefold() if match else None


def _win_titles_match(expected_title: str | None, foreground_title: str | None) -> bool:
    expected = " ".join((expected_title or "").split()).casefold()
    actual = " ".join((foreground_title or "").split()).casefold()
    if not expected or not actual:
        return False
    expected_marker = _win_extract_mouse_fallback_marker(expected_title)
    actual_marker = _win_extract_mouse_fallback_marker(foreground_title)
    if expected_marker and actual_marker and expected_marker == actual_marker:
        return True
    return expected in actual or actual in expected


def _win_drain_mouse_fallback_events(
    pending: queue.SimpleQueue[WheelEvent] | None,
) -> list[WheelEvent]:
    events: list[WheelEvent] = []
    if pending is None:
        return events
    while True:
        try:
            events.append(pending.get_nowait())
        except queue.Empty:
            return events


def _win_call_next_hook_ex(user32: Any, n_code: int, w_param: int, l_param: int) -> int:
    return int(user32.CallNextHookEx(None, n_code, w_param, l_param))


def _win_translate_console_mouse_event(event_flags: int, button_state: int) -> WheelEvent | None:
    if event_flags != _WIN_MOUSE_WHEELED:
        return None
    import ctypes

    delta = ctypes.c_short((button_state >> 16) & 0xFFFF).value
    if delta > 0:
        return WheelEvent(direction="up")
    if delta < 0:
        return WheelEvent(direction="down")
    return None


def _win_try_read_console_event() -> ParsedInputEvent | bool | None:
    """Read a non-key Windows console event when one is pending."""
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        import ctypes.wintypes as wintypes

        class _COORD(ctypes.Structure):
            _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

        class _MOUSE_EVENT_RECORD(ctypes.Structure):
            _fields_ = [
                ("dwMousePosition", _COORD),
                ("dwButtonState", wintypes.DWORD),
                ("dwControlKeyState", wintypes.DWORD),
                ("dwEventFlags", wintypes.DWORD),
            ]

        class _KEY_EVENT_RECORD(ctypes.Structure):
            _fields_ = [
                ("bKeyDown", wintypes.BOOL),
                ("wRepeatCount", wintypes.WORD),
                ("wVirtualKeyCode", wintypes.WORD),
                ("wVirtualScanCode", wintypes.WORD),
                ("uChar", wintypes.WCHAR),
                ("dwControlKeyState", wintypes.DWORD),
            ]

        class _EVENT_UNION(ctypes.Union):
            _fields_ = [
                ("KeyEvent", _KEY_EVENT_RECORD),
                ("MouseEvent", _MOUSE_EVENT_RECORD),
            ]

        class _INPUT_RECORD(ctypes.Structure):
            _fields_ = [("EventType", wintypes.WORD), ("Event", _EVENT_UNION)]

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-10)
        if handle in (0, -1):
            return None

        available = wintypes.DWORD()
        if not kernel32.GetNumberOfConsoleInputEvents(handle, ctypes.byref(available)):
            return None
        if available.value == 0:
            return None

        record = _INPUT_RECORD()
        count = wintypes.DWORD()
        if not kernel32.PeekConsoleInputW(handle, ctypes.byref(record), 1, ctypes.byref(count)):
            return None
        if count.value == 0:
            return None
        if record.EventType == _WIN_INPUT_EVENT_KEY:
            return None

        if not kernel32.ReadConsoleInputW(handle, ctypes.byref(record), 1, ctypes.byref(count)):
            return None
        if count.value == 0:
            return None

        if record.EventType == _WIN_INPUT_EVENT_MOUSE:
            wheel = _win_translate_console_mouse_event(
                record.Event.MouseEvent.dwEventFlags,
                record.Event.MouseEvent.dwButtonState,
            )
            return wheel if wheel is not None else False

        return False
    except Exception:
        return None


def _win_read_pipe_chunk() -> str | None:
    """Read available stdin bytes on Windows when running under a VT pipe/ConPTY.

    Returns:
    - decoded text when bytes were available
    - "" when stdin is a pipe but no bytes are currently available
    - None when stdin is not a pipe or probing failed
    """
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        import ctypes.wintypes as wintypes
        import msvcrt

        fd = sys.stdin.fileno()
        handle = msvcrt.get_osfhandle(fd)
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        if kernel32.GetFileType(handle) != _WIN_FILE_TYPE_PIPE:
            return None

        available = wintypes.DWORD()
        if not kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
            return None
        if available.value == 0:
            return ""

        raw = os.read(fd, available.value)
        while True:
            if not kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
                break
            if available.value == 0:
                break
            more = os.read(fd, available.value)
            if not more:
                break
            raw += more
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def _win_stdin_is_pipe() -> bool:
    if sys.platform != "win32":
        return False

    try:
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(sys.stdin.fileno())
        return ctypes.windll.kernel32.GetFileType(handle) == _WIN_FILE_TYPE_PIPE  # type: ignore[attr-defined]
    except Exception:
        return False


def _win_get_console_title() -> str | None:
    if sys.platform != "win32":
        return None

    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(1024)
        length = ctypes.windll.kernel32.GetConsoleTitleW(buffer, len(buffer))  # type: ignore[attr-defined]
        if length <= 0:
            return None
        return buffer.value
    except Exception:
        return None


def _win_set_console_title(title: str) -> bool:
    if sys.platform != "win32":
        return False

    try:
        import ctypes

        return bool(ctypes.windll.kernel32.SetConsoleTitleW(title))  # type: ignore[attr-defined]
    except Exception:
        return False


def _win_get_foreground_window_title() -> str | None:
    if sys.platform != "win32":
        return None

    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return None
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value
    except Exception:
        return None


def _win_get_mouse_fallback_debug_snapshot(
    fallback: "_WindowsMouseWheelFallback | None",
) -> dict[str, Any]:
    return {
        "active": fallback is not None,
        "hookInstalled": getattr(fallback, "_hook_installed", False),
        "sessionTitle": getattr(fallback, "_session_title", None),
        "foregroundTitle": _win_get_foreground_window_title() if sys.platform == "win32" else None,
        "rawCallbacks": getattr(fallback, "_raw_callback_count", 0),
        "matchedCallbacks": getattr(fallback, "_matched_callback_count", 0),
        "callbackForegroundTitle": getattr(fallback, "_last_callback_foreground_title", None),
    }


class _WindowsMouseWheelFallback:
    """Capture wheel input on Windows terminals that expose stdin as a pipe.

    ConPTY-hosted terminals may deliver keyboard input through the stdin pipe
    while dropping real mouse wheel events entirely. A low-level mouse hook
    lets Astrid recover wheel scrolling without relying on the terminal to
    translate those events back into VT sequences.
    """

    def __init__(self) -> None:
        self._events: queue.SimpleQueue[WheelEvent] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None
        self._thread_ready = threading.Event()
        self._stop = threading.Event()
        self._thread_id: int | None = None
        self._hook_installed = False
        self._callback: Any = None
        self._original_title: str | None = None
        self._session_title: str | None = None
        self._raw_callback_count = 0
        self._matched_callback_count = 0
        self._last_callback_foreground_title: str | None = None

    @property
    def events(self) -> queue.SimpleQueue[WheelEvent]:
        return self._events

    def start(self) -> bool:
        if sys.platform != "win32":
            return False

        self._original_title = _win_get_console_title() or ""
        self._session_title = _win_build_mouse_fallback_title(self._original_title)
        _win_set_console_title(self._session_title)

        self._thread = threading.Thread(
            target=self._run,
            name="astrid-win-wheel-hook",
            daemon=True,
        )
        self._thread.start()
        self._thread_ready.wait(timeout=0.5)
        if not self._hook_installed:
            self.stop()
        return self._hook_installed

    def stop(self) -> None:
        self._stop.set()
        if self._thread_id is not None:
            try:
                import ctypes

                ctypes.windll.user32.PostThreadMessageW(  # type: ignore[attr-defined]
                    self._thread_id,
                    _WIN_WM_QUIT,
                    0,
                    0,
                )
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None
        if self._original_title is not None:
            _win_set_console_title(self._original_title)
        self._session_title = None
        self._original_title = None

    def _run(self) -> None:
        try:
            import ctypes
            import ctypes.wintypes as wintypes

            class _POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            class _MSLLHOOKSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("pt", _POINT),
                    ("mouseData", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t),
                ]

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            user32.CallNextHookEx.argtypes = [
                wintypes.HHOOK,
                ctypes.c_int,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.CallNextHookEx.restype = ctypes.c_ssize_t
            low_level_mouse_proc = ctypes.WINFUNCTYPE(
                ctypes.c_ssize_t,
                ctypes.c_int,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )

            def _proc(n_code: int, w_param: int, l_param: int) -> int:
                if n_code >= 0 and w_param == _WIN_WM_MOUSEWHEEL and self._session_title:
                    self._raw_callback_count += 1
                    foreground_title = _win_get_foreground_window_title()
                    self._last_callback_foreground_title = foreground_title
                    if _win_titles_match(self._session_title, foreground_title):
                        self._matched_callback_count += 1
                        mouse = ctypes.cast(
                            l_param,
                            ctypes.POINTER(_MSLLHOOKSTRUCT),
                        ).contents
                        delta = ctypes.c_short((mouse.mouseData >> 16) & 0xFFFF).value
                        if delta > 0:
                            self._events.put(WheelEvent(direction="up"))
                        elif delta < 0:
                            self._events.put(WheelEvent(direction="down"))
                return _win_call_next_hook_ex(user32, n_code, w_param, l_param)

            self._callback = low_level_mouse_proc(_proc)
            self._thread_id = kernel32.GetCurrentThreadId()
            hook = user32.SetWindowsHookExW(
                _WIN_WH_MOUSE_LL,
                self._callback,
                None,
                0,
            )
            self._hook_installed = bool(hook)
            self._thread_ready.set()
            if not hook:
                return

            message = wintypes.MSG()
            while not self._stop.is_set():
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result in (0, -1):
                    break
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))

            user32.UnhookWindowsHookEx(hook)
        except Exception:
            logging.debug("Windows wheel fallback hook failed", exc_info=True)
            self._thread_ready.set()


def _maybe_start_windows_mouse_wheel_fallback() -> _WindowsMouseWheelFallback | None:
    if sys.platform != "win32":
        return None
    if _terminal_mode() == "shell":
        return None

    fallback = _WindowsMouseWheelFallback()
    if fallback.start():
        return fallback
    return None


def _read_clipboard_text() -> str:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

            if not user32.OpenClipboard(None):
                return ""
            try:
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    return ""
                pointer = kernel32.GlobalLock(handle)
                if not pointer:
                    return ""
                try:
                    text = ctypes.wstring_at(pointer)
                finally:
                    kernel32.GlobalUnlock(handle)
                return text or ""
            finally:
                user32.CloseClipboard()
        except Exception:
            return ""

    return ""


def _normalize_pasted_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    return normalized


def _insert_input_text(state: ScreenState, text: str) -> bool:
    if not text:
        return False
    state.input = state.input[:state.cursor_offset] + text + state.input[state.cursor_offset:]
    state.cursor_offset += len(text)
    state.selected_slash_index = 0
    state.history_index = len(state.history)
    return True


def _win_read_one_key() -> str:
    """Read one logical key from Windows msvcrt, translating special keys
    into ANSI escape sequences.

    Returns an empty string if no key is available.
    """
    import msvcrt

    if not msvcrt.kbhit():
        return ""

    ch = msvcrt.getwch()

    # Special-key prefix: next char is a scan code
    if ch in ("\x00", "\xe0"):
        if msvcrt.kbhit():
            scan = ord(msvcrt.getwch())
        else:
            # Prefix arrived alone (rare) 鈥?treat as Escape
            return "\x1b"
        return _WIN_SCANCODE_TO_ANSI.get(scan, "")

    # Ctrl+C 鈫?keep as '\x03' so parse_input_chunk handles it
    return ch


def _read_raw_char() -> str:
    """Read a single character from stdin in raw mode, cross-platform."""
    if sys.platform == "win32":
        return _win_read_one_key()
    else:
        import select

        fd = sys.stdin.fileno()
        ready, _, _ = select.select([fd], [], [], 0.05)
        if ready:
            # Use os.read() to bypass Python's TextIOWrapper buffering.
            # In raw/cbreak mode the kernel returns whatever bytes are
            # available, so os.read() won't block.
            data = os.read(fd, 4096)
            return data.decode("utf-8", errors="replace") if data else ""
        return ""


def _read_raw_chunk() -> str:
    """Read all available raw chars as a single chunk."""
    if sys.platform == "win32":
        result = ""
        while True:
            ch = _win_read_one_key()
            if not ch:
                break
            result += ch
        return result
    else:
        import select

        fd = sys.stdin.fileno()
        # First wait with a timeout for initial data
        ready, _, _ = select.select([fd], [], [], 0.05)
        if not ready:
            return ""
        # Read all available bytes in one go.  In raw mode the kernel
        # delivers whatever has arrived so far; os.read() returns
        # immediately with 1..N bytes.
        data = os.read(fd, 4096)
        if not data:
            return ""
        # Drain any remaining bytes without blocking
        while True:
            ready2, _, _ = select.select([fd], [], [], 0)
            if not ready2:
                break
            more = os.read(fd, 4096)
            if not more:
                break
            data += more
        return data.decode("utf-8", errors="replace")


class _RawModeContext:
    """Context manager for raw terminal mode.

    On Unix: switches stdin to raw mode via termios/tty and restores on exit.
    On Windows: msvcrt provides character-at-a-time input natively, but we
    need to ensure the console code page is set for UTF-8 and VT processing
    is enabled.
    """

    def __init__(self) -> None:
        self._old_settings: Any = None
        self._old_cp: int | None = None
        self._old_input_mode: int | None = None

    def __enter__(self) -> _RawModeContext:
        if sys.platform == "win32":
            # Ensure VT processing is active (idempotent)
            from astrid.tui.screen import _enable_windows_vt_processing
            _enable_windows_vt_processing()
            # Switch console to UTF-8 code page for proper Unicode handling
            try:
                import ctypes
                import ctypes.wintypes as wintypes
                kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
                self._old_cp = kernel32.GetConsoleOutputCP()
                kernel32.SetConsoleOutputCP(65001)  # UTF-8

                h_in = kernel32.GetStdHandle(-10)
                mode_in = wintypes.DWORD()
                if kernel32.GetConsoleMode(h_in, ctypes.byref(mode_in)):
                    self._old_input_mode = mode_in.value
                    kernel32.SetConsoleMode(h_in, _win_build_input_mode(mode_in.value))
            except Exception:
                pass
        else:
            import termios

            fd = sys.stdin.fileno()
            self._old_settings = termios.tcgetattr(fd)
            new = termios.tcgetattr(fd)
            # Input flags: disable CR鈫扤L translation and XON/XOFF flow control,
            # strip high bit, and break signal generation.
            new[0] &= ~(
                termios.BRKINT | termios.ICRNL | termios.INPCK
                | termios.ISTRIP | termios.IXON
            )
            # Output flags: KEEP OPOST so that \n 鈫?\r\n translation still
            # works.  tty.setraw() clears OPOST which causes "staircase"
            # output on Linux/macOS 鈥?every newline only moves down without
            # returning the cursor to column 0.
            # new[1] is intentionally left untouched.
            # Control flags: set 8-bit chars
            new[2] &= ~(termios.CSIZE | termios.PARENB)
            new[2] |= termios.CS8
            # Local flags: disable echo, canonical mode, extended processing,
            # and signal generation from keys (Ctrl-C, Ctrl-Z).
            new[3] &= ~(
                termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG
            )
            # Special characters: read returns after 1 byte, no timeout.
            new[6][termios.VMIN] = 1
            new[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSAFLUSH, new)
        return self

    def __exit__(self, *_: Any) -> None:
        if sys.platform == "win32":
            if self._old_cp is not None:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetConsoleOutputCP(self._old_cp)  # type: ignore[attr-defined]
                except Exception:
                    pass
            if self._old_input_mode is not None:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetConsoleMode(  # type: ignore[attr-defined]
                        ctypes.windll.kernel32.GetStdHandle(-10),  # type: ignore[attr-defined]
                        self._old_input_mode,
                    )
                except Exception:
                    pass
        elif self._old_settings is not None:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_settings)


# ---------------------------------------------------------------------------
# Tool shortcut execution
# ---------------------------------------------------------------------------


def _execute_tool_shortcut(
    args: TtyAppArgs,
    state: ScreenState,
    tool_name: str,
    tool_input: Any,
    rerender: Callable[[], None],
) -> None:
    state.is_busy = True
    summary = _summarize_tool_input(tool_name, tool_input)
    _set_single_agent_busy_state(
        state,
        verb="Running",
        summary=summary,
        status=f"Running {tool_name}...",
    )
    state.active_tool = tool_name
    entry_id = _push_transcript_entry(
        state,
        kind="tool",
        toolName=tool_name,
        status="running",
        body=summary,
        actionSummary=summary,
    )
    rerender()

    try:
        result = args.tools.execute(
            tool_name,
            tool_input,
            context=ToolContext(cwd=args.cwd, permissions=args.permissions),
        )
        state.recent_tools.append({
            "name": tool_name,
            "status": "success" if result.ok else "error",
        })
        output = result.output if result.ok else f"ERROR: {result.output}"
        _update_tool_entry(state, entry_id, "success" if result.ok else "error", output)
        _collapse_tool_entry(state, entry_id, _summarize_collapsed_tool_body(output))
        # Don't reset scroll offset 鈥?respect user's manual scroll position
    finally:
        state.is_busy = False
        state.active_tool = None
        state.current_action_summary = None
        _finalize_dangling_running_tools(state)
        if not _get_running_tool_entries(state):
            state.status = None
        _drain_next_queued_turn(args, state, rerender)


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


def _handle_input(
    args: TtyAppArgs,
    state: ScreenState,
    rerender: Callable[[], None],
    submitted_raw_input: str | None = None,
) -> bool:
    """Returns True if /exit was typed."""
    input_text = (submitted_raw_input if submitted_raw_input is not None else state.input).strip()
    if state.is_busy:
        _enqueue_next_turn(state, input_text)
        return False

    terminal_mode = _terminal_mode()
    if not input_text:
        return False
    if input_text == "/exit":
        return True
    if not _has_non_welcome_transcript_entries(state):
        _sync_welcome_transcript_entry(args, state)

    # History
    if not state.history or state.history[-1] != input_text:
        state.history.append(input_text)
        save_history_entries(state.history, args.cwd)
    state.history_index = len(state.history)
    state.history_draft = ""

    # Autosave trigger
    if state.autosave:
        state.autosave.mark_dirty()

    # /tools
    if input_text == "/tools":
        _push_transcript_entry(
            state,
            kind="assistant",
            body="\n".join(
                f"{t.name}: {t.description}" for t in args.tools.list()
            ),
        )
        return False

    # /debug 鈥?show scroll diagnostics
    if input_text == "/debug":
        from astrid.tui.transcript import _compute_total_lines
        cols, rows = _get_terminal_size()
        compact = _is_compact_terminal()
        viewport_lines = max(8, rows)
        document = _build_simple_page_flow_document(args, state, include_scroll_hint=False)
        document_lines = len(_split_rendered_lines(document))
        total_lines = _compute_total_lines(state.transcript, separator_lines=[""])
        max_scroll = max(0, document_lines - viewport_lines)
        lines = [
            "=== Scroll Debug ===",
            f"Terminal: {cols}x{rows}  compact={compact}",
            "Primary view: page-flow",
            f"Viewport window: {viewport_lines} lines",
            f"Rendered document: {document_lines} lines",
            f"Transcript total: {total_lines} lines",
            f"Scroll offset: {state.transcript_scroll_offset}/{max_scroll}",
            f"Mouse tracking: ESC[?1000h ESC[?1003h ESC[?1006h",
            f"Wheel events seen: {state.wheel_debug_event_count}",
            f"Last wheel direction: {state.wheel_debug_last_direction or 'none'}",
            f"Windows fallback active: {state.wheel_debug_fallback_active}",
            f"Windows fallback hook: {state.wheel_debug_fallback_hook}",
            f"Windows session title: {state.wheel_debug_session_title or 'n/a'}",
            f"Windows foreground title: {state.wheel_debug_foreground_title or 'n/a'}",
            f"Windows raw wheel callbacks: {state.wheel_debug_raw_callback_count}",
            f"Windows matched wheel callbacks: {state.wheel_debug_matched_callback_count}",
            f"Windows callback fg title: {state.wheel_debug_callback_foreground_title or 'n/a'}",
            "",
            "Try scrolling now. If scroll_offset changes, mouse events work.",
            "Use PageUp/PageDown or Ctrl+A/E as keyboard alternatives.",
        ]
        _push_transcript_entry(state, kind="assistant", body="\n".join(lines))
        return False

    companion_result = _handle_companion_command(state, input_text)
    if companion_result is not None:
        _push_transcript_entry(state, kind="assistant", body=companion_result)
        return False

    # Local commands
    local_result = try_handle_local_command(input_text, tools=args.tools)
    if local_result is not None:
        _push_transcript_entry(state, kind="assistant", body=local_result)
        return False

    # Tool shortcuts
    shortcut = parse_local_tool_shortcut(input_text)
    if shortcut:
        _execute_tool_shortcut(
            args, state, shortcut["toolName"], shortcut["input"], rerender
        )
        return False

    # Unknown slash commands
    if input_text.startswith("/"):
        matches = find_matching_slash_commands(input_text)
        _push_transcript_entry(
            state,
            kind="assistant",
            body=(
                f"Unknown command. Did you mean:\n{chr(10).join(matches)}"
                if matches
                else "Unknown command. Type /help to see available commands."
            ),
        )
        return False

    # Agent turn
    _push_transcript_entry(state, kind="user", body=input_text)
    state.transcript_scroll_offset = 0
    state.is_busy = True
    _set_single_agent_busy_state(
        state,
        verb=_SINGLE_AGENT_DEFAULT_VERB,
        summary="reviewing request",
        status="Thinking...",
    )
    
    # Update app state
    if state.app_state:
        from astrid.state import set_busy
        state.app_state.set_state(set_busy())
    
    rerender()

    pending_tool_entries: dict[str, list[int]] = defaultdict(list)
    aggregated_edit_by_key: dict[str, AggregatedEditProgress] = {}
    aggregated_edit_by_entry_id: dict[int, AggregatedEditProgress] = {}

    if hasattr(args.tools, "refresh_capabilities"):
        args.tools.refresh_capabilities()

    # Refresh system prompt
    args.messages[0] = {
        "role": "system",
        "content": build_system_prompt(
            args.cwd,
            args.permissions.get_summary(),
            {
                "skills": args.tools.get_skills(),
                "mcpServers": args.tools.get_mcp_servers(),
            },
        ),
    }
    args.messages.append({"role": "user", "content": input_text})
    use_multi_agent = _is_multi_agent_candidate(input_text)
    if use_multi_agent:
        _begin_orchestration(state, input_text)
        state.sub_agent_manager = SubAgentManager(
            parent_session_id=state.session.session_id if state.session else "live-session",
            app_state=state.app_state,
        )

    def on_assistant_message(content: str) -> None:
        _set_single_agent_busy_state(
            state,
            verb="Answering",
            summary="drafting final response",
        )
        _prune_completed_progress_entries(state)
        _push_transcript_entry(state, kind="assistant", body=content)
        # Don't reset scroll offset 鈥?respect user's manual scroll position
        rerender()

    def on_progress_message(content: str) -> None:
        verb, summary = _summarize_progress_update(content)
        _set_single_agent_busy_state(
            state,
            verb=verb,
            summary=summary,
            status=f"{verb}...",
        )
        if _should_record_progress_entries(terminal_mode):
            _push_transcript_entry(
                state,
                kind="progress",
                body=content,
                actionSummary=summary,
                phaseVerb=verb,
            )
        # Don't reset scroll offset 鈥?respect user's manual scroll position
        rerender()

    def on_tool_start(tool_name: str, tool_input: Any) -> None:
        summary = _summarize_tool_input(tool_name, tool_input)
        _set_single_agent_busy_state(
            state,
            verb="Running",
            summary=summary,
            status=f"Running {tool_name}...",
        )
        state.active_tool = tool_name
        state.tool_start_time = time.monotonic()  # 璁板綍宸ュ叿鍚姩鏃堕棿

        target_path = _extract_path_from_tool_input(tool_input)
        can_aggregate = _is_file_edit_tool(tool_name) and target_path is not None

        if can_aggregate:
            key = f"{tool_name}:{target_path}"
            existing = aggregated_edit_by_key.get(key)
            if existing:
                existing.total += 1
                existing.last_output = _summarize_tool_input(tool_name, tool_input)
                entry_id = existing.entry_id
                _update_tool_entry(
                    state,
                    entry_id,
                    "error" if existing.errors > 0 else "running",
                    f"Aggregated {tool_name} for {target_path}\nCompleted: {existing.completed}/{existing.total}",
                )
            else:
                entry_id = _push_transcript_entry(
                    state,
                    kind="tool",
                    toolName=tool_name,
                    status="running",
                    body=summary,
                    actionSummary=summary,
                )
                progress = AggregatedEditProgress(
                    entry_id=entry_id,
                    tool_name=tool_name,
                    path=target_path,
                    total=1,
                    completed=0,
                    errors=0,
                    last_output=summary,
                )
                aggregated_edit_by_key[key] = progress
                aggregated_edit_by_entry_id[entry_id] = progress
        else:
            entry_id = _push_transcript_entry(
                state,
                kind="tool",
                toolName=tool_name,
                status="running",
                body=summary,
                actionSummary=summary,
            )

        pending_tool_entries[tool_name].append(entry_id)
        # Don't reset scroll offset 鈥?respect user's manual scroll position
        rerender()

    def on_tool_result(tool_name: str, output: str, is_error: bool) -> None:
        # 璁＄畻骞舵樉绀哄伐鍏锋墽琛屾椂闂?        elapsed = ""
        if state.tool_start_time is not None:
            elapsed_secs = time.monotonic() - state.tool_start_time
            if elapsed_secs > 1:
                elapsed = f" ({elapsed_secs:.1f}s)"
        
        pending = pending_tool_entries.get(tool_name, [])
        entry_id = pending.pop(0) if pending else None
        if entry_id is not None:
            aggregated = aggregated_edit_by_entry_id.get(entry_id)
            if aggregated and aggregated.tool_name == tool_name:
                aggregated.completed += 1
                if is_error:
                    aggregated.errors += 1
                aggregated.last_output = output
                done = aggregated.completed >= aggregated.total
                if done:
                    state.recent_tools.append({
                        "name": f"{tool_name} x{aggregated.total}",
                        "status": "error" if aggregated.errors > 0 else "success",
                    })
                body = (
                    "\n".join([
                        f"Aggregated {tool_name} for {aggregated.path}",
                        f"Operations: {aggregated.total}, errors: {aggregated.errors}",
                        f"Last result: {aggregated.last_output}",
                    ])
                    if done
                    else f"Aggregated {tool_name} for {aggregated.path}\nCompleted: {aggregated.completed}/{aggregated.total}"
                )
                _update_tool_entry(
                    state,
                    entry_id,
                    "error" if aggregated.errors > 0 else ("success" if done else "running"),
                    body,
                )
                if done:
                    _collapse_tool_entry(state, entry_id, _summarize_collapsed_tool_body(body))
                    aggregated_edit_by_entry_id.pop(entry_id, None)
                    aggregated_edit_by_key.pop(f"{tool_name}:{aggregated.path}", None)
            else:
                state.recent_tools.append({
                    "name": tool_name,
                    "status": "error" if is_error else "success",
                })
                
                # Error recovery hints (plain text, no emoji)
                display_output = output
                if is_error:
                    suggestions = []
                    output_lower = output.lower()
                    if "not found" in output_lower or "no such file" in output_lower:
                        suggestions.append("Hint: file not found 鈥?use /ls to list files")
                    elif "permission" in output_lower or "denied" in output_lower:
                        suggestions.append("Hint: permission denied 鈥?check file access rights")
                    elif "syntax" in output_lower or "error" in output_lower:
                        suggestions.append("Hint: error occurred 鈥?review output and fix issues")

                    if suggestions:
                        display_output = f"ERROR: {output}\n\n" + "\n".join(suggestions)
                    else:
                        display_output = f"ERROR: {output}"
                
                _update_tool_entry(
                    state,
                    entry_id,
                    "error" if is_error else "success",
                    display_output,
                )
                _schedule_tool_auto_collapse(
                    state,
                    entry_id,
                    display_output,
                    rerender,
                )

        state.active_tool = None
        _set_single_agent_busy_state(
            state,
            verb="Collecting",
            summary=f"{tool_name} finished: {_summarize_collapsed_tool_body(output)}",
        )
        remaining = sum(len(v) for v in pending_tool_entries.values())
        if remaining > 0:
            state.status = f"{remaining} tool(s) still running..."
        else:
            state.status = None
        # Don't reset scroll offset 鈥?respect user's manual scroll position
        rerender()

    args.permissions.begin_turn()
    
    # Run agent turn in background thread to keep UI responsive
    agent_error = None
    agent_result: dict = {"messages": None}
    agent_thread_lock = threading.Lock()

    def _make_worker_callbacks(
        worker_id: str,
        worker_name: str,
    ) -> tuple[
        Callable[[str], None],
        Callable[[str], None],
        Callable[[str, dict], None],
        Callable[[str, str, bool], None],
    ]:
        def _worker_assistant(content: str) -> None:
            _set_worker_state(
                state,
                worker_id,
                latest_event=f"reported: {content.splitlines()[0][:80]}",
            )
            rerender()

        def _worker_progress(content: str) -> None:
            _set_worker_state(
                state,
                worker_id,
                latest_event=f"thinking: {content.splitlines()[0][:80]}",
            )
            rerender()

        def _worker_tool_start(tool_name: str, tool_input: dict) -> None:
            summary = _summarize_tool_input(tool_name, tool_input)
            _set_worker_state(
                state,
                worker_id,
                status=WorkerRuntimeState.RUNNING,
                latest_event=summary[:100],
            )
            state.status = f"{worker_name} running {tool_name}..."
            rerender()

        def _worker_tool_result(tool_name: str, output: str, is_error: bool) -> None:
            result_prefix = "error" if is_error else "done"
            first_line = next((line.strip() for line in output.splitlines() if line.strip()), tool_name)
            _set_worker_state(
                state,
                worker_id,
                latest_event=f"{result_prefix}: {first_line[:92]}",
            )
            rerender()

        return _worker_assistant, _worker_progress, _worker_tool_start, _worker_tool_result

    def _run_multi_agent_background() -> None:
        nonlocal agent_error, agent_result
        manager = state.sub_agent_manager
        runtime_state = state.orchestration
        if manager is None or runtime_state is None:
            return

        try:
            worker_specs = [
                (
                    AgentType.EXPLORE,
                    WorkerRole.CONTEXT_SCOUT,
                    "inspect relevant files and summarize code context",
                    "read-only search and context gathering",
                ),
                (
                    AgentType.GENERAL,
                    WorkerRole.CODE_WORKER,
                    "produce implementation changes or a concrete patch strategy",
                    "code modification and execution within current workspace",
                ),
            ]
            completed_summaries: list[str] = []
            reviewer_evidence_blocks: list[str] = []

            for index, (agent_type, role, mission, scope) in enumerate(worker_specs):
                worker_name, color = _pick_worker_name(role, index)
                worker_record = runtime_state.spawn_worker(
                    name=worker_name,
                    role=role,
                    mission=mission,
                    scope=scope,
                    color=color,
                )
                _set_worker_state(
                    state,
                    worker_record.id,
                    status=WorkerRuntimeState.RUNNING,
                    latest_event="starting",
                )
                runtime_state.task_state = TaskRuntimeState.RUNNING
                runtime_state.narrative = f"{worker_name} is working on {role.value}..."
                _sync_orchestration_entry(state)
                rerender()

                callbacks = _make_worker_callbacks(worker_record.id, worker_name)
                instance = manager.spawn_agent(
                    agent_type,
                    (
                        f"{input_text}\n\n"
                        f"Your role: {role.value}.\n"
                        f"Mission: {mission}.\n"
                        f"Scope: {scope}."
                    ),
                )
                instance = manager.execute_agent(
                    instance.id,
                    model=args.model,
                    tools=args.tools,
                    cwd=args.cwd,
                    permissions=args.permissions,
                    on_assistant_message=callbacks[0],
                    on_progress_message=callbacks[1],
                    on_tool_start=callbacks[2],
                    on_tool_result=callbacks[3],
                )
                mark_worker_reported(runtime_state, worker_record.id, instance.result or "")
                _sync_orchestration_entry(state)
                completed_summaries.append(_summarize_worker_result(instance))
                reviewer_evidence_blocks.append(manager.compile_result_summary(instance.id))
                rerender()

            reviewer_name, reviewer_color = _pick_worker_name(WorkerRole.REVIEW_AGENT, 0)
            reviewer_record = runtime_state.spawn_worker(
                name=reviewer_name,
                role=WorkerRole.REVIEW_AGENT,
                mission="validate worker output and highlight risk",
                scope="review collected worker summaries only",
                color=reviewer_color,
            )
            mark_review_required(runtime_state, reviewer_summary="review in progress")
            _set_buddy_reaction(state, "Double-checking the patch", duration=5.0)
            _set_worker_state(
                state,
                reviewer_record.id,
                status=WorkerRuntimeState.RUNNING,
                latest_event="checking worker output",
            )
            _sync_orchestration_entry(state)
            rerender()

            callbacks = _make_worker_callbacks(reviewer_record.id, reviewer_name)
            reviewer_instance = manager.spawn_agent(
                AgentType.PLAN,
                (
                    f"Review the following worker results for the task:\n{input_text}\n\n"
                    + "\n\n".join(reviewer_evidence_blocks)
                    + "\n\nReturn a concise review verdict with risks and confidence."
                ),
            )
            reviewer_instance = manager.execute_agent(
                reviewer_instance.id,
                model=args.model,
                tools=args.tools,
                cwd=args.cwd,
                permissions=args.permissions,
                on_assistant_message=callbacks[0],
                on_progress_message=callbacks[1],
                on_tool_start=callbacks[2],
                on_tool_result=callbacks[3],
            )
            mark_worker_reported(runtime_state, reviewer_record.id, reviewer_instance.result or "")
            runtime_state.task_state = TaskRuntimeState.MERGING
            runtime_state.narrative = "Merging worker output into final response..."
            _set_buddy_reaction(state, "Stitching the results together", duration=5.0)
            _sync_orchestration_entry(state)

            final_summary = "\n".join(completed_summaries + [_summarize_worker_result(reviewer_instance)])
            final_message = "Multi-agent summary\n\n" + final_summary
            _push_transcript_entry(
                state,
                kind="assistant",
                body=final_message,
            )

            for worker_id in list(runtime_state.workers.keys()):
                archive_worker(runtime_state, worker_id)
            _sync_orchestration_entry(state)

            with agent_thread_lock:
                agent_result["messages"] = list(args.messages) + [{"role": "assistant", "content": final_message}]
        except Exception as e:
            agent_error = e
        finally:
            args.permissions.end_turn()
            with agent_thread_lock:
                agent_result["done"] = True
            _prune_completed_progress_entries(state)
            state.is_busy = False
            state.active_tool = None
            state.current_action_summary = None
            state.status = state.orchestration.narrative if state.orchestration else None
            rerender()
    
    def _run_agent_background():
        nonlocal agent_error, agent_result
        try:
            next_messages = run_agent_turn(
                model=args.model,
                tools=args.tools,
                messages=list(args.messages),  # Copy to avoid race condition
                cwd=args.cwd,
                permissions=args.permissions,
                on_tool_start=on_tool_start,
                on_tool_result=on_tool_result,
                on_assistant_message=on_assistant_message,
                on_progress_message=on_progress_message,
            )
            with agent_thread_lock:
                agent_result["messages"] = next_messages
        except Exception as e:
            agent_error = e
        finally:
            args.permissions.end_turn()
            with agent_thread_lock:
                agent_result["done"] = True
            _prune_completed_progress_entries(state)
            state.is_busy = False
            state.active_tool = None
            state.current_action_summary = None
            state.status = None
            rerender()
    
    target = _run_multi_agent_background if use_multi_agent else _run_agent_background
    agent_thread = threading.Thread(target=target, daemon=True)
    agent_thread.start()
    state.agent_thread = agent_thread
    # Assign lock BEFORE result 鈥?the main loop checks agent_result first,
    # so the lock must already be available to avoid AttributeError.
    state.agent_lock = agent_thread_lock
    state.agent_result = agent_result
    
    # Return immediately - agent runs in background
    return False


# ---------------------------------------------------------------------------
# Main event-driven TTY app
# ---------------------------------------------------------------------------


def run_tty_app(
    *,
    runtime: dict | None,
    tools: ToolRegistry,
    model: ModelAdapter,
    messages: list[ChatMessage],
    cwd: str,
    permissions: PermissionManager,
    resume_session: str | None = None,
    list_sessions_only: bool = False,
) -> list[ChatMessage]:
    """Event-driven full-screen TTY application, ported from the TypeScript version.
    
    Args:
        resume_session: Session ID to resume, or "latest" for most recent
        list_sessions_only: If True, print session list and exit
    """

    args = TtyAppArgs(
        runtime=runtime,
        tools=tools,
        model=model,
        messages=messages,
        cwd=cwd,
        permissions=permissions,
    )

    # Session initialization
    session: SessionData | None = None
    
    if list_sessions_only:
        sessions = list_sessions()
        print(format_session_list(sessions))
        return messages
    
    if resume_session:
        if resume_session == "latest":
            session = get_latest_session(workspace=str(Path(cwd).resolve()))
            if session:
                print(format_session_resume(session))
            else:
                print("No previous session found for this workspace.")
                session = create_new_session(workspace=str(Path(cwd).resolve()))
        else:
            session = load_session(resume_session)
            if not session:
                print(f"Session '{resume_session}' not found.")
                return messages
            print(format_session_resume(session))
    else:
        # Check for existing session in current workspace
        session = get_latest_session(workspace=str(Path(cwd).resolve()))
        if session:
            print(f"Previous session found: {session.session_id[:8]}")
            print("Use --resume to continue, or starting fresh session.")
            session = None
    
    if not session:
        session = create_new_session(workspace=str(Path(cwd).resolve()))
    
    # Initialize AppState store (Zustand-style)
    app_state_store = create_app_store({
        "session_id": session.session_id,
        "workspace": cwd,
        "model": runtime.get("model", "unknown") if runtime else "unknown",
    })
    
    # Initialize CostTracker
    cost_tracker = CostTracker()

    state = ScreenState(
        history=load_history_entries(cwd),
        session=session,
        autosave=AutosaveManager(session),
        app_state=app_state_store,
        cost_tracker=cost_tracker,
    )
    _apply_startup_pet_state(state)
    state.history_index = len(state.history)

    # Restore session state if resuming
    if session.messages:
        # Restore messages
        args.messages.clear()
        args.messages.extend(session.messages)
        
        # Restore transcript entries
        for entry_data in session.transcript_entries:
            entry = TranscriptEntry(**entry_data)
            state.transcript.append(entry)
        
        print(f"Restored {len(session.messages)} messages, {len(state.transcript)} transcript entries.")

    # Wire up permission prompt handler
    approval_event = threading.Event()
    approval_result: dict[str, Any] = {}

    def _permission_prompt_handler(request: dict[str, Any]) -> dict[str, Any]:
        nonlocal approval_result
        state.pending_approval = PendingApproval(
            request=request,
            resolve=lambda r: None,
        )
        # Signal the main thread's throttled renderer to show the approval UI.
        # Do NOT call _render_screen() here 鈥?we're on the agent thread and
        # writing to stdout concurrently with the main thread would corrupt
        # the terminal display.  request() only sets a pending flag; the main
        # event loop's next flush() will do the actual render safely.
        rerender()
        approval_event.clear()
        approval_event.wait()
        result = approval_result.copy()
        state.pending_approval = None
        return result

    permissions.prompt = _permission_prompt_handler

    terminal_mode = _terminal_mode()
    use_alternate_screen = _should_use_alternate_screen()
    _has_inline_frame = False
    _inline_line_count = 0
    _native_transcript_ids: tuple[int, ...] = ()
    _native_prompt_line_count = 0
    _screen_writer = _LineDiffScreenWriter(sys.stdout)

    def _render_active_frame() -> None:
        nonlocal _has_inline_frame, _inline_line_count, _native_transcript_ids, _native_prompt_line_count
        write_start = time.perf_counter()
        bytes_written = 0
        if use_alternate_screen:
            frame = _build_screen_simple(args, state)
            rendered = _screen_writer.render(frame, force_full=not _has_inline_frame)
            bytes_written = len(rendered)
        elif terminal_mode == "shell":
            if not _has_non_welcome_transcript_entries(state):
                _sync_welcome_transcript_entry(args, state)
            rendered, _native_transcript_ids, _native_prompt_line_count = _render_agent_frame_update(
                list(state.transcript),
                _native_transcript_ids,
                _build_agent_prompt_region(state),
                _native_prompt_line_count,
            )
            sys.stdout.write(rendered)
            bytes_written = len(rendered)
        else:
            frame = _build_screen_simple(args, state)
            width, _ = _get_terminal_size()
            rendered, _inline_line_count = _render_inline_frame_update(
                frame,
                _inline_line_count if _has_inline_frame else 0,
                width,
            )
            sys.stdout.write(rendered)
            bytes_written = len(rendered)
        sys.stdout.flush()
        _record_tui_profile(
            {
                "terminal_write_ms": round((time.perf_counter() - write_start) * 1000, 3),
                "bytes_written": bytes_written,
            }
        )
        if not use_alternate_screen:
            _has_inline_frame = True
        else:
            _has_inline_frame = True

    # Throttled renderer: coalesces rapid rerender() calls to reduce flickering
    throttled = _ThrottledRenderer(
        _render_active_frame,
        min_interval=_render_throttle_interval(terminal_mode),
    )

    def rerender() -> None:
        throttled.request()

    input_remainder = ""
    should_exit = False
    windows_wheel_fallback = (
        _maybe_start_windows_mouse_wheel_fallback()
        if _should_start_windows_wheel_fallback(terminal_mode)
        else None
    )
    state.wheel_debug_fallback_active = windows_wheel_fallback is not None
    state.wheel_debug_fallback_hook = bool(getattr(windows_wheel_fallback, "_hook_installed", False))
    state.wheel_debug_session_title = getattr(windows_wheel_fallback, "_session_title", None)
    state.wheel_debug_foreground_title = _win_get_foreground_window_title() if sys.platform == "win32" else None
    # Autosave throttle: check at most every ~2 seconds, not every 20ms
    _autosave_counter = 0
    _AUTOSAVE_CHECK_INTERVAL = 100  # iterations (~2s at 20ms polling)
    _last_animation_tick = time.monotonic()

    enter_alternate_screen()
    hide_cursor()

    # On Unix, listen for SIGWINCH so terminal resizes are picked up
    # immediately rather than waiting for the 0.5s cache TTL.
    # signal.signal() can only be called from the main thread.
    _prev_sigwinch = None
    if (
        sys.platform != "win32"
        and threading.current_thread() is threading.main_thread()
    ):
        import signal as _signal

        from astrid.tui.chrome import invalidate_terminal_size_cache

        def _on_sigwinch(_signum: int, _frame: Any) -> None:
            invalidate_terminal_size_cache()
            throttled.request()

        try:
            _prev_sigwinch = _signal.signal(_signal.SIGWINCH, _on_sigwinch)
        except (OSError, ValueError):
            # Couldn't set signal handler (e.g. not main thread despite check)
            _prev_sigwinch = None

    try:
        _render_active_frame()

        with _RawModeContext():
            while not should_exit:
                now = time.monotonic()
                animation_interval = _busy_animation_interval(terminal_mode)
                if (
                    animation_interval is not None
                    and now - _last_animation_tick >= animation_interval
                    and (
                        (
                            state.orchestration is not None
                            and state.orchestration.task_state not in {TaskRuntimeState.DONE, TaskRuntimeState.FAILED}
                        )
                        or (state.is_busy and state.orchestration is None)
                    )
                ):
                    state.animation_frame += 1
                    if state.orchestration is not None:
                        _sync_orchestration_entry(state)
                    throttled.request()
                    _last_animation_tick = now

                if (
                    terminal_mode != "shell"
                    and _should_rotate_welcome_tips()
                    and
                    not state.is_busy
                    and state.orchestration is None
                    and now - state.welcome_tip_rotated_at >= 5.0
                ):
                    state.welcome_tip_index += 1
                    state.welcome_tip_rotated_at = now
                    throttled.request()

                # Autosave check (throttled)
                _autosave_counter += 1
                if state.autosave and _autosave_counter >= _AUTOSAVE_CHECK_INTERVAL:
                    _autosave_counter = 0
                    state.autosave.save_if_needed()
                
                # Check if background agent thread completed
                agent_result_data = state.agent_result
                lock = getattr(state, "agent_lock", None)
                if agent_result_data is not None and lock is not None and agent_result_data.get("done"):
                    with lock:
                        if agent_result_data.get("messages"):
                            args.messages = agent_result_data["messages"]
                        agent_result_data["done"] = False  # Reset flag
                    _drain_next_queued_turn(args, state, rerender)

                # Read raw input
                if sys.platform == "win32":
                    import msvcrt

                    state.wheel_debug_foreground_title = _win_get_foreground_window_title()

                    fallback_events = _win_drain_mouse_fallback_events(
                        windows_wheel_fallback.events if windows_wheel_fallback is not None else None
                    )
                    if fallback_events:
                        for event in fallback_events:
                            try:
                                _handle_event(args, state, event, rerender, approval_event, approval_result)
                                if state.input == "/exit":
                                    raise SystemExit(0)
                            except SystemExit:
                                should_exit = True
                                break
                        if should_exit:
                            continue
                        throttled.flush()
                        continue

                    pipe_chunk = _win_read_pipe_chunk()
                    if pipe_chunk is not None:
                        if not pipe_chunk:
                            throttled.flush()
                            time.sleep(_idle_poll_interval(terminal_mode))
                            continue
                        chunk = pipe_chunk
                    elif windows_wheel_fallback is None and _should_capture_mouse():
                        pending_windows_events: list[ParsedInputEvent] = []
                        while True:
                            win_event = _win_try_read_console_event()
                            if win_event is False:
                                continue
                            if win_event is None:
                                break
                            pending_windows_events.append(win_event)

                        if pending_windows_events:
                            for event in pending_windows_events:
                                try:
                                    _handle_event(args, state, event, rerender, approval_event, approval_result)
                                    if state.input == "/exit":
                                        raise SystemExit(0)
                                except SystemExit:
                                    should_exit = True
                                    break
                            if should_exit:
                                continue
                            throttled.flush()
                            continue

                    if not msvcrt.kbhit():
                        # Flush any deferred renders during idle
                        throttled.flush()
                        time.sleep(_idle_poll_interval(terminal_mode))
                        continue
                    # Use _win_read_one_key to translate special keys
                    chunk = ""
                    while True:
                        ch = _win_read_one_key()
                        if not ch:
                            break
                        chunk += ch
                else:
                    import select

                    _fd = sys.stdin.fileno()
                    ready, _, _ = select.select([_fd], [], [], 0.05)
                    if not ready:
                        # Flush any deferred renders during idle
                        throttled.flush()
                        continue
                    # Use os.read() to bypass Python's TextIOWrapper/
                    # BufferedReader which can block on partial UTF-8
                    # sequences in raw mode.
                    _raw = os.read(_fd, 4096)
                    if not _raw:
                        should_exit = True
                        continue
                    # Drain any remaining bytes without blocking
                    while True:
                        ready2, _, _ = select.select([_fd], [], [], 0)
                        if not ready2:
                            break
                        _more = os.read(_fd, 4096)
                        if not _more:
                            break
                        _raw += _more
                    chunk = _raw.decode("utf-8", errors="replace")

                if not chunk:
                    continue

                parsed = parse_input_chunk(input_remainder + chunk)
                input_remainder = parsed.rest

                for event in parsed.events:
                    try:
                        _handle_event(args, state, event, rerender, approval_event, approval_result)
                        if state.input == "/exit":
                            raise SystemExit(0)
                    except SystemExit:
                        should_exit = True
                        break
                    except Exception as e:
                        # 璁板綍浜嬩欢澶勭悊閿欒锛屼絾涓嶄腑鏂富寰幆
                        logging.debug("Event handling error: %s", e, exc_info=True)

                # Ensure the final state after processing all events is visible
                throttled.flush()

    finally:
        # Restore previous SIGWINCH handler on Unix
        if _prev_sigwinch is not None and sys.platform != "win32":
            import signal as _signal

            _signal.signal(_signal.SIGWINCH, _prev_sigwinch)

        if windows_wheel_fallback is not None:
            windows_wheel_fallback.stop()

        show_cursor()
        exit_alternate_screen()
        if not use_alternate_screen:
            sys.stdout.write("\n")
            sys.stdout.flush()
        
        # Final session save
        if state.session:
            # Update session with current state
            state.session.messages = list(args.messages)
            state.session.transcript_entries = [
                {
                    "id": e.id,
                    "kind": e.kind,
                    "toolName": e.toolName,
                    "status": e.status,
                    "body": e.body,
                    "collapsed": e.collapsed,
                    "collapsedSummary": e.collapsedSummary,
                    "collapsePhase": e.collapsePhase,
                }
                for e in state.transcript
            ]
            state.session.history = state.history
            state.session.permissions_summary = args.permissions.get_summary()
            state.session.skills = args.tools.get_skills()
            state.session.mcp_servers = args.tools.get_mcp_servers()
            
            # Force save
            if state.autosave:
                state.autosave.force_save()
            else:
                save_session(state.session)
            
            print(f"\nSession saved: {state.session.session_id[:8]}")

    return args.messages


def _handle_event(
    args: TtyAppArgs,
    state: ScreenState,
    event: ParsedInputEvent,
    rerender: Callable[[], None],
    approval_event: threading.Event,
    approval_result: dict[str, Any],
) -> None:
    """Process a single parsed input event.
    
    Routes the event to the appropriate handler based on current state:
    - Ctrl+C: Exit immediately
    - Pending approval: Handle permission dialog input
    - Normal mode: Handle input, navigation, and commands
    
    Args:
        args: Application arguments (tools, model, permissions)
        state: Current screen state
        event: Parsed input event from terminal
        rerender: Function to trigger screen redraw
        approval_event: Threading event for approval synchronization
        approval_result: Dict to store approval decision
    """
    # ---------- Ctrl+C 鈫?exit ----------
    # \x03 is parsed as KeyEvent(name='c', ctrl=True) by parse_input_chunk
    # (CTRL_CHAR_TO_NAME maps \x03 鈫?'c', produces KeyEvent not TextEvent)
    if isinstance(event, KeyEvent) and event.ctrl and event.name == "c":
        raise SystemExit(0)
    if isinstance(event, TextEvent) and event.ctrl and event.text == "c":
        raise SystemExit(0)

    # ---------- Pending approval mode ----------
    # Capture locally to avoid TOCTOU 鈥?the agent thread may clear
    # state.pending_approval between our check and the handler's use.
    pending = state.pending_approval
    if pending is not None:
        _handle_pending_approval_event(state, pending, event, rerender, approval_event, approval_result)
        return

    # ---------- Normal mode ----------
    _handle_normal_mode_event(args, state, event, rerender)


# ---------------------------------------------------------------------------
# Pending approval event handlers
# ---------------------------------------------------------------------------


def _handle_pending_approval_event(
    state: ScreenState,
    pending: Any,
    event: ParsedInputEvent,
    rerender: Callable[[], None],
    approval_event: threading.Event,
    approval_result: dict[str, Any],
) -> None:
    """Handle input events while a permission approval is pending.
    
    ``pending`` is captured by the caller to avoid TOCTOU races with the
    agent thread (which may set ``state.pending_approval = None`` after an
    approval event is signalled).
    """
    if pending.feedback_mode:
        _handle_feedback_mode_event(state, event, rerender, approval_event, approval_result)
        return
    
    if isinstance(event, KeyEvent):
        if _handle_pending_approval_key(state, event, rerender, approval_event, approval_result):
            return
    
    if isinstance(event, TextEvent) and not event.ctrl:
        if _handle_pending_approval_text(state, event, rerender, approval_event, approval_result):
            return
    
    if isinstance(event, WheelEvent):
        if not _should_capture_mouse():
            return
        state.wheel_debug_event_count += 1
        state.wheel_debug_last_direction = event.direction
        if _handle_pending_approval_wheel(state, event, rerender):
            return


def _handle_pending_approval_key(
    state: ScreenState,
    event: KeyEvent,
    rerender: Callable[[], None],
    approval_event: threading.Event,
    approval_result: dict[str, Any],
) -> bool:
    """Handle key events during pending approval. Returns True if handled."""
    pending = state.pending_approval
    
    if event.name == "escape":
        approval_result.clear()
        approval_result["decision"] = "deny_once"
        approval_event.set()
        rerender()
        return True
    
    if event.name == "return":
        _confirm_pending_choice(state, rerender, approval_event, approval_result)
        return True
    
    if event.name == "up" and _move_pending_approval_selection(state, -1):
        rerender()
        return True
    
    if event.name == "down" and _move_pending_approval_selection(state, 1):
        rerender()
        return True
    
    if event.name == "pageup" and _scroll_pending_approval_by(state, -5):
        rerender()
        return True
    
    if event.name == "pagedown" and _scroll_pending_approval_by(state, 5):
        rerender()
        return True
    
    # Digit keys for choices
    choices = pending.request.get("choices", [])
    for choice in choices:
        if event.text == choice.get("key"):
            _select_pending_choice(state, choice, rerender, approval_event, approval_result)
            return True
    
    return False


def _handle_pending_approval_text(
    state: ScreenState,
    event: TextEvent,
    rerender: Callable[[], None],
    approval_event: threading.Event,
    approval_result: dict[str, Any],
) -> bool:
    """Handle text events during pending approval. Returns True if handled."""
    pending = state.pending_approval
    
    if event.text == "v" and _toggle_pending_approval_expand(state):
        rerender()
        return True
    
    # Check digit keys for choices
    choices = pending.request.get("choices", [])
    for choice in choices:
        if event.text == choice.get("key"):
            _select_pending_choice(state, choice, rerender, approval_event, approval_result)
            return True
    
    return False


def _handle_pending_approval_wheel(
    state: ScreenState,
    event: WheelEvent,
    rerender: Callable[[], None],
) -> bool:
    """Handle wheel events during pending approval for scrolling. Returns True if handled."""
    if not _should_capture_mouse():
        return False
    delta = 3 if event.direction == "up" else -3
    if _scroll_pending_approval_by(state, delta):
        rerender()
        return True
    return False



def _confirm_pending_choice(
    state: ScreenState,
    rerender: Callable[[], None],
    approval_event: threading.Event,
    approval_result: dict[str, Any],
) -> None:
    """Confirm the selected permission choice."""
    pending = state.pending_approval
    choices = pending.request.get("choices", [])
    
    if choices and 0 <= pending.selected_choice_index < len(choices):
        choice = choices[pending.selected_choice_index]
        _select_pending_choice(state, choice, rerender, approval_event, approval_result)
    else:
        approval_result.clear()
        approval_result["decision"] = "allow_once"
        approval_event.set()
        rerender()


def _select_pending_choice(
    state: ScreenState,
    choice: dict,
    rerender: Callable[[], None],
    approval_event: threading.Event,
    approval_result: dict[str, Any],
) -> None:
    """Select a permission choice and resolve."""
    pending = state.pending_approval
    decision = choice.get("decision", "allow_once")
    
    if decision == "deny_with_feedback":
        pending.feedback_mode = True
        pending.feedback_input = ""
        rerender()
        return
    
    approval_result.clear()
    approval_result["decision"] = decision
    approval_event.set()
    rerender()


# ---------------------------------------------------------------------------
# Normal mode event handlers
# ---------------------------------------------------------------------------


def _handle_normal_mode_event(
    args: TtyAppArgs,
    state: ScreenState,
    event: ParsedInputEvent,
    rerender: Callable[[], None],
) -> None:
    """Handle input events in normal mode (no pending approval)."""
    visible_commands = _get_visible_commands(state.input)
    
    if isinstance(event, KeyEvent):
        if _handle_normal_mode_key(args, state, event, visible_commands, rerender):
            return
    elif isinstance(event, TextEvent):
        if _handle_normal_mode_text(args, state, event, visible_commands, rerender):
            return
    elif isinstance(event, WheelEvent):
        if _handle_normal_mode_wheel(args, state, event, rerender):
            return


def _handle_normal_mode_key(
    args: TtyAppArgs,
    state: ScreenState,
    event: KeyEvent,
    visible_commands: list,
    rerender: Callable[[], None],
) -> bool:
    """Handle key events in normal mode. Returns True if handled."""
    if event.ctrl:
        if event.name == "u":
            state.input = ""
            state.cursor_offset = 0
            state.selected_slash_index = 0
            rerender()
            return True

        if event.name == "a":
            if not state.input:
                if _jump_transcript_to_edge(args, state, "top"):
                    rerender()
                return True
            state.cursor_offset = 0
            rerender()
            return True

        if event.name == "e":
            if not state.input:
                if _jump_transcript_to_edge(args, state, "bottom"):
                    rerender()
                return True
            state.cursor_offset = len(state.input)
            rerender()
            return True

        if event.name == "p":
            if _history_up(state):
                rerender()
            return True

        if event.name == "n":
            if _history_down(state):
                rerender()
            return True

        if event.name == "v":
            pasted = _normalize_pasted_text(_read_clipboard_text())
            if _insert_input_text(state, pasted):
                rerender()
            return True

    # Return 鈫?submit input or select slash command
    if event.name == "return":
        _handle_normal_mode_return(args, state, visible_commands, rerender)
        return True
    
    # Tab 鈫?autocomplete slash command
    if event.name == "tab" and visible_commands:
        _handle_normal_mode_tab(state, visible_commands, rerender)
        return True
    
    # Navigation and editing keys
    if _handle_normal_mode_navigation(state, event, rerender):
        return True
    
    # Ctrl shortcuts (P, N handled in text handler)
    # PageUp/PageDown 鈫?scroll transcript
    if event.name == "pageup":
        handled = _scroll_transcript_by(args, state, 8)
        if handled:
            rerender()
        return True
    
    if event.name == "pagedown":
        handled = _scroll_transcript_by(args, state, -8)
        if handled:
            rerender()
        return True
    
    # Alt+Up / Alt+Down 鈫?scroll transcript (keyboard alternative to mouse wheel)
    if event.name == "up" and event.meta:
        handled = _scroll_transcript_by(args, state, 3)
        if handled:
            rerender()
        return True
    
    if event.name == "down" and event.meta:
        handled = _scroll_transcript_by(args, state, -3)
        if handled:
            rerender()
        return True
    
    # Up/Down arrows (history or command selection)
    if event.name == "up":
        _handle_up_arrow(args, state, visible_commands, rerender)
        return True
    
    if event.name == "down":
        _handle_down_arrow(args, state, visible_commands, rerender)
        return True
    
    return False


def _handle_normal_mode_return(
    args: TtyAppArgs,
    state: ScreenState,
    visible_commands: list,
    rerender: Callable[[], None],
) -> None:
    """Handle Return key in normal mode."""
    if visible_commands and 0 <= state.selected_slash_index < len(visible_commands):
        selected = visible_commands[state.selected_slash_index]
        usage = getattr(selected, "usage", str(selected))
        # Only auto-fill if the current input doesn't already exactly match the
        # selected command. If it already matches, fall through and submit.
        if state.input.strip() != usage:
            state.input = usage
            state.cursor_offset = len(state.input)
            state.selected_slash_index = 0
            rerender()
            return
    
    submitted = state.input
    state.input = ""
    state.cursor_offset = 0
    state.selected_slash_index = 0
    rerender()
    if _handle_input(args, state, rerender, submitted):
        raise SystemExit(0)
    rerender()


def _handle_normal_mode_tab(
    state: ScreenState,
    visible_commands: list,
    rerender: Callable[[], None],
) -> None:
    """Handle Tab key for slash command autocompletion."""
    selected = visible_commands[min(state.selected_slash_index, len(visible_commands) - 1)]
    usage = getattr(selected, "usage", str(selected))
    state.input = usage + " "
    state.cursor_offset = len(state.input)
    state.selected_slash_index = 0
    rerender()


def _handle_normal_mode_navigation(
    state: ScreenState,
    event: KeyEvent,
    rerender: Callable[[], None],
) -> bool:
    """Handle navigation and editing keys. Returns True if handled."""
    if event.name == "backspace" and state.cursor_offset > 0:
        state.input = state.input[:state.cursor_offset - 1] + state.input[state.cursor_offset:]
        state.cursor_offset -= 1
        state.selected_slash_index = 0
        rerender()
        return True
    
    if event.name == "delete" and state.cursor_offset < len(state.input):
        state.input = state.input[:state.cursor_offset] + state.input[state.cursor_offset + 1:]
        state.selected_slash_index = 0
        rerender()
        return True
    
    if event.name == "home":
        state.cursor_offset = 0
        rerender()
        return True
    
    if event.name == "end":
        state.cursor_offset = len(state.input)
        rerender()
        return True
    
    if event.name == "left":
        state.cursor_offset = max(0, state.cursor_offset - 1)
        rerender()
        return True
    
    if event.name == "right":
        state.cursor_offset = min(len(state.input), state.cursor_offset + 1)
        rerender()
        return True
    
    if event.name == "escape":
        state.input = ""
        state.cursor_offset = 0
        state.selected_slash_index = 0
        rerender()
        return True
    
    return False


def _handle_up_arrow(
    args: TtyAppArgs,
    state: ScreenState,
    visible_commands: list,
    rerender: Callable[[], None],
) -> None:
    """Handle Up arrow key."""
    if visible_commands:
        state.selected_slash_index = (state.selected_slash_index - 1 + len(visible_commands)) % len(visible_commands)
        rerender()
    elif _history_up(state):
        rerender()


def _handle_down_arrow(
    args: TtyAppArgs,
    state: ScreenState,
    visible_commands: list,
    rerender: Callable[[], None],
) -> None:
    """Handle Down arrow key."""
    if visible_commands:
        state.selected_slash_index = (state.selected_slash_index + 1) % len(visible_commands)
        rerender()
    elif _history_down(state):
        rerender()


def _handle_normal_mode_text(
    args: TtyAppArgs,
    state: ScreenState,
    event: TextEvent,
    visible_commands: list,
    rerender: Callable[[], None],
) -> bool:
    """Handle text events in normal mode. Returns True if handled."""
    # Regular text input (accept any non-empty text, including multi-byte CJK/emoji)
    if not event.ctrl and event.text:
        if not _insert_input_text(state, event.text):
            return False
        rerender()
        return True
    
    return False


def _handle_normal_mode_wheel(
    args: TtyAppArgs,
    state: ScreenState,
    event: WheelEvent,
    rerender: Callable[[], None],
) -> bool:
    """Handle wheel events in normal mode for scrolling. Returns True if handled."""
    if not _should_capture_mouse():
        return False
    handled = _scroll_transcript_by(args, state, 3 if event.direction == "up" else -3)
    if handled:
        rerender()
        return True
    return False


# ---------------------------------------------------------------------------
# Public API / backward-compatible exports for tests
# ---------------------------------------------------------------------------


def summarize_tool_input(tool_name: str, tool_input: Any) -> str:
    """Generate a human-readable summary of tool input.
    
    Public wrapper around _summarize_tool_input for external callers.
    
    Args:
        tool_name: Name of the tool being called
        tool_input: Input dictionary passed to the tool
        
    Returns:
        Human-readable summary string for display in transcript
    """
    return _summarize_tool_input(tool_name, tool_input)


def summarize_tool_output(tool_name: str, output: str) -> str:
    """Summarize tool output for collapsed display.
    
    Picks the first meaningful line and truncates to 140 characters.
    
    Args:
        tool_name: Name of the tool (unused but kept for API consistency)
        output: Full tool output string
        
    Returns:
        Truncated summary suitable for collapsed tool display
    """
    return _summarize_collapsed_tool_body(output)


def _format_history(entries: list[str], limit: int = 20) -> str:
    """Format recent history entries with 1-based numbers."""
    start = max(0, len(entries) - limit)
    return "\n".join(
        f"{start + i + 1}. {entry}" for i, entry in enumerate(entries[start:])
    )


def _save_transcript(state_obj: Any, cwd: str, permissions: PermissionManager, output_path: str) -> str:
    """Save transcript entries to file. Returns the resolved path string."""
    from astrid.tui.transcript import format_transcript_text

    target = resolve_tool_path(ToolContext(cwd=cwd, permissions=permissions), output_path, "write")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_transcript_text(state_obj.transcript), encoding="utf-8")
    return str(target)


def _apply_tool_result_visual_state(
    entry: TranscriptEntry,
    tool_name: str,
    output: str,
    is_error: bool,
) -> None:
    """Apply tool result visual state to a transcript entry."""
    entry.status = "error" if is_error else "success"
    entry.body = f"ERROR: {output}" if is_error else output
    if is_error:
        entry.collapsed = False
        entry.collapsedSummary = None
        entry.collapsePhase = None
    else:
        entry.collapsed = True
        entry.collapsedSummary = _summarize_collapsed_tool_body(output)
        entry.collapsePhase = 3


def _mark_unfinished_tools(state_obj: Any) -> int:
    """Mark running tool entries as errors and clean up state. Returns count of affected entries."""
    count = 0
    for entry in state_obj.transcript:
        if entry.kind == "tool" and entry.status == "running":
            entry.status = "error"
            entry.body = (
                f"{entry.body}\n\n"
                "ERROR: Tool did not report a final result before the turn ended. "
                "This usually means the command kept running in the background "
                "or the tool lifecycle got out of sync."
            )
            entry.collapsed = False
            entry.collapsedSummary = None
            entry.collapsePhase = None
            state_obj.recent_tools.append({"name": entry.toolName or "unknown", "status": "error"})
            count += 1
    if hasattr(state_obj, "pending_tool_runs"):
        state_obj.pending_tool_runs = {}
    state_obj.active_tool = None
    return count


def _handle_feedback_mode_event(
    state: ScreenState,
    event: ParsedInputEvent,
    rerender: Callable[[], None],
    approval_event: threading.Event,
    approval_result: dict[str, Any],
) -> None:
    """Handle events when in feedback mode (rejection guidance input)."""
    pending = state.pending_approval
    if not pending:
        return

    if isinstance(event, KeyEvent):
        if event.name == "escape":
            pending.feedback_mode = False
            pending.feedback_input = ""
            rerender()
            return
        if event.name == "return":
            approval_result.clear()
            approval_result["decision"] = "deny_with_feedback"
            approval_result["feedback"] = pending.feedback_input
            approval_event.set()
            rerender()
            return
        if event.name == "backspace":
            if pending.feedback_input:
                pending.feedback_input = pending.feedback_input[:-1]
                rerender()
            return

    if isinstance(event, TextEvent) and not event.ctrl:
        pending.feedback_input += event.text
        rerender()

