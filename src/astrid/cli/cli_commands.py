from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from astrid.runtime.config import (
    ASTRID_MCP_PATH,
    ASTRID_PERMISSIONS_PATH,
    ASTRID_SETTINGS_PATH,
    load_runtime_config,
    save_mini_code_settings,
)
from astrid.state.history import load_history_entries
from astrid.integrations.skills import _external_skills_root
from astrid.runtime.task_tracker import TaskManager
from astrid.core.tooling import ToolContext
from astrid.tui.buddy import BUDDY_SPECIES


@dataclass(frozen=True, slots=True)
class SlashCommand:
    name: str
    usage: str
    description: str


SLASH_COMMANDS = [
    SlashCommand("/help", "/help", "Show available slash commands."),
    SlashCommand("/tools", "/tools", "List tools available to the coding agent and tool shortcuts."),
    SlashCommand("/status", "/status", "Show application state summary and current model."),
    SlashCommand("/cost", "/cost [--detailed]", "Show API cost and usage report."),
    SlashCommand("/context", "/context", "Show context window usage."),
    SlashCommand("/tasks", "/tasks", "Show current task list."),
    SlashCommand("/memory", "/memory [search <query>]", "Show memory status or search memories."),
    SlashCommand("/skills", "/skills [exec <name>]", "List or execute registered skills."),
    SlashCommand("/bootstrap", "/bootstrap", "Show bootstrap system status and improvement history."),
    SlashCommand("/config", "/config", "Show configuration diagnostics and validation."),
    SlashCommand("/history", "/history", "Show recent prompt history from ~/.astrid/history.json."),
    SlashCommand("/clear", "/clear", "Clear the current transcript view."),
    SlashCommand("/retry", "/retry", "Retry the last natural-language prompt in this session."),
    SlashCommand("/transcript-save", "/transcript-save <path>", "Save the current session transcript to a text file."),
    SlashCommand("/model", "/model", "Show the current model."),
    SlashCommand("/model", "/model <model-name>", "Persist a model override into ~/.astrid/settings.json."),
    SlashCommand("/config-paths", "/config-paths", "Show Astrid settings paths."),
    SlashCommand("/mcp", "/mcp", "Show configured MCP servers and connection state."),
    SlashCommand("/permissions", "/permissions", "Show astrid permission storage path."),
    SlashCommand("/pet", "/pet list", "List available buddy species."),
    SlashCommand("/pet", "/pet show", "Show the welcome buddy on idle screens."),
    SlashCommand("/pet", "/pet hide", "Hide the welcome buddy on idle screens."),
    SlashCommand("/pet", "/pet next", "Switch to the next buddy species."),
    SlashCommand("/pet", "/pet switch <species>", "Switch the welcome buddy species."),
    SlashCommand("/pet", "/pet pet", "Trigger a short heart reaction for the welcome buddy."),
    SlashCommand("/pet", "/pet profile", "Show the current buddy profile and rarity traits."),
    SlashCommand("/pet", "/pet import <path-or-url> [--ascii|--ansi]", "Import a custom pet sprite from a local image or URL."),
    SlashCommand("/pet", "/pet mode <ascii|ansi>", "Switch the imported pet render mode."),
    SlashCommand("/pet", "/pet save <name>", "Save the current imported pet as a named preset."),
    SlashCommand("/pet", "/pet use <name>", "Load a named preset pet into the welcome screen."),
    SlashCommand("/pet", "/pet remove <name>", "Remove a named preset pet."),
    SlashCommand("/exit", "/exit", "Exit astrid."),
    SlashCommand("/debug", "/debug", "Show scroll and terminal diagnostics."),
    SlashCommand("/ls", "/ls [path]", "List files in a directory."),
    SlashCommand("/grep", "/grep <pattern>::[path]", "Search text in files."),
    SlashCommand("/read", "/read <path>", "Read a file directly."),
    SlashCommand("/write", "/write <path>::<content>", "Write a file directly."),
    SlashCommand("/modify", "/modify <path>::<content>", "Replace a file, showing a reviewable diff before applying it."),
    SlashCommand("/edit", "/edit <path>::<search>::<replace>", "Edit a file by exact replacement."),
    SlashCommand("/patch", "/patch <path>::<search1>::<replace1>::<search2>::<replace2>...", "Apply multiple replacements to one file in one command."),
    SlashCommand("/cmd", "/cmd [cwd::]<command> [args...]", "Run an allowed development command directly."),
]


def format_slash_commands() -> str:
    command_groups = {
        "Core Commands": [
            ("/help", "Show this help message"),
            ("/exit", "Exit astrid"),
            ("/clear", "Clear the current transcript view"),
            ("/history", "Show recent prompt history"),
        ],
        "Tool Commands": [
            ("/tools", "List all available tools"),
            ("/skills", "List discovered SKILL.md workflows"),
            ("/mcp", "Show MCP servers and connection state"),
            ("/cmd", "Run development commands directly"),
        ],
        "Status & Info": [
            ("/status", "Show application state summary"),
            ("/model", "Show or change current model"),
            ("/cost", "Show API cost and usage report"),
            ("/context", "Show context window usage"),
            ("/tasks", "Show current task list"),
            ("/memory", "Show memory system status"),
        ],
        "File Operations": [
            ("/ls [path]", "List files in directory"),
            ("/grep <pattern>", "Search text in files"),
            ("/read <path>", "Read a file directly"),
            ("/write <path>", "Write content to file"),
            ("/edit <path>", "Edit file by exact replacement"),
            ("/patch <path>", "Apply multiple replacements in one go"),
            ("/modify <path>", "Replace file with reviewable diff"),
        ],
        "Session Management": [
            ("/transcript-save <path>", "Save transcript to text file"),
            ("/retry", "Retry the last prompt"),
            ("/permissions", "Show permission storage path"),
            ("/config-paths", "Show settings file paths"),
        ],
    }

    lines = ["Available Commands", "==================", ""]
    for group_name, commands in command_groups.items():
        lines.append(f"{group_name}:")
        for cmd, desc in commands:
            lines.append(f"  {cmd:<22} {desc}")
        lines.append("")

    lines.extend(
        [
            "Tips:",
            "  - Use Tab to autocomplete commands",
            "  - Prefix with / to access any command",
            "  - Type naturally - Astrid understands Chinese and English",
        ]
    )
    return "\n".join(lines)


def find_matching_slash_commands(user_input: str) -> list[str]:
    return [command.usage for command in SLASH_COMMANDS if command.usage.startswith(user_input)]


def complete_slash_command(line: str) -> tuple[list[str], str]:
    hits = [command.usage for command in SLASH_COMMANDS if command.usage.startswith(line)]
    return (hits if hits else [command.usage for command in SLASH_COMMANDS], line)


def _format_history(entries: list[str], limit: int = 20) -> str:
    if not entries:
        return "No recent prompt history for this workspace."
    start = max(0, len(entries) - limit)
    return "\n".join(f"{start + index + 1}. {entry}" for index, entry in enumerate(entries[start:]))


def try_handle_local_command(user_input: str, tools=None) -> str | None:
    if user_input in {"/", "/help"}:
        return format_slash_commands()

    if user_input == "/history":
        return _format_history(load_history_entries(str(Path.cwd())))

    if user_input == "/config-paths":
        return "\n".join(
            [
                f"astrid settings: {ASTRID_SETTINGS_PATH}",
                f"astrid permissions: {ASTRID_PERMISSIONS_PATH}",
                f"astrid mcp: {ASTRID_MCP_PATH}",
            ]
        )

    if user_input == "/permissions":
        return f"permission store: {ASTRID_PERMISSIONS_PATH}"

    if user_input == "/pet list":
        return "Available buddies:\n" + ", ".join(BUDDY_SPECIES)

    if user_input == "/skills":
        if tools is not None and hasattr(tools, "refresh_capabilities"):
            tools.refresh_capabilities()
        skills = tools.get_skills() if tools else []
        if not skills:
            return (
                "No skills discovered. "
                f"Add skills under {_external_skills_root()}\\<name>\\SKILL.md, "
                "or .astrid/skills/<name>/SKILL.md."
            )
        return "\n".join(
            f"{skill['name']}  {skill['description']}  [{skill['source']}]"
            for skill in skills
        )

    if user_input.startswith("/skills exec "):
        skill_name = user_input[len("/skills exec ") :].strip()
        if not skill_name:
            return "Usage: /skills exec <name>"
        if tools is None:
            return "Skill loading requires an active tool registry."
        if hasattr(tools, "refresh_capabilities"):
            tools.refresh_capabilities()
        result = tools.execute(
            "load_skill",
            {"name": skill_name},
            context=ToolContext(cwd=str(Path.cwd())),
        )
        if result.ok:
            return result.output
        return f"{result.output}\nTip: run /skills to see discovered skill names."

    if user_input == "/config":
        from astrid.runtime.config import format_config_diagnostic

        return format_config_diagnostic()

    if user_input == "/memory":
        lines = ["Memory System Status", "=" * 50, ""]
        try:
            from astrid.state.memory import memories_root, workspace_id

            cwd = Path.cwd()
            lines.append(f"Memory root: {memories_root()}")
            lines.append(f"Workspace id: {workspace_id(cwd)}")
            lines.append("")
        except Exception as e:
            lines.append(f"Memory path error: {e}")
            lines.append("")
        try:
            from astrid.tools.advanced_memory_tools import _advanced_memory_mgr

            adv_mgr = _advanced_memory_mgr
            if adv_mgr:
                stats = adv_mgr.get_statistics()
                lines.append("Advanced Memory:")
                lines.append(f"  Total memories: {stats.get('total_memories', 0)}")
                lines.append(f"  Registered skills: {stats.get('total_skills', 0)}")
                lines.append(f"  Terminology entries: {stats.get('total_terminologies', 0)}")

                memory_stats = stats.get("memory_stats", {})
                for scope_name, scope_data in memory_stats.items():
                    if scope_data.get("count", 0) > 0:
                        lines.append(f"    {scope_name}: {scope_data['count']} entries")

                lines.append("")
                recent = adv_mgr.list_memories()[:8]
                if recent:
                    lines.append("Recent Memories:")
                    for entry in recent:
                        scope_str = f"[{entry.scope.value}]" if hasattr(entry, "scope") else ""
                        type_str = f"[{entry.type.value}]" if hasattr(entry, "type") else ""
                        lines.append(f"  - {scope_str}{type_str} {entry.content[:70]}")
                        if hasattr(entry, "tags") and entry.tags:
                            lines.append(f"    Tags: {', '.join(entry.tags[:4])}")
                else:
                    lines.append("No memories stored yet.")
            else:
                lines.append("  Advanced memory not initialized.")
        except Exception as e:
            lines.append(f"  Advanced memory error: {e}")

        lines.append("")
        try:
            from astrid.state.memory import MemoryManager

            memory_mgr = MemoryManager(project_root=Path.cwd())
            basic_stats = memory_mgr.get_stats()
            has_basic = any(scope.get("entries", 0) > 0 for scope in basic_stats.values())
            if has_basic:
                lines.append("Basic Memory (MEMORY.md):")
                for scope_name, scope_data in basic_stats.items():
                    if scope_data.get("entries", 0) > 0:
                        lines.append(f"  {scope_name}: {scope_data['entries']} entries")
        except Exception:
            pass

        return "\n".join(lines)

    if user_input.startswith("/memory search "):
        query = user_input[len("/memory search ") :].strip()
        if not query:
            return "Usage: /memory search <query>"
        try:
            from astrid.tools.advanced_memory_tools import _advanced_memory_mgr

            if not _advanced_memory_mgr:
                return "Advanced memory not initialized."
            results = _advanced_memory_mgr.search_memories(query, limit=10)
            if not results:
                return f"No memories found for: {query}"
            lines = [f"Search results for '{query}' ({len(results)} found):", ""]
            for entry in results:
                scope_str = f"[{entry.scope.value}]" if hasattr(entry, "scope") else ""
                type_str = f"[{entry.type.value}]" if hasattr(entry, "type") else ""
                lines.append(f"  {scope_str}{type_str} {entry.content[:120]}")
                if hasattr(entry, "tags") and entry.tags:
                    lines.append(f"    Tags: {', '.join(entry.tags[:4])}")
            return "\n".join(lines)
        except Exception as e:
            return f"Search error: {e}"

    if user_input == "/bootstrap":
        lines = ["Bootstrap (Self-Bootstrapping) System", "=" * 50, ""]
        try:
            from astrid.tools.advanced_memory_tools import _advanced_memory_mgr, _bootstrap_system

            if _bootstrap_system:
                records = _bootstrap_system.bootstrap_records
                lines.append(f"  Total bootstrap cycles: {len(records)}")
                if records:
                    last = records[-1]
                    lines.append(f"  Last cycle phase: {last.phase.value if hasattr(last, 'phase') else 'unknown'}")
                    lines.append(f"  Last cycle result: {'success' if last.success else 'failed'}")
                    if last.error_message:
                        lines.append(f"  Last error: {last.error_message[:80]}")
                    lines.append("")
                    lines.append("Recent Bootstrap Cycles:")
                    for record in records[-5:]:
                        phase = record.phase.value if hasattr(record, "phase") else "unknown"
                        result = "OK" if record.success else "FAIL"
                        lines.append(f"  [{result}] {phase}: {record.description[:60]}")
            else:
                lines.append("  Bootstrap system not initialized.")

            if _advanced_memory_mgr:
                lines.append("")
                lines.append("System Statistics:")
                stats = _advanced_memory_mgr.get_statistics()
                lines.append(f"  Memory entries: {stats.get('total_memories', 'N/A')}")
                lines.append(f"  Skills: {stats.get('total_skills', 'N/A')}")
                lines.append(f"  Terminology: {stats.get('total_terminologies', 'N/A')}")
        except Exception as e:
            lines.append(f"  Error: {e}")

        return "\n".join(lines)

    if user_input == "/context":
        try:
            from astrid.core.context_manager import load_context_state

            ctx_mgr = load_context_state()
            if ctx_mgr:
                return ctx_mgr.format_context_details()
            return "No context state available. Context tracking starts after first turn."
        except Exception as e:
            return f"Error loading context: {e}"

    if user_input == "/tasks":
        try:
            task_manager = TaskManager()
            if task_manager.active_list:
                return task_manager.format_details()
            return "No active task list. Tasks are auto-detected from multi-step requests."
        except Exception as e:
            return f"Task system error: {e}"

    if user_input == "/mcp":
        if tools is not None and hasattr(tools, "refresh_capabilities"):
            tools.refresh_capabilities(connect_mcp=True)
        servers = tools.get_mcp_servers() if tools else []
        if not servers:
            return "No MCP servers configured. Add mcpServers to ~/.astrid/settings.json, ~/.astrid/mcp.json, or project .mcp.json."
        lines = []
        for server in servers:
            suffix = f"  error={server['error']}" if server.get("error") else ""
            protocol = f"  protocol={server['protocol']}" if server.get("protocol") else ""
            resources = f"  resources={server['resourceCount']}" if server.get("resourceCount") is not None else ""
            prompts = f"  prompts={server['promptCount']}" if server.get("promptCount") is not None else ""
            lines.append(
                f"{server['name']}  status={server['status']}  tools={server['toolCount']}{resources}{prompts}{protocol}{suffix}"
            )
        return "\n".join(lines)

    if user_input == "/status":
        try:
            runtime = load_runtime_config()
        except Exception as error:  # noqa: BLE001
            return f"runtime not configured: {error}"
        auth = "ANTHROPIC_AUTH_TOKEN" if runtime.get("authToken") else "ANTHROPIC_API_KEY"
        return "\n".join(
            [
                f"model: {runtime['model']}",
                f"baseUrl: {runtime['baseUrl']}",
                f"auth: {auth}",
                f"mcp servers: {len(runtime.get('mcpServers', {}))}",
                runtime["sourceSummary"],
            ]
        )

    if user_input == "/model":
        try:
            runtime = load_runtime_config()
        except Exception as error:  # noqa: BLE001
            return f"runtime not configured: {error}"
        return f"current model: {runtime['model']}"

    if user_input.startswith("/model "):
        model = user_input[len("/model ") :].strip()
        if not model:
            return "usage: /model <model-name>"
        save_mini_code_settings({"model": model})
        return f"saved model={model} to {ASTRID_SETTINGS_PATH}"

    return None
