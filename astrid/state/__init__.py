"""State boundary for Astrid.

Phase one keeps the historic ``from astrid.state import AppState`` API working
while this package becomes the home for persistent/session state modules.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class Store(Generic[T]):
    """Zustand-style state management."""

    def __init__(
        self,
        initial_state: T,
        on_change: Callable[[T, T], None] | None = None,
    ):
        self._state = initial_state
        self._listeners: list[Callable[[], None]] = []
        self._on_change = on_change
        self._update_count = 0

    def get_state(self) -> T:
        return self._state

    def set_state(self, updater: Callable[[T], T]) -> None:
        prev = self._state
        next_state = updater(prev)
        if next_state is prev:
            return
        if self._on_change:
            self._on_change(next_state, prev)
        self._state = next_state
        self._update_count += 1
        for listener in self._listeners:
            try:
                listener()
            except Exception:
                pass

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe():
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    @property
    def update_count(self) -> int:
        return self._update_count

    @property
    def subscriber_count(self) -> int:
        return len(self._listeners)


@dataclass
class AppState:
    session_id: str = ""
    workspace: str = ""
    model: str = "unknown"
    message_count: int = 0
    tool_call_count: int = 0
    token_usage: int = 0
    context_window_size: int = 128_000
    context_usage_percentage: float = 0.0
    total_cost_usd: float = 0.0
    api_calls: int = 0
    api_errors: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    is_busy: bool = False
    active_tool: str | None = None
    status_message: str = ""
    verbose: bool = False
    skills_enabled: bool = True
    mcp_enabled: bool = True
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_timestamp(self) -> None:
        self.last_updated = time.time()


def create_app_store(
    initial: dict[str, Any] | None = None,
    on_change: Callable[[AppState, AppState], None] | None = None,
) -> Store[AppState]:
    state = AppState()
    if initial:
        for key, value in initial.items():
            if hasattr(state, key):
                setattr(state, key, value)
    return Store(state, on_change)


def format_app_state_summary(state: AppState) -> str:
    lines = [
        "Application State",
        "=" * 50,
        "",
        "Session:",
        f"  ID: {state.session_id[:8] if state.session_id else 'new'}",
        f"  Model: {state.model}",
        f"  Workspace: {state.workspace}",
        "",
        "Context:",
        f"  Messages: {state.message_count}",
        f"  Tool calls: {state.tool_call_count}",
        f"  Tokens: {state.token_usage:,} / {state.context_window_size:,} "
        f"({state.context_usage_percentage:.1f}%)",
        "",
        "Cost:",
        f"  Total: ${state.total_cost_usd:.4f}",
        f"  API calls: {state.api_calls}",
        f"  API errors: {state.api_errors}",
        "",
        "Tasks:",
        f"  Active: {state.active_tasks}",
        f"  Completed: {state.completed_tasks}",
        "",
        "Status:",
        f"  Busy: {'Yes' if state.is_busy else 'No'}",
        f"  Active tool: {state.active_tool or 'none'}",
        f"  Message: {state.status_message or 'ready'}",
    ]
    return "\n".join(lines)


def update_message_count(count: int) -> Callable[[AppState], AppState]:
    def updater(state: AppState) -> AppState:
        state.message_count = count
        state.update_timestamp()
        return state

    return updater


def increment_tool_calls() -> Callable[[AppState], AppState]:
    def updater(state: AppState) -> AppState:
        state.tool_call_count += 1
        state.update_timestamp()
        return state

    return updater


def update_context_usage(tokens: int, window_size: int | None = None) -> Callable[[AppState], AppState]:
    def updater(state: AppState) -> AppState:
        state.token_usage = tokens
        if window_size is not None:
            state.context_window_size = window_size
        if state.context_window_size > 0:
            state.context_usage_percentage = tokens / state.context_window_size * 100
        state.update_timestamp()
        return state

    return updater


def add_cost(cost_usd: float) -> Callable[[AppState], AppState]:
    def updater(state: AppState) -> AppState:
        state.total_cost_usd += cost_usd
        state.api_calls += 1
        state.update_timestamp()
        return state

    return updater


def record_api_error() -> Callable[[AppState], AppState]:
    def updater(state: AppState) -> AppState:
        state.api_errors += 1
        state.api_calls += 1
        state.update_timestamp()
        return state

    return updater


def set_busy(tool_name: str | None = None) -> Callable[[AppState], AppState]:
    def updater(state: AppState) -> AppState:
        state.is_busy = True
        state.active_tool = tool_name
        state.status_message = f"Running {tool_name}..." if tool_name else "Working..."
        state.update_timestamp()
        return state

    return updater


def set_idle() -> Callable[[AppState], AppState]:
    def updater(state: AppState) -> AppState:
        state.is_busy = False
        state.active_tool = None
        state.status_message = "Ready"
        state.update_timestamp()
        return state

    return updater
