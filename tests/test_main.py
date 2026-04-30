from __future__ import annotations

import io
from pathlib import Path

import astrid.main as main_mod
from astrid.tui.types import TranscriptEntry


class _FakeStdin(io.StringIO):
    def __init__(self, text: str, *, isatty: bool) -> None:
        super().__init__(text)
        self._isatty = isatty

    def isatty(self) -> bool:
        return self._isatty


class _DummyTools:
    def get_skills(self) -> list[str]:
        return []

    def get_mcp_servers(self) -> list[str]:
        return []

    def list(self) -> list[object]:
        return []

    def dispose(self) -> None:
        return None


class _DummyPermissions:
    def __init__(self, cwd: str, prompt=None) -> None:
        self.cwd = cwd
        self.prompt = prompt

    def get_summary(self) -> list[str]:
        return [f"cwd: {self.cwd}"]

    def ensure_path_access(self, path: str, intent: str) -> None:
        return None

    def begin_turn(self) -> None:
        return None

    def end_turn(self) -> None:
        return None


class _DummyMemory:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def get_relevant_context(self):
        return []


class _DummyAdvancedMemory:
    def format_context_for_prompt(self, max_tokens: int = 5000) -> str:
        return ""

    def get_statistics(self) -> dict[str, int]:
        return {"total_memories": 0}

    def save_all(self) -> None:
        return None

    def apply_memory_decay(self) -> int:
        return 0


class _DummyBootstrap:
    def execute_bootstrap_cycle(self, payload) -> dict[str, str]:
        return {"status": "ok"}


class _DummyLogger:
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None


def _patch_main_runtime(monkeypatch) -> dict[str, object]:
    calls: dict[str, object] = {"tty_calls": 0, "shell_calls": 0}

    monkeypatch.setattr(main_mod, "_configure_stdio", lambda: None)
    monkeypatch.setattr(main_mod, "maybe_handle_management_command", lambda cwd, argv: False)
    monkeypatch.setattr(main_mod, "load_runtime_config", lambda cwd: None)
    monkeypatch.setattr(main_mod, "create_default_tool_registry", lambda cwd, runtime=None, **kwargs: _DummyTools())
    monkeypatch.setattr(main_mod, "PermissionManager", _DummyPermissions)
    monkeypatch.setattr(main_mod, "MockModelAdapter", lambda: object())
    monkeypatch.setattr(main_mod, "build_system_prompt", lambda *args, **kwargs: "system")
    monkeypatch.setattr(main_mod, "load_history_entries", lambda workspace=None: [])
    monkeypatch.setattr("astrid.logging_config.setup_logging", lambda level="WARNING": None)
    monkeypatch.setattr("astrid.logging_config.get_logger", lambda name="main": _DummyLogger())
    monkeypatch.setattr("astrid.memory.MemoryManager", _DummyMemory)
    monkeypatch.setattr("astrid.advanced_memory.create_memory_integration", lambda *args, **kwargs: _DummyAdvancedMemory())
    monkeypatch.setattr("astrid.skill_engine.create_default_skill_engine", lambda memory: object())
    monkeypatch.setattr("astrid.terminology_governance.create_terminology_governance_system", lambda memory: object())
    monkeypatch.setattr("astrid.bootstrap_system.create_bootstrap_system", lambda *args, **kwargs: _DummyBootstrap())
    monkeypatch.setattr("astrid.agent_loop.set_advanced_memory", lambda memory: None)

    def _fake_run_tty_app(**kwargs) -> None:
        calls["tty_calls"] = int(calls["tty_calls"]) + 1

    monkeypatch.setattr(main_mod, "run_tty_app", _fake_run_tty_app)

    def _fake_run_shell_repl(**kwargs):
        calls["shell_calls"] = int(calls["shell_calls"]) + 1
        return kwargs["messages"]

    monkeypatch.setattr(main_mod, "_run_shell_repl", _fake_run_shell_repl)
    return calls


def test_should_render_legacy_intro_only_for_non_tty() -> None:
    assert main_mod._should_render_legacy_intro(stdin_isatty=False) is True
    assert main_mod._should_render_legacy_intro(stdin_isatty=True) is False


def test_main_skips_legacy_intro_for_tty_mode(monkeypatch, capsys, tmp_path) -> None:
    calls = _patch_main_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod.sys, "argv", ["astrid"])
    monkeypatch.setattr(main_mod.sys, "stdin", _FakeStdin("", isatty=True))

    main_mod.main()

    captured = capsys.readouterr()
    assert calls["tty_calls"] == 0
    assert calls["shell_calls"] == 1
    assert "Quick Start Guide" not in captured.out
    assert "minimal Astrid shell" not in captured.out
    assert "Astrid - Your Terminal Coding Assistant" not in captured.out


def test_main_keeps_legacy_intro_for_non_tty_mode(monkeypatch, capsys, tmp_path) -> None:
    _patch_main_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod.sys, "argv", ["astrid"])
    monkeypatch.setattr(main_mod.sys, "stdin", _FakeStdin("/exit\n", isatty=False))

    main_mod.main()

    captured = capsys.readouterr()
    assert "Quick Start Guide" in captured.out
    assert "Astrid - Your Terminal Coding Assistant" in captured.out


def test_main_routes_management_command_before_argparse_failure(monkeypatch, tmp_path) -> None:
    calls = _patch_main_runtime(monkeypatch)
    handled: dict[str, object] = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod.sys, "argv", ["astrid", "skills", "list"])
    monkeypatch.setattr(main_mod.sys, "stdin", _FakeStdin("", isatty=True))

    def _fake_manage(cwd, argv):
        handled["cwd"] = cwd
        handled["argv"] = list(argv)
        return True

    monkeypatch.setattr(main_mod, "maybe_handle_management_command", _fake_manage)

    main_mod.main()

    assert handled["argv"] == ["skills", "list"]
    assert calls["tty_calls"] == 0
    assert calls["shell_calls"] == 0


def test_main_preserves_management_scope_flags(monkeypatch, tmp_path) -> None:
    _patch_main_runtime(monkeypatch)
    handled: dict[str, object] = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod.sys, "argv", ["astrid", "mcp", "list", "--project"])
    monkeypatch.setattr(main_mod.sys, "stdin", _FakeStdin("", isatty=True))

    def _fake_manage(cwd, argv):
        handled["argv"] = list(argv)
        return True

    monkeypatch.setattr(main_mod, "maybe_handle_management_command", _fake_manage)

    main_mod.main()

    assert handled["argv"] == ["mcp", "list", "--project"]


def test_save_transcript_file_sanitizes_invalid_surrogates(tmp_path: Path) -> None:
    permissions = _DummyPermissions(str(tmp_path))
    transcript = [TranscriptEntry(id=1, kind="assistant", body="bad-surrogate-\udcbf")]

    saved = main_mod._save_transcript_file(
        str(tmp_path),
        permissions,
        transcript,
        "transcript.txt",
    )

    text = Path(saved).read_text(encoding="utf-8")
    assert "bad-surrogate-" in text


def test_normalize_cli_input_strips_bom_and_nul() -> None:
    assert main_mod._normalize_cli_input("\ufeff/history\x00\n") == "/history"
    assert main_mod._normalize_cli_input("ďť\udcbf/history\n") == "/history"
    assert main_mod._normalize_cli_input("锘?/history\n") == "/history"


def test_handle_cli_input_streams_tool_events(monkeypatch, capsys, tmp_path) -> None:
    transcript: list[TranscriptEntry] = []
    messages = [{"role": "system", "content": "system"}]

    class _Tools(_DummyTools):
        def refresh_capabilities(self) -> None:
            return None

    def _fake_run_agent_turn(**kwargs):
        kwargs["on_progress_message"]("Planning the next step")
        kwargs["on_tool_start"]("write_file", {"path": "index.html", "content": "<html>"})
        kwargs["on_tool_result"]("write_file", "wrote index.html", False)
        return [*kwargs["messages"], {"role": "assistant", "content": "done"}]

    monkeypatch.setattr(main_mod, "run_agent_turn", _fake_run_agent_turn)
    monkeypatch.setattr(main_mod, "build_system_prompt", lambda *args, **kwargs: "system")
    monkeypatch.setattr(main_mod, "save_history_entries", lambda history, cwd: None)

    next_messages = main_mod._handle_cli_input(
        user_input="build it",
        cwd=str(tmp_path),
        permissions=_DummyPermissions(str(tmp_path)),
        transcript=transcript,
        tools=_Tools(),
        messages=messages,
        history=[],
        model=object(),
        max_tool_steps=25,
        advanced_memory_mgr=_DummyAdvancedMemory(),
        context_mgr=None,
        logger=_DummyLogger(),
    )

    captured = capsys.readouterr()
    assert next_messages is not None
    assert "[progress] Planning the next step" in captured.out
    assert "[tool:start] write_file" in captured.out
    assert "[tool:success] write_file" in captured.out
    assert any(entry.kind == "tool" and entry.toolName == "write_file" for entry in transcript)


def test_apply_terminal_mode_enables_shell_scrollback() -> None:
    main_mod._apply_terminal_mode("shell")

    assert main_mod.os.environ["ASTRID_TERMINAL_MODE"] == "shell"
    assert main_mod.os.environ["ASTRID_ALT_SCREEN"] == "0"


def test_apply_terminal_mode_uses_native_scrollback_for_agent_default(monkeypatch) -> None:
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)

    main_mod._apply_terminal_mode("agent")

    assert main_mod.os.environ["ASTRID_TERMINAL_MODE"] == "shell"
    assert main_mod.os.environ["ASTRID_ALT_SCREEN"] == "0"


def test_apply_terminal_mode_enables_fullscreen_tui(monkeypatch) -> None:
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)

    main_mod._apply_terminal_mode("tui")

    assert main_mod.os.environ["ASTRID_TERMINAL_MODE"] == "tui"
    assert main_mod.os.environ["ASTRID_ALT_SCREEN"] == "1"


def test_resolve_terminal_mode_defaults_to_agent_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(main_mod.sys, "platform", "win32")

    assert main_mod._resolve_terminal_mode(shell_flag=False, tui_flag=False) == "agent"


def test_resolve_terminal_mode_allows_explicit_tui_override(monkeypatch) -> None:
    monkeypatch.setattr(main_mod.sys, "platform", "win32")

    assert main_mod._resolve_terminal_mode(shell_flag=False, tui_flag=True) == "tui"


def test_resolve_terminal_mode_rejects_conflicting_flags() -> None:
    try:
        main_mod._resolve_terminal_mode(shell_flag=True, tui_flag=True)
    except RuntimeError as exc:
        assert "--shell and --tui cannot be used together." in str(exc)
    else:
        raise AssertionError("expected conflicting terminal mode flags to fail")


def test_main_shell_flag_sets_shell_terminal_mode(monkeypatch, tmp_path) -> None:
    calls = _patch_main_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod.sys, "argv", ["astrid", "--shell"])
    monkeypatch.setattr(main_mod.sys, "stdin", _FakeStdin("", isatty=True))
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)

    main_mod.main()

    assert calls["tty_calls"] == 0
    assert calls["shell_calls"] == 1
    assert main_mod.os.environ["ASTRID_TERMINAL_MODE"] == "shell"
    assert main_mod.os.environ["ASTRID_ALT_SCREEN"] == "0"


def test_main_defaults_to_native_scrollback_mode_on_windows(monkeypatch, tmp_path) -> None:
    calls = _patch_main_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod.sys, "argv", ["astrid"])
    monkeypatch.setattr(main_mod.sys, "stdin", _FakeStdin("", isatty=True))
    monkeypatch.setattr(main_mod.sys, "platform", "win32")
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)

    main_mod.main()

    assert calls["tty_calls"] == 0
    assert calls["shell_calls"] == 1
    assert main_mod.os.environ["ASTRID_TERMINAL_MODE"] == "shell"
    assert main_mod.os.environ["ASTRID_ALT_SCREEN"] == "0"


def test_main_shell_flag_overrides_default_agent_mode_on_windows(monkeypatch, tmp_path) -> None:
    calls = _patch_main_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod.sys, "argv", ["astrid", "--shell"])
    monkeypatch.setattr(main_mod.sys, "stdin", _FakeStdin("", isatty=True))
    monkeypatch.setattr(main_mod.sys, "platform", "win32")
    monkeypatch.delenv("ASTRID_TERMINAL_MODE", raising=False)
    monkeypatch.delenv("ASTRID_ALT_SCREEN", raising=False)

    main_mod.main()

    assert calls["tty_calls"] == 0
    assert calls["shell_calls"] == 1
    assert main_mod.os.environ["ASTRID_TERMINAL_MODE"] == "shell"
    assert main_mod.os.environ["ASTRID_ALT_SCREEN"] == "0"


def test_main_tui_flag_disables_shell_mode_on_windows(monkeypatch, tmp_path) -> None:
    calls = _patch_main_runtime(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod.sys, "argv", ["astrid", "--tui"])
    monkeypatch.setattr(main_mod.sys, "stdin", _FakeStdin("", isatty=True))
    monkeypatch.setattr(main_mod.sys, "platform", "win32")
    monkeypatch.setenv("ASTRID_TERMINAL_MODE", "shell")
    monkeypatch.setenv("ASTRID_ALT_SCREEN", "0")

    main_mod.main()

    assert calls["tty_calls"] == 1
    assert calls["shell_calls"] == 0
    assert main_mod.os.environ["ASTRID_TERMINAL_MODE"] == "tui"
    assert main_mod.os.environ["ASTRID_ALT_SCREEN"] == "1"


def test_run_shell_repl_prints_intro_and_stops_on_exit(monkeypatch, capsys) -> None:
    history: list[str] = []
    prompts: list[str] = []

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": prompts.append(prompt) or "/exit",
    )

    messages = main_mod._run_shell_repl(
        cwd="F:\\demo",
        permissions=_DummyPermissions("F:\\demo"),
        transcript=[],
        tools=_DummyTools(),
        messages=[{"role": "system", "content": "system"}],
        history=history,
        model=object(),
        max_tool_steps=25,
        advanced_memory_mgr=_DummyAdvancedMemory(),
        context_mgr=None,
        logger=_DummyLogger(),
    )

    captured = capsys.readouterr()
    assert messages == [{"role": "system", "content": "system"}]
    assert "Astrid shell mode" in captured.out
    assert "PowerShell keeps native scrollback" in captured.out
    assert prompts == ["astrid> "]
