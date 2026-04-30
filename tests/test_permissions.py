from pathlib import Path

import pytest

from astrid.runtime.permissions import PermissionManager, get_permission_policy_snapshot, normalize_permission_mode


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


def test_permission_mode_accept_edits_allows_workspace_edits(tmp_path: Path) -> None:
    manager = PermissionManager(str(tmp_path), mode="accept-edits")

    manager.ensure_edit(str(tmp_path / "demo.txt"), "diff")


def test_permission_mode_eval_workspace_allows_common_dev_command(tmp_path: Path) -> None:
    manager = PermissionManager(str(tmp_path), mode="eval-workspace")

    manager.ensure_command("python", ["-m", "pytest", "tests"], str(tmp_path))


def test_permission_mode_eval_workspace_rejects_dangerous_command(tmp_path: Path) -> None:
    manager = PermissionManager(str(tmp_path), mode="eval-workspace")

    with pytest.raises(RuntimeError, match="Command denied by eval-workspace mode"):
        manager.ensure_command("rm", ["-rf", "build"], str(tmp_path))


def test_permission_mode_eval_workspace_rejects_outside_path(tmp_path: Path) -> None:
    manager = PermissionManager(str(tmp_path), mode="eval-workspace")

    with pytest.raises(RuntimeError, match="outside workspace"):
        manager.ensure_path_access(str(tmp_path.parent / "outside.txt"), "read")


def test_permission_mode_bypass_allows_dangerous_and_outside(tmp_path: Path) -> None:
    manager = PermissionManager(str(tmp_path), mode="bypassPermissions")

    manager.ensure_path_access(str(tmp_path.parent / "outside.txt"), "read")
    manager.ensure_edit(str(tmp_path.parent / "outside.txt"), "diff")
    manager.ensure_command("rm", ["-rf", "build"], str(tmp_path))
    assert any("WARNING" in line for line in manager.get_summary())


def test_permission_mode_normalizes_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASTRID_PERMISSION_MODE", "eval_workspace")

    assert normalize_permission_mode(None) == "eval-workspace"
    assert PermissionManager(str(tmp_path)).mode == "eval-workspace"


def test_workspace_allowlist_env_allows_extra_root(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    external = tmp_path / "external"
    workspace.mkdir()
    external.mkdir()
    monkeypatch.setenv("ASTRID_WORKSPACE_ALLOWLIST", str(external))
    manager = PermissionManager(str(workspace), mode="eval-workspace")

    manager.ensure_path_access(str(external / "file.txt"), "read")
    manager.ensure_edit(str(external / "file.txt"), "diff")
    manager.ensure_command("python", ["-m", "pytest"], str(external))


def test_eval_workspace_still_rejects_dangerous_command_in_allowlisted_root(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    external = tmp_path / "external"
    workspace.mkdir()
    external.mkdir()
    monkeypatch.setenv("ASTRID_WORKSPACE_ALLOWLIST", str(external))
    manager = PermissionManager(str(workspace), mode="eval-workspace")

    with pytest.raises(RuntimeError, match="Command denied by eval-workspace mode"):
        manager.ensure_command("git", ["reset", "--hard"], str(external))
