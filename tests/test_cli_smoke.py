from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _smoke_env(repo_root: Path, home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(repo_root)
    env["ASTRID_MODEL_MODE"] = "mock"
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_BASE_URL",
        "ASTRID_MODEL",
    ):
        env.pop(key, None)
    return env


def test_cli_module_help_smoke(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [sys.executable, "-B", "-m", "astrid.main", "--help"],
        cwd=tmp_path,
        env=_smoke_env(repo_root, tmp_path / "home"),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0
    assert "Astrid - A lightweight terminal coding assistant" in completed.stdout
    assert "--shell" in completed.stdout
    assert "--tui" in completed.stdout


def test_cli_shell_mode_accepts_piped_local_commands(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [sys.executable, "-B", "-m", "astrid.main", "--shell"],
        cwd=tmp_path,
        env=_smoke_env(repo_root, tmp_path / "home"),
        input="/help\n/status\n/permissions\n/exit\n",
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )

    assert completed.returncode == 0
    assert "Quick Start Guide" in completed.stdout
    assert "Available Commands" in completed.stdout
    assert "permission store:" in completed.stdout
