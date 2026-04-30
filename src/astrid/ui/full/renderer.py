from __future__ import annotations

from astrid.tui.chrome import render_welcome_workbench


def render_full_welcome(
    *,
    app_name: str,
    version: str,
    model_name: str,
    workspace: str,
    buddy_block: str,
    tips: list[str],
    recent_items: list[str],
    width: int | None,
) -> str:
    return render_welcome_workbench(
        app_name=app_name,
        version=version,
        model_name=model_name,
        workspace=workspace,
        buddy_block=buddy_block,
        tips=tips,
        recent_items=recent_items,
        width=width,
    )
