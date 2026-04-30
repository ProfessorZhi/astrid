from __future__ import annotations

from dataclasses import dataclass


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"


def _fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _bg(r: int, g: int, b: int) -> str:
    return f"\x1b[48;2;{r};{g};{b}m"


@dataclass(frozen=True, slots=True)
class InlinePalette:
    prompt: str = _fg(242, 141, 66)
    user: str = _fg(72, 153, 116)
    assistant: str = _fg(80, 141, 214)
    progress: str = _fg(158, 116, 214)
    tool: str = _fg(213, 151, 79)
    success: str = _fg(87, 166, 98)
    error: str = _fg(218, 82, 82)
    approval: str = _fg(227, 179, 74)
    path: str = _fg(130, 169, 220)
    muted: str = _fg(132, 137, 145)
    panel_bg: str = _bg(33, 35, 39)


PALETTE = InlinePalette()


def paint(text: str, color: str, *, bold: bool = False, dim: bool = False) -> str:
    prefix = color
    if bold:
        prefix += BOLD
    if dim:
        prefix += DIM
    return f"{prefix}{text}{RESET}"


def render_prompt() -> str:
    return f"{paint('astrid', PALETTE.prompt, bold=True)}{paint('>', PALETTE.muted)} "


def render_role_header(role: str) -> str:
    color = {
        "you": PALETTE.user,
        "assistant": PALETTE.assistant,
        "tool": PALETTE.tool,
        "progress": PALETTE.progress,
    }.get(role, PALETTE.muted)
    return paint(role, color, bold=True)


def render_status_line(content: str) -> str:
    clean = " ".join(str(content).split()).strip()
    if not clean:
        clean = "working"
    return f"{paint('status', PALETTE.progress, bold=True)} {paint(clean[:180], PALETTE.muted)}"


def render_mode_line(mode: str, *, high_risk: bool = False) -> str:
    color = PALETTE.error if high_risk else PALETTE.success
    label = "permission"
    return f"{paint(label, PALETTE.approval, bold=True)} {paint(mode, color)}"


def render_warning_line(text: str) -> str:
    return paint(text, PALETTE.error, bold=True)


def render_tool_start(tool_name: str) -> str:
    return f"{paint('tool', PALETTE.tool, bold=True)} {paint(tool_name, PALETTE.path)} {paint('running', PALETTE.muted)}"


def render_tool_result(tool_name: str, output: str, is_error: bool) -> str:
    status = "error" if is_error else "success"
    status_color = PALETTE.error if is_error else PALETTE.success
    preview = output.strip().splitlines()[0] if output.strip() else status
    header = f"{paint('tool', PALETTE.tool, bold=True)} {paint(tool_name, PALETTE.path)} {paint(status, status_color)}"
    return f"{header}\n  {paint(preview[:180], PALETTE.muted)}\n"


def render_assistant_message(content: str) -> str:
    return f"{render_role_header('assistant')}\n{content}\n"


def render_paste_preview(index: int, extra_lines: int) -> str:
    return paint(f"[Pasted text #{index} +{extra_lines} lines]", PALETTE.approval)


def render_permission_panel(request: dict) -> str:
    lines = [
        "",
        paint("Action Required", PALETTE.approval, bold=True),
        str(request.get("summary") or "Permission request"),
    ]
    details = request.get("details") or []
    for detail in details[:3]:
        text = str(detail).rstrip()
        if text:
            lines.append(f"  {paint(text, PALETTE.muted)}")
    lines.append(paint("Use number keys, Enter for default, or Esc/5 to reject.", PALETTE.muted))
    for index, choice in enumerate(request.get("choices", [])):
        key = choice.get("key", str(index + 1))
        label = choice.get("label", "")
        marker = ">" if index == 0 else " "
        color = PALETTE.approval if index == 0 else PALETTE.muted
        lines.append(paint(f" {marker} {key} {label}", color))
    return "\n".join(lines)
