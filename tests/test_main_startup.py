from __future__ import annotations

import builtins
from types import SimpleNamespace

import astrid.main as main_module


class _FakeLogger:
    def info(self, *args, **kwargs) -> None:
        pass

    def warning(self, *args, **kwargs) -> None:
        pass

    def debug(self, *args, **kwargs) -> None:
        pass


class _FakeMemoryIntegration:
    def format_context_for_prompt(self, *, max_tokens: int) -> str:
        return "memory-context"

    def get_statistics(self) -> dict[str, int]:
        return {"total_memories": 0}

    def save_all(self) -> None:
        pass

    def apply_memory_decay(self) -> int:
        return 0


class _FakeMemoryManager:
    def __init__(self, project_root) -> None:
        self.project_root = project_root

    def get_relevant_context(self) -> str:
        return "memory-context"


class _FakeTools:
    def get_skills(self) -> list[str]:
        return []

    def get_mcp_servers(self) -> list[str]:
        return []

    def list(self) -> list[object]:
        return []

    def dispose(self) -> None:
        pass


class _FakePermissions:
    def __init__(self, cwd: str, prompt=None) -> None:
        self.cwd = cwd
        self.prompt = prompt

    def get_summary(self) -> list[str]:
        return []

    def begin_turn(self) -> None:
        pass

    def end_turn(self) -> None:
        pass


class _FakePipeStdin:
    def isatty(self) -> bool:
        return False

    def __iter__(self):
        return iter(())


def _patch_common_main_dependencies(monkeypatch, stdin) -> list[str]:
    printed: list[str] = []

    def fake_print(*args, **kwargs) -> None:
        printed.append(" ".join(str(arg) for arg in args))

    monkeypatch.setattr(main_module.sys, "stdin", stdin)
    monkeypatch.setattr(main_module.sys, "argv", ["astrid"])
    monkeypatch.setattr(builtins, "print", fake_print)
    monkeypatch.setattr("astrid.logging_config.setup_logging", lambda level: None)
    monkeypatch.setattr("astrid.logging_config.get_logger", lambda name: _FakeLogger())
    monkeypatch.setattr(main_module, "maybe_handle_management_command", lambda cwd, argv: False)
    monkeypatch.setattr(main_module, "load_runtime_config", lambda cwd: None)
    monkeypatch.setattr(main_module, "MockModelAdapter", lambda: object())
    monkeypatch.setattr("astrid.memory.MemoryManager", _FakeMemoryManager)
    monkeypatch.setattr("astrid.advanced_memory.create_memory_integration", lambda *args, **kwargs: _FakeMemoryIntegration())
    monkeypatch.setattr("astrid.skill_engine.create_default_skill_engine", lambda advanced_memory_mgr: object())
    monkeypatch.setattr(
        "astrid.terminology_governance.create_terminology_governance_system",
        lambda advanced_memory_mgr: object(),
    )
    monkeypatch.setattr(
        "astrid.bootstrap_system.create_bootstrap_system",
        lambda advanced_memory_mgr, skill_engine, terminology_governance: SimpleNamespace(
            execute_bootstrap_cycle=lambda payload: {"status": "ok"}
        ),
    )
    monkeypatch.setattr(main_module, "create_default_tool_registry", lambda *args, **kwargs: _FakeTools())
    monkeypatch.setattr(main_module, "PermissionManager", _FakePermissions)
    monkeypatch.setattr(main_module, "build_system_prompt", lambda *args, **kwargs: "system-prompt")
    monkeypatch.setattr(main_module, "load_history_entries", lambda workspace=None: [])
    monkeypatch.setattr(main_module, "save_history_entries", lambda history, workspace=None: None)
    monkeypatch.setattr("astrid.agent_loop.set_advanced_memory", lambda advanced_memory_mgr: None)
    monkeypatch.setattr(main_module, "run_tty_app", lambda **kwargs: None)
    monkeypatch.setattr(main_module, "_run_shell_repl", lambda **kwargs: kwargs["messages"])
    return printed


def test_tty_startup_skips_legacy_banner_and_guide(monkeypatch) -> None:
    printed = _patch_common_main_dependencies(monkeypatch, SimpleNamespace(isatty=lambda: True))

    main_module.main()

    assert not any("Quick Start Guide" in line for line in printed)
    assert not any("Astrid - Your Terminal Coding Assistant" in line for line in printed)


def test_pipe_startup_keeps_legacy_intro(monkeypatch) -> None:
    printed = _patch_common_main_dependencies(monkeypatch, _FakePipeStdin())

    main_module.main()

    assert any("Quick Start Guide" in line for line in printed)
    assert any("Astrid - Your Terminal Coding Assistant" in line for line in printed)
