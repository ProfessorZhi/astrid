from __future__ import annotations

from typing import Any, Callable

from astrid.tui.chrome import get_permission_prompt_max_scroll_offset
from astrid.tui.input_parser import KeyEvent, ParsedInputEvent, TextEvent, WheelEvent


def render_shell_permission_prompt(state: Any) -> str:
    pending = state.pending_approval
    request = pending.request if pending is not None else {}
    lines = ["Action Required", request.get("summary", "Permission Request")]
    details = request.get("details", [])
    for detail in details:
        for line in str(detail).splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
                break
        if len(lines) >= 4:
            break
    lines.append("")
    lines.append("Use number keys, arrows + Enter, or Esc to reject.")
    choices = request.get("choices", [])
    selected = getattr(pending, "selected_choice_index", 0) if pending is not None else 0
    for index, choice in enumerate(choices):
        marker = ">" if index == selected else " "
        key = choice.get("key", "")
        label = choice.get("label", "")
        lines.append(f"{marker} {key} {label}".rstrip())
    return "\n".join(lines)


def scroll_pending_approval_by(state: Any, delta: int) -> bool:
    pending = state.pending_approval
    if not pending or not pending.details_expanded:
        return False
    max_offset = get_permission_prompt_max_scroll_offset(pending.request, expanded=True)
    next_offset = max(0, min(max_offset, pending.details_scroll_offset + delta))
    if next_offset == pending.details_scroll_offset:
        return False
    pending.details_scroll_offset = next_offset
    return True


def toggle_pending_approval_expand(state: Any) -> bool:
    pending = state.pending_approval
    if not pending or pending.request.get("kind") != "edit":
        return False
    pending.details_expanded = not pending.details_expanded
    pending.details_scroll_offset = 0
    return True


def move_pending_approval_selection(state: Any, delta: int) -> bool:
    pending = state.pending_approval
    if not pending or pending.feedback_mode:
        return False
    total = len(pending.request.get("choices", []))
    if total <= 0:
        return False
    pending.selected_choice_index = (pending.selected_choice_index + delta + total) % total
    return True


def handle_pending_approval_event(
    state: Any,
    pending: Any,
    event: ParsedInputEvent,
    rerender: Callable[[], None],
    approval_event: Any,
    approval_result: dict[str, Any],
    *,
    feedback_handler: Callable[[Any, ParsedInputEvent, Callable[[], None], Any, dict[str, Any]], None],
    capture_mouse: Callable[[], bool],
) -> None:
    """Handle input events while a permission approval is pending."""
    if pending.feedback_mode:
        feedback_handler(state, event, rerender, approval_event, approval_result)
        return

    if isinstance(event, KeyEvent):
        if handle_pending_approval_key(state, event, rerender, approval_event, approval_result):
            return

    if isinstance(event, TextEvent) and not event.ctrl:
        if handle_pending_approval_text(state, event, rerender, approval_event, approval_result):
            return

    if isinstance(event, WheelEvent):
        if not capture_mouse():
            return
        state.wheel_debug_event_count += 1
        state.wheel_debug_last_direction = event.direction
        handle_pending_approval_wheel(state, event, rerender, capture_mouse=capture_mouse)


def handle_pending_approval_key(
    state: Any,
    event: KeyEvent,
    rerender: Callable[[], None],
    approval_event: Any,
    approval_result: dict[str, Any],
) -> bool:
    """Handle key events during pending approval. Returns True if handled."""
    pending = state.pending_approval

    if event.name == "escape":
        approval_result.clear()
        approval_result["decision"] = "deny_once"
        approval_event.set()
        rerender()
        return True

    if event.name == "return":
        confirm_pending_choice(state, rerender, approval_event, approval_result)
        return True

    if event.name == "up" and move_pending_approval_selection(state, -1):
        rerender()
        return True

    if event.name == "down" and move_pending_approval_selection(state, 1):
        rerender()
        return True

    if event.name == "pageup" and scroll_pending_approval_by(state, -5):
        rerender()
        return True

    if event.name == "pagedown" and scroll_pending_approval_by(state, 5):
        rerender()
        return True

    choices = pending.request.get("choices", [])
    for choice in choices:
        if event.text == choice.get("key"):
            select_pending_choice(state, choice, rerender, approval_event, approval_result)
            return True

    return False


def handle_pending_approval_text(
    state: Any,
    event: TextEvent,
    rerender: Callable[[], None],
    approval_event: Any,
    approval_result: dict[str, Any],
) -> bool:
    """Handle text events during pending approval. Returns True if handled."""
    pending = state.pending_approval

    if event.text == "v" and toggle_pending_approval_expand(state):
        rerender()
        return True

    choices = pending.request.get("choices", [])
    for choice in choices:
        if event.text == choice.get("key"):
            select_pending_choice(state, choice, rerender, approval_event, approval_result)
            return True

    return False


def handle_pending_approval_wheel(
    state: Any,
    event: WheelEvent,
    rerender: Callable[[], None],
    *,
    capture_mouse: Callable[[], bool],
) -> bool:
    """Handle wheel events during pending approval for scrolling."""
    if not capture_mouse():
        return False
    delta = 3 if event.direction == "up" else -3
    if scroll_pending_approval_by(state, delta):
        rerender()
        return True
    return False


def confirm_pending_choice(
    state: Any,
    rerender: Callable[[], None],
    approval_event: Any,
    approval_result: dict[str, Any],
) -> None:
    """Confirm the selected permission choice."""
    pending = state.pending_approval
    choices = pending.request.get("choices", [])

    if choices and 0 <= pending.selected_choice_index < len(choices):
        choice = choices[pending.selected_choice_index]
        select_pending_choice(state, choice, rerender, approval_event, approval_result)
    else:
        approval_result.clear()
        approval_result["decision"] = "allow_once"
        approval_event.set()
        rerender()


def select_pending_choice(
    state: Any,
    choice: dict[str, Any],
    rerender: Callable[[], None],
    approval_event: Any,
    approval_result: dict[str, Any],
) -> None:
    """Select a permission choice and resolve it."""
    pending = state.pending_approval
    decision = choice.get("decision", "allow_once")

    if decision == "deny_with_feedback":
        pending.feedback_mode = True
        pending.feedback_input = ""
        rerender()
        return

    approval_result.clear()
    approval_result["decision"] = decision
    approval_event.set()
    rerender()
