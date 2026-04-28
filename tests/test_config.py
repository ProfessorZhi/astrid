from pathlib import Path

import astrid.config as config_mod
from astrid.config import load_pet_settings, merge_settings, read_mcp_config_file, save_pet_settings


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
