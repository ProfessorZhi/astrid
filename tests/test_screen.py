from __future__ import annotations

from io import StringIO

from astrid.tui import screen


def test_empty_term_is_not_treated_as_dumb_terminal(monkeypatch) -> None:
    monkeypatch.setenv("TERM", "")
    monkeypatch.setattr(screen.sys, "stdout", type("TTY", (), {"isatty": lambda self: True})())

    assert screen._is_dumb_terminal() is False


def test_enter_alternate_screen_still_writes_sequences_when_term_is_empty(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "")
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "linux")
    monkeypatch.setattr(screen, "_enable_windows_vt_processing", lambda: None)
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.enter_alternate_screen()

    rendered = output.getvalue()
    assert screen.ENTER_ALT_SCREEN in rendered
    assert screen.ERASE_SCREEN_AND_HOME in rendered


def test_exit_alternate_screen_still_writes_sequences_when_term_is_empty(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "")
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "linux")
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.exit_alternate_screen()

    rendered = output.getvalue()
    assert screen.EXIT_ALT_SCREEN in rendered


def test_dumb_term_skips_alternate_screen_sequences(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen, "_enable_windows_vt_processing", lambda: None)
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.enter_alternate_screen()

    assert output.getvalue() == ""


def test_windows_enter_alternate_screen_uses_alt_buffer_by_default(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "win32")
    monkeypatch.setattr(screen, "_enable_windows_vt_processing", lambda: None)
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.enter_alternate_screen()

    rendered = output.getvalue()
    assert screen.ENTER_ALT_SCREEN in rendered
    assert screen.ERASE_SCREEN_AND_HOME in rendered
    assert screen.DISABLE_ALTERNATE_SCROLL in rendered
    assert screen.ENABLE_MOUSE_TRACKING not in rendered


def test_windows_exit_alternate_screen_restores_alt_buffer_by_default(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "win32")
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.exit_alternate_screen()

    rendered = output.getvalue()
    assert screen.ENABLE_ALTERNATE_SCROLL in rendered
    assert screen.EXIT_ALT_SCREEN in rendered
    assert screen.DISABLE_MOUSE_TRACKING not in rendered


def test_windows_can_explicitly_disable_alternate_screen(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("ASTRID_ALT_SCREEN", "0")
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "win32")
    monkeypatch.setattr(screen, "_enable_windows_vt_processing", lambda: None)
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.enter_alternate_screen()

    rendered = output.getvalue()
    assert screen.ENTER_ALT_SCREEN not in rendered
    assert screen.ERASE_SCREEN_AND_HOME not in rendered
    assert rendered == screen.DISABLE_ALTERNATE_SCROLL


def test_windows_disable_alt_screen_still_keeps_mouse_capture_in_tui_mode(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("ASTRID_ALT_SCREEN", "0")
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "win32")
    monkeypatch.setattr(screen, "_enable_windows_vt_processing", lambda: None)
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.enter_alternate_screen()

    rendered = output.getvalue()
    assert screen.ENTER_ALT_SCREEN not in rendered
    assert rendered == screen.DISABLE_ALTERNATE_SCROLL


def test_agent_mode_uses_same_alt_screen_setup_as_tui(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "agent")
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "win32")
    monkeypatch.setattr(screen, "_enable_windows_vt_processing", lambda: None)
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.enter_alternate_screen()

    rendered = output.getvalue()
    assert screen.ENTER_ALT_SCREEN in rendered
    assert rendered == (
        screen.ENTER_ALT_SCREEN
        + screen.ERASE_SCREEN_AND_HOME
        + screen.DISABLE_ALTERNATE_SCROLL
    )


def test_windows_can_explicitly_enable_mouse_tracking(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("ASTRID_ENABLE_MOUSE", "1")
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "win32")
    monkeypatch.setattr(screen, "_enable_windows_vt_processing", lambda: None)
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.enter_alternate_screen()

    rendered = output.getvalue()
    assert screen.ENTER_ALT_SCREEN in rendered
    assert screen.DISABLE_ALTERNATE_SCROLL in rendered
    assert screen.ENABLE_MOUSE_TRACKING in rendered


def test_windows_exit_without_alt_screen_still_disables_mouse_tracking(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("ASTRID_ALT_SCREEN", "0")
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.setattr(screen.sys, "platform", "win32")
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.exit_alternate_screen()

    assert output.getvalue() == screen.ENABLE_ALTERNATE_SCROLL


def test_shell_mode_skips_alt_screen_and_mouse_capture(monkeypatch) -> None:
    output = StringIO()

    class _TTYBuffer:
        def isatty(self) -> bool:
            return True

        def write(self, data: str) -> int:
            return output.write(data)

        def flush(self) -> None:
            output.flush()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "shell")
    monkeypatch.setenv("ASTRID_ALT_SCREEN", "0")
    monkeypatch.setattr(screen.sys, "platform", "win32")
    monkeypatch.setattr(screen, "_enable_windows_vt_processing", lambda: None)
    monkeypatch.setattr(screen.sys, "stdout", _TTYBuffer())

    screen.enter_alternate_screen()
    screen.exit_alternate_screen()

    assert output.getvalue() == ""
