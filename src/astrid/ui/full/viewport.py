from __future__ import annotations


def slice_content_lines(
    lines: list[str],
    scroll_offset: int,
    window_size: int,
    *,
    subtle: str = "",
    reset: str = "",
) -> list[str]:
    window_size = max(1, window_size)
    max_offset = max(0, len(lines) - window_size)
    offset = max(0, min(scroll_offset, max_offset))
    if offset > 0:
        content_window_size = max(1, window_size - 1)
        end = min(len(lines), content_window_size + offset + 1)
        start = max(0, end - content_window_size)
        visible = list(lines[start:end])
        visible.append(f"{subtle}── scroll {offset}/{max_offset} (PgUp/PgDn or scroll)──{reset}")
        return visible
    end = len(lines)
    start = max(0, end - window_size)
    return lines[start:end]


def slice_top_anchored_content_lines(
    lines: list[str],
    scroll_offset: int,
    window_size: int,
    *,
    subtle: str = "",
    reset: str = "",
) -> list[str]:
    window_size = max(1, window_size)
    max_offset = max(0, len(lines) - window_size)
    offset = max(0, min(scroll_offset, max_offset))
    if offset <= 0:
        return lines[:window_size]
    return slice_content_lines(lines, offset, window_size, subtle=subtle, reset=reset)
