from __future__ import annotations

from astrid.tty_app import run_tty_app


def run_full_tui_app(**kwargs):
    """Run the current full-screen TUI implementation.

    ``astrid.tty_app`` remains the compatibility entrypoint during the first
    package reorganization phase.
    """
    return run_tty_app(**kwargs)
