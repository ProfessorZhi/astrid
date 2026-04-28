from pathlib import Path

import pytest

from astrid.permissions import PermissionManager


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
