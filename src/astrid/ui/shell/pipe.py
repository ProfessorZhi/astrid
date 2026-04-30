from __future__ import annotations

from collections.abc import Iterable

from astrid.runtime.controller import RuntimeController
from astrid.ui.common.text_input import normalize_cli_input
from astrid.ui.shell.banner import render_banner, render_quick_start


def should_render_legacy_intro(stdin_isatty: bool) -> bool:
    return not stdin_isatty


def render_pipe_intro(
    *,
    runtime: dict | None,
    cwd: str,
    permission_summary: list[str],
    counts: dict[str, int],
) -> None:
    print(render_banner(runtime, cwd, permission_summary, counts))
    print(render_quick_start())


def run_pipe_inputs(
    *,
    input_stream: Iterable[str],
    controller: RuntimeController,
) -> list[dict[str, str]]:
    messages = controller.messages
    raw_text = "".join(input_stream)
    normalized_lines = [normalize_cli_input(line) for line in raw_text.splitlines()]
    nonempty_lines = [line for line in normalized_lines if line]
    if not nonempty_lines:
        return messages

    if all(line.startswith("/") for line in nonempty_lines):
        inputs = nonempty_lines
    else:
        inputs = [normalize_cli_input(raw_text)]

    for user_input in inputs:
        if not user_input:
            continue
        next_messages = controller.handle_user_input(user_input)
        if next_messages is None:
            break
        messages = next_messages
    return messages
