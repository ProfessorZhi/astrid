from __future__ import annotations

import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from .theme import theme

# ---------------------------------------------------------------------------
# Re-export legacy ANSI constants (kept for backward compatibility)
# ---------------------------------------------------------------------------
RESET = "\x1b[0m"
DIM = "\x1b[2m"
CYAN = "\x1b[36m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
BOLD = "\x1b[1m"
REVERSE = "\x1b[7m"
ITALIC = "\x1b[3m"
UNDERLINE = "\x1b[4m"
BRIGHT_GREEN = "\x1b[92m"
BRIGHT_RED = "\x1b[91m"
BRIGHT_CYAN = "\x1b[96m"
BRIGHT_YELLOW = "\x1b[93m"
BRIGHT_BLUE = "\x1b[94m"
BRIGHT_MAGENTA = "\x1b[95m"
BRIGHT_WHITE = "\x1b[97m"
# Extended 256-color palette
BORDER = "\x1b[38;5;39m"
BORDER_DIM = "\x1b[38;5;24m"
ACCENT = "\x1b[38;5;214m"
ACCENT2 = "\x1b[38;5;141m"
SUBTLE = "\x1b[38;5;243m"
HIGHLIGHT_BG = "\x1b[48;5;236m"

# Welcome workbench palette: warm orange tones kept local to this layout.
WELCOME_BORDER = "\x1b[38;2;225;130;60m"
WELCOME_BORDER_DIM = "\x1b[38;2;163;92;42m"
WELCOME_ACCENT = "\x1b[38;2;248;179;102m"
WELCOME_MUTED = "\x1b[38;2;184;133;93m"

# ---------------------------------------------------------------------------
# Unicode decorative characters
# ---------------------------------------------------------------------------
ICON_MINICODE = "\u2726"   # ✦
ICON_USER = "\u25B6"       # ▶
ICON_ASSISTANT = "\u2734"  # ✴
ICON_TOOL = "\u2699"       # ⚙
ICON_PROGRESS = "\u25CF"   # ●
ICON_SUCCESS = "\u2714"    # ✔
ICON_ERROR = "\u2718"      # ✘
ICON_RUNNING = "\u25CB"    # ○
ICON_FOLDER = "\u25A0"     # ■
ICON_MODEL = "\u25C6"      # ◆
ICON_PROVIDER = "\u25C8"   # ◈
ICON_PROMPT = "\u276F"     # ❯
ICON_SKILL = "\u2605"      # ★
ICON_MSG = "\u25AC"        # ▬
ICON_EVENT = "\u25AA"      # ▪
ICON_MCP = "\u25C9"        # ◉
ICON_BG = "\u25D0"         # ◐
ICON_LOCK = "\u25A3"       # ▣
ICON_DIVIDER = "\u2500"    # ─
ICON_DOT = "\u00B7"        # ·
ICON_ARROW = "\u25B8"      # ▸

# Pre-compiled regex for ANSI stripping
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Cached terminal size
# ---------------------------------------------------------------------------
_ts_cache: tuple[int, int] | None = None
_ts_cache_time: float = 0.0
_TS_TTL: float = 0.5


def _cached_terminal_size() -> tuple[int, int]:
    """Return (columns, rows) with caching."""
    global _ts_cache, _ts_cache_time
    now = time.monotonic()
    if _ts_cache is None or (now - _ts_cache_time) > _TS_TTL:
        try:
            ts = os.get_terminal_size()
            cols, rows = ts.columns, ts.lines
            if cols <= 0 or rows <= 0:
                _ts_cache = (100, 40)
            else:
                _ts_cache = (cols, rows)
        except (AttributeError, ValueError, OSError):
            _ts_cache = (100, 40)
        _ts_cache_time = now
    return _ts_cache


def invalidate_terminal_size_cache() -> None:
    """Force the next ``_cached_terminal_size`` call to re-query the OS."""
    global _ts_cache
    _ts_cache = None


# ---------------------------------------------------------------------------
# Width computation
# ---------------------------------------------------------------------------

_WIDE_CHAR_PATTERN = re.compile(
    r'[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF'
    r'\uF900-\uFAFF\uFE10-\uFE19\uFE30-\uFE6F\uFF00-\uFF60\uFFE0-\uFFE6'
    r'\U0001F300-\U0001FAF6\U00020000-\U0003FFFD]'
)


def char_display_width(char: str) -> int:
    """CJK/Emoji width detection (return 2 for wide chars, 1 otherwise)."""
    if not char:
        return 0
    code = ord(char)
    if (
        0x1100 <= code <= 0x115F
        or code == 0x2329
        or code == 0x232A
        or (0x2E80 <= code <= 0xA4CF and code != 0x303F)
        or 0xAC00 <= code <= 0xD7A3
        or 0xF900 <= code <= 0xFAFF
        or 0xFE10 <= code <= 0xFE19
        or 0xFE30 <= code <= 0xFE6F
        or 0xFF00 <= code <= 0xFF60
        or 0xFFE0 <= code <= 0xFFE6
        or 0x1F300 <= code <= 0x1FAF6
        or 0x20000 <= code <= 0x3FFFD
    ):
        return 2
    return 1


@lru_cache(maxsize=2048)
def _stripped_display_width(stripped: str) -> int:
    """Width of a string that is already ANSI-stripped. Cached for hot paths."""
    wide_chars = len(_WIDE_CHAR_PATTERN.findall(stripped))
    return len(stripped) + wide_chars


def string_display_width(text: str) -> int:
    """Sum of char_display_width for stripped text."""
    stripped = _ANSI_RE.sub("", text)
    return _stripped_display_width(stripped)


def truncate_plain(text: str, width: int) -> str:
    """Truncate with '...' suffix, CJK aware. Preserves ANSI codes."""
    if string_display_width(text) <= width:
        return text

    limit = max(0, width - 3)
    res = ""
    w = 0
    i = 0
    while i < len(text):
        match = _ANSI_RE.match(text, i)
        if match:
            res += match.group()
            i = match.end()
            continue

        char = text[i]
        cw = char_display_width(char)
        if w + cw > limit:
            res += "..."
            i += 1
            while i < len(text):
                m = _ANSI_RE.match(text, i)
                if m:
                    res += m.group()
                    i = m.end()
                else:
                    i += 1
            return res

        res += char
        w += cw
        i += 1
    return res


def pad_plain(text: str, width: int) -> str:
    """Right-pad to width, CJK aware."""
    display_w = string_display_width(text)
    return text + (" " * max(0, width - display_w))


def truncate_path_middle(path: str, width: int) -> str:
    """Truncate middle with '...' keeping both ends."""
    if string_display_width(path) <= width:
        return path
    if width <= 5:
        return truncate_plain(path, width)

    half = (width - 3) // 2
    start_chars = ""
    start_w = 0
    for c in path:
        cw = char_display_width(c)
        if start_w + cw > half:
            break
        start_chars += c
        start_w += cw

    end_chars = ""
    end_w = 0
    for c in reversed(path):
        cw = char_display_width(c)
        if end_w + cw > (width - 3 - start_w):
            break
        end_chars = c + end_chars
        end_w += cw

    return start_chars + "..." + end_chars


def color_badge(label: str, value: str, color: str, icon: str = "") -> str:
    """Render a styled badge: icon [label] value."""
    t = theme()
    icon_part = f"{color}{icon} " if icon else ""
    return f"{icon_part}{color}{t.dim}[{label}]{t.reset} {t.bold}{value}{t.reset}"


_WORKER_ACCENTS: dict[str, str] = {
    "teal": "\x1b[38;2;109;159;156m",
    "blue": "\x1b[38;2;110;145;186m",
    "amber": "\x1b[38;2;190;145;84m",
    "coral": "\x1b[38;2;186;112;103m",
    "sage": "\x1b[38;2;133;160;118m",
    "violet": "\x1b[38;2;145;127;176m",
}
_WORKER_ACCENT_ORDER: tuple[str, ...] = tuple(_WORKER_ACCENTS.values())


def get_worker_accent(color_key: str | None, index: int = 0) -> str:
    """Resolve a stable worker accent color by semantic key or fallback index."""
    if color_key and color_key in _WORKER_ACCENTS:
        return _WORKER_ACCENTS[color_key]
    return _WORKER_ACCENT_ORDER[index % len(_WORKER_ACCENT_ORDER)]


def border_line(kind: str, width: int, color: str = "") -> str:
    """ASCII-safe border line for terminals with inconsistent wide-char handling."""
    c = color or BORDER
    middle = "-" * max(0, width - 2)
    if kind == "top":
        return f"{c}+{middle}+{RESET}"
    elif kind == "bottom":
        return f"{c}+{middle}+{RESET}"
    else:
        return f"{c}|{middle}|{RESET}"


def panel_row(left: str, width: int, right: str | None = None, border_color: str = "") -> str:
    """ASCII-safe panel row."""
    bc = border_color or BORDER
    inner_width = width - 4
    if right:
        l_w = string_display_width(left)
        r_w = string_display_width(right)
        gap = inner_width - l_w - r_w
        if gap < 1:
            left = truncate_plain(left, inner_width - r_w - 1)
            gap = 1
        return f"{bc}|{RESET} {left}{' ' * gap}{right} {bc}|{RESET}"
    else:
        return f"{bc}|{RESET} {pad_plain(left, inner_width)} {bc}|{RESET}"


def empty_panel_row(width: int) -> str:
    return panel_row("", width)


def wrap_panel_body_line(line: str, width: int) -> list[str]:
    """Wrap long lines for panel, CJK aware."""
    inner_width = width - 4
    if string_display_width(line) <= inner_width:
        return [line]

    ansi_spans: list[tuple[int, int]] = []
    for m in _ANSI_RE.finditer(line):
        ansi_spans.append((m.start(), m.end()))

    lines: list[str] = []
    current_line = ""
    current_w = 0
    i = 0
    span_idx = 0

    while i < len(line):
        if span_idx < len(ansi_spans) and i == ansi_spans[span_idx][0]:
            end = ansi_spans[span_idx][1]
            current_line += line[i:end]
            i = end
            span_idx += 1
            continue

        char = line[i]
        cw = char_display_width(char)
        if current_w + cw > inner_width:
            lines.append(current_line)
            current_line = ""
            current_w = 0
            if char == " ":
                i += 1
                continue
        current_line += char
        current_w += cw
        i += 1
    if current_line:
        lines.append(current_line)
    return lines


_PANEL_ICONS: dict[str, str] = {
    "astrid": ICON_MINICODE,
    "session feed": ICON_MSG,
    "prompt": ICON_PROMPT,
    "activity": ICON_TOOL,
    "action required": ICON_LOCK,
}


def render_panel(
    title: str,
    body: str,
    right_title: str | None = None,
    min_body_lines: int = 0,
    border_color: str = "",
) -> str:
    """Full panel with Unicode borders.

    The border color defaults to the theme value for the given panel title
    (workspace → header, session → session, prompt → input, etc.).
    """
    t = theme()
    width, _ = _cached_terminal_size()
    if width < 40:
        width = 40

    # Pick border color from theme based on title
    if not border_color:
        title_lower = title.lower()
        if "workspace" in title_lower or "astrid" in title_lower:
            border_color = t.header
        elif "session" in title_lower:
            border_color = t.session
        elif "prompt" in title_lower or "input" in title_lower:
            border_color = t.input
        elif "action" in title_lower or "approval" in title_lower:
            border_color = t.approval
        else:
            border_color = BORDER

    icon = _PANEL_ICONS.get(title.lower(), "")
    icon_str = f"{ACCENT}{icon} {RESET}" if icon else ""

    res = [border_line("top", width, border_color)]
    title_display = f"{icon_str}{t.bold}{title}{t.reset}"
    right_display = f"{t.subtle}{right_title}{t.reset}" if right_title else None
    res.append(panel_row(title_display, width, right_display, border_color))

    inner = width - 4
    divider_line = f"{BORDER_DIM}{'╌' * inner}{RESET}"
    res.append(panel_row(divider_line, width, border_color=border_color))

    body_lines = body.splitlines() if body else []
    wrapped_lines: list[str] = []
    for bl in body_lines:
        wrapped_lines.extend(wrap_panel_body_line(bl, width))

    while len(wrapped_lines) < min_body_lines:
        wrapped_lines.append("")

    for wl in wrapped_lines:
        res.append(panel_row(wl, width, border_color=border_color))
    res.append(border_line("bottom", width, border_color))
    return "\n".join(res)


# ---------------------------------------------------------------------------
# Banner / header — aligned with Rust's build_header_lines
# ---------------------------------------------------------------------------

def render_banner(
    runtime: dict | None,
    cwd: str,
    permission_summary: list[str],
    session: dict[str, int],
    compact: bool = False,
    companion_preview: str | None = None,
) -> str:
    """Render the workspace header panel.

    Layout matches Rust's build_header_lines:
      Line 1: project <cwd>   provider <host>   model <name>   auth <kind>
      Line 2: session messages=N events=N tools=N skills=N mcp=N
      Line 3: permissions info

    When compact=True (small terminal), all info is compressed into one line.
    """
    t = theme()

    model = runtime.get("model", "(unconfigured)") if runtime else "(unconfigured)"

    # Provider hostname (strip scheme)
    provider = "offline"
    if runtime and runtime.get("baseUrl"):
        provider = (
            runtime["baseUrl"]
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
        )

    # Auth kind
    auth = "none"
    if runtime:
        if runtime.get("authToken"):
            auth = "auth_token"
        elif runtime.get("apiKey"):
            auth = "api_key"

    msg_count = session.get("messageCount", 0)
    evt_count = session.get("transcriptCount", 0)
    skill_count = session.get("skillCount", 0)
    mcp_count = session.get("mcpCount", 0)

    if compact:
        # Single-line compact header for small terminals
        import os as _os
        cwd_short = _os.path.basename(cwd) or cwd
        body = (
            f"{t.header_label_info}{t.bold}project{t.reset} {cwd_short}"
            f"  {t.header_label_info}{t.bold}model{t.reset} {model}"
            f"  {t.header_label_session}{t.bold}msgs{t.reset} {msg_count}"
        )
        if companion_preview:
            body = f"{body}\n\n{companion_preview}"
        return render_panel("Workspace", body)

    # Line 1 — project / provider / model / auth
    line1 = (
        f"{t.header_label_info}{t.bold}project{t.reset} {cwd}"
        f"   {t.header_label_info}{t.bold}provider{t.reset} {provider}"
        f"   {t.header_label_info}{t.bold}model{t.reset} {model}"
        f"   {t.header_label_info}{t.bold}auth{t.reset} {auth}"
    )

    # Line 2 — session stats
    line2 = (
        f"{t.header_label_session}{t.bold}session{t.reset}"
        f" messages={msg_count}"
        f" events={evt_count}"
        f" skills={skill_count}"
        f" mcp={mcp_count}"
    )

    body = "\n".join([line1, line2])
    if companion_preview:
        body = f"{body}\n\n{companion_preview}"
    return render_panel("Workspace", body)


def _welcome_column_widths(width: int, buddy_block: str) -> tuple[int, int]:
    """Split the welcome card into Claude Code-like compact left / flexible right columns."""
    inner_width = max(20, width - 4)
    separator_width = 3
    content_width = max(
        20,
        string_display_width("Welcome back"),
        *(string_display_width(line) for line in buddy_block.splitlines() or [""]),
    )
    left_width = min(max(content_width + 4, 28), 50, max(28, inner_width - separator_width - 22))
    right_width = max(18, inner_width - separator_width - left_width)
    return left_width, right_width


def _welcome_section_lines(
    title: str,
    items: list[str],
    width: int,
    *,
    item_prefix: str = "",
) -> list[str]:
    lines = [f"{WELCOME_ACCENT}{BOLD}{title}{RESET}"]
    if not items:
        items = ["(none)"]
    prefix_width = string_display_width(item_prefix)
    item_width = max(0, width - prefix_width)
    for item in items:
        for chunk in item.splitlines() or [""]:
            text = truncate_plain(chunk, item_width)
            if item_prefix:
                text = f"{item_prefix}{text}"
            lines.append(text)
    return lines


def _render_welcome_row(left: str, right: str, width: int, *, left_width: int, right_width: int) -> str:
    """Render a single two-column row inside the welcome card."""
    divider = f"{WELCOME_BORDER_DIM}|{RESET}"
    left_cell = pad_plain(truncate_plain(left, left_width), left_width)
    right_cell = pad_plain(truncate_plain(right, right_width), right_width)
    content = f"{left_cell} {divider} {right_cell}"
    return f"{WELCOME_BORDER}|{RESET} {content} {WELCOME_BORDER}|{RESET}"


def render_welcome_workbench(
    *,
    app_name: str,
    version: str,
    model_name: str,
    workspace: str,
    buddy_block: str,
    tips: list[str],
    recent_items: list[str],
    width: int | None = None,
) -> str:
    """Render a compact welcome header that survives page flow."""
    t = theme()
    resolved_width = width if width is not None else _cached_terminal_size()[0]
    panel_width = max(52, resolved_width - 4)
    inner_width = max(28, panel_width - 4)

    def _body_line(text: str = "") -> str:
        return (
            f"{WELCOME_BORDER}|{RESET} "
            f"{pad_plain(truncate_plain(text, inner_width), inner_width)} "
            f"{WELCOME_BORDER}|{RESET}"
        )

    buddy_lines = [line.rstrip() for line in buddy_block.splitlines()]
    while buddy_lines and not strip_ansi(buddy_lines[0]).strip():
        buddy_lines.pop(0)
    while buddy_lines and not strip_ansi(buddy_lines[-1]).strip():
        buddy_lines.pop()
    if not buddy_lines:
        buddy_lines = ["Buddy"]

    tip_items = [item.strip("- ").strip() for item in tips[:2] if item.strip()]
    recent_text = " | ".join(item.strip("- ").strip() for item in recent_items[:2] if item.strip()) or "No recent activity yet"
    meta_text = f"{WELCOME_MUTED}{version or app_name}{RESET}"
    workspace_text = f"{WELCOME_MUTED}model {model_name} | {truncate_path_middle(workspace, max(16, inner_width - 18))}{RESET}"
    right_lines = [
        f"{WELCOME_ACCENT}{t.bold}Welcome back{t.reset}",
        meta_text,
        workspace_text,
    ]
    if tip_items:
        right_lines.append(f"{WELCOME_ACCENT}{t.bold}tips{t.reset}  {tip_items[0]}")
        right_lines.extend(f"      {item}" for item in tip_items[1:])
    right_lines.append(f"{WELCOME_ACCENT}{t.bold}recent{t.reset}  {recent_text}")

    lines: list[str] = [f"{WELCOME_BORDER}+{'-' * (panel_width - 2)}+{RESET}"]

    if inner_width >= 68:
        left_width, right_width = _welcome_column_widths(panel_width, "\n".join(buddy_lines))
        row_count = max(len(buddy_lines), len(right_lines))
        for index in range(row_count):
            left = buddy_lines[index] if index < len(buddy_lines) else ""
            right = right_lines[index] if index < len(right_lines) else ""
            lines.append(
                _render_welcome_row(
                    left,
                    right,
                    panel_width,
                    left_width=left_width,
                    right_width=right_width,
                )
            )
    else:
        for line in buddy_lines:
            lines.append(_body_line(line))
        lines.append(_body_line())
        for line in right_lines:
            lines.append(_body_line(line))

    lines.append(f"{WELCOME_BORDER}+{'-' * (panel_width - 2)}+{RESET}")
    return "\n".join(lines)


def render_status_line(status: str | None) -> str:
    """Render the status line."""
    t = theme()
    if status:
        return f"{t.tool}{t.bold}{ICON_RUNNING} {status}{t.reset}"
    return f"{t.assistant}{ICON_SUCCESS} Ready{t.reset}"


def render_tool_panel(
    active_tool: str | None,
    recent_tools: list[dict[str, str]],
    background_tasks: list[dict[str, Any]] | None = None,
) -> str:
    """Render current tool activity summary."""
    t = theme()
    if background_tasks is None:
        background_tasks = []
    parts: list[str] = []
    if active_tool:
        parts.append(f"{ICON_RUNNING} {t.tool}{t.bold}running{t.reset} {active_tool}")
    for task in background_tasks:
        if task.get("status") == "running":
            parts.append(f"{ICON_BG} {t.progress}bg{t.reset} {task.get('label', 'task')}")
    if not parts and not recent_tools:
        parts.append(f"{t.subtle}{ICON_DOT} idle{t.reset}")
    else:
        for tool in recent_tools[-3:]:
            if tool.get("status") == "success":
                parts.append(f"{t.assistant}{ICON_SUCCESS} {tool.get('name', 'tool')}{t.reset}")
            else:
                parts.append(f"{t.tool_error}{ICON_ERROR} {tool.get('name', 'tool')}{t.reset}")
    return f"{ICON_TOOL} {t.dim}tools{t.reset}  " + f"  {t.subtle}{ICON_DOT}{t.reset}  ".join(parts)


def render_footer_bar(
    status: str | None,
    tools_enabled: bool,
    skills_enabled: bool,
    background_tasks: list[dict[str, Any]] | None = None,
) -> str:
    """Single-line footer bar."""
    t = theme()
    if background_tasks is None:
        background_tasks = []
    width, _ = _cached_terminal_size()
    left = render_status_line(status)

    bg_info = ""
    if background_tasks:
        bg_info = f" {ICON_BG} {t.progress}{len(background_tasks)} bg{t.reset} {t.subtle}│{t.reset}"

    tools_indicator = f"{t.assistant}{ICON_SUCCESS}{t.reset}" if tools_enabled else f"{t.tool_error}{ICON_ERROR}{t.reset}"
    skills_indicator = f"{t.assistant}{ICON_SUCCESS}{t.reset}" if skills_enabled else f"{t.tool_error}{ICON_ERROR}{t.reset}"

    right = (
        f"{bg_info} {ICON_TOOL} {t.subtle}tools{t.reset} {tools_indicator}"
        f" {t.subtle}│{t.reset} {ICON_SKILL} {t.subtle}skills{t.reset} {skills_indicator}"
    )
    gap = max(1, width - string_display_width(left) - string_display_width(right))
    return f"{left}{' ' * gap}{right}"


def render_slash_menu(commands: list[Any], selected_index: int) -> str:
    """Render slash command menu with highlight."""
    t = theme()
    if not commands:
        return f"{t.subtle}no commands{t.reset}"
    width, _ = _cached_terminal_size()
    rows = [f"{ACCENT}{ICON_ARROW}{RESET} {t.dim}commands{t.reset}"]
    for i, cmd in enumerate(commands):
        usage = pad_plain(getattr(cmd, "usage", str(cmd)), 14)
        desc = getattr(cmd, "description", "")
        if i == selected_index:
            line = (
                f"  {t.command_highlight_bg}{BRIGHT_CYAN}{ICON_ARROW}{RESET}"
                f"{t.command_highlight_bg} {BRIGHT_WHITE}{t.bold}{usage}{RESET}"
                f"{t.command_highlight_bg} {desc} {RESET}"
            )
        else:
            line = f"   {t.subtle}{ICON_DOT}{t.reset} {usage} {t.subtle}{desc}{t.reset}"
        rows.append(truncate_plain(line, width))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Diff colorization
# ---------------------------------------------------------------------------

def classify_diff_line(line: str) -> str:
    if line.startswith(("+++", "---", "@@")):
        return "meta"
    if line.startswith("+"):
        return "add"
    if line.startswith("-"):
        return "remove"
    return "context"


def compute_changed_range(removed: str, added: str) -> tuple[int, int] | None:
    if not removed or not added:
        return None
    p = 0
    while p < len(removed) and p < len(added) and removed[p] == added[p]:
        p += 1
    s = 0
    while s < (len(removed) - p) and s < (len(added) - p) and removed[-(s + 1)] == added[-(s + 1)]:
        s += 1
    return (p, len(added) - s) if p < (len(added) - s) else None


def apply_word_emphasis(content: str, color: str, emphasis_range: tuple[int, int] | None = None) -> str:
    if not emphasis_range:
        return f"{color}{content}{RESET}"
    s, e = emphasis_range
    return f"{color}{content[:s]}{BOLD}{REVERSE}{content[s:e]}{RESET}{color}{content[e:]}{RESET}"


def colorize_unified_diff_block(block: str) -> str:
    """Full diff with word-level highlighting."""
    lines = block.splitlines()
    res: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(("--- ", "+++ ", "@@ ")):
            res.append(f"{CYAN}{line}{RESET}")
            i += 1
            continue
        if line.startswith("-"):
            removals: list[str] = []
            while i < len(lines) and lines[i].startswith("-"):
                removals.append(lines[i][1:])
                i += 1
            additions: list[str] = []
            while i < len(lines) and lines[i].startswith("+"):
                additions.append(lines[i][1:])
                i += 1
            paired = min(len(removals), len(additions))
            for j in range(paired):
                emphasis = compute_changed_range(removals[j], additions[j])
                res.append("-" + apply_word_emphasis(removals[j], RED, emphasis))
                res.append("+" + apply_word_emphasis(additions[j], GREEN, emphasis))
            for j in range(paired, len(removals)):
                res.append(f"{RED}-{removals[j]}{RESET}")
            for j in range(paired, len(additions)):
                res.append(f"{GREEN}+{additions[j]}{RESET}")
            continue
        if line.startswith("+"):
            res.append(f"{GREEN}{line}{RESET}")
            i += 1
        else:
            res.append(f"{DIM}{line}{RESET}")
            i += 1
    return "\n".join(res)


def _looks_like_diff_block(detail: str) -> bool:
    return "\n" in detail and (
        "--- a/" in detail or "+++ b/" in detail or "@@ " in detail
    )


def colorize_edit_permission_details(details: list[str]) -> list[str]:
    return [
        colorize_unified_diff_block(d) if _looks_like_diff_block(d) else d
        for d in details
    ]


# ---------------------------------------------------------------------------
# Permission prompt
# ---------------------------------------------------------------------------

def get_permission_prompt_max_scroll_offset(
    request: dict[str, Any], expanded: bool = False
) -> int:
    if not expanded:
        return 0
    flat = flatten_detail_lines(request.get("details", []))
    _, rows = _cached_terminal_size()
    max_visible = max(4, rows - 20)
    return max(0, len(flat) - max_visible)


def flatten_detail_lines(details: list[str]) -> list[str]:
    result: list[str] = []
    for detail in details:
        result.extend(detail.split("\n"))
    return result


def slice_visible_details(
    flat_lines: list[str], scroll_offset: int, max_visible: int | None = None
) -> tuple[list[str], int]:
    if max_visible is None:
        _, rows = _cached_terminal_size()
        max_visible = max(4, rows - 20)
    total = len(flat_lines)
    offset = max(0, min(scroll_offset, max(0, total - max_visible)))
    return flat_lines[offset:offset + max_visible], total


def render_permission_prompt(
    request: dict[str, Any],
    expanded: bool = False,
    scroll_offset: int = 0,
    selected_choice_index: int = 0,
    feedback_mode: bool = False,
    feedback_input: str = "",
) -> str:
    """Interactive permission prompt with Morandi theme."""
    t = theme()
    lines: list[str] = []
    if feedback_mode:
        lines.extend([
            f"{t.progress}{t.bold}{ICON_PROMPT} Provide reason for rejection:{t.reset}",
            f"  {t.assistant}{ICON_PROMPT}{t.reset} {feedback_input}_",
            "",
            f"{t.subtle}  Press Enter to send, Esc to cancel.{t.reset}",
        ])
    else:
        lines.extend([request.get("summary", "Permission Request"), ""])
        details = request.get("details", [])
        if details:
            flat = flatten_detail_lines(details)
            if not expanded:
                lines.append(
                    f"{t.subtle}  {ICON_ARROW} {len(flat)} lines hidden "
                    f"{t.subtle}│{t.reset} {t.dim}press 'v' to expand │ Ctrl+O toggle{t.reset}"
                )
            else:
                colorized = colorize_edit_permission_details(flat)
                visible, total = slice_visible_details(colorized, scroll_offset)
                lines.extend(visible)
                if total > len(visible):
                    lines.append(
                        f"{t.subtle}  {ICON_DIVIDER * 3} scroll "
                        f"{scroll_offset + 1}/{total} (Wheel/PgUp/PgDn) "
                        f"{ICON_DIVIDER * 3}{t.reset}"
                    )
            lines.append("")
        for i, choice in enumerate(request.get("choices", [])):
            label = choice.get("label", "")
            key = choice.get("key", "")
            if i == selected_choice_index:
                lines.append(
                    f"  {t.command_highlight_bg}{BRIGHT_CYAN}{ICON_ARROW}{RESET}"
                    f"{t.command_highlight_bg} {BRIGHT_WHITE}{t.bold}{label}{RESET}"
                    f"{t.command_highlight_bg} {t.subtle}({key}){RESET}"
                )
            else:
                lines.append(f"    {t.subtle}{ICON_DOT}{t.reset} {label} {t.subtle}({key}){t.reset}")
    return render_panel("Action Required", "\n".join(lines), right_title="Permission")
