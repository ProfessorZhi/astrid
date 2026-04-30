from __future__ import annotations

from dataclasses import dataclass

from astrid.ui.inline.rendering import render_paste_preview


@dataclass(slots=True)
class _Segment:
    text: str
    display: str | None = None


class InlineInputBuffer:
    """Small chat-composer state for Astrid's inline frontend.

    The buffer keeps the full submitted text while allowing the visible input
    line to compress large or multiline paste blocks.
    """

    def __init__(self) -> None:
        self._segments: list[_Segment] = []
        self._paste_count = 0

    @property
    def value(self) -> str:
        return "".join(segment.text for segment in self._segments)

    @property
    def display_text(self) -> str:
        return "".join(segment.display if segment.display is not None else segment.text for segment in self._segments)

    def clear(self) -> None:
        self._segments.clear()

    def insert_text(self, text: str) -> None:
        if not text:
            return
        if self._segments and self._segments[-1].display is None:
            self._segments[-1].text += text
            return
        self._segments.append(_Segment(text=text))

    def insert_paste(self, text: str) -> None:
        if not text:
            return
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        self._paste_count += 1
        line_count = normalized.count("\n") + 1
        if line_count > 1:
            display = render_paste_preview(self._paste_count, line_count - 1)
        else:
            display = None
        self._segments.append(_Segment(text=normalized, display=display))

    def backspace(self) -> None:
        if not self._segments:
            return
        segment = self._segments[-1]
        if segment.display is not None:
            self._segments.pop()
            return
        segment.text = segment.text[:-1]
        if not segment.text:
            self._segments.pop()

    def submit(self) -> str:
        value = self.value
        self.clear()
        return value
