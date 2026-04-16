from __future__ import annotations

from dataclasses import dataclass

from astrid.poly_commands import create_builtin_commands, CommandRegistry
from astrid.config import (
    CLAUDE_SETTINGS_PATH,
    ASTRID_MCP_PATH,
    ASTRID_PERMISSIONS_PATH,
    ASTRID_SETTINGS_PATH,
    load_runtime_config,
    save_mini_code_settings,
)


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
    SlashCommand("/config-paths", "/config-paths", "Show astrid and Claude fallback settings paths."),
    SlashCommand("/mcp", "/mcp", "Show configured MCP servers and connection state."),
    SlashCommand("/permissions", "/permissions", "Show astrid permission storage path."),
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
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  📚 Available Commands                                  ║",
        "╠══════════════════════════════════════════════════════════╣",
    ]
    
    command_groups = {
        "🔧 Core Commands": [
            ("/help", "Show this help message"),
            ("/exit", "Exit astrid"),
            ("/clear", "Clear the current transcript view"),
            ("/history", "Show recent prompt history"),
        ],
        "🛠️ Tool Commands": [
            ("/tools", "List all available tools"),
            ("/skills", "List discovered SKILL.md workflows"),
            ("/mcp", "Show MCP servers and connection state"),
            ("/cmd", "Run development commands directly"),
        ],
        "📊 Status & Info": [
            ("/status", "Show application state summary"),
            ("/model", "Show or change current model"),
            ("/cost", "Show API cost and usage report"),
            ("/context", "Show context window usage"),
            ("/tasks", "Show current task list"),
            ("/memory", "Show memory system status"),
        ],
        "✏️ File Operations": [
            ("/ls [path]", "List files in directory"),
            ("/grep <pattern>", "Search text in files"),
            ("/read <path>", "Read a file directly"),
            ("/write <path>", "Write content to file"),
            ("/edit <path>", "Edit file by exact replacement"),
            ("/patch <path>", "Apply multiple replacements in one go"),
            ("/modify <path>", "Replace file with reviewable diff"),
        ],
        "💾 Session Management": [
            ("/transcript-save <path>", "Save transcript to text file"),
            ("/retry", "Retry the last prompt"),
            ("/permissions", "Show permission storage path"),
            ("/config-paths", "Show settings file paths"),
        ],
    }
    
    for group_name, commands in command_groups.items():
        lines.append(f"║  {group_name:<54}║")
        for cmd, desc in commands:
            cmd_display = f"    {cmd}"
            lines.append(f"║  {cmd_display:<20} {desc:<33} ║")
        lines.append("╠══════════════════════════════════════════════════════════╣")
    
    lines.extend([
        "║  💡 Tips:                                              ║",
        "║  - Use Tab to autocomplete commands                    ║",
        "║  - Prefix with / to access any command                 ║",
        "║  - Type naturally - I'll understand Chinese & English  ║",
        "╚══════════════════════════════════════════════════════════╝",
    ])
    
    return "\n".join(lines)


def find_matching_slash_commands(user_input: str) -> list[str]:
    return [command.usage for command in SLASH_COMMANDS if command.usage.startswith(user_input)]


def complete_slash_command(line: str) -> tuple[list[str], str]:
    hits = [command.usage for command in SLASH_COMMANDS if command.usage.startswith(line)]
    return (hits if hits else [command.usage for command in SLASH_COMMANDS], line)


def try_handle_local_command(user_input: str, tools=None) -> str | None:
    if user_input in {"/", "/help"}:
        return format_slash_commands()

    if user_input == "/config-paths":
        return "\n".join(
            [
                f"astrid settings: {ASTRID_SETTINGS_PATH}",
                f"astrid permissions: {ASTRID_PERMISSIONS_PATH}",
                f"astrid mcp: {ASTRID_MCP_PATH}",
                f"compat fallback: {CLAUDE_SETTINGS_PATH}",
            ]
        )

    if user_input == "/permissions":
        return f"permission store: {ASTRID_PERMISSIONS_PATH}"

    if user_input == "/skills":
        skills = tools.get_skills() if tools else []
        if not skills:
            return "No skills discovered. Add skills under ~/.astrid/skills/<name>/SKILL.md, .astrid/skills/<name>/SKILL.md, .claude/skills/<name>/SKILL.md, or ~/.claude/skills/<name>/SKILL.md."
        return "\n".join(
            f"{skill['name']}  {skill['description']}  [{skill['source']}]"
            for skill in skills
        )

    if user_input == "/config":
        from astrid.config import format_config_diagnostic
        return format_config_diagnostic()

    if user_input == "/memory":
        # Enhanced memory system display (advanced memory + basic memory)
        lines = ["Memory System Status", "=" * 50, ""]
        try:
            from astrid.advanced_memory import create_memory_integration
            from astrid.tools.advanced_memory_tools import _advanced_memory_mgr
            
            adv_mgr = _advanced_memory_mgr
            if adv_mgr:
                stats = adv_mgr.get_statistics()
                lines.append(f"Advanced Memory:")
                lines.append(f"  Total memories: {stats.get('total_memories', 0)}")
                lines.append(f"  Registered skills: {stats.get('total_skills', 0)}")
                lines.append(f"  Terminology entries: {stats.get('total_terminologies', 0)}")
                
                # 按范围统计
                memory_stats = stats.get("memory_stats", {})
                for scope_name, scope_data in memory_stats.items():
                    if scope_data.get("count", 0) > 0:
                        lines.append(f"    {scope_name}: {scope_data['count']} entries")
                
                lines.append("")
                
                # 显示最近记忆
                recent = adv_mgr.list_memories()[:8]
                if recent:
                    lines.append("Recent Memories:")
                    for entry in recent:
                        scope_str = f"[{entry.scope.value}]" if hasattr(entry, 'scope') else ""
                        type_str = f"[{entry.type.value}]" if hasattr(entry, 'type') else ""
                        lines.append(f"  - {scope_str}{type_str} {entry.content[:70]}")
                        if hasattr(entry, 'tags') and entry.tags:
                            lines.append(f"    Tags: {', '.join(entry.tags[:4])}")
                else:
                    lines.append("No memories stored yet.")
            else:
                lines.append("  Advanced memory not initialized.")
        except Exception as e:
            lines.append(f"  Advanced memory error: {e}")
        
        lines.append("")
        
        # 也显示基础记忆信息
        try:
            from astrid.memory import MemoryManager
            from pathlib import Path
            memory_mgr = MemoryManager(project_root=Path.cwd())
            basic_stats = memory_mgr.get_stats()
            has_basic = any(s.get("entries", 0) > 0 for s in basic_stats.values())
            if has_basic:
                lines.append("Basic Memory (MEMORY.md):")
                for scope_name, scope_data in basic_stats.items():
                    if scope_data.get("entries", 0) > 0:
                        lines.append(f"  {scope_name}: {scope_data['entries']} entries")
        except Exception:
            pass
        
        return "\n".join(lines)

    if user_input.startswith("/memory search "):
        # 搜索高级记忆
        query = user_input[len("/memory search "):].strip()
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
                scope_str = f"[{entry.scope.value}]" if hasattr(entry, 'scope') else ""
                type_str = f"[{entry.type.value}]" if hasattr(entry, 'type') else ""
                lines.append(f"  {scope_str}{type_str} {entry.content[:120]}")
                if hasattr(entry, 'tags') and entry.tags:
                    lines.append(f"    Tags: {', '.join(entry.tags[:4])}")
            return "\n".join(lines)
        except Exception as e:
            return f"Search error: {e}"

    if user_input == "/bootstrap":
        # Bootstrap system status
        lines = ["Bootstrap (Self-Bootstrapping) System", "=" * 50, ""]
        try:
            from astrid.tools.advanced_memory_tools import _bootstrap_system, _advanced_memory_mgr
            
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
                    phase = record.phase.value if hasattr(record, 'phase') else 'unknown'
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
        # Context usage display
        try:
            from astrid.context_manager import load_context_state
            ctx_mgr = load_context_state()
            if ctx_mgr:
                return ctx_mgr.format_context_details()
            else:
                return "No context state available. Context tracking starts after first turn."
        except Exception as e:
            return f"Error loading context: {e}"

    if user_input == "/mcp":
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
