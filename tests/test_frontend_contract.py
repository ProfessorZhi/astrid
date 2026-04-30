from __future__ import annotations

from astrid.ui.common.frontend import FrontendRuntime
from astrid.ui.inline.app import InlineTuiFrontend
from astrid.ui.shell.repl import ShellFrontend


class _DummyController:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self.inputs: list[str] = []

    def handle_user_input(self, user_input: str):
        self.inputs.append(user_input)
        if user_input == "/exit":
            return None
        return self.messages

    @property
    def permissions(self):
        class _Permissions:
            def get_summary(self):
                return ["permission mode: default (policy_only)"]

        return _Permissions()


def test_shell_frontend_delegates_turns_to_runtime_controller() -> None:
    controller = _DummyController()
    entered = iter(["hello", "/exit"])
    runtime = FrontendRuntime(
        cwd=".",
        controller=controller,  # type: ignore[arg-type]
        transcript=[],
    )

    result = ShellFrontend(
        input_reader=lambda _prompt: next(entered),
        intro="",
    ).run(runtime)

    assert result == []
    assert controller.inputs == ["hello", "/exit"]


def test_inline_frontend_delegates_turns_to_runtime_controller() -> None:
    controller = _DummyController()
    entered = iter(["hello\nworld", "/exit"])
    runtime = FrontendRuntime(
        cwd=".",
        controller=controller,  # type: ignore[arg-type]
        transcript=[],
    )

    result = InlineTuiFrontend(
        input_reader=lambda _prompt: next(entered),
        intro="",
    ).run(runtime)

    assert result == []
    assert controller.inputs == ["hello\nworld", "/exit"]
