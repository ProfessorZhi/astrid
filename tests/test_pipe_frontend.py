from __future__ import annotations

from astrid.ui.shell.pipe import run_pipe_inputs


class _DummyController:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.inputs: list[str] = []

    def handle_user_input(self, user_input: str):
        self.inputs.append(user_input)
        if user_input == "/exit":
            return None
        return self.messages


def test_pipe_multiline_prompt_is_one_turn() -> None:
    controller = _DummyController()

    run_pipe_inputs(input_stream=["Please build this\n", "- include movement\n", "- include shooting\n"], controller=controller)  # type: ignore[arg-type]

    assert controller.inputs == ["Please build this\n- include movement\n- include shooting"]


def test_pipe_slash_command_script_stays_line_oriented() -> None:
    controller = _DummyController()

    run_pipe_inputs(input_stream=["/help\n", "/status\n", "/exit\n"], controller=controller)  # type: ignore[arg-type]

    assert controller.inputs == ["/help", "/status", "/exit"]
