from pathlib import Path

from astrid.cli.cli_commands import find_matching_slash_commands, format_slash_commands, try_handle_local_command
from astrid.cli import cli_commands as cli_commands_mod
from astrid.runtime.local_tool_shortcuts import parse_local_tool_shortcut
from astrid.integrations.skills import install_skill
from astrid.core.tooling import ToolCatalog, ToolRegistry
from astrid.tools import create_default_tool_registry


def test_find_matching_slash_commands_returns_help_variants() -> None:
    matches = find_matching_slash_commands("/mo")
    assert "/model" in matches
    assert "/model <model-name>" in matches


def test_parse_local_tool_shortcut_parses_cmd() -> None:
    shortcut = parse_local_tool_shortcut("/cmd src::git status")
    assert shortcut == {
        "toolName": "run_command",
        "input": {"command": "git status", "cwd": "src"},
    }


def test_parse_local_tool_shortcut_parses_patch_pairs() -> None:
    shortcut = parse_local_tool_shortcut("/patch demo.txt::hello::hi::world::earth")
    assert shortcut == {
        "toolName": "patch_file",
        "input": {
            "path": "demo.txt",
            "replacements": [
                {"search": "hello", "replace": "hi"},
                {"search": "world", "replace": "earth"},
            ],
        },
    }


def test_format_slash_commands_includes_permissions() -> None:
    assert "/permissions" in format_slash_commands()


def test_format_slash_commands_describes_patch_replacements() -> None:
    commands = format_slash_commands()
    # 检查格式化后的帮助信息包含关键命令
    assert "/patch" in commands
    assert "replacements" in commands or "multiple" in commands


def test_format_slash_commands_includes_history_and_retry() -> None:
    commands = format_slash_commands()
    assert "/history" in commands
    assert "/retry" in commands
    assert "Available Commands" in commands


def test_try_handle_local_command_executes_named_skill_from_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(tmp_path / "astrid-skills"))
    source_skill = tmp_path / "source-skill"
    source_skill.mkdir()
    (source_skill / "SKILL.md").write_text(
        "# Demo\n\nProject skill description\n\nUse this workflow.\n",
        encoding="utf-8",
    )
    install_skill(tmp_path, str(source_skill), name="demo", scope="project")

    tools = create_default_tool_registry(str(tmp_path), runtime=None)
    try:
        result = try_handle_local_command("/skills exec demo", tools=tools)
    finally:
        tools.dispose()

    assert result is not None
    assert "SKILL: demo" in result
    assert "Project skill description" in result
    assert "Use this workflow." in result


def test_try_handle_local_command_refreshes_newly_added_skill_listing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("ASTRID_SKILLS_ROOT", str(tmp_path / "astrid-skills"))
    tools = create_default_tool_registry(str(tmp_path), runtime=None)
    source_skill = tmp_path / "late-source"
    source_skill.mkdir()
    (source_skill / "SKILL.md").write_text("# Late\n\nLate-loaded skill\n", encoding="utf-8")
    install_skill(tmp_path, str(source_skill), name="late", scope="project")
    try:
        result = try_handle_local_command("/skills", tools=tools)
    finally:
        tools.dispose()

    assert result is not None
    assert "late" in result
    assert "Late-loaded skill" in result


def test_try_handle_local_command_reports_live_mcp_servers(tmp_path: Path) -> None:
    server_script = Path(__file__).parent / "fixtures" / "fake_mcp_server.py"
    tools = create_default_tool_registry(
        str(tmp_path),
        runtime={
            "mcpServers": {
                "fake": {
                    "command": "python",
                    "args": [str(server_script)],
                    "protocol": "newline-json",
                }
            }
        },
    )
    try:
        result = try_handle_local_command("/mcp", tools=tools)
    finally:
        tools.dispose()

    assert result is not None
    assert "fake  status=connected" in result
    assert "tools=1" in result
    assert "resources=1" in result
    assert "prompts=1" in result


def test_default_tool_registry_defers_mcp_connection_until_requested(tmp_path: Path) -> None:
    server_script = Path(__file__).parent / "fixtures" / "fake_mcp_server.py"
    tools = create_default_tool_registry(
        str(tmp_path),
        runtime={
            "mcpServers": {
                "fake": {
                    "command": "python",
                    "args": [str(server_script)],
                    "protocol": "newline-json",
                }
            }
        },
    )
    try:
        servers = tools.get_mcp_servers()
        assert servers[0]["name"] == "fake"
        assert servers[0]["status"] == "configured"
        assert servers[0]["toolCount"] == 0
        assert tools.find("mcp__fake__echo") is None

        tools.refresh_capabilities(connect_mcp=True)

        connected = tools.get_mcp_servers()[0]
        assert connected["status"] == "connected"
        assert connected["toolCount"] == 1
        assert tools.find("mcp__fake__echo") is not None
    finally:
        tools.dispose()


def test_try_handle_local_command_mcp_triggers_refresh_hook() -> None:
    refreshed: list[str] = []

    def _refresh() -> ToolCatalog:
        refreshed.append("called")
        return ToolCatalog(
            tools=[],
            skills=[],
            mcp_servers=[
                {
                    "name": "dynamic",
                    "status": "connected",
                    "toolCount": 2,
                    "resourceCount": 1,
                    "promptCount": 1,
                    "protocol": "newline-json",
                    "error": None,
                }
            ],
        )

    tools = ToolRegistry([], refresh_catalog=_refresh)

    result = try_handle_local_command("/mcp", tools=tools)

    assert refreshed == ["called"]
    assert result is not None
    assert "dynamic  status=connected" in result


def test_try_handle_local_command_history_reads_workspace_history(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_commands_mod, "load_history_entries", lambda workspace=None: ["first", "second"])

    result = try_handle_local_command("/history")

    assert result == "1. first\n2. second"
