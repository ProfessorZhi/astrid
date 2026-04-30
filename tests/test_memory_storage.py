from __future__ import annotations

import json
from pathlib import Path

from astrid import advanced_memory as advanced_memory_mod
from astrid.state import memory as memory_mod
from astrid.advanced_memory import AdvancedMemoryManager, MemoryScope as AdvancedScope
from astrid.cli.cli_commands import try_handle_local_command
from astrid.state.memory import MemoryManager, MemoryScope
from astrid.core.prompt import build_system_prompt


def test_memory_root_defaults_to_user_memories(monkeypatch, tmp_path):
    astrid_home = tmp_path / ".astrid"
    monkeypatch.delenv("ASTRID_MEMORIES_ROOT", raising=False)
    monkeypatch.setattr(memory_mod, "ASTRID_DIR", astrid_home)
    monkeypatch.setattr(advanced_memory_mod, "ASTRID_DIR", astrid_home)

    assert memory_mod.memories_root() == astrid_home / "memories"
    assert advanced_memory_mod.memories_root() == astrid_home / "memories"


def test_memory_root_honors_environment_override(monkeypatch, tmp_path):
    override = tmp_path / "custom-memories"
    monkeypatch.setenv("ASTRID_MEMORIES_ROOT", str(override))

    assert memory_mod.memories_root() == override
    assert advanced_memory_mod.memories_root() == override


def test_memory_managers_do_not_create_project_memory_dirs(monkeypatch, tmp_path):
    root = tmp_path / "home-memories"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("ASTRID_MEMORIES_ROOT", str(root))

    MemoryManager(project_root=workspace)
    AdvancedMemoryManager(workspace=workspace)

    assert not (workspace / ".memory").exists()
    assert not (workspace / ".astrid-memory").exists()
    assert not (workspace / ".astrid-memory-local").exists()
    assert not (workspace / ".astrid-session-memory").exists()


def test_basic_memory_writes_project_bucket_and_markdown(monkeypatch, tmp_path):
    root = tmp_path / "memories"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("ASTRID_MEMORIES_ROOT", str(root))

    manager = MemoryManager(project_root=workspace)
    entry = manager.add_entry(MemoryScope.PROJECT, "decision", "Use pytest", tags=["tests"])

    project_dir = root / "projects" / memory_mod.workspace_id(workspace)
    parsed = json.loads((project_dir / "memory.json").read_text(encoding="utf-8"))
    markdown = (project_dir / "MEMORY.md").read_text(encoding="utf-8")

    assert parsed["entries"][0]["id"] == entry.id
    assert parsed["entries"][0]["workspace_id"] == memory_mod.workspace_id(workspace)
    assert "Use pytest" in markdown
    assert not (workspace / ".astrid-memory").exists()


def test_advanced_memory_writes_project_bucket(monkeypatch, tmp_path):
    root = tmp_path / "memories"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("ASTRID_MEMORIES_ROOT", str(root))

    manager = AdvancedMemoryManager(workspace=workspace)
    entry_id = manager.store_memory("Project fact", scope=AdvancedScope.PROJECT)

    project_file = root / "projects" / memory_mod.workspace_id(workspace) / "advanced_memory.json"
    parsed = json.loads(project_file.read_text(encoding="utf-8"))

    assert parsed["entries"][0]["id"] == entry_id
    assert not (workspace / ".astrid-memory").exists()


def test_legacy_basic_project_memory_migrates_without_overwriting(monkeypatch, tmp_path):
    root = tmp_path / "memories"
    workspace = tmp_path / "workspace"
    legacy = workspace / ".astrid-memory"
    legacy.mkdir(parents=True)
    legacy_payload = {
        "entries": [
            {
                "id": "project-1",
                "scope": "project",
                "category": "old",
                "content": "old project memory",
            }
        ]
    }
    (legacy / "memory.json").write_text(json.dumps(legacy_payload), encoding="utf-8")
    monkeypatch.setenv("ASTRID_MEMORIES_ROOT", str(root))

    project_dir = root / "projects" / memory_mod.workspace_id(workspace)
    project_dir.mkdir(parents=True)
    existing_payload = {
        "entries": [
            {
                "id": "project-1",
                "scope": "project",
                "category": "new",
                "content": "keep new project memory",
            }
        ]
    }
    (project_dir / "memory.json").write_text(json.dumps(existing_payload), encoding="utf-8")

    manager = MemoryManager(project_root=workspace)

    assert manager.memories[MemoryScope.PROJECT].entries[0].content == "keep new project memory"
    assert list(workspace.glob(".astrid-memory.backup-*"))
    assert not (workspace / ".astrid-memory").exists()


def test_legacy_advanced_project_memory_migrates(monkeypatch, tmp_path):
    root = tmp_path / "memories"
    workspace = tmp_path / "workspace"
    legacy = workspace / ".astrid-memory"
    legacy.mkdir(parents=True)
    legacy_payload = {
        "entries": [
            {
                "id": "project-context-old",
                "scope": "project",
                "type": "context",
                "content": "legacy advanced memory",
            }
        ]
    }
    (legacy / "advanced_memory.json").write_text(json.dumps(legacy_payload), encoding="utf-8")
    monkeypatch.setenv("ASTRID_MEMORIES_ROOT", str(root))

    manager = AdvancedMemoryManager(workspace=workspace)

    assert manager.memories[AdvancedScope.PROJECT][0].content == "legacy advanced memory"
    assert list(workspace.glob(".astrid-memory.backup-*"))
    assert not (workspace / ".astrid-memory").exists()


def test_build_system_prompt_injects_basic_memory_context(tmp_path):
    prompt = build_system_prompt(
        str(tmp_path),
        [],
        {
            "memory_context": "# Project Memory\n\n- Follow local architecture",
            "advanced_memory_context": "## Relevant Memories\n\n- advanced fact",
        },
    )

    assert "## Project Memory & Context" in prompt
    assert "Follow local architecture" in prompt
    assert "## Active Memory Context" in prompt
    assert "advanced fact" in prompt


def test_memory_command_reports_unified_root_without_project_dirs(monkeypatch, tmp_path):
    root = tmp_path / "memories"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("ASTRID_MEMORIES_ROOT", str(root))
    monkeypatch.chdir(workspace)

    output = try_handle_local_command("/memory")

    assert output is not None
    assert f"Memory root: {root}" in output
    assert f"Workspace id: {memory_mod.workspace_id(workspace)}" in output
    assert not (workspace / ".astrid-memory").exists()
    assert not (workspace / ".astrid-memory-local").exists()
