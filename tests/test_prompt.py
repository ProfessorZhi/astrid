from pathlib import Path

from astrid.core.prompt import build_system_prompt


def test_build_system_prompt_includes_skills_and_mcp(tmp_path: Path) -> None:
    prompt = build_system_prompt(
        str(tmp_path),
        ["cwd: test"],
        {
            "skills": [{"name": "demo", "description": "demo skill"}],
            "mcpServers": [{"name": "fake", "status": "connected", "toolCount": 1, "resourceCount": 1, "promptCount": 1, "protocol": "newline-json"}],
        },
    )

    assert "Available skills:" in prompt
    assert "demo skill" in prompt
    assert "Configured MCP servers:" in prompt
    assert "fake: connected, tools=1" in prompt


def test_build_system_prompt_mentions_sequential_thinking_server(tmp_path: Path) -> None:
    prompt = build_system_prompt(
        str(tmp_path),
        [],
        {
            "mcpServers": [
                {"name": "SequentialThinking", "status": "connected", "toolCount": 1}
            ]
        },
    )

    assert "SEQUENTIAL THINKING MCP SERVER IS CONNECTED" in prompt
    assert "sequential_thinking" in prompt


def test_build_system_prompt_ignores_global_claude_folder(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    global_claude = home / ".claude" / "CLAUDE.md"
    global_claude.parent.mkdir(parents=True)
    global_claude.write_text("do not leak this", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: home)

    prompt = build_system_prompt(str(tmp_path), [], {})

    assert "do not leak this" not in prompt
    assert ".claude" not in prompt


def test_build_system_prompt_includes_root_agents_md_before_child_agents_md(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    child = root / "packages" / "app"
    child.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("root instruction", encoding="utf-8")
    (child / "AGENTS.md").write_text("child instruction", encoding="utf-8")

    prompt = build_system_prompt(str(child), [], {})

    assert f"Project instructions from {root / 'AGENTS.md'}" in prompt
    assert f"Project instructions from {child / 'AGENTS.md'}" in prompt
    assert prompt.index("root instruction") < prompt.index("child instruction")


def test_build_system_prompt_does_not_read_global_agents_md(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    global_codex_agents = home / ".codex" / "AGENTS.md"
    global_astrid_agents = home / ".astrid" / "AGENTS.md"
    global_codex_agents.parent.mkdir(parents=True)
    global_astrid_agents.parent.mkdir(parents=True)
    global_codex_agents.write_text("do not leak codex global", encoding="utf-8")
    global_astrid_agents.write_text("do not leak astrid global", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: home)

    prompt = build_system_prompt(str(tmp_path), [], {})

    assert "do not leak codex global" not in prompt
    assert "do not leak astrid global" not in prompt


def test_build_system_prompt_includes_agents_md_and_claude_md(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("agents rule", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude compatibility rule", encoding="utf-8")

    prompt = build_system_prompt(str(tmp_path), [], {})

    assert "Project instructions from" in prompt
    assert "AGENTS.md" in prompt
    assert "agents rule" in prompt
    assert "CLAUDE.md" in prompt
    assert "claude compatibility rule" in prompt
