from __future__ import annotations

from collections.abc import Callable

from astrid.runtime.controller import RuntimeController
from astrid.ui.common.text_input import normalize_cli_input


def render_shell_intro() -> str:
    return (
        "Astrid shell mode\n"
        "PowerShell keeps native scrollback and wheel behavior.\n"
        "Use 'astrid --tui' for the full-screen interface.\n"
    )


def run_shell_repl(
    *,
    controller: RuntimeController,
    input_reader: Callable[[str], str] | None = None,
    intro: str | None = None,
) -> list[dict[str, str]]:
    print(intro if intro is not None else render_shell_intro())
    read_input = input_reader or input
    messages = controller.messages
    while True:
        try:
            raw_input = read_input("astrid> ")
        except EOFError:
            break
        user_input = normalize_cli_input(raw_input)
        if not user_input:
            continue
        next_messages = controller.handle_user_input(user_input)
        if next_messages is None:
            break
        messages = next_messages
    return messages
