from __future__ import annotations

import argparse
import sys
import os
import time
from pathlib import Path

from astrid.agent_loop import run_agent_turn
from astrid.anthropic_adapter import AnthropicModelAdapter
from astrid.cli_commands import find_matching_slash_commands, try_handle_local_command
from astrid.config import load_runtime_config
from astrid.history import load_history_entries, save_history_entries
from astrid.local_tool_shortcuts import parse_local_tool_shortcut
from astrid.manage_cli import maybe_handle_management_command
from astrid.mock_model import MockModelAdapter
from astrid.permissions import PermissionManager
from astrid.prompt import build_system_prompt
from astrid.tools import create_default_tool_registry
from astrid.tooling import ToolContext
from astrid.tui.transcript import format_transcript_text
from astrid.tui.types import TranscriptEntry
from astrid.tty_app import run_tty_app
from astrid.workspace import resolve_tool_path


def _handle_local_command(user_input: str, tools) -> str | None:
    if user_input == "/tools":
        return "\n".join(f"{tool.name}: {tool.description}" for tool in tools.list())
    local_result = try_handle_local_command(user_input, tools=tools)
    return local_result


def _render_banner(runtime: dict | None, cwd: str, permission_summary: list[str], counts: dict[str, int]) -> str:
    model = runtime["model"] if runtime else "unconfigured"
    mem_count = counts.get("memoryCount", 0)
    lines = [
        "+" + "-" * 60 + "+",
        "|  Astrid - Your Terminal Coding Assistant                |",
        "+" + "-" * 60 + "+",
        f"|  Model: {model:<49}|",
        f"|  CWD: {cwd:<51}|",
    ]
    if permission_summary:
        for perm in permission_summary[:2]:
            lines.append(f"|  {perm:<58}|")
    lines.append("+" + "-" * 60 + "+")
    lines.append(
        f"|  Skills: {counts['skillCount']:>2} | MCP: {counts['mcpCount']:>2} | Memory: {mem_count:>3} | Tools: {counts.get('toolCount', 0):>2}         |"
    )
    lines.append("+" + "-" * 60 + "+")
    return "\n".join(lines)


def _render_quick_start() -> str:
    """Render the non-interactive quick-start help."""
    return """
Quick Start Guide:
  Edit files:     edit_file.py or patch_file.py
  Search code:    /grep <pattern> or grep_files tool
  Run commands:   /cmd <command> or run_command tool
  Think deeply:   Use sequential_thinking MCP tool
  View skills:    /skills
  Get help:       /help

Try saying:
  "Summarize this project."
  "Use TDD to fix the failing test."
  "Find the root cause of this bug."
  "List the available skills."
"""


def _append_transcript(transcript: list[TranscriptEntry], **kwargs) -> None:
    transcript.append(TranscriptEntry(id=len(transcript) + 1, **kwargs))


def _strip_leading_bom_mojibake(text: str) -> str:
    cleaned = text.lstrip("﻿")
    slash_index = cleaned.find("/")
    if 0 < slash_index <= 3:
        prefix = cleaned[:slash_index]
        if all((ord(ch) > 127) or ch == "?" or (0xDC00 <= ord(ch) <= 0xDFFF) for ch in prefix):
            return cleaned[slash_index:]
    return cleaned


def _normalize_cli_input(raw_input: str) -> str:
    return _strip_leading_bom_mojibake(raw_input).replace("\x00", "").strip()


def _make_cli_permission_prompt():
    """Create a simple CLI-based permission prompt for non-TTY fallback."""
    def _prompt(request: dict) -> dict:
        print(f"\n{request.get('summary', 'Permission Request')}")
        choices = request.get("choices", [])
        if choices:
            for choice in choices:
                print(f"  [{choice.get('key', '')}] {choice.get('label', '')}")
            answer = input("Choose: ").strip()
            for choice in choices:
                if answer == choice.get("key"):
                    return {"decision": choice.get("decision", "allow_once")}
        answer = input("Allow? (y/n): ").strip().lower()
        return {"decision": "allow_once" if answer in ("y", "yes") else "deny_once"}
    return _prompt


def _save_transcript_file(cwd: str, permissions, transcript: list[TranscriptEntry], output_path: str) -> str:
    target = resolve_tool_path(ToolContext(cwd=cwd, permissions=permissions), output_path, "write")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = format_transcript_text(transcript)
    safe_text = text.encode("utf-8", errors="replace").decode("utf-8")
    target.write_text(safe_text, encoding="utf-8")
    return str(target)


def _configure_stdio() -> None:
    """Prefer UTF-8 stdio on Windows so startup banners and piped input stay readable."""
    for stream_name, encoding in (("stdin", "utf-8-sig"), ("stdout", "utf-8"), ("stderr", "utf-8")):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding=encoding, errors="replace")
            except Exception:
                pass


def _should_render_legacy_intro(stdin_isatty: bool) -> bool:
    """Only keep the old banner/guide for pipe and non-interactive mode."""
    return not stdin_isatty


def _is_shell_mode() -> bool:
    return os.environ.get("ASTRID_TERMINAL_MODE", "").strip().lower() == "shell"


def _apply_terminal_mode(mode: str) -> None:
    if mode == "shell":
        os.environ["ASTRID_TERMINAL_MODE"] = "shell"
        os.environ["ASTRID_ALT_SCREEN"] = "0"
        return
    if mode == "agent":
        # Backward-compat alias: the broken inline/agent path is retired.
        os.environ["ASTRID_TERMINAL_MODE"] = "tui"
        os.environ["ASTRID_ALT_SCREEN"] = "1"
        return
    os.environ["ASTRID_TERMINAL_MODE"] = "tui"
    os.environ["ASTRID_ALT_SCREEN"] = "1"


def _default_terminal_mode() -> str:
    if sys.platform == "win32":
        return "shell"
    return "tui"


def _resolve_terminal_mode(*, shell_flag: bool, tui_flag: bool) -> str:
    if shell_flag and tui_flag:
        raise RuntimeError("--shell and --tui cannot be used together.")
    if shell_flag:
        return "shell"
    if tui_flag:
        return "tui"
    return _default_terminal_mode()


def _render_shell_intro() -> str:
    return (
        "Astrid shell mode\n"
        "PowerShell keeps native scrollback and wheel behavior.\n"
        "Use 'astrid --tui' for the full-screen interface.\n"
    )


def _handle_cli_input(
    *,
    user_input: str,
    cwd: str,
    permissions,
    transcript: list[TranscriptEntry],
    tools,
    messages: list[dict[str, str]],
    history: list[str],
    model,
    advanced_memory_mgr,
    context_mgr,
    logger,
) -> list[dict[str, str]] | None:
    if user_input == "/exit":
        return None
    if user_input.startswith("/transcript-save "):
        output_path = user_input[len("/transcript-save ") :].strip()
        if not output_path:
            print("Usage: /transcript-save <path>")
            return messages
        saved_path = _save_transcript_file(cwd, permissions, transcript, output_path)
        print(f"Saved transcript to {saved_path}")
        return messages
    local_result = _handle_local_command(user_input, tools)
    if local_result is not None:
        _append_transcript(transcript, kind="user", body=user_input)
        _append_transcript(transcript, kind="assistant", body=local_result)
        print(local_result)
        return messages
    shortcut = parse_local_tool_shortcut(user_input)
    if shortcut is not None:
        _append_transcript(transcript, kind="user", body=user_input)
        result = tools.execute(
            shortcut["toolName"],
            shortcut["input"],
            context=ToolContext(cwd=cwd, permissions=permissions),
        )
        _append_transcript(
            transcript,
            kind="tool",
            body=result.output,
            toolName=shortcut["toolName"],
            status="success" if result.ok else "error",
        )
        print(result.output)
        return messages
    _append_transcript(transcript, kind="user", body=user_input)
    messages.append({"role": "user", "content": user_input})
    history.append(user_input)
    save_history_entries(history, cwd)
    if hasattr(tools, "refresh_capabilities"):
        tools.refresh_capabilities()
    messages[0] = {
        "role": "system",
        "content": build_system_prompt(
            cwd,
            permissions.get_summary(),
            {
                "skills": tools.get_skills(),
                "mcpServers": tools.get_mcp_servers(),
                "advanced_memory_context": advanced_memory_mgr.format_context_for_prompt(max_tokens=5000),
            },
        ),
    }
    permissions.begin_turn()
    messages = run_agent_turn(
        model=model,
        tools=tools,
        messages=messages,
        cwd=cwd,
        permissions=permissions,
        context_manager=context_mgr,
    )
    permissions.end_turn()
    if context_mgr:
        stats = context_mgr.get_stats()
        logger.debug("After turn: %d tokens (%.0f%%)", stats.total_tokens, stats.usage_percentage)
    last_assistant = next((message for message in reversed(messages) if message["role"] == "assistant"), None)
    if last_assistant:
        _append_transcript(transcript, kind="assistant", body=last_assistant["content"])
        print(last_assistant["content"])
    return messages


def _run_shell_repl(
    *,
    cwd: str,
    permissions,
    transcript: list[TranscriptEntry],
    tools,
    messages: list[dict[str, str]],
    history: list[str],
    model,
    advanced_memory_mgr,
    context_mgr,
    logger,
) -> list[dict[str, str]]:
    print(_render_shell_intro())
    while True:
        try:
            raw_input = input("astrid> ")
        except EOFError:
            break
        user_input = _normalize_cli_input(raw_input)
        if not user_input:
            continue
        next_messages = _handle_cli_input(
            user_input=user_input,
            cwd=cwd,
            permissions=permissions,
            transcript=transcript,
            tools=tools,
            messages=messages,
            history=history,
            model=model,
            advanced_memory_mgr=advanced_memory_mgr,
            context_mgr=context_mgr,
            logger=logger,
        )
        if next_messages is None:
            break
        messages = next_messages
    return messages

def main() -> None:
    _configure_stdio()
    parser = argparse.ArgumentParser(
        description="Astrid - A lightweight terminal coding assistant",
        add_help=True,
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const="latest",
        default=None,
        metavar="SESSION_ID",
        help="Resume a previous session (use 'latest' or session ID)",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all saved sessions and exit",
    )
    parser.add_argument(
        "--session",
        default=None,
        metavar="SESSION_ID",
        help="Start with a specific session ID",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Run the interactive installer",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration and exit",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (default: WARNING)",
    )
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Run Astrid in shell mode so PowerShell keeps its native scrollback and wheel behavior.",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Run Astrid in full-screen TUI mode with Astrid-owned rendering and scrolling.",
    )

    args, remaining = parser.parse_known_args()

    # Initialize logging
    from astrid.logging_config import setup_logging
    setup_logging(level=args.log_level)

    # Run config validation if requested
    if args.validate_config:
        from astrid.config import format_config_diagnostic
        print(format_config_diagnostic())
        return
    
    # Run installer if requested
    if args.install:
        from astrid.install import main as install_main
        install_main()
        return
    
    cwd = str(Path.cwd())

    management_argv = list(remaining)
    if maybe_handle_management_command(cwd, management_argv):
        return
    if remaining:
        parser.error(f"unrecognized arguments: {' '.join(remaining)}")

    _apply_terminal_mode(_resolve_terminal_mode(shell_flag=args.shell, tui_flag=args.tui))

    runtime = None
    try:
        runtime = load_runtime_config(cwd)
    except Exception as e:  # noqa: BLE001
        runtime = None
        print(
            f"⚠️  Warning: Failed to load runtime config: {e}\n",
            file=sys.stderr,
        )
        print(
            "🔧 How to fix this:\n"
            "  1. Set your model name: export ANTHROPIC_MODEL=claude-sonnet-4-20250514\n"
            "  2. Set your API key: export ANTHROPIC_API_KEY=sk-ant-...\n"
            "  3. Or edit ~/.astrid/settings.json:\n"
            '     {"model": "claude-sonnet-4-20250514", "env": {"ANTHROPIC_API_KEY": "sk-ant-..."}}\n'
            "  4. Restart Astrid\n\n"
            "📖 For more info: https://github.com/ProfessorZhi/Astrid\n"
            "   Falling back to mock model for now...\n",
            file=sys.stderr,
        )

    prompt_handler = _make_cli_permission_prompt() if sys.stdin.isatty() else None
    
    # Initialize logging
    from astrid.logging_config import get_logger
    logger = get_logger("main")
    
    # Initialize ContextManager for context window management
    from astrid.context_manager import ContextManager
    context_mgr = None
    if runtime:
        context_mgr = ContextManager(model=runtime.get("model", "default"))
        logger.info("Context manager initialized for model: %s", runtime.get("model", "unknown"))
    
    # Initialize MemoryManager for cross-session knowledge retention
    from astrid.memory import MemoryManager
    memory_mgr = MemoryManager(project_root=Path(cwd))
    logger.info("Memory manager initialized")
    
    # Initialize Advanced Memory System for enhanced capabilities
    from astrid.advanced_memory import create_memory_integration
    advanced_memory_mgr = create_memory_integration()
    logger.info("Advanced memory manager initialized")
    
    # Initialize Skill Engine for skill-based execution
    from astrid.skill_engine import create_default_skill_engine
    skill_engine = create_default_skill_engine(advanced_memory_mgr)
    logger.info("Skill engine initialized")
    
    # Initialize Terminology Governance System
    from astrid.terminology_governance import create_terminology_governance_system
    terminology_governance = create_terminology_governance_system(advanced_memory_mgr)
    logger.info("Terminology governance system initialized")
    
    # Initialize Bootstrap (Self-bootstrapping) System
    from astrid.bootstrap_system import create_bootstrap_system
    bootstrap_system = create_bootstrap_system(
        advanced_memory_mgr, 
        skill_engine, 
        terminology_governance
    )
    logger.info("Bootstrap (self-bootstrapping) system initialized")
    
    # Inject advanced memory into agent loop for auto-insight extraction
    from astrid.agent_loop import set_advanced_memory
    set_advanced_memory(advanced_memory_mgr)
    
    # Create tool registry with new system integration
    tools = create_default_tool_registry(
        cwd, 
        runtime=runtime,
        advanced_memory_mgr=advanced_memory_mgr,
        skill_engine=skill_engine,
        bootstrap_system=bootstrap_system,
    )
    permissions = PermissionManager(cwd, prompt=prompt_handler)
    model = (
        MockModelAdapter()
        if runtime is None or os.environ.get("ASTRID_MODEL_MODE") == "mock"
        else AnthropicModelAdapter(runtime, tools)
    )
    
    import threading
    def run_initial_bootstrap():
        try:
            result = bootstrap_system.execute_bootstrap_cycle({
                "context": "initial_startup",
                "system_version": "Astrid",
                "timestamp": time.time(),
            })
            logger.info("Initial bootstrap cycle completed: %s", result.get("status", "unknown"))
        except Exception as e:
            logger.warning("Initial bootstrap cycle failed: %s", e)
    
    bootstrap_thread = threading.Thread(target=run_initial_bootstrap, daemon=True)
    bootstrap_thread.start()
    logger.info("Initial bootstrap cycle started in background")
    
    messages = [
        {
            "role": "system",
            "content": build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                    "memory_context": memory_mgr.get_relevant_context(),  # 基础记忆
                    "advanced_memory_context": advanced_memory_mgr.format_context_for_prompt(max_tokens=5000),  # 高级记忆上下文
                },
            ),
        }
    ]
    history = load_history_entries(cwd)
    transcript: list[TranscriptEntry] = []
    stdin_isatty = sys.stdin.isatty()

    if _should_render_legacy_intro(stdin_isatty):
        print(
            _render_banner(
                runtime,
                cwd,
                permissions.get_summary(),
                {
                    "transcriptCount": 0,
                    "messageCount": len(messages),
                    "skillCount": len(tools.get_skills()),
                    "mcpCount": len(tools.get_mcp_servers()),
                    "toolCount": len(tools.list()),
                    "memoryCount": advanced_memory_mgr.get_statistics().get("total_memories", 0),
                },
            )
        )
        print(_render_quick_start())

    try:
        if not stdin_isatty:
            for raw_input in sys.stdin:
                user_input = _normalize_cli_input(raw_input)
                if not user_input:
                    continue
                next_messages = _handle_cli_input(
                    user_input=user_input,
                    cwd=cwd,
                    permissions=permissions,
                    transcript=transcript,
                    tools=tools,
                    messages=messages,
                    history=history,
                    model=model,
                    advanced_memory_mgr=advanced_memory_mgr,
                    context_mgr=context_mgr,
                    logger=logger,
                )
                if next_messages is None:
                    break
                messages = next_messages
            return

        if args.shell:
            _run_shell_repl(
                cwd=cwd,
                permissions=permissions,
                transcript=transcript,
                tools=tools,
                messages=messages,
                history=history,
                model=model,
                advanced_memory_mgr=advanced_memory_mgr,
                context_mgr=context_mgr,
                logger=logger,
            )
            return

        run_tty_app(
            runtime=runtime,
            tools=tools,
            model=model,
            messages=messages,
            cwd=cwd,
            permissions=permissions,
            resume_session=args.resume,
            list_sessions_only=args.list_sessions,
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Shutting down gracefully...")
    finally:
        # Graceful shutdown: clean up all resources
        from astrid.logging_config import get_logger
        logger = get_logger("main")
        logger.info("Shutting down...")
        
        # Save advanced memory system state
        try:
            advanced_memory_mgr.save_all()
            logger.info("Advanced memory saved successfully")
        except Exception as e:
            logger.warning("Error saving advanced memory: %s", e)
        
        # Apply memory decay on shutdown
        try:
            decayed = advanced_memory_mgr.apply_memory_decay()
            if decayed > 0:
                logger.info("Memory decay applied: %d entries affected", decayed)
        except Exception as e:
            logger.warning("Error applying memory decay: %s", e)
        
        # Dispose tools (closes MCP connections)
        try:
            tools.dispose()
            logger.info("Tools disposed successfully")
        except Exception as e:
            logger.warning("Error disposing tools: %s", e)
        
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
