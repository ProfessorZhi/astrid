from __future__ import annotations

import os
import sys

ENTER_ALT_SCREEN = "\u001b[?1049h"
EXIT_ALT_SCREEN = "\u001b[?1049l"
ERASE_SCREEN_AND_HOME = "\u001b[2J\u001b[H"
DISABLE_ALTERNATE_SCROLL = "\u001b[?1007l"
ENABLE_ALTERNATE_SCROLL = "\u001b[?1007h"
# Mouse tracking sequence breakdown:
#   ?1000h  — basic X10 mouse reporting (button press/release)
#   ?1002h  — button-event tracking (only reports while button pressed, can interfere)
#   ?1003h  — any-event tracking (reports all mouse events including scroll without button)
#   ?1006h  — SGR extended encoding (supports coordinates > 223, required for modern terminals)
# Strategy: use ?1000h (basic) + ?1003h (any-event for reliable scroll) + ?1006h (SGR format)
# This matches the TypeScript astrid version behavior (?1000h + ?1006h) but adds
# ?1003h for better SSH/remote terminal scroll wheel support.
ENABLE_MOUSE_TRACKING = "\u001b[?1000h\u001b[?1003h\u001b[?1006h"
DISABLE_MOUSE_TRACKING = "\u001b[?1006l\u001b[?1003l\u001b[?1000l"

# Terminal types that do not support alternate screen or mouse tracking.
_DUMB_TERMS = frozenset({"dumb", "linux"})


# ---------------------------------------------------------------------------
# Windows VT processing
# ---------------------------------------------------------------------------

_vt_enabled = False


def _enable_windows_vt_processing() -> None:
    """Enable ANSI / VT escape sequence processing on Windows 10+.

    Without this call the console ignores escape codes for colours,
    alternate-screen, cursor visibility, mouse tracking, etc.
    The function is a no-op on non-Windows platforms or when the
    underlying API call is unavailable.
    """
    global _vt_enabled
    if _vt_enabled:
        return

    if sys.platform != "win32":
        _vt_enabled = True
        return

    try:
        import ctypes
        import ctypes.wintypes as wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        STD_OUTPUT_HANDLE = -11
        STD_ERROR_HANDLE = -12
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        ENABLE_PROCESSED_OUTPUT = 0x0001

        for handle_id in (STD_OUTPUT_HANDLE, STD_ERROR_HANDLE):
            handle = kernel32.GetStdHandle(handle_id)
            mode = wintypes.DWORD()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING | ENABLE_PROCESSED_OUTPUT
                kernel32.SetConsoleMode(handle, new_mode)

        # Also enable VT input processing so the console sends ANSI
        # escape sequences for special keys instead of Windows-native
        # key events (useful for ConPTY / Windows Terminal).
        STD_INPUT_HANDLE = -10
        ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200
        h_in = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        mode_in = wintypes.DWORD()
        if kernel32.GetConsoleMode(h_in, ctypes.byref(mode_in)):
            kernel32.SetConsoleMode(h_in, mode_in.value | ENABLE_VIRTUAL_TERMINAL_INPUT)

        _vt_enabled = True
    except Exception:
        # If ctypes is unavailable or the call fails (e.g. old Windows),
        # fall through silently — ANSI codes will simply not render.
        _vt_enabled = True


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def hide_cursor() -> None:
    _enable_windows_vt_processing()
    sys.stdout.write("\u001b[?25l")
    sys.stdout.flush()


def show_cursor() -> None:
    sys.stdout.write("\u001b[?25h")
    sys.stdout.flush()


def _is_dumb_terminal() -> bool:
    """Return True if the terminal likely doesn't support escape sequences."""
    isatty = getattr(sys.stdout, "isatty", None)
    if callable(isatty) and not isatty():
        return True
    term = os.environ.get("TERM")
    if term is None:
        return False
    return term.lower() in _DUMB_TERMS


def _should_use_alternate_screen() -> bool:
    """Return True when the dedicated alt buffer should be used.

    Windows defaults to the alternate buffer so the interactive UI does not
    write directly into the host shell scrollback. Users can override with
    ASTRID_ALT_SCREEN=1 or ASTRID_ALT_SCREEN=0.
    """
    override = os.environ.get("ASTRID_ALT_SCREEN")
    if override is not None:
        normalized = override.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return _terminal_mode() == "tui"


def _is_codex_embedded_terminal() -> bool:
    originator = os.environ.get("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", "")
    return os.environ.get("CODEX_SHELL") == "1" or originator.strip().lower() == "codex desktop"


def _terminal_mode() -> str:
    raw_mode = os.environ.get("ASTRID_TERMINAL_MODE")
    if raw_mode is None and _is_codex_embedded_terminal():
        return "shell"
    mode = (raw_mode or "tui").strip().lower()
    if mode == "agent":
        return "tui"
    return mode if mode in {"tui", "shell"} else "tui"


def _is_mouse_tracking_enabled() -> bool:
    override = os.environ.get("ASTRID_ENABLE_MOUSE")
    if override is not None:
        normalized = override.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if sys.platform == "win32":
        return False
    return True


def _should_capture_mouse() -> bool:
    return _terminal_mode() == "tui" and _is_mouse_tracking_enabled()


def enter_alternate_screen() -> None:
    _enable_windows_vt_processing()
    if _is_dumb_terminal():
        # Dumb terminals (e.g. 'linux' console, 'dumb', piped output)
        # don't support alternate screen or mouse tracking.
        return
    sequence = ""
    if _should_use_alternate_screen():
        sequence += ENTER_ALT_SCREEN + ERASE_SCREEN_AND_HOME
    if _terminal_mode() == "tui":
        # Always disable terminal alternate-scroll rewrite in interactive TUI mode.
        # Otherwise some Windows terminals translate wheel input into Up/Down keys,
        # which collides with Astrid's history/slash navigation handlers.
        sequence += DISABLE_ALTERNATE_SCROLL
    if _should_capture_mouse():
        sequence += DISABLE_MOUSE_TRACKING + ENABLE_MOUSE_TRACKING
    sys.stdout.write(sequence)
    sys.stdout.flush()


def exit_alternate_screen() -> None:
    if _is_dumb_terminal():
        return
    sequence = ""
    if _should_capture_mouse():
        sequence += DISABLE_MOUSE_TRACKING
    if _terminal_mode() == "tui":
        sequence += ENABLE_ALTERNATE_SCROLL
    if _should_use_alternate_screen():
        sequence += EXIT_ALT_SCREEN
    sys.stdout.write(sequence)
    sys.stdout.flush()


def clear_screen() -> None:
    sys.stdout.write("\u001b[H\u001b[J")
    sys.stdout.flush()
