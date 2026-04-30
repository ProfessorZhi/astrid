from __future__ import annotations

from typing import TextIO

SCREEN_CLEAR = "\x1b[2J\x1b[H"
CLEAR_LINE = "\x1b[2K"


def strip_screen_clear_prefix(frame: str) -> str:
    if frame.startswith(SCREEN_CLEAR):
        return frame[len(SCREEN_CLEAR) :]
    return frame


class LineDiffScreenWriter:
    """Write terminal frames by updating only rows whose text changed."""

    def __init__(self, output: TextIO) -> None:
        self._output = output
        self._previous_lines: list[str] = []
        self._has_frame = False

    def reset(self) -> None:
        self._previous_lines = []
        self._has_frame = False

    def render(self, frame: str, *, force_full: bool = False) -> str:
        content = strip_screen_clear_prefix(frame)
        next_lines = content.split("\n") if content else [""]
        if force_full or not self._has_frame:
            rendered = SCREEN_CLEAR + content
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
            chunks.append(f"\x1b[{index + 1};1H{CLEAR_LINE}{current}")

        rendered = "".join(chunks)
        if rendered:
            self._output.write(rendered)
        self._previous_lines = next_lines
        return rendered
