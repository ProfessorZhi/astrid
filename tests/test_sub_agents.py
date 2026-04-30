from __future__ import annotations

from pathlib import Path

from astrid.integrations.mock_model import MockModelAdapter
from astrid.runtime.permissions import PermissionManager
from astrid.core.sub_agents import AgentType, SubAgentManager
from astrid.tools import create_default_tool_registry


def _auto_allow_permissions(workspace: Path) -> PermissionManager:
    return PermissionManager(str(workspace), prompt=lambda request: {"decision": "allow_once"})


def test_general_sub_agent_can_complete_a_workspace_write_task(tmp_path: Path) -> None:
    tools = create_default_tool_registry(str(tmp_path), runtime=None)
    permissions = _auto_allow_permissions(tmp_path)
    manager = SubAgentManager(parent_session_id="session-1")
    agent = manager.spawn_agent(AgentType.GENERAL, "/write plan.txt::sub-agent wrote this")

    try:
        result = manager.execute_agent(
            agent.id,
            model=MockModelAdapter(),
            tools=tools,
            cwd=str(tmp_path),
            permissions=permissions,
        )
    finally:
        tools.dispose()

    assert result.status == "completed"
    assert (tmp_path / "plan.txt").read_text(encoding="utf-8") == "sub-agent wrote this"
    assert result.result_summary is not None
    assert result.result_summary["status"] == "completed"
    assert result.result_summary["agent_type"] == "general"


def test_general_sub_agent_can_complete_natural_language_workspace_task(tmp_path: Path) -> None:
    tools = create_default_tool_registry(str(tmp_path), runtime=None)
    permissions = _auto_allow_permissions(tmp_path)
    manager = SubAgentManager(parent_session_id="session-1")
    agent = manager.spawn_agent(
        AgentType.GENERAL,
        "Please create hello.txt with hello from natural language in it.",
    )

    try:
        result = manager.execute_agent(
            agent.id,
            model=MockModelAdapter(),
            tools=tools,
            cwd=str(tmp_path),
            permissions=permissions,
        )
    finally:
        tools.dispose()

    assert result.status == "completed"
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "hello from natural language"


def test_explore_sub_agent_cannot_write_outside_its_read_only_toolset(tmp_path: Path) -> None:
    tools = create_default_tool_registry(str(tmp_path), runtime=None)
    permissions = _auto_allow_permissions(tmp_path)
    manager = SubAgentManager(parent_session_id="session-1")
    agent = manager.spawn_agent(AgentType.EXPLORE, "/write blocked.txt::should not exist")

    try:
        result = manager.execute_agent(
            agent.id,
            model=MockModelAdapter(),
            tools=tools,
            cwd=str(tmp_path),
            permissions=permissions,
        )
    finally:
        tools.dispose()

    assert result.status == "failed"
    assert not (tmp_path / "blocked.txt").exists()
    assert result.error == "Unknown tool: write_file"


def test_general_sub_agent_denied_edit_is_marked_failed(tmp_path: Path) -> None:
    tools = create_default_tool_registry(str(tmp_path), runtime=None)
    permissions = PermissionManager(str(tmp_path), prompt=lambda request: {"decision": "deny_once"})
    manager = SubAgentManager(parent_session_id="session-1")
    agent = manager.spawn_agent(AgentType.GENERAL, "/write blocked.txt::should not exist")

    try:
        result = manager.execute_agent(
            agent.id,
            model=MockModelAdapter(),
            tools=tools,
            cwd=str(tmp_path),
            permissions=permissions,
        )
    finally:
        tools.dispose()

    assert result.status == "failed"
    assert not (tmp_path / "blocked.txt").exists()
    assert result.error is not None
    assert "denied" in result.error.lower()


def test_compile_result_summary_reflects_failed_status() -> None:
    manager = SubAgentManager(parent_session_id="session-1")
    agent = manager.spawn_agent(AgentType.GENERAL, "do something risky")

    assert manager.fail_agent(agent.id, "permission denied") is True

    summary = manager.compile_result_summary(agent.id)

    assert "[Sub-agent General failed]" in summary
    assert "Status: failed" in summary
    assert "Error: permission denied" in summary


def test_cancelled_agent_summary_is_terminal_and_reportable() -> None:
    manager = SubAgentManager(parent_session_id="session-1")
    agent = manager.spawn_agent(AgentType.PLAN, "stop after planning")

    assert manager.cancel_agent(agent.id, "parent task cancelled") is True

    summary = manager.compile_result_summary(agent.id)
    report = manager.compile_merge_report()

    assert manager.is_agent_terminal(agent.id) is True
    assert "[Sub-agent Plan cancelled]" in summary
    assert "Status: cancelled" in summary
    assert "Error: parent task cancelled" in summary
    assert report["total"] == 1
    assert report["cancelled"] == 1
    assert report["active"] == 0
    assert report["ready_to_merge"] is False
