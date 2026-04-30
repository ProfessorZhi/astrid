from __future__ import annotations

from .chrome import (
    RESET, DIM, BOLD, ITALIC, HIGHLIGHT_BG,
    BRIGHT_GREEN, SUBTLE,
    ICON_PROMPT, ICON_DOT,
)
from .theme import theme


def render_input_prompt(current_input: str, cursor_offset: int, compact: bool = False) -> str:
    """Render the input prompt line.

    Format matches the Rust version:
      astrid> <input with cursor>

    When compact=True (small terminal), the hint bar is hidden to save lines.
    """
    t = theme()
    offset = max(0, min(cursor_offset, len(current_input)))
    before = current_input[:offset]
    current = current_input[offset] if offset < len(current_input) else " "
    after = current_input[offset + 1:]

    placeholder = (
        "" if current_input
        else f"{ITALIC} msg or /help{RESET}"
    )

    # Prompt: "astrid> " prefix (matches Rust render_screen)
    prefix = f"{t.input}{BOLD}astrid>{RESET} "
    input_line = f"{prefix}{before}{HIGHLIGHT_BG}{BRIGHT_GREEN}{current}{RESET}{after}{DIM}{placeholder}{RESET}"

    return input_line
