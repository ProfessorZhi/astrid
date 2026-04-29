import os
from dataclasses import asdict

from astrid.mcp import create_mcp_backed_tools
from astrid.skills import discover_skills
from astrid.tooling import ToolCatalog, ToolRegistry
from astrid.tools.advanced_memory_tools import (
    bootstrap_status_tool,
    memory_search_tool,
    memory_store_tool,
    skill_execute_tool,
    skill_list_tool,
)
from astrid.tools.api_tester import api_tester_tool
from astrid.tools.ask_user import ask_user_tool
from astrid.tools.code_nav import find_references_tool, find_symbols_tool, get_ast_info_tool
from astrid.tools.code_review import code_review_tool
from astrid.tools.db_explorer import db_explorer_tool
from astrid.tools.diff_viewer import diff_viewer_tool
from astrid.tools.docker_helper import docker_helper_tool
from astrid.tools.edit_file import edit_file_tool
from astrid.tools.file_tree import file_tree_tool
from astrid.tools.git import git_tool
from astrid.tools.governance_audit_tool import governance_audit_tool
from astrid.tools.grep_files import grep_files_tool
from astrid.tools.list_files import list_files_tool
from astrid.tools.load_skill import create_load_skill_tool
from astrid.tools.modify_file import modify_file_tool
from astrid.tools.multi_edit import multi_edit_tool
from astrid.tools.notebook_edit import notebook_edit_tool
from astrid.tools.patch_file import patch_file_tool
from astrid.tools.read_file import read_file_tool
from astrid.tools.run_command import run_command_tool
from astrid.tools.run_with_debug import run_with_debug_tool
from astrid.tools.test_runner import test_runner_tool
from astrid.tools.todo_write import todo_write_tool
from astrid.tools.web_fetch import web_fetch_tool
from astrid.tools.web_search import web_search_tool
from astrid.tools.write_file import write_file_tool


def _should_eager_start_mcp() -> bool:
    value = os.environ.get("ASTRID_EAGER_MCP", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _configured_mcp_server_summaries(mcp_servers: dict[str, dict]) -> list[dict]:
    summaries: list[dict] = []
    for name, config in mcp_servers.items():
        status = "disabled" if config.get("enabled") is False else "configured"
        summaries.append(
            {
                "name": name,
                "command": config.get("command", ""),
                "status": status,
                "toolCount": 0,
                "resourceCount": None,
                "promptCount": None,
                "protocol": config.get("protocol"),
                "error": None,
            }
        )
    return summaries


def create_default_tool_registry(
    cwd: str,
    runtime: dict | None = None,
    advanced_memory_mgr=None,
    skill_engine=None,
    bootstrap_system=None,
) -> ToolRegistry:
    static_tools = [
        ask_user_tool,
        list_files_tool,
        grep_files_tool,
        read_file_tool,
        write_file_tool,
        modify_file_tool,
        edit_file_tool,
        patch_file_tool,
        run_command_tool,
        run_with_debug_tool,
        web_fetch_tool,
        web_search_tool,
        api_tester_tool,
        todo_write_tool,
        git_tool,
        notebook_edit_tool,
        find_symbols_tool,
        find_references_tool,
        get_ast_info_tool,
        multi_edit_tool,
        code_review_tool,
        file_tree_tool,
        diff_viewer_tool,
        test_runner_tool,
        db_explorer_tool,
        docker_helper_tool,
        governance_audit_tool,
        memory_search_tool,
        memory_store_tool,
        skill_execute_tool,
        skill_list_tool,
        bootstrap_status_tool,
        create_load_skill_tool(cwd),
    ]

    def _build_catalog(*, connect_mcp: bool = False) -> ToolCatalog:
        skills = [asdict(skill) for skill in discover_skills(cwd)]
        configured_mcp = dict(runtime.get("mcpServers", {})) if runtime else {}
        if connect_mcp or _should_eager_start_mcp():
            mcp = create_mcp_backed_tools(
                cwd=cwd,
                mcp_servers=configured_mcp,
            )
        else:
            mcp = {
                "tools": [],
                "servers": _configured_mcp_server_summaries(configured_mcp),
                "dispose": None,
            }
        return ToolCatalog(
            tools=[*static_tools, *mcp["tools"]],
            skills=skills,
            mcp_servers=mcp["servers"],
            disposer=mcp["dispose"],
        )

    catalog = _build_catalog(connect_mcp=False)

    if advanced_memory_mgr or skill_engine or bootstrap_system:
        from astrid.tools.advanced_memory_tools import initialize as init_advanced_tools

        init_advanced_tools(advanced_memory_mgr, skill_engine, bootstrap_system)

    return ToolRegistry(
        catalog.tools,
        skills=catalog.skills,
        mcp_servers=catalog.mcp_servers,
        disposer=catalog.disposer,
        refresh_catalog=_build_catalog,
    )
