from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def normalize_pasted_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def clear_paste_display(state: Any) -> None:
    state.paste_display_start = None
    state.paste_display_end = None
    state.paste_display_line_count = 0


def has_valid_paste_display(state: Any) -> bool:
    return (
        state.paste_display_start is not None
        and state.paste_display_end is not None
        and 0 <= state.paste_display_start <= state.paste_display_end <= len(state.input)
    )


def insert_input_text(state: Any, text: str) -> bool:
    if not text:
        return False
    insert_at = state.cursor_offset
    state.input = state.input[: state.cursor_offset] + text + state.input[state.cursor_offset :]
    state.cursor_offset += len(text)
    if has_valid_paste_display(state):
        text_len = len(text)
        if insert_at <= state.paste_display_start:
            state.paste_display_start += text_len
            state.paste_display_end += text_len
        elif insert_at < state.paste_display_end:
            clear_paste_display(state)
    state.selected_slash_index = 0
    state.history_index = len(state.history)
    return True


def insert_paste_text(state: Any, raw_text: str) -> bool:
    pasted = normalize_pasted_text(raw_text)
    paste_start = state.cursor_offset
    if not insert_input_text(state, pasted):
        return False
    if "\n" in pasted:
        state.paste_display_start = paste_start
        state.paste_display_end = paste_start + len(pasted)
        state.paste_display_line_count = len(pasted.splitlines()) or 1
    return True


def adjust_paste_display_after_delete(state: Any, delete_at: int) -> None:
    if not has_valid_paste_display(state):
        return
    if delete_at < state.paste_display_start:
        state.paste_display_start -= 1
        state.paste_display_end -= 1
    elif delete_at < state.paste_display_end:
        clear_paste_display(state)


def delete_paste_block_before_cursor(state: Any) -> bool:
    if not has_valid_paste_display(state):
        return False
    if state.paste_display_start < state.cursor_offset <= state.paste_display_end:
        start = state.paste_display_start
        end = state.paste_display_end
        state.input = state.input[:start] + state.input[end:]
        state.cursor_offset = start
        clear_paste_display(state)
        state.selected_slash_index = 0
        return True
    return False


def delete_paste_block_at_cursor(state: Any) -> bool:
    if not has_valid_paste_display(state):
        return False
    if state.paste_display_start <= state.cursor_offset < state.paste_display_end:
        start = state.paste_display_start
        end = state.paste_display_end
        state.input = state.input[:start] + state.input[end:]
        state.cursor_offset = start
        clear_paste_display(state)
        state.selected_slash_index = 0
        return True
    return False


def cursor_at_paste_start(state: Any) -> bool:
    return has_valid_paste_display(state) and state.cursor_offset == state.paste_display_start


def cursor_at_paste_end(state: Any) -> bool:
    return has_valid_paste_display(state) and state.cursor_offset == state.paste_display_end
