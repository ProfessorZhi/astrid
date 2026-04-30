from astrid.tui.chrome import (
    get_permission_prompt_max_scroll_offset,
    render_banner,
    render_footer_bar,
    render_panel,
    render_permission_prompt,
    render_slash_menu,
    render_status_line,
    render_tool_panel,
)
from astrid.tui.input import render_input_prompt
from astrid.tui.input_parser import (
    KeyEvent,
    ParsedInputEvent,
    ParseResult,
    TextEvent,
    WheelEvent,
    parse_input_chunk,
)
from astrid.tui.markdown import render_markdownish
from astrid.tui.screen import (
    clear_screen,
    enter_alternate_screen,
    exit_alternate_screen,
    hide_cursor,
    show_cursor,
)
from astrid.tui.theme import ColorTheme, theme
from astrid.tui.transcript import (
    format_transcript_text,
    get_transcript_max_scroll_offset,
    get_transcript_window_size,
    render_transcript,
)
from astrid.tui.types import TranscriptEntry

__all__ = [
    # screen
    "clear_screen",
    "enter_alternate_screen",
    "exit_alternate_screen",
    "hide_cursor",
    "show_cursor",
    # chrome
    "get_permission_prompt_max_scroll_offset",
    "render_banner",
    "render_footer_bar",
    "render_panel",
    "render_permission_prompt",
    "render_slash_menu",
    "render_status_line",
    "render_tool_panel",
    # input
    "render_input_prompt",
    # input_parser
    "KeyEvent",
    "ParsedInputEvent",
    "ParseResult",
    "TextEvent",
    "WheelEvent",
    "parse_input_chunk",
    # markdown
    "render_markdownish",
    # theme
    "ColorTheme",
    "theme",
    # transcript
    "format_transcript_text",
    "get_transcript_max_scroll_offset",
    "get_transcript_window_size",
    "render_transcript",
    # types
    "TranscriptEntry",
]
