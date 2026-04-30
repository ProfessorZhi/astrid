from pathlib import Path

import astrid.config as config_mod
from astrid.config import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_TOOL_STEPS,
    DEFAULT_MODEL_TIMEOUT_SECONDS,
    load_effective_settings,
    load_pet_settings,
    load_runtime_config,
    merge_settings,
    read_mcp_config_file,
    save_pet_settings,
)


def test_merge_settings_merges_env_and_mcp_servers() -> None:
    merged = merge_settings(
        {
            "env": {"A": "1"},
            "mcpServers": {
                "fs": {"command": "npx", "args": ["a"], "env": {"X": "1"}}
            },
        },
        {
            "env": {"B": "2"},
            "mcpServers": {
                "fs": {"command": "uvx", "env": {"Y": "2"}},
                "search": {"command": "python"},
            },
        },
    )

    assert merged["env"] == {"A": "1", "B": "2"}
    assert merged["mcpServers"]["fs"]["command"] == "uvx"
    assert merged["mcpServers"]["fs"]["args"] == ["a"]
    assert merged["mcpServers"]["fs"]["env"] == {"X": "1", "Y": "2"}
    assert merged["mcpServers"]["search"]["command"] == "python"


def test_save_and_load_pet_settings(tmp_path: Path, monkeypatch) -> None:
    astrid_dir = tmp_path / ".astrid"
    settings_path = astrid_dir / "settings.json"
    monkeypatch.setattr(config_mod, "ASTRID_DIR", astrid_dir)
    monkeypatch.setattr(config_mod, "ASTRID_SETTINGS_PATH", settings_path)

    save_pet_settings(
        {
            "companionEnabled": True,
            "companionSpecies": "robot",
            "importedPetName": "asuna",
            "importedPetMode": "ansi",
        }
    )

    pet = load_pet_settings()

    assert pet["companionEnabled"] is True
    assert pet["companionSpecies"] == "robot"
    assert pet["importedPetName"] == "asuna"
    assert pet["importedPetMode"] == "ansi"


def test_read_mcp_config_file_accepts_utf8_bom(tmp_path: Path) -> None:
    config_path = tmp_path / ".mcp.json"
    config_path.write_text(
        '{\n  "mcpServers": {\n    "fake": {"command": "python"}\n  }\n}\n',
        encoding="utf-8-sig",
    )

    servers = read_mcp_config_file(config_path)

    assert servers == {"fake": {"command": "python"}}


def test_load_effective_settings_ignores_claude_settings(tmp_path: Path, monkeypatch) -> None:
    astrid_dir = tmp_path / ".astrid"
    claude_dir = tmp_path / ".claude"
    workspace = tmp_path / "workspace"
    astrid_dir.mkdir()
    claude_dir.mkdir()
    workspace.mkdir()

    monkeypatch.setattr(config_mod, "ASTRID_DIR", astrid_dir)
    monkeypatch.setattr(config_mod, "ASTRID_SETTINGS_PATH", astrid_dir / "settings.json")
    monkeypatch.setattr(config_mod, "ASTRID_MCP_PATH", astrid_dir / "mcp.json")

    (claude_dir / "settings.json").write_text(
        """
        {
          "model": "claude-should-not-leak",
          "env": {"CLAUDE_ONLY": "bad"},
          "mcpServers": {"claude-server": {"command": "bad"}}
        }
        """,
        encoding="utf-8",
    )
    (astrid_dir / "settings.json").write_text(
        """
        {
          "env": {"ASTRID_ONLY": "ok"},
          "mcpServers": {"astrid-server": {"command": "astrid"}}
        }
        """,
        encoding="utf-8",
    )
    (astrid_dir / "mcp.json").write_text(
        '{"mcpServers": {"global-server": {"command": "global"}}}',
        encoding="utf-8",
    )
    (workspace / ".mcp.json").write_text(
        '{"mcpServers": {"project-server": {"command": "project"}}}',
        encoding="utf-8",
    )

    settings = load_effective_settings(workspace)

    assert "model" not in settings
    assert settings["env"] == {"ASTRID_ONLY": "ok"}
    assert settings["mcpServers"]["astrid-server"]["command"] == "astrid"
    assert settings["mcpServers"]["global-server"]["command"] == "global"
    assert settings["mcpServers"]["project-server"]["command"] == "project"
    assert "claude-server" not in settings["mcpServers"]


def test_runtime_source_summary_excludes_claude_settings(tmp_path: Path, monkeypatch) -> None:
    astrid_dir = tmp_path / ".astrid"
    workspace = tmp_path / "workspace"
    astrid_dir.mkdir()
    workspace.mkdir()

    monkeypatch.setattr(config_mod, "ASTRID_DIR", astrid_dir)
    monkeypatch.setattr(config_mod, "ASTRID_SETTINGS_PATH", astrid_dir / "settings.json")
    monkeypatch.setattr(config_mod, "ASTRID_MCP_PATH", astrid_dir / "mcp.json")
    monkeypatch.setenv("ANTHROPIC_MODEL", "MiniMax-M2.7")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    runtime = load_runtime_config(workspace)

    assert runtime["model"] == "MiniMax-M2.7"
    assert runtime["maxOutputTokens"] == DEFAULT_MAX_OUTPUT_TOKENS
    assert runtime["maxToolSteps"] == DEFAULT_MAX_TOOL_STEPS
    assert runtime["modelTimeoutSeconds"] == DEFAULT_MODEL_TIMEOUT_SECONDS
    assert ".claude" not in runtime["sourceSummary"]
    assert str(astrid_dir / "settings.json") in runtime["sourceSummary"]


def test_settings_anthropic_env_wins_over_process_anthropic_env(
    tmp_path: Path, monkeypatch
) -> None:
    astrid_dir = tmp_path / ".astrid"
    workspace = tmp_path / "workspace"
    astrid_dir.mkdir()
    workspace.mkdir()

    monkeypatch.setattr(config_mod, "ASTRID_DIR", astrid_dir)
    monkeypatch.setattr(config_mod, "ASTRID_SETTINGS_PATH", astrid_dir / "settings.json")
    monkeypatch.setattr(config_mod, "ASTRID_MCP_PATH", astrid_dir / "mcp.json")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-code-global-model")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://claude-code.example/anthropic")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "claude-code-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "claude-code-api-key")

    (astrid_dir / "settings.json").write_text(
        """
        {
          "model": "MiniMax-M2.7",
          "env": {
            "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "astrid-token"
          }
        }
        """,
        encoding="utf-8",
    )

    runtime = load_runtime_config(workspace)

    assert runtime["model"] == "MiniMax-M2.7"
    assert runtime["baseUrl"] == "https://api.minimaxi.com/anthropic"
    assert runtime["authToken"] == "astrid-token"
    assert runtime["apiKey"] is None


def test_runtime_max_output_tokens_can_be_overridden(tmp_path: Path, monkeypatch) -> None:
    astrid_dir = tmp_path / ".astrid"
    workspace = tmp_path / "workspace"
    astrid_dir.mkdir()
    workspace.mkdir()

    monkeypatch.setattr(config_mod, "ASTRID_DIR", astrid_dir)
    monkeypatch.setattr(config_mod, "ASTRID_SETTINGS_PATH", astrid_dir / "settings.json")
    monkeypatch.setattr(config_mod, "ASTRID_MCP_PATH", astrid_dir / "mcp.json")
    monkeypatch.setenv("ANTHROPIC_MODEL", "MiniMax-M2.7")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ASTRID_MAX_OUTPUT_TOKENS", "16000")
    monkeypatch.setenv("ASTRID_MAX_TOOL_STEPS", "12")
    monkeypatch.setenv("ASTRID_MODEL_TIMEOUT_SECONDS", "240")

    runtime = load_runtime_config(workspace)

    assert runtime["maxOutputTokens"] == 16000
    assert runtime["maxToolSteps"] == 12
    assert runtime["modelTimeoutSeconds"] == 240
