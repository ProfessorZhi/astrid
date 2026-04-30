from __future__ import annotations

from typing import Any

from astrid.tui.types import TranscriptEntry


def mark_running_tools_as_error(state: Any, message: str) -> None:
    """Mark all currently running tool entries as failed."""
    for entry in state.transcript:
        if entry.kind == "tool" and entry.status == "running":
            entry.status = "error"
            entry.body = message
            entry.collapsed = False
            entry.collapsedSummary = None
            entry.collapsePhase = None
            state.recent_tools.append({"name": entry.toolName or "unknown", "status": "error"})
    if any(e.kind == "tool" and e.status == "error" for e in state.transcript):
        state.active_tool = None


def update_tool_entry(state: Any, entry_id: int, status: str, body: str) -> None:
    """Update a tool entry's status and output body."""
    for entry in state.transcript:
        if entry.id == entry_id and entry.kind == "tool":
            entry.status = status
            entry.body = body
            entry.collapsed = False
            entry.collapsedSummary = None
            entry.collapsePhase = None
            return


def set_tool_entry_collapse_phase(state: Any, entry_id: int, phase: int) -> None:
    """Set the collapse animation phase for a completed tool entry."""
    for entry in state.transcript:
        if entry.id == entry_id and entry.kind == "tool" and entry.status != "running":
            entry.collapsePhase = phase
            return


def collapse_tool_entry(state: Any, entry_id: int, summary: str) -> None:
    """Collapse a completed tool entry to show only a summary line."""
    for entry in state.transcript:
        if entry.id == entry_id and entry.kind == "tool" and entry.status != "running":
            entry.collapsePhase = None
            entry.collapsed = True
            entry.collapsedSummary = summary
            return


def get_running_tool_entries(state: Any) -> list[TranscriptEntry]:
    """Return transcript entries that are still in running status."""
    return [e for e in state.transcript if e.kind == "tool" and e.status == "running"]


def finalize_dangling_running_tools(state: Any) -> None:
    """Mark running tools as errors when a turn ends unexpectedly."""
    running = get_running_tool_entries(state)
    if running:
        error_message = (
            f"{running[0].body}\n\n"
            "ERROR: Tool did not report a final result before the turn ended. "
            "This usually means the command kept running in the background "
            "or the tool lifecycle got out of sync."
        )
        mark_running_tools_as_error(state, error_message)
        state.status = f"Previous turn ended with {len(running)} unfinished tool call(s)."


def summarize_collapsed_tool_body(output: str) -> str:
    line = next(
        (line.strip() for line in output.split("\n") if line.strip()),
        "output collapsed",
    )
    return line[:140] + "..." if len(line) > 140 else line


def apply_tool_result_visual_state(
    entry: TranscriptEntry,
    tool_name: str,
    output: str,
    is_error: bool,
) -> None:
    """Apply tool result visual state to a transcript entry."""
    entry.status = "error" if is_error else "success"
    entry.body = f"ERROR: {output}" if is_error else output
    if is_error:
        entry.collapsed = False
        entry.collapsedSummary = None
        entry.collapsePhase = None
    else:
        entry.collapsed = True
        entry.collapsedSummary = summarize_collapsed_tool_body(output)
        entry.collapsePhase = 3


def mark_unfinished_tools(state: Any) -> int:
    """Mark running tool entries as errors and clean up state. Returns affected count."""
    count = 0
    for entry in state.transcript:
        if entry.kind == "tool" and entry.status == "running":
            entry.status = "error"
            entry.body = (
                f"{entry.body}\n\n"
                "ERROR: Tool did not report a final result before the turn ended. "
                "This usually means the command kept running in the background "
                "or the tool lifecycle got out of sync."
            )
            entry.collapsed = False
            entry.collapsedSummary = None
            entry.collapsePhase = None
            state.recent_tools.append({"name": entry.toolName or "unknown", "status": "error"})
            count += 1
    if hasattr(state, "pending_tool_runs"):
        state.pending_tool_runs = {}
    state.active_tool = None
    return count
