from dataclasses import asdict

from astrid.mcp import create_mcp_backed_tools
from astrid.skills import discover_skills
from astrid.tooling import ToolRegistry
from astrid.tools.advanced_memory_tools import (
    memory_search_tool,
    memory_store_tool,
    skill_execute_tool,
    skill_list_tool,
    bootstrap_status_tool,
)
from astrid.tools.api_tester import api_tester_tool
from astrid.tools.ask_user import ask_user_tool
from astrid.tools.code_nav import find_symbols_tool, find_references_tool, get_ast_info_tool
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


def create_default_tool_registry(
    cwd: str,
    runtime: dict | None = None,
    advanced_memory_mgr=None,
    skill_engine=None,
    bootstrap_system=None,
) -> ToolRegistry:
    skills = [asdict(skill) for skill in discover_skills(cwd)]
    mcp = create_mcp_backed_tools(cwd=cwd, mcp_servers=dict(runtime.get("mcpServers", {})) if runtime else {})
    
    # 注入高级记忆系统实例到工具中
    if advanced_memory_mgr or skill_engine or bootstrap_system:
        from astrid.tools.advanced_memory_tools import initialize as init_advanced_tools
        init_advanced_tools(advanced_memory_mgr, skill_engine, bootstrap_system)
    
    return ToolRegistry(
        [
            # User interaction
            ask_user_tool,
            # File operations
            list_files_tool,
            grep_files_tool,
            read_file_tool,
            write_file_tool,
            modify_file_tool,
            edit_file_tool,
            patch_file_tool,
            # Command execution
            run_command_tool,
            run_with_debug_tool,
            # Web tools
            web_fetch_tool,
            web_search_tool,
            api_tester_tool,
            # Task management
            todo_write_tool,
            # Git workflow
            git_tool,
            # Notebook editing
            notebook_edit_tool,
            # Code intelligence
            find_symbols_tool,
            find_references_tool,
            get_ast_info_tool,
            multi_edit_tool,
            code_review_tool,
            # Visualization
            file_tree_tool,
            diff_viewer_tool,
            # Testing & Debugging
            test_runner_tool,
            # Database & Docker (NEW!)
            db_explorer_tool,
            docker_helper_tool,
            # Governance audit
            governance_audit_tool,
            # Advanced memory tools
            memory_search_tool,
            memory_store_tool,
            skill_execute_tool,
            skill_list_tool,
            bootstrap_status_tool,
            # Skills
            create_load_skill_tool(cwd),
            # MCP tools
            *mcp["tools"],
        ],
        skills=skills,
        mcp_servers=mcp["servers"],
        disposer=mcp["dispose"],
    )
