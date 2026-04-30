from pathlib import Path

import pytest

from astrid.runtime.permissions import PermissionManager, get_permission_policy_snapshot


def test_permission_manager_uses_prompt_for_external_path(tmp_path: Path) -> None:
    external = tmp_path.parent / "outside.txt"
    manager = PermissionManager(str(tmp_path), prompt=lambda request: {"decision": "allow_once"})
    manager.ensure_path_access(str(external), "read")


def test_permission_manager_denies_external_path_without_prompt(tmp_path: Path) -> None:
    external = tmp_path.parent / "outside.txt"
    manager = PermissionManager(str(tmp_path))
    with pytest.raises(RuntimeError):
        manager.ensure_path_access(str(external), "read")


def test_fork_for_subagent_resets_turn_scoped_edit_grants(tmp_path: Path) -> None:
    decisions = iter(["allow_turn", "deny_once"])

    def _prompt(_request: dict) -> dict:
        return {"decision": next(decisions)}

    manager = PermissionManager(str(tmp_path), prompt=_prompt)
    first_worker = manager.fork_for_subagent()
    second_worker = manager.fork_for_subagent()

    first_worker.begin_turn()
    first_worker.ensure_edit(str(tmp_path / "demo.txt"), "diff")

    second_worker.begin_turn()
    with pytest.raises(RuntimeError, match="Edit denied"):
        second_worker.ensure_edit(str(tmp_path / "demo.txt"), "diff")


def test_permission_policy_snapshot_declares_current_policy_layers() -> None:
    snapshot = get_permission_policy_snapshot()

    assert snapshot["version"] == 1
    assert snapshot["sandboxSupport"] == "policy_only"

    layers = {layer["name"]: layer for layer in snapshot["layers"]}
    assert layers["permission_prompt"]["enforced"] is True
    assert layers["command_allow_deny_patterns"]["enforced"] is True
    assert layers["edit_allow_deny_paths"]["enforced"] is True
    assert layers["os_sandbox"]["enforced"] is False
    assert layers["future_sandbox_modes"]["enforced"] is False


def test_permission_policy_snapshot_command_layer_matches_current_behavior(tmp_path: Path) -> None:
    snapshot = get_permission_policy_snapshot()
    command_layer = next(layer for layer in snapshot["layers"] if layer["name"] == "command_allow_deny_patterns")
    manager = PermissionManager(str(tmp_path))

    assert command_layer["enforced"] is True
    with pytest.raises(RuntimeError, match="Command requires approval: python -c print"):
        manager.ensure_command("python", ["-c", "print(1)"], str(tmp_path))


def test_auto_approve_workspace_allows_workspace_edits_and_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_AUTO_APPROVE_WORKSPACE", "1")
    manager = PermissionManager(str(tmp_path))

    manager.ensure_edit(str(tmp_path / "demo.txt"), "diff")
    manager.ensure_command("python", ["-c", "print(1)"], str(tmp_path))


def test_auto_approve_workspace_does_not_allow_outside_edits(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_AUTO_APPROVE_WORKSPACE", "1")
    manager = PermissionManager(str(tmp_path))

    with pytest.raises(RuntimeError, match="Edit requires approval"):
        manager.ensure_edit(str(tmp_path.parent / "outside.txt"), "diff")


def test_permission_policy_snapshot_does_not_claim_os_sandbox_enforcement() -> None:
    snapshot = get_permission_policy_snapshot()
    os_sandbox = next(layer for layer in snapshot["layers"] if layer["name"] == "os_sandbox")

    assert snapshot["sandboxSupport"] == "policy_only"
    assert os_sandbox["enforced"] is False
    assert "OS-level sandbox" in os_sandbox["reason"]


def test_permission_policy_snapshot_is_not_mutable_global_state() -> None:
    snapshot = get_permission_policy_snapshot()
    snapshot["layers"][0]["enforced"] = False

    fresh_snapshot = get_permission_policy_snapshot()
    assert fresh_snapshot["layers"][0]["enforced"] is True
