from __future__ import annotations

from .chrome import (
    _cached_terminal_size,
    RESET, DIM, BOLD,
    ICON_DIVIDER, ICON_DOT,
    get_worker_accent,
)
from .markdown import render_markdownish
from .theme import theme
from .types import OrchestrationWorker, TranscriptEntry

# Pre-build the separator string once (immutable)
_SEPARATOR = f"  {DIM}{ICON_DOT} {ICON_DIVIDER * 3} {ICON_DOT}{RESET}"
_SEPARATOR_LINES = ["", _SEPARATOR, ""]
_SEPARATOR_LINE_COUNT = 3
_SIMPLE_SEPARATOR_LINES = [""]
_ROUND_SEPARATOR = f"  {DIM}{'-' * 36}{RESET}"
_ROUND_SEPARATOR_LINES = ["", _ROUND_SEPARATOR, ""]

# Tool output preview limits (match Rust TOOL_PREVIEW_LINES / TOOL_PREVIEW_CHARS)
_TOOL_PREVIEW_LINES = 6
_TOOL_PREVIEW_CHARS = 180
_SPINNER_FRAMES = (".", "o", "O", "o")


def _render_progress_meter(frame: int, width: int = 6) -> str:
    width = max(4, width)
    pulse_span = 2
    travel = width + pulse_span - 1
    pulse_head = frame % travel
    chars = [" "] * width
    start = max(0, pulse_head - pulse_span + 1)
    end = min(width, pulse_head + 1)
    for index in range(start, end):
        chars[index] = "="
    if 0 <= pulse_head < width:
        chars[pulse_head] = ">"
    return "[" + "".join(chars) + "]"


def _indent_block(text: str, prefix: str = "  ") -> str:
    """Indent all lines in a block of text."""
    return "\n".join(prefix + line for line in text.split("\n"))


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _render_status_line(verb: str, summary: str | None, color: str) -> str:
    t = theme()
    line = f"{color}{t.bold}{verb}{t.reset}"
    if summary:
        line = f"{line}  {t.subtle}{summary}{t.reset}"
    return line


def preview_tool_body(tool_name: str, body: str) -> str:
    """Truncate tool output based on tool name and content size."""
    max_chars = 1000 if tool_name == "read_file" else 1800
    max_lines = 20 if tool_name == "read_file" else 36

    lines = body.split("\n")
    limited_lines = lines[:max_lines] if len(lines) > max_lines else lines
    limited = "\n".join(limited_lines)

    if len(limited) > max_chars:
        limited = limited[:max_chars] + "..."

    if limited != body:
        return f"{limited}\n{DIM}... output truncated in transcript{RESET}"

    return limited


def _render_worker_status(status: str) -> str:
    t = theme()
    if status == "running":
        return f"{t.progress}running{t.reset}"
    if status == "queued":
        return f"{t.subtle}queued{t.reset}"
    if status == "reporting":
        return f"{t.assistant}reporting{t.reset}"
    if status == "blocked":
        return f"{t.tool_error}blocked{t.reset}"
    if status == "done":
        return f"{t.assistant}done{t.reset}"
    if status == "failed":
        return f"{t.tool_error}failed{t.reset}"
    return f"{t.subtle}{status}{t.reset}"


def _render_orchestration_worker(worker: OrchestrationWorker, index: int, animation_frame: int) -> str:
    t = theme()
    accent = get_worker_accent(worker.colorKey, index=index)
    worker_name = f"{accent}{t.bold}{worker.name}{t.reset}"
    role = f"{t.subtle}{worker.role}{t.reset}"
    mission = f"{t.subtle}{worker.mission}{t.reset}"
    status = _render_worker_status(worker.status)
    meter = ""
    if worker.status == "running":
        meter = f" {accent}{_render_progress_meter(animation_frame + index)}{t.reset}"
    first_line = f"{accent}{ICON_DIVIDER}{t.reset} {worker_name}  {role}  {mission}  {status}{meter}"
    if worker.latestEvent:
        prefix = worker.spinnerVerb if worker.status == "running" and worker.spinnerVerb else "latest"
        event_line = f"  {t.subtle}{prefix}: {worker.latestEvent}{t.reset}"
        return f"{first_line}\n{event_line}"
    return first_line


def render_orchestration_block(entry: TranscriptEntry) -> str:
    """Render the narrative line and worker tree for orchestration events."""
    t = theme()
    narrative = entry.narrativeLine or entry.body or "Coordinating workers..."
    phase_label = entry.phaseLabel or "unravelling"
    phase_verb = entry.phaseVerb or "Working"
    spinner = _SPINNER_FRAMES[entry.animationFrame % len(_SPINNER_FRAMES)]
    lines = [f"{t.accent}{t.bold}{phase_label}{t.reset}  {render_markdownish(narrative)}"]
    active_workers = [worker for worker in entry.workers if worker.status != "done"]
    archived_workers = [worker for worker in entry.workers if worker.status == "done"]
    if active_workers or archived_workers:
        lines[0] = f"{t.accent}{t.bold}{spinner} {phase_label}{t.reset}  {t.assistant}{phase_verb}{t.reset}  {render_markdownish(narrative)}"

    for index, worker in enumerate(active_workers):
        lines.append(_render_orchestration_worker(worker, index, entry.animationFrame))
    if archived_workers:
        names = ", ".join(worker.name for worker in archived_workers[:3])
        more = len(archived_workers) - 3
        if more > 0:
            names = f"{names}, +{more} more"
        lines.append(f"{t.subtle}  {len(archived_workers)} archived worker(s): {names}{t.reset}")
    return "\n".join(lines)


def _tool_status_text(status: str | None) -> tuple[str, str, str]:
    t = theme()
    if status == "running":
        return "running", "Running", t.progress
    if status == "success":
        return "result", "Result", t.assistant
    if status == "error":
        return "error", "Error", t.tool_error
    return "unknown", "Status", t.subtle


def _render_tool_entry(entry: TranscriptEntry) -> str:
    t = theme()
    status_text, status_verb, status_color = _tool_status_text(entry.status)
    tool_name_display = f"{t.tool}{t.bold}{entry.toolName}{t.reset}"

    body_lines = entry.body.split("\n") if entry.body else []
    total_lines = len(body_lines)
    collapsible_by_lines = total_lines > _TOOL_PREVIEW_LINES
    collapsible_by_chars = any(
        len(ln) > _TOOL_PREVIEW_CHARS
        for ln in body_lines[:_TOOL_PREVIEW_LINES]
    )
    can_toggle = collapsible_by_lines or collapsible_by_chars

    is_collapsed = entry.collapsed
    is_collapsing = entry.collapsePhase is not None and not entry.collapsed

    if can_toggle:
        toggle_text = (
            f"  {t.expandable}{t.bold}[hide]{t.reset}"
            if not is_collapsed
            else f"  {t.expandable}{t.bold}[show]{t.reset}"
        )
    else:
        toggle_text = ""

    label = (
        f"{t.tool}{t.bold}tool{t.reset} {tool_name_display}"
        f" {status_color}{ICON_DOT} {status_text}{t.reset}{toggle_text}"
    )

    summary = _first_line(entry.actionSummary or "")
    if not summary and entry.status == "running":
        summary = _first_line(entry.body)
    status_line = _render_status_line(status_verb, summary or None, status_color)

    if entry.status == "running":
        body = entry.body
    elif is_collapsing:
        phase_label = f"collapsing{'.' * min(int(entry.collapsePhase or 1), 3)}"
        body = f"{t.subtle}{t.italic}{phase_label}{t.reset}"
    elif is_collapsed:
        summary_text = entry.collapsedSummary or "output collapsed"
        body = f"{t.subtle}{t.italic}{summary_text}{t.reset}"
    else:
        if collapsible_by_lines:
            preview = "\n".join(body_lines[:_TOOL_PREVIEW_LINES])
            hidden = total_lines - _TOOL_PREVIEW_LINES
            body = (
                preview_tool_body(entry.toolName or "", render_markdownish(preview))
                + f"\n{t.subtle}  ... {hidden} more lines{t.reset}"
            )
        else:
            body = preview_tool_body(
                entry.toolName or "", render_markdownish(entry.body)
            )

    parts = [label, _indent_block(status_line)]
    if body:
        parts.append(_indent_block(body))
    return "\n".join(parts)


def _render_transcript_entry(entry: TranscriptEntry) -> str:
    """Render a single TranscriptEntry with Morandi theme colors."""
    t = theme()

    if entry.kind == "welcome":
        return entry.body

    if entry.kind == "user":
        label = f"{t.user}{t.bold}you{t.reset}"
        return f"{label}\n{_indent_block(entry.body)}"

    if entry.kind == "assistant":
        label = f"{t.assistant}{t.bold}assistant{t.reset}"
        return f"{label}\n{_indent_block(render_markdownish(entry.body))}"

    if entry.kind == "progress":
        label = f"{t.progress}{t.bold}progress{t.reset}"
        summary = _first_line(entry.actionSummary or entry.body)
        detail = _render_status_line(
            entry.phaseVerb or "Working",
            summary or None,
            t.progress,
        )
        return f"{label}\n{_indent_block(detail)}"

    if entry.kind == "orchestration":
        label = f"{t.accent2}{t.bold}orchestration{t.reset}"
        return f"{label}\n{_indent_block(render_orchestration_block(entry))}"

    if entry.kind == "tool":
        return _render_tool_entry(entry)

    return ""


def _simple_separator_lines(prev_entry: TranscriptEntry, entry: TranscriptEntry) -> list[str]:
    if entry.kind == "user" and prev_entry.kind != "welcome":
        return _ROUND_SEPARATOR_LINES
    return _SIMPLE_SEPARATOR_LINES


def get_transcript_window_size(window_size: int | None = None) -> int:
    if window_size is not None:
        return max(4, window_size)
    _, rows = _cached_terminal_size()
    return max(8, rows - 15)


# ---------------------------------------------------------------------------
# Simple rendering (Claude Code style - no panels)
# ---------------------------------------------------------------------------

def render_transcript_simple(entries: list[TranscriptEntry]) -> str:
    """Render transcript in simple style like Claude Code - no panels, no borders.

    Each entry is rendered with a label prefix and a blank line separator.
    """
    if not entries:
        return ""

    t = theme()
    parts: list[str] = []

    for i, entry in enumerate(entries):
        if i > 0:
            parts.extend(_simple_separator_lines(entries[i - 1], entry))

        if entry.kind == "welcome":
            parts.append(entry.body)

        elif entry.kind == "user":
            parts.append(f"{t.user}{t.bold}you{t.reset}")
            if entry.body:
                parts.append(_indent_block(entry.body))

        elif entry.kind == "assistant":
            parts.append(f"{t.assistant}{t.bold}assistant{t.reset}")
            if entry.body:
                parts.append(_indent_block(render_markdownish(entry.body)))

        elif entry.kind == "progress":
            parts.append(f"{t.progress}{t.bold}progress{t.reset}")
            summary = _first_line(entry.actionSummary or entry.body)
            parts.append(
                _indent_block(
                    _render_status_line(
                        entry.phaseVerb or "Working",
                        summary or None,
                        t.progress,
                    )
                )
            )

        elif entry.kind == "orchestration":
            parts.append(f"{t.accent2}{t.bold}orchestration{t.reset}")
            parts.append(_indent_block(render_orchestration_block(entry)))

        elif entry.kind == "tool":
            parts.append(_render_tool_entry(entry))

    return "\n".join(parts)


def _entry_state(entry: TranscriptEntry) -> tuple:
    return (
        entry.kind,
        entry.body,
        entry.status,
        entry.actionSummary,
        entry.collapsed,
        entry.collapsePhase,
        entry.collapsedSummary,
        entry.toolName,
        entry.narrativeLine,
        entry.phaseLabel,
        entry.phaseVerb,
        entry.animationFrame,
        tuple(
            (
                worker.name,
                worker.role,
                worker.mission,
                worker.status,
                worker.colorKey,
                worker.latestEvent,
                worker.spinnerVerb,
            )
            for worker in entry.workers
        ),
    )


# ---------------------------------------------------------------------------
# Per-entry rendering cache
# ---------------------------------------------------------------------------

_entry_cache: dict[int, tuple[tuple, list[str]]] = {}
_CACHE_MAX_SIZE = 500


def _get_entry_lines(entry: TranscriptEntry) -> list[str]:
    state = _entry_state(entry)

    entry_id = id(entry)
    cached = _entry_cache.get(entry_id)
    if cached is not None and cached[0] == state:
        return cached[1]

    lines = _render_transcript_entry(entry).split("\n")

    if len(_entry_cache) > _CACHE_MAX_SIZE:
        keys = list(_entry_cache.keys())
        for k in keys[: len(keys) // 2]:
            del _entry_cache[k]

    _entry_cache[entry_id] = (state, lines)
    return lines


# ---------------------------------------------------------------------------
# Per-entry line count cache
# ---------------------------------------------------------------------------

_line_count_cache: dict[int, tuple[tuple, int]] = {}


def _get_entry_line_count(entry: TranscriptEntry) -> int:
    state = _entry_state(entry)
    entry_id = id(entry)

    cached_lc = _line_count_cache.get(entry_id)
    if cached_lc is not None and cached_lc[0] == state:
        return cached_lc[1]

    cached_full = _entry_cache.get(entry_id)
    if cached_full is not None and cached_full[0] == state:
        count = len(cached_full[1])
        _line_count_cache[entry_id] = (state, count)
        return count

    lines = _get_entry_lines(entry)
    count = len(lines)
    _line_count_cache[entry_id] = (state, count)
    return count


# ---------------------------------------------------------------------------
# Windowed transcript rendering — O(visible)
# ---------------------------------------------------------------------------

def _compute_total_lines(
    entries: list[TranscriptEntry],
    separator_lines: list[str] | tuple[str, ...] = _SEPARATOR_LINES,
) -> int:
    if not entries:
        return 0
    separator_line_count = len(separator_lines)
    total = 0
    for i, entry in enumerate(entries):
        if i > 0:
            total += separator_line_count
        total += _get_entry_line_count(entry)
    return total


def _render_visible_window(
    entries: list[TranscriptEntry],
    start_line: int,
    end_line: int,
    separator_lines: list[str] | tuple[str, ...] = _SEPARATOR_LINES,
) -> list[str]:
    if not entries:
        return []

    result: list[str] = []
    current_line = 0
    separator_line_count = len(separator_lines)

    for i, entry in enumerate(entries):
        if i > 0:
            sep_start = current_line
            sep_end = current_line + separator_line_count
            if sep_start < end_line and sep_end > start_line:
                vis_start = max(0, start_line - sep_start)
                vis_end = min(separator_line_count, end_line - sep_start)
                result.extend(separator_lines[vis_start:vis_end])
            current_line = sep_end
            if current_line >= end_line:
                break

        entry_line_count = _get_entry_line_count(entry)
        entry_start = current_line
        entry_end = current_line + entry_line_count

        if entry_start < end_line and entry_end > start_line:
            lines = _get_entry_lines(entry)
            vis_start = max(0, start_line - entry_start)
            vis_end = min(entry_line_count, end_line - entry_start)
            result.extend(lines[vis_start:vis_end])

        current_line = entry_end
        if current_line >= end_line:
            break

    return result


def get_transcript_max_scroll_offset(
    entries: list[TranscriptEntry],
    window_size: int | None = None,
    *,
    separator_lines: list[str] | tuple[str, ...] = _SEPARATOR_LINES,
) -> int:
    if not entries:
        return 0
    total = _compute_total_lines(entries, separator_lines=separator_lines)
    ws = get_transcript_window_size(window_size)
    return max(0, total - ws)


def render_transcript(
    entries: list[TranscriptEntry],
    scroll_offset: int,
    window_size: int | None = None,
    *,
    separator_lines: list[str] | tuple[str, ...] = _SEPARATOR_LINES,
) -> str:
    """Render a windowed view of the transcript. O(visible)."""
    t = theme()
    if not entries:
        return ""

    total_lines = _compute_total_lines(entries, separator_lines=separator_lines)
    ws = get_transcript_window_size(window_size)
    max_offset = max(0, total_lines - ws)
    offset = max(0, min(scroll_offset, max_offset))

    if offset == 0:
        # No scroll indicator needed — use full window
        end = total_lines
        start = max(0, end - ws)
        visible_lines = _render_visible_window(entries, start, end, separator_lines=separator_lines)
        return "\n".join(visible_lines)

    # Reserve 1 line for the scroll indicator so the panel stays within bounds
    content_ws = max(1, ws - 1)
    end = total_lines - offset
    start = max(0, end - content_ws)
    visible_lines = _render_visible_window(entries, start, end, separator_lines=separator_lines)
    body = "\n".join(visible_lines)

    return (
        f"{body}\n"
        f"{t.subtle}  {ICON_DIVIDER * 2} scroll {offset}/{max_offset} "
        f"(PgUp/PgDn or scroll){ICON_DIVIDER * 2}{t.reset}"
    )


def render_transcript_simple_windowed(
    entries: list[TranscriptEntry],
    scroll_offset: int,
    window_size: int | None = None,
) -> str:
    return render_transcript(
        entries,
        scroll_offset,
        window_size,
        separator_lines=_SIMPLE_SEPARATOR_LINES,
    )


# ---------------------------------------------------------------------------
# Legacy full-render API (backward compat)
# ---------------------------------------------------------------------------

def _render_transcript_lines(entries: list[TranscriptEntry]) -> list[str]:
    """Render all entries into lines with separators. Kept for backward compat."""
    all_lines: list[str] = []
    for i, entry in enumerate(entries):
        if i > 0:
            all_lines.extend(_SEPARATOR_LINES)
        all_lines.extend(_get_entry_lines(entry))
    return all_lines


def format_transcript_text(entries: list[TranscriptEntry]) -> str:
    """Format transcript entries as plain text (no ANSI) for file saving."""
    parts = []
    for entry in entries:
        label = "you" if entry.kind == "user" else entry.kind
        if entry.kind == "tool":
            status_text = f" ({entry.status})" if entry.status else ""
            label = f"{entry.toolName or 'tool'}{status_text}"
        body = render_orchestration_block(entry) if entry.kind == "orchestration" else entry.body
        indented = "\n".join("  " + line for line in body.splitlines())
        parts.append(f"{label}\n{indented}")
    return "\n\n---\n\n".join(parts)
