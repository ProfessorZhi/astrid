from __future__ import annotations

from astrid.ui.common.frontend import FrontendRuntime


class InlineTuiFrontend:
    """Codex-style inline TUI placeholder.

    Inline TUI will share RuntimeController with shell/fullscreen frontends so
    permission modes and steering stay runtime-owned.
    """

    name = "inline"

    def run(self, runtime: FrontendRuntime) -> list[dict[str, str]] | None:
        raise NotImplementedError("inline TUI is planned but not implemented yet")


def run_inline_tui_app(**kwargs):
    runtime = kwargs.get("frontend_runtime")
    if isinstance(runtime, FrontendRuntime):
        return InlineTuiFrontend().run(runtime)
    raise NotImplementedError("inline TUI is planned but not implemented yet")
