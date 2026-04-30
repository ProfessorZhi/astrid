from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.tui.types import TranscriptEntry


@dataclass
class RuntimeSession:
    cwd: str
    runtime: dict | None
    tools: Any
    permissions: Any
    model: Any
    messages: list[dict[str, str]]
    history: list[str]
    transcript: list[TranscriptEntry]
    context_mgr: Any
    memory_mgr: Any
    advanced_memory_mgr: Any
    logger: Any
    max_tool_steps: int | None


@dataclass
class BootstrapDependencies:
    load_runtime_config: Any
    create_default_tool_registry: Any
    permission_manager_cls: Any
    mock_model_adapter_cls: Any
    anthropic_model_adapter_cls: Any
    build_system_prompt: Any
    load_history_entries: Any
    context_manager_cls: Any
    memory_manager_cls: Any
    create_memory_integration: Any
    create_default_skill_engine: Any
    create_terminology_governance_system: Any
    create_bootstrap_system: Any
    set_advanced_memory: Any


def _print_runtime_config_warning(exc: Exception) -> None:
    print(
        f"鈿狅笍  Warning: Failed to load runtime config: {exc}\n",
        file=sys.stderr,
    )
    print(
        "馃敡 How to fix this:\n"
        "  1. Set your model name: export ANTHROPIC_MODEL=claude-sonnet-4-20250514\n"
        "  2. Set your API key: export ANTHROPIC_API_KEY=sk-ant-...\n"
        "  3. Or edit ~/.astrid/settings.json:\n"
        '     {"model": "claude-sonnet-4-20250514", "env": {"ANTHROPIC_API_KEY": "sk-ant-..."}}\n'
        "  4. Restart Astrid\n\n"
        "馃摉 For more info: https://github.com/ProfessorZhi/Astrid\n"
        "   Falling back to mock model for now...\n",
        file=sys.stderr,
    )


def _max_tool_steps(runtime: dict | None) -> int | None:
    if runtime and runtime.get("maxToolSteps"):
        return int(runtime.get("maxToolSteps"))
    return None


def initialize_runtime_session(
    *,
    cwd: str,
    prompt_handler: Any,
    logger: Any,
    deps: BootstrapDependencies,
    permission_mode: str | None = None,
) -> RuntimeSession:
    runtime = None
    try:
        runtime = deps.load_runtime_config(cwd)
    except Exception as exc:  # noqa: BLE001
        _print_runtime_config_warning(exc)

    context_mgr = None
    if runtime:
        context_mgr = deps.context_manager_cls(model=runtime.get("model", "default"))
        logger.info("Context manager initialized for model: %s", runtime.get("model", "unknown"))

    memory_mgr = deps.memory_manager_cls(project_root=Path(cwd))
    logger.info("Memory manager initialized")

    advanced_memory_mgr = deps.create_memory_integration(workspace=Path(cwd))
    logger.info("Advanced memory manager initialized")

    skill_engine = deps.create_default_skill_engine(advanced_memory_mgr)
    logger.info("Skill engine initialized")

    terminology_governance = deps.create_terminology_governance_system(advanced_memory_mgr)
    logger.info("Terminology governance system initialized")

    bootstrap_system = deps.create_bootstrap_system(
        advanced_memory_mgr,
        skill_engine,
        terminology_governance,
    )
    logger.info("Bootstrap (self-bootstrapping) system initialized")

    deps.set_advanced_memory(advanced_memory_mgr)

    tools = deps.create_default_tool_registry(
        cwd,
        runtime=runtime,
        advanced_memory_mgr=advanced_memory_mgr,
        skill_engine=skill_engine,
        bootstrap_system=bootstrap_system,
    )
    try:
        permissions = deps.permission_manager_cls(cwd, prompt=prompt_handler, mode=permission_mode)
    except TypeError:
        permissions = deps.permission_manager_cls(cwd, prompt=prompt_handler)
    model = (
        deps.mock_model_adapter_cls()
        if runtime is None or os.environ.get("ASTRID_MODEL_MODE") == "mock"
        else deps.anthropic_model_adapter_cls(runtime, tools)
    )

    def run_initial_bootstrap():
        try:
            result = bootstrap_system.execute_bootstrap_cycle(
                {
                    "context": "initial_startup",
                    "system_version": "Astrid",
                    "timestamp": time.time(),
                }
            )
            logger.info("Initial bootstrap cycle completed: %s", result.get("status", "unknown"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Initial bootstrap cycle failed: %s", exc)

    bootstrap_thread = threading.Thread(target=run_initial_bootstrap, daemon=True)
    bootstrap_thread.start()
    logger.info("Initial bootstrap cycle started in background")

    messages = [
        {
            "role": "system",
            "content": deps.build_system_prompt(
                cwd,
                permissions.get_summary(),
                {
                    "skills": tools.get_skills(),
                    "mcpServers": tools.get_mcp_servers(),
                    "memory_context": memory_mgr.get_relevant_context(),
                    "advanced_memory_context": advanced_memory_mgr.format_context_for_prompt(max_tokens=5000),
                },
            ),
        }
    ]
    history = deps.load_history_entries(cwd)
    transcript: list[TranscriptEntry] = []
    if getattr(permissions, "mode", None) == "bypassPermissions":
        transcript.append(
            TranscriptEntry(
                id=1,
                kind="welcome",
                body="WARNING: bypassPermissions mode is active. Astrid policy prompts are bypassed.",
            )
        )

    return RuntimeSession(
        cwd=cwd,
        runtime=runtime,
        tools=tools,
        permissions=permissions,
        model=model,
        messages=messages,
        history=history,
        transcript=transcript,
        context_mgr=context_mgr,
        memory_mgr=memory_mgr,
        advanced_memory_mgr=advanced_memory_mgr,
        logger=logger,
        max_tool_steps=_max_tool_steps(runtime),
    )
