from __future__ import annotations

import threading
import time
from collections.abc import Callable


class ThrottledRenderer:
    """Coalesce rapid rerender requests onto the main UI thread."""

    __slots__ = ("_render_fn", "_min_interval", "_pending", "_last_render_time", "_lock")

    def __init__(self, render_fn: Callable[[], None], min_interval: float = 0.033) -> None:
        self._render_fn = render_fn
        self._min_interval = min_interval
        self._pending = False
        self._last_render_time: float = 0.0
        self._lock = threading.Lock()

    def request(self) -> None:
        with self._lock:
            self._pending = True

    def flush(self) -> None:
        now = time.monotonic()
        with self._lock:
            if not self._pending:
                return
            if now - self._last_render_time < self._min_interval:
                return
            self._pending = False
            self._last_render_time = now
        self._render_fn()

    def force(self) -> None:
        with self._lock:
            self._pending = False
            self._last_render_time = time.monotonic()
        self._render_fn()


def busy_animation_interval(terminal_mode: str) -> float | None:
    if terminal_mode == "shell":
        return None
    return 0.25


def idle_poll_interval(terminal_mode: str) -> float:
    if terminal_mode == "shell":
        return 0.1
    return 0.05


def render_throttle_interval(terminal_mode: str) -> float:
    if terminal_mode == "shell":
        return 0.08
    return 0.016


def should_skip_agent_frame_update(
    transcript_ids: tuple[int, ...],
    rendered_ids: tuple[int, ...],
    prompt_body: str,
    previous_prompt_body: str,
) -> bool:
    return transcript_ids == rendered_ids and prompt_body == previous_prompt_body
