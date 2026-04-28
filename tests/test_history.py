from __future__ import annotations

import json

from astrid import history as history_mod


def test_load_history_entries_keeps_workspace_history_isolated(monkeypatch, tmp_path) -> None:
    history_path = tmp_path / "history.json"
    workspace_a = str((tmp_path / "workspace-a").resolve())
    workspace_b = str((tmp_path / "workspace-b").resolve())
    history_path.write_text(
        json.dumps(
            {
                "byWorkspace": {
                    workspace_a: ["hello from a"],
                    workspace_b: ["hello from b"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(history_mod, "ASTRID_HISTORY_PATH", history_path)

    assert history_mod.load_history_entries(workspace_a) == ["hello from a"]
    assert history_mod.load_history_entries(workspace_b) == ["hello from b"]


def test_load_history_entries_does_not_leak_legacy_global_entries_into_workspace(monkeypatch, tmp_path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps({"entries": ["legacy global prompt"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(history_mod, "ASTRID_HISTORY_PATH", history_path)

    assert history_mod.load_history_entries(str((tmp_path / "workspace").resolve())) == []
    assert history_mod.load_history_entries() == ["legacy global prompt"]


def test_save_history_entries_writes_workspace_bucket_without_touching_others(monkeypatch, tmp_path) -> None:
    astrid_dir = tmp_path / ".astrid"
    history_path = astrid_dir / "history.json"
    workspace_a = str((tmp_path / "workspace-a").resolve())
    workspace_b = str((tmp_path / "workspace-b").resolve())
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(
            {
                "byWorkspace": {
                    workspace_a: ["keep me"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(history_mod, "ASTRID_DIR", astrid_dir)
    monkeypatch.setattr(history_mod, "ASTRID_HISTORY_PATH", history_path)

    history_mod.save_history_entries(["new entry"], workspace_b)

    parsed = json.loads(history_path.read_text(encoding="utf-8"))
    assert parsed == {
        "byWorkspace": {
            workspace_a: ["keep me"],
            workspace_b: ["new entry"],
        }
    }


def test_load_history_entries_strips_bom_and_nul(monkeypatch, tmp_path) -> None:
    history_path = tmp_path / "history.json"
    workspace = str((tmp_path / "workspace").resolve())
    history_path.write_text(
        json.dumps({"byWorkspace": {workspace: ["\ufeffbad\x00entry"]}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(history_mod, "ASTRID_HISTORY_PATH", history_path)

    assert history_mod.load_history_entries(workspace) == ["badentry"]
    history_path.write_text(
        json.dumps({"byWorkspace": {workspace: ["ďť\udcbf/history"]}}),
        encoding="utf-8",
    )
    assert history_mod.load_history_entries(workspace) == ["/history"]
    history_path.write_text(
        json.dumps({"byWorkspace": {workspace: ["锘?/history"]}}),
        encoding="utf-8",
    )
    assert history_mod.load_history_entries(workspace) == ["/history"]


def test_save_history_entries_strips_bom_and_nul(monkeypatch, tmp_path) -> None:
    astrid_dir = tmp_path / ".astrid"
    history_path = astrid_dir / "history.json"
    workspace = str((tmp_path / "workspace").resolve())
    monkeypatch.setattr(history_mod, "ASTRID_DIR", astrid_dir)
    monkeypatch.setattr(history_mod, "ASTRID_HISTORY_PATH", history_path)

    history_mod.save_history_entries(["\ufeffhello\x00world"], workspace)

    parsed = json.loads(history_path.read_text(encoding="utf-8"))
    assert parsed == {"byWorkspace": {workspace: ["helloworld"]}}

    history_mod.save_history_entries(["ďť\udcbf/history"], workspace)
    parsed = json.loads(history_path.read_text(encoding="utf-8"))
    assert parsed == {"byWorkspace": {workspace: ["/history"]}}

    history_mod.save_history_entries(["锘?/history"], workspace)
    parsed = json.loads(history_path.read_text(encoding="utf-8"))
    assert parsed == {"byWorkspace": {workspace: ["/history"]}}
