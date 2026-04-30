from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.tui.chrome import render_welcome_workbench
from astrid.ui.common.pet import pick_startup_pet


@dataclass(frozen=True, slots=True)
class WelcomeContext:
    app_name: str = "Astrid"
    version: str = "welcome · inline mode"
    model_name: str = "unknown"
    workspace: str = "."
    permission_mode: str = "default"
    recent_items: tuple[str, ...] = ()
    tips: tuple[str, ...] = (
        "Type a message to start working",
        "Use --shell for native fallback or --tui for full-screen UI",
    )


def _model_name_from_controller(controller: Any) -> str:
    model = getattr(controller, "model", None)
    runtime = getattr(model, "runtime", None)
    if isinstance(runtime, dict):
        return str(runtime.get("model") or runtime.get("modelName") or "unknown")
    return str(getattr(model, "model", None) or getattr(model, "name", None) or "unknown")


def _permission_mode_from_controller(controller: Any) -> str:
    permissions = getattr(controller, "permissions", None)
    get_summary = getattr(permissions, "get_summary", None)
    if not callable(get_summary):
        return "default"
    for line in get_summary():
        if str(line).startswith("permission mode:"):
            return str(line).split(":", 1)[1].strip()
    return "default"


def build_welcome_context(*, cwd: str, controller: Any, mode: str) -> WelcomeContext:
    return WelcomeContext(
        version=f"welcome · {mode} mode",
        model_name=_model_name_from_controller(controller),
        workspace=str(Path(cwd)),
        permission_mode=_permission_mode_from_controller(controller),
    )


def render_startup_welcome(*, cwd: str, controller: Any, mode: str, width: int | None = None) -> str:
    context = build_welcome_context(cwd=cwd, controller=controller, mode=mode)
    tips = list(context.tips)
    if context.permission_mode:
        tips.append(f"permission {context.permission_mode}")
    buddy = pick_startup_pet(seed=f"{cwd}:{context.model_name}:{mode}")
    return render_welcome_workbench(
        app_name=context.app_name,
        version=context.version,
        model_name=context.model_name,
        workspace=context.workspace,
        buddy_block=buddy,
        tips=tips,
        recent_items=list(context.recent_items),
        width=width,
    )
