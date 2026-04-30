from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from astrid.integrations.desktop_control import click_at, focus_window, press_key, scroll_at, take_screenshot, type_text

CREATE_NEW_CONSOLE = 0x00000010


def build_launch_command(*, title: str, repo_root: Path, workspace: Path) -> str:
    safe_title = title.replace("'", "''")
    safe_repo = str(repo_root).replace("'", "''")
    safe_workspace = str(workspace).replace("'", "''")
    safe_python = sys.executable.replace("'", "''")
    return (
        f"$Host.UI.RawUI.WindowTitle = '{safe_title}'; "
        f"Set-Location '{safe_repo}'; "
        f"& '{safe_python}' '{safe_repo}\\scripts\\run_astrid.py' --workspace '{safe_workspace}'"
    )


def build_screenshot_prefix(title: str) -> str:
    return "-".join(title.lower().split())


def launch_astrid_process(*, command: str, repo_root: Path):
    return subprocess.Popen(
        [
            "powershell",
            "-NoExit",
            "-Command",
            command,
        ],
        cwd=str(repo_root),
        creationflags=CREATE_NEW_CONSOLE,
    )


def run_smoke_test(
    *,
    repo_root: Path,
    workspace: Path,
    title: str,
    output_dir: Path,
    startup_delay: float,
) -> list[str]:
    command = build_launch_command(title=title, repo_root=repo_root, workspace=workspace)
    launch_astrid_process(command=command, repo_root=repo_root)
    time.sleep(startup_delay)

    window = focus_window(title)
    rect = window["rect"]
    center_x = rect["left"] + max(20, rect["width"] // 2)
    center_y = rect["top"] + max(20, rect["height"] // 2)
    input_y = rect["top"] + max(40, rect["height"] - 120)
    prefix = build_screenshot_prefix(title)

    click_at(center_x, input_y)
    before = take_screenshot(output_dir / f"{prefix}-before.png")
    type_text("/help", interval=0.02)
    press_key("enter")
    time.sleep(1.0)
    mid = take_screenshot(output_dir / f"{prefix}-help.png")
    scroll_at(center_x, center_y, -800)
    time.sleep(0.5)
    after = take_screenshot(output_dir / f"{prefix}-after-scroll.png")
    click_at(center_x, input_y)
    type_text("/exit", interval=0.02)
    press_key("enter")

    return [before, mid, after]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch Astrid in PowerShell and perform a desktop smoke test.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--workspace", default=str(REPO_ROOT))
    parser.add_argument("--title", default="Astrid Smoke")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parents[1] / ".tmp_desktop_smoke"))
    parser.add_argument("--startup-delay", type=float, default=3.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    outputs = run_smoke_test(
        repo_root=Path(args.repo_root).resolve(),
        workspace=Path(args.workspace).resolve(),
        title=args.title,
        output_dir=Path(args.output_dir).resolve(),
        startup_delay=args.startup_delay,
    )
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
