from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from astrid.runtime.controller import RuntimeController
from astrid.tui.types import TranscriptEntry


@dataclass
class FrontendRuntime:
    """UI-neutral runtime surface shared by Astrid terminal frontends.

    Frontends should render and collect input; turn execution, history,
    transcript writes, permission flow, and future permission modes stay behind
    ``RuntimeController``.
    """

    cwd: str
    controller: RuntimeController
    transcript: list[TranscriptEntry]


class AstridFrontend(Protocol):
    """Contract implemented by shell, inline TUI, and fullscreen TUI frontends."""

    name: str

    def run(self, runtime: FrontendRuntime) -> list[dict[str, str]] | None:
        """Run the frontend and return the latest model messages when relevant."""
