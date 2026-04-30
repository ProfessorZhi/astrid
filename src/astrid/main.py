from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from astrid.core.agent_loop import run_agent_turn, set_advanced_memory
from astrid.integrations.anthropic_adapter import AnthropicModelAdapter
from astrid.cli.cli_commands import find_matching_slash_commands, try_handle_local_command
from astrid.runtime.config import load_runtime_config
from astrid.state.history import load_history_entries, save_history_entries
from astrid.cli.manage_cli import maybe_handle_management_command
from astrid.integrations.mock_model import MockModelAdapter
from astrid.runtime.permissions import PermissionManager
from astrid.core.prompt import build_system_prompt
from astrid.runtime.bootstrap import BootstrapDependencies, initialize_runtime_session
from astrid.runtime.controller import RuntimeController, append_transcript
from astrid.tools import create_default_tool_registry
from astrid.core.tooling import ToolContext
from astrid.tui.transcript import format_transcript_text
from astrid.tui.types import TranscriptEntry
from astrid.ui.common.text_input import normalize_cli_input, strip_leading_bom_mojibake
from astrid.ui.full.app import run_full_tui_app as run_tty_app
from astrid.ui.shell.banner import render_banner, render_quick_start
from astrid.ui.shell.pipe import run_pipe_inputs, should_render_legacy_intro
from astrid.ui.shell.repl import render_shell_intro, run_shell_repl
from astrid.core.workspace import resolve_tool_path


def _handle_local_command(user_input: str, tools) -> str | None:
    if user_input == "/tools":
        return "\n".join(f"{tool.name}: {tool.description}" for tool in tools.list())
    return try_handle_local_command(user_input, tools=tools)


def _render_banner(runtime: dict | None, cwd: str, permission_summary: list[str], counts: dict[str, int]) -> str:
    return render_banner(runtime, cwd, permission_summary, counts)


def _render_quick_start() -> str:
    return render_quick_start()


def _append_transcript(transcript: list[TranscriptEntry], **kwargs) -> None:
    append_transcript(transcript, **kwargs)


def _strip_leading_bom_mojibake(text: str) -> str:
    return strip_leading_bom_mojibake(text)


def _normalize_cli_input(raw_input: str) -> str:
    return normalize_cli_input(raw_input)


def _make_cli_permission_prompt():
    """Create a simple CLI-based permission prompt for TTY fallback."""

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
    return should_render_legacy_intro(stdin_isatty)


def _is_shell_mode() -> bool:
    return os.environ.get("ASTRID_TERMINAL_MODE", "").strip().lower() == "shell"


def _apply_terminal_mode(mode: str) -> None:
    if mode == "shell":
        os.environ["ASTRID_TERMINAL_MODE"] = "shell"
        os.environ["ASTRID_ALT_SCREEN"] = "0"
        return
    if mode == "agent":
        os.environ["ASTRID_TERMINAL_MODE"] = "shell"
        os.environ["ASTRID_ALT_SCREEN"] = "0"
        return
    os.environ["ASTRID_TERMINAL_MODE"] = "tui"
    os.environ["ASTRID_ALT_SCREEN"] = "1"


def _default_terminal_mode() -> str:
    return "agent"


def _resolve_terminal_mode(*, shell_flag: bool, tui_flag: bool) -> str:
    if shell_flag and tui_flag:
        raise RuntimeError("--shell and --tui cannot be used together.")
    if shell_flag:
        return "shell"
    if tui_flag:
        return "tui"
    return _default_terminal_mode()


def _render_shell_intro() -> str:
    return render_shell_intro()


def _make_runtime_controller(
    *,
    cwd: str,
    permissions,
    transcript: list[TranscriptEntry],
    tools,
    messages: list[dict[str, str]],
    history: list[str],
    model,
    max_tool_steps: int | None,
    advanced_memory_mgr,
    context_mgr,
    logger,
) -> RuntimeController:
    return RuntimeController(
        cwd=cwd,
        permissions=permissions,
        transcript=transcript,
        tools=tools,
        messages=messages,
        history=history,
        model=model,
        max_tool_steps=max_tool_steps,
        advanced_memory_mgr=advanced_memory_mgr,
        context_mgr=context_mgr,
        logger=logger,
        local_command_handler=_handle_local_command,
        transcript_saver=lambda output_path: _save_transcript_file(cwd, permissions, transcript, output_path),
        run_agent_turn_fn=run_agent_turn,
        build_system_prompt_fn=build_system_prompt,
        save_history_entries_fn=save_history_entries,
    )


def _make_bootstrap_dependencies() -> BootstrapDependencies:
    from astrid.state.advanced_memory import create_memory_integration
    from astrid.integrations.bootstrap_system import create_bootstrap_system
    from astrid.core.context_manager import ContextManager
    from astrid.state.memory import MemoryManager
    from astrid.integrations.skill_engine import create_default_skill_engine
    from astrid.integrations.terminology_governance import create_terminology_governance_system

    return BootstrapDependencies(
        load_runtime_config=load_runtime_config,
        create_default_tool_registry=create_default_tool_registry,
        permission_manager_cls=PermissionManager,
        mock_model_adapter_cls=MockModelAdapter,
        anthropic_model_adapter_cls=AnthropicModelAdapter,
        build_system_prompt=build_system_prompt,
        load_history_entries=load_history_entries,
        context_manager_cls=ContextManager,
        memory_manager_cls=MemoryManager,
        create_memory_integration=create_memory_integration,
        create_default_skill_engine=create_default_skill_engine,
        create_terminology_governance_system=create_terminology_governance_system,
        create_bootstrap_system=create_bootstrap_system,
        set_advanced_memory=set_advanced_memory,
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
    max_tool_steps: int | None,
    advanced_memory_mgr,
    context_mgr,
    logger,
) -> list[dict[str, str]] | None:
    controller = _make_runtime_controller(
        cwd=cwd,
        permissions=permissions,
        transcript=transcript,
        tools=tools,
        messages=messages,
        history=history,
        model=model,
        max_tool_steps=max_tool_steps,
        advanced_memory_mgr=advanced_memory_mgr,
        context_mgr=context_mgr,
        logger=logger,
    )
    return controller.handle_user_input(user_input)


def _run_shell_repl(
    *,
    cwd: str,
    permissions,
    transcript: list[TranscriptEntry],
    tools,
    messages: list[dict[str, str]],
    history: list[str],
    model,
    max_tool_steps: int | None,
    advanced_memory_mgr,
    context_mgr,
    logger,
) -> list[dict[str, str]]:
    controller = _make_runtime_controller(
        cwd=cwd,
        permissions=permissions,
        transcript=transcript,
        tools=tools,
        messages=messages,
        history=history,
        model=model,
        max_tool_steps=max_tool_steps,
        advanced_memory_mgr=advanced_memory_mgr,
        context_mgr=context_mgr,
        logger=logger,
    )
    return run_shell_repl(controller=controller, intro=_render_shell_intro())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Astrid - A lightweight terminal coding assistant",
        add_help=True,
    )
    parser.add_argument("--resume", nargs="?", const="latest", default=None, metavar="SESSION_ID")
    parser.add_argument("--list-sessions", action="store_true", help="List all saved sessions and exit")
    parser.add_argument("--session", default=None, metavar="SESSION_ID")
    parser.add_argument("--install", action="store_true", help="Run the interactive installer")
    parser.add_argument("--validate-config", action="store_true", help="Validate configuration and exit")
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (default: WARNING)",
    )
    parser.add_argument("--shell", action="store_true", help="Run Astrid in simplified shell fallback mode.")
    parser.add_argument("--tui", action="store_true", help="Run Astrid in full-screen TUI mode.")
    return parser


def _cleanup_runtime_session(session) -> None:
    logger = session.logger
    logger.info("Shutting down...")
    try:
        session.advanced_memory_mgr.save_all()
        logger.info("Advanced memory saved successfully")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error saving advanced memory: %s", exc)
    try:
        decayed = session.advanced_memory_mgr.apply_memory_decay()
        if decayed > 0:
            logger.info("Memory decay applied: %d entries affected", decayed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error applying memory decay: %s", exc)
    try:
        session.tools.dispose()
        logger.info("Tools disposed successfully")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error disposing tools: %s", exc)
    logger.info("Shutdown complete")


def main() -> None:
    _configure_stdio()
    parser = _build_parser()
    args, remaining = parser.parse_known_args()

    from astrid.runtime.logging_config import setup_logging

    setup_logging(level=args.log_level)

    if args.validate_config:
        from astrid.runtime.config import format_config_diagnostic

        print(format_config_diagnostic())
        return

    if args.install:
        from astrid.cli.install import main as install_main

        install_main()
        return

    cwd = str(Path.cwd())
    management_argv = list(remaining)
    if maybe_handle_management_command(cwd, management_argv):
        return
    if remaining:
        parser.error(f"unrecognized arguments: {' '.join(remaining)}")
    if args.list_sessions:
        from astrid.state.session import format_session_list, list_sessions

        print(format_session_list(list_sessions()))
        return

    _apply_terminal_mode(_resolve_terminal_mode(shell_flag=args.shell, tui_flag=args.tui))

    from astrid.runtime.logging_config import get_logger

    logger = get_logger("main")
    prompt_handler = _make_cli_permission_prompt() if sys.stdin.isatty() else None
    session = initialize_runtime_session(
        cwd=cwd,
        prompt_handler=prompt_handler,
        logger=logger,
        deps=_make_bootstrap_dependencies(),
    )
    stdin_isatty = sys.stdin.isatty()

    if _should_render_legacy_intro(stdin_isatty):
        print(
            _render_banner(
                session.runtime,
                session.cwd,
                session.permissions.get_summary(),
                {
                    "transcriptCount": 0,
                    "messageCount": len(session.messages),
                    "skillCount": len(session.tools.get_skills()),
                    "mcpCount": len(session.tools.get_mcp_servers()),
                    "toolCount": len(session.tools.list()),
                    "memoryCount": session.advanced_memory_mgr.get_statistics().get("total_memories", 0),
                },
            )
        )
        print(_render_quick_start())

    try:
        if not stdin_isatty:
            controller = _make_runtime_controller(
                cwd=session.cwd,
                permissions=session.permissions,
                transcript=session.transcript,
                tools=session.tools,
                messages=session.messages,
                history=session.history,
                model=session.model,
                max_tool_steps=session.max_tool_steps,
                advanced_memory_mgr=session.advanced_memory_mgr,
                context_mgr=session.context_mgr,
                logger=session.logger,
            )
            session.messages = run_pipe_inputs(input_stream=sys.stdin, controller=controller)
            return

        if _is_shell_mode():
            _run_shell_repl(
                cwd=session.cwd,
                permissions=session.permissions,
                transcript=session.transcript,
                tools=session.tools,
                messages=session.messages,
                history=session.history,
                model=session.model,
                max_tool_steps=session.max_tool_steps,
                advanced_memory_mgr=session.advanced_memory_mgr,
                context_mgr=session.context_mgr,
                logger=session.logger,
            )
            return

        controller = _make_runtime_controller(
            cwd=session.cwd,
            permissions=session.permissions,
            transcript=session.transcript,
            tools=session.tools,
            messages=session.messages,
            history=session.history,
            model=session.model,
            max_tool_steps=session.max_tool_steps,
            advanced_memory_mgr=session.advanced_memory_mgr,
            context_mgr=session.context_mgr,
            logger=session.logger,
        )
        run_tty_app(
            runtime=session.runtime,
            tools=session.tools,
            model=session.model,
            messages=session.messages,
            cwd=session.cwd,
            permissions=session.permissions,
            controller=controller,
            resume_session=args.resume,
            list_sessions_only=args.list_sessions,
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Shutting down gracefully...")
    finally:
        _cleanup_runtime_session(session)


if __name__ == "__main__":
    main()
