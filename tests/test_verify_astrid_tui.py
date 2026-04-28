from __future__ import annotations

from pathlib import Path

from scripts import verify_astrid_tui


def test_launch_astrid_process_uses_new_console(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_popen(args, cwd=None, creationflags=0):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["creationflags"] = creationflags
        return object()

    monkeypatch.setattr(verify_astrid_tui.subprocess, "Popen", fake_popen)

    verify_astrid_tui.launch_astrid_process(
        command="demo",
        repo_root=Path(r"F:\agent_project\codingagent\Astrid"),
    )

    assert captured["args"] == ["powershell", "-NoExit", "-Command", "demo"]
    assert captured["cwd"] == r"F:\agent_project\codingagent\Astrid"
    assert captured["creationflags"] == 0x10


def test_build_launch_command_sets_window_title_and_starts_astrid() -> None:
    repo = Path(r"F:\agent_project\codingagent\Astrid")
    workspace = Path(r"F:\agent_project\codingagent\Astrid")

    command = verify_astrid_tui.build_launch_command(
        title="Astrid Smoke",
        repo_root=repo,
        workspace=workspace,
    )

    assert "$Host.UI.RawUI.WindowTitle = 'Astrid Smoke'" in command
    assert "Set-Location 'F:\\agent_project\\codingagent\\Astrid'" in command
    assert "run_astrid.py" in command
    assert "--workspace 'F:\\agent_project\\codingagent\\Astrid'" in command


def test_screenshot_prefix_sanitizes_spaces() -> None:
    prefix = verify_astrid_tui.build_screenshot_prefix("Astrid Smoke")

    assert prefix == "astrid-smoke"
