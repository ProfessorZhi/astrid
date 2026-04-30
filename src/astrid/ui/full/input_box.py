from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FullInputSnapshot:
    value: str
    cursor: int
    display: str
    display_cursor: int


def render_input_snapshot(value: str, cursor: int, *, display: str | None = None, display_cursor: int | None = None) -> FullInputSnapshot:
    return FullInputSnapshot(
        value=value,
        cursor=max(0, min(cursor, len(value))),
        display=value if display is None else display,
        display_cursor=max(0, display_cursor if display_cursor is not None else cursor),
    )
