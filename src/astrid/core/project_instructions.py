from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectInstruction:
    path: Path
    content: str
    kind: str


def _maybe_read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def find_project_root(cwd: str | Path) -> Path:
    current = Path(cwd).resolve()
    start = current if current.is_dir() else current.parent
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def _path_chain(root: Path, cwd: Path) -> list[Path]:
    root = root.resolve()
    current = cwd.resolve()
    start = current if current.is_dir() else current.parent
    if start == root:
        return [root]
    try:
        relative = start.relative_to(root)
    except ValueError:
        return [root]

    chain = [root]
    current_path = root
    for part in relative.parts:
        current_path = current_path / part
        chain.append(current_path)
    return chain


def load_project_instructions(cwd: str | Path) -> list[ProjectInstruction]:
    cwd_path = Path(cwd)
    root = find_project_root(cwd_path)
    instructions: list[ProjectInstruction] = []

    for directory in _path_chain(root, cwd_path):
        agents_path = directory / "AGENTS.md"
        agents_content = _maybe_read(agents_path)
        if agents_content:
            instructions.append(ProjectInstruction(agents_path, agents_content, "agents"))

    claude_path = cwd_path / "CLAUDE.md"
    claude_content = _maybe_read(claude_path)
    if claude_content:
        instructions.append(ProjectInstruction(claude_path, claude_content, "claude"))

    return instructions


def format_project_instructions(instructions: list[ProjectInstruction]) -> str:
    return "\n\n".join(
        f"Project instructions from {instruction.path}:\n{instruction.content}"
        for instruction in instructions
    )
