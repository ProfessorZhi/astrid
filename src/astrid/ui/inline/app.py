from __future__ import annotations

from collections.abc import Callable

from astrid.ui.common.frontend import FrontendRuntime
from astrid.ui.common.text_input import normalize_cli_input


def render_inline_intro(runtime: FrontendRuntime) -> str:
    summary = runtime.controller.permissions.get_summary()
    mode = next((line for line in summary if line.startswith("permission mode:")), "permission mode: default")
    warning = ""
    if "bypassPermissions" in mode:
        warning = "\nWARNING: bypassPermissions is high risk and bypasses Astrid policy prompts."
    return (
        "Astrid inline TUI\n"
        "Native scrollback stays available. Use --shell for plain fallback or --tui for full-screen UI.\n"
        f"{mode}{warning}\n"
    )


class InlineTuiFrontend:
    """Codex-style inline TUI MVP.

    This keeps transcript history in native terminal scrollback and delegates
    all turn execution to RuntimeController.
    """

    name = "inline"

    def __init__(
        self,
        *,
        input_reader: Callable[[str], str] | None = None,
        intro: str | None = None,
    ) -> None:
        self.input_reader = input_reader
        self.intro = intro

    def run(self, runtime: FrontendRuntime) -> list[dict[str, str]] | None:
        print(self.intro if self.intro is not None else render_inline_intro(runtime))
        read_input = self.input_reader or input
        messages = runtime.controller.messages
        while True:
            try:
                raw_input = read_input("astrid> ")
            except EOFError:
                break
            user_input = normalize_cli_input(raw_input)
            if not user_input:
                continue
            if "\n" in user_input:
                line_count = user_input.count("\n") + 1
                print(f"[Pasted text #1 +{line_count - 1} lines]")
            next_messages = runtime.controller.handle_user_input(user_input)
            if next_messages is None:
                break
            messages = next_messages
        return messages


def run_inline_tui_app(**kwargs):
    runtime = kwargs.get("frontend_runtime")
    if isinstance(runtime, FrontendRuntime):
        return InlineTuiFrontend().run(runtime)
    raise NotImplementedError("inline TUI is planned but not implemented yet")
