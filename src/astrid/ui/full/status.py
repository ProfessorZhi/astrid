from __future__ import annotations

from typing import Any

from astrid.tui.theme import theme


SINGLE_AGENT_BUSY_SPINNER_FRAMES: tuple[str, ...] = ("◜", "◠", "◝", "◞", "◡", "◟")
SINGLE_AGENT_DEFAULT_VERB = "Transfiguring"


def render_busy_spinner(frame: int) -> str:
    spinner = SINGLE_AGENT_BUSY_SPINNER_FRAMES[frame % len(SINGLE_AGENT_BUSY_SPINNER_FRAMES)]
    t = theme()
    return f"{t.progress}{t.bold}{spinner}{t.reset}"


def summarize_progress_update(content: str, *, truncate) -> tuple[str, str]:
    summary = truncate(" ".join(content.split()).strip(), 160)
    lowered = summary.lower()
    if any(token in lowered for token in ("review", "validate", "check", "审查", "校验")):
        return "Reviewing", summary
    if any(token in lowered for token in ("search", "scan", "inspect", "read", "grep", "搜索", "扫描", "读取")):
        return "Inspecting", summary
    if any(token in lowered for token in ("command", "tool", "run", "execute", "命令", "工具", "执行")):
        return "Running", summary
    if any(token in lowered for token in ("merge", "combine", "collect", "汇总", "合并")):
        return "Collecting", summary
    return SINGLE_AGENT_DEFAULT_VERB, summary


def render_single_agent_busy_line(state: Any) -> str:
    t = theme()
    line = f"{render_busy_spinner(state.animation_frame)} {t.progress}{t.bold}{state.busy_verb}{t.reset}{t.progress}...{t.reset}"
    summary = state.current_action_summary
    if not summary and state.status and state.status != f"{state.busy_verb}...":
        summary = state.status
    if summary:
        return f"{line}\n  {t.assistant}{summary}{t.reset}"
    return line
