"""Warm orange theme for Astrid TUI.

The palette leans toward a Claude-Code-like warm orange and sand direction
while keeping enough contrast for long coding sessions.
"""

from __future__ import annotations

from dataclasses import dataclass


def _rgb(r: int, g: int, b: int) -> str:
    """24-bit foreground color escape code."""
    return f"\x1b[38;2;{r};{g};{b}m"


def _rgb_bg(r: int, g: int, b: int) -> str:
    """24-bit background color escape code."""
    return f"\x1b[48;2;{r};{g};{b}m"


@dataclass(frozen=True)
class ColorTheme:
    """Warm terminal theme for Astrid."""

    header: str
    session: str
    input: str
    approval: str

    user: str
    assistant: str
    progress: str
    tool: str
    tool_error: str

    command_highlight_bg: str
    expandable: str

    header_label_info: str
    header_label_session: str
    header_label_permissions: str
    header_label_recent: str

    reset: str = "\x1b[0m"
    bold: str = "\x1b[1m"
    dim: str = "\x1b[2m"
    italic: str = "\x1b[3m"
    underline: str = "\x1b[4m"
    reverse: str = "\x1b[7m"

    subtle: str = "\x1b[38;5;243m"
    border: str = "\x1b[38;5;173m"
    border_dim: str = "\x1b[38;5;130m"
    accent: str = "\x1b[38;5;215m"
    accent2: str = "\x1b[38;5;180m"
    highlight_bg: str = "\x1b[48;5;236m"


def _default_theme() -> ColorTheme:
    """Build the default warm orange theme."""
    return ColorTheme(
        header=_rgb(202, 126, 74),
        session=_rgb(184, 115, 70),
        input=_rgb(216, 142, 81),
        approval=_rgb(191, 96, 74),
        user=_rgb(177, 112, 67),
        assistant=_rgb(215, 162, 104),
        progress=_rgb(232, 167, 88),
        tool=_rgb(194, 138, 86),
        tool_error=_rgb(204, 92, 72),
        command_highlight_bg=_rgb_bg(96, 63, 44),
        expandable=_rgb(226, 170, 107),
        header_label_info=_rgb(211, 164, 110),
        header_label_session=_rgb(189, 125, 86),
        header_label_permissions=_rgb(170, 129, 98),
        header_label_recent=_rgb(170, 129, 98),
    )


_THEME: ColorTheme | None = None


def theme() -> ColorTheme:
    """Return the global ColorTheme instance."""
    global _THEME
    if _THEME is None:
        _THEME = _default_theme()
    return _THEME
