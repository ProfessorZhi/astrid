from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from astrid.core.orchestration import OrchestratorState
from astrid.core.sub_agents import SubAgentManager
from astrid.core.types import ChatMessage, ModelAdapter
from astrid.core.tooling import ToolRegistry
from astrid.runtime.controller import RuntimeController
from astrid.runtime.cost_tracker import CostTracker
from astrid.runtime.permissions import PermissionManager
from astrid.state import AppState, Store
from astrid.state.session import AutosaveManager, SessionData
from astrid.tui.buddy_state import BuddyProfile, BuddyRuntimeState
from astrid.tui.types import TranscriptEntry


@dataclass
class TtyAppArgs:
    runtime: dict | None
    tools: ToolRegistry
    model: ModelAdapter
    messages: list[ChatMessage]
    cwd: str
    permissions: PermissionManager
    controller: RuntimeController | None = None


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
    paste_display_start: int | None = None
    paste_display_end: int | None = None
    paste_display_line_count: int = 0
    queued_inputs: list[str] = field(default_factory=list)
    steering_inputs: list[str] = field(default_factory=list)
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
    session: SessionData | None = None
    autosave: AutosaveManager | None = None
    app_state: Store[AppState] | None = None
    cost_tracker: CostTracker | None = None
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
    ctrl_c_exit_armed: bool = False
