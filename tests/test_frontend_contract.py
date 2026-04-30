from __future__ import annotations

from astrid.ui.common.frontend import FrontendRuntime
from astrid.ui.inline import app as inline_app
from astrid.ui.inline.app import InlineTuiFrontend
from astrid.ui.inline.bottom_pane import InlineInputBuffer
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


def test_inline_input_buffer_compresses_multiline_paste_for_display() -> None:
    buffer = InlineInputBuffer()

    buffer.insert_paste("line1\nline2\nline3")

    assert buffer.value == "line1\nline2\nline3"
    assert buffer.display_text == "[Pasted text #1 +2 lines]"


def test_inline_input_buffer_backspace_removes_paste_block() -> None:
    buffer = InlineInputBuffer()
    buffer.insert_text("prefix ")
    buffer.insert_paste("line1\nline2")

    buffer.backspace()

    assert buffer.value == "prefix "
    assert buffer.display_text == "prefix "


def test_inline_input_buffer_keeps_text_after_paste_editable() -> None:
    buffer = InlineInputBuffer()
    buffer.insert_paste("line1\nline2")
    buffer.insert_text(" suffix")

    assert buffer.value == "line1\nline2 suffix"
    assert buffer.display_text == "[Pasted text #1 +1 lines] suffix"


def test_inline_windows_reader_uses_ctrl_v_clipboard(monkeypatch) -> None:
    keys = iter(["\x16", "\r"])
    writes: list[str] = []

    class _FakeMsvcrt:
        @staticmethod
        def getwch():
            return next(keys)

        @staticmethod
        def kbhit():
            return False

    monkeypatch.setitem(__import__("sys").modules, "msvcrt", _FakeMsvcrt)
    monkeypatch.setattr(inline_app, "_read_clipboard_text", lambda: "line1\nline2")
    monkeypatch.setattr(inline_app.sys.stdout, "write", lambda text: writes.append(text) or len(text))
    monkeypatch.setattr(inline_app.sys.stdout, "flush", lambda: None)

    result = inline_app._read_inline_input_windows("astrid> ")

    assert result == "line1\nline2"
    assert any("[Pasted text #1 +1 lines]" in write for write in writes)
