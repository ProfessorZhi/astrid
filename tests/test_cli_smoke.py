from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _smoke_env(repo_root: Path, home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(repo_root / "src")
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


def _astrid_module_command(repo_root: Path, *args: str) -> list[str]:
    runner = (
        "import runpy, sys; "
        f"sys.path.insert(0, {str(repo_root / 'src')!r}); "
        "sys.argv = ['astrid.main', *sys.argv[1:]]; "
        "runpy.run_module('astrid.main', run_name='__main__')"
    )
    return [sys.executable, "-B", "-c", runner, *args]


def test_cli_module_help_smoke(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        _astrid_module_command(repo_root, "--help"),
        cwd=tmp_path,
        env=_smoke_env(repo_root, tmp_path / "home"),
        text=True,
        encoding="utf-8",
        errors="replace",
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
        _astrid_module_command(repo_root, "--shell"),
        cwd=tmp_path,
        env=_smoke_env(repo_root, tmp_path / "home"),
        input="/help\n/status\n/permissions\n/exit\n",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=45,
        check=False,
    )

    assert completed.returncode == 0
    assert "Quick Start Guide" in completed.stdout
    assert "Available Commands" in completed.stdout
    assert "permission store:" in completed.stdout


def test_cli_shell_mode_executes_local_tool_shortcuts(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "sample.txt").write_text("astrid smoke file\n", encoding="utf-8")

    completed = subprocess.run(
        _astrid_module_command(repo_root, "--shell"),
        cwd=tmp_path,
        env=_smoke_env(repo_root, tmp_path / "home"),
        input="/ls .\n/read sample.txt\n/cmd echo astrid-smoke\n/exit\n",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=45,
        check=False,
    )

    assert completed.returncode == 0
    assert "sample.txt" in completed.stdout
    assert "astrid smoke file" in completed.stdout
    assert "astrid-smoke" in completed.stdout


def test_cli_management_commands_run_before_interactive_startup(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = _smoke_env(repo_root, tmp_path / "home")

    mcp_result = subprocess.run(
        _astrid_module_command(repo_root, "mcp", "list", "--project"),
        cwd=tmp_path,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
        check=False,
    )
    skills_result = subprocess.run(
        _astrid_module_command(repo_root, "skills", "list", "--project"),
        cwd=tmp_path,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert mcp_result.returncode == 0
    assert "No MCP servers configured" in mcp_result.stdout
    assert "Quick Start Guide" not in mcp_result.stdout
    assert skills_result.returncode == 0
    assert "Quick Start Guide" not in skills_result.stdout


def test_management_mcp_list_project_reads_project_config_before_runtime(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "demo": {
                        "command": "python",
                        "args": ["server.py"],
                        "protocol": "newline-json",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        _astrid_module_command(repo_root, "mcp", "list", "--project"),
        cwd=tmp_path,
        env=_smoke_env(repo_root, tmp_path / "home"),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0
    assert "demo: python server.py protocol=newline-json" in completed.stdout
    assert "Quick Start Guide" not in completed.stdout


def test_cli_list_sessions_entry_runs_without_tui_startup(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    astrid_dir = home / ".astrid"
    astrid_dir.mkdir(parents=True)
    (astrid_dir / "sessions_index.json").write_text(
        json.dumps(
            {
                "smoke-session": {
                    "session_id": "smoke-session",
                    "created_at": 1.0,
                    "updated_at": 2.0,
                    "first_message": "start here",
                    "last_message": "done",
                    "message_count": 3,
                    "workspace": str(tmp_path),
                }
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        _astrid_module_command(repo_root, "--list-sessions"),
        cwd=tmp_path,
        env=_smoke_env(repo_root, home),
        input="",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0
    assert "Saved sessions:" in completed.stdout
    assert "smoke-se" in completed.stdout
    assert "Quick Start Guide" not in completed.stdout
