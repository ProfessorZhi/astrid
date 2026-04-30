"""Lightweight sub-agent system for Astrid.

Inspired by Claude Code's AgentTool and coordinator/ system.
Provides specialized agents for different task types:
- Explore: Read-only, fast, for codebase exploration
- Plan: Read-only, thorough, for context gathering
- General-purpose: Full tools, for complex multi-step tasks

Each agent runs in isolation with its own context window,
preventing main conversation context from bloating.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from astrid.agent_loop import run_agent_turn
from astrid.core.context_manager import ContextManager
from astrid.state import AppState, Store
from astrid.core.tooling import ToolDefinition, ToolRegistry
from astrid.core.types import ChatMessage, ModelAdapter


# ---------------------------------------------------------------------------
# Agent types
# ---------------------------------------------------------------------------

class AgentType(str, Enum):
    """Sub-agent types (inspired by Claude Code's built-in agents)."""
    EXPLORE = "explore"           # Read-only, fast (like Haiku)
    PLAN = "plan"                 # Read-only, thorough (like Sonnet in plan mode)
    GENERAL = "general"           # Full tools, complex tasks


TERMINAL_AGENT_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass
class AgentDefinition:
    """Sub-agent definition.
    
    Inspired by Claude Code's agent definitions with custom system prompts,
    tool whitelists, and model selection.
    """
    type: AgentType
    name: str
    description: str
    system_prompt_template: str
    allowed_tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)
    model: str = "inherit"  # inherit from parent or specific model
    max_turns: int = 10
    is_read_only: bool = False
    
    @classmethod
    def explore_agent(cls) -> "AgentDefinition":
        """Create Explore agent - fast, read-only exploration."""
        return cls(
            type=AgentType.EXPLORE,
            name="Explore",
            description="Fast, read-only agent for codebase exploration and search",
            system_prompt_template=(
                "You are an exploration agent. Your job is to quickly search and "
                "understand codebases. You should be fast and focused on finding "
                "relevant files and understanding structure. "
                "You can only use read-only tools."
            ),
            allowed_tools=["read_file", "list_files", "grep_files"],
            is_read_only=True,
            max_turns=5,
        )
    
    @classmethod
    def plan_agent(cls) -> "AgentDefinition":
        """Create Plan agent - thorough context gathering."""
        return cls(
            type=AgentType.PLAN,
            name="Plan",
            description="Thorough agent for gathering context and understanding code",
            system_prompt_template=(
                "You are a planning agent. Your job is to thoroughly understand "
                "the codebase and task before acting. Read multiple files, trace "
                "code paths, and build a complete mental model. "
                "You can only use read-only tools."
            ),
            allowed_tools=["read_file", "list_files", "grep_files"],
            is_read_only=True,
            max_turns=8,
        )
    
    @classmethod
    def general_agent(cls) -> "AgentDefinition":
        """Create General-purpose agent - full capabilities."""
        return cls(
            type=AgentType.GENERAL,
            name="General",
            description="Full-featured agent for complex multi-step tasks",
            system_prompt_template=(
                "You are a general-purpose coding agent. You can read, write, "
                "and modify code. Follow best practices and explain your changes. "
                "Break complex tasks into smaller steps."
            ),
            is_read_only=False,
            max_turns=15,
        )


# ---------------------------------------------------------------------------
# Agent instance (runtime)
# ---------------------------------------------------------------------------

@dataclass
class AgentInstance:
    """Running agent instance."""
    id: str
    definition: AgentDefinition
    parent_session_id: str
    task_description: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    context_manager: ContextManager | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    status: str = "running"  # running, completed, failed, cancelled
    result: str | None = None
    result_summary: dict[str, Any] | None = None
    error: str | None = None
    turn_count: int = 0


# ---------------------------------------------------------------------------
# Sub-agent manager
# ---------------------------------------------------------------------------

class SubAgentManager:
    """Manages sub-agent lifecycle.
    
    Inspired by Claude Code's coordinator/ system.
    """
    
    def __init__(self, parent_session_id: str, app_state: Store[AppState] | None = None):
        self.parent_session_id = parent_session_id
        self.app_state = app_state
        self.agents: dict[str, AgentInstance] = {}
        self.definitions: dict[AgentType, AgentDefinition] = {
            AgentType.EXPLORE: AgentDefinition.explore_agent(),
            AgentType.PLAN: AgentDefinition.plan_agent(),
            AgentType.GENERAL: AgentDefinition.general_agent(),
        }

    def _build_result_summary(self, instance: AgentInstance) -> dict[str, Any]:
        """Build a structured result summary for parent orchestration."""
        token_usage = 0
        message_count = len(instance.messages)
        if instance.context_manager:
            stats = instance.context_manager.get_stats()
            token_usage = stats.total_tokens
            message_count = stats.messages_count

        return {
            "agent_id": instance.id,
            "agent_name": instance.definition.name,
            "agent_type": instance.definition.type.value,
            "status": instance.status,
            "task_description": instance.task_description,
            "turn_count": instance.turn_count,
            "final_output": instance.result or "",
            "error": instance.error,
            "message_count": message_count,
            "token_usage": token_usage,
        }

    def _refresh_result_summary(self, instance: AgentInstance) -> None:
        instance.result_summary = self._build_result_summary(instance)

    def _ensure_task_prompt(self, instance: AgentInstance) -> list[ChatMessage]:
        """Ensure the worker sees its task description as a user message."""
        messages = list(instance.messages)
        if not any(
            message.get("role") == "user"
            and message.get("content") == instance.task_description
            for message in messages
        ):
            messages.append({"role": "user", "content": instance.task_description})
        return messages

    def _filter_tools_for_agent(
        self,
        instance: AgentInstance,
        tools: ToolRegistry | list[ToolDefinition],
    ) -> ToolRegistry:
        """Restrict tools according to the agent definition."""
        registry = tools if isinstance(tools, ToolRegistry) else ToolRegistry(list(tools))
        available_tools = registry.list()
        allowed = set(instance.definition.allowed_tools)
        disallowed = set(instance.definition.disallowed_tools)

        if allowed:
            filtered = [tool for tool in available_tools if tool.name in allowed]
        else:
            filtered = list(available_tools)

        if disallowed:
            filtered = [tool for tool in filtered if tool.name not in disallowed]

        return ToolRegistry(
            filtered,
            skills=registry.get_skills(),
            mcp_servers=registry.get_mcp_servers(),
        )
    
    def get_definition(self, agent_type: AgentType) -> AgentDefinition:
        """Get agent definition."""
        return self.definitions[agent_type]
    
    def spawn_agent(
        self,
        agent_type: AgentType,
        task_description: str,
        model: str | None = None,
    ) -> AgentInstance:
        """Spawn a new sub-agent.
        
        Args:
            agent_type: Type of agent to spawn
            task_description: Task description for the agent
            model: Optional model override
        
        Returns:
            AgentInstance
        """
        definition = self.get_definition(agent_type)
        
        agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        
        # Create context manager for isolated context
        context_manager = ContextManager(
            model=model or definition.model,
        )
        
        # Build system message
        system_message = {
            "role": "system",
            "content": definition.system_prompt_template,
        }
        
        instance = AgentInstance(
            id=agent_id,
            definition=definition,
            parent_session_id=self.parent_session_id,
            task_description=task_description,
            messages=[system_message],
            context_manager=context_manager,
        )
        
        self.agents[agent_id] = instance
        return instance
    
    def add_message(self, agent_id: str, message: dict[str, Any]) -> bool:
        """Add message to agent conversation."""
        instance = self.agents.get(agent_id)
        if not instance or instance.status != "running":
            return False
        
        instance.messages.append(message)
        instance.turn_count += 1
        
        # Update context
        if instance.context_manager:
            instance.context_manager.add_message(message)
        
        return True

    def execute_agent(
        self,
        agent_id: str,
        *,
        model: ModelAdapter,
        tools: ToolRegistry | list[ToolDefinition],
        cwd: str,
        permissions: Any | None = None,
        max_steps: int | None = None,
        on_tool_start: Callable[[str, dict], None] | None = None,
        on_tool_result: Callable[[str, str, bool], None] | None = None,
        on_assistant_message: Callable[[str], None] | None = None,
        on_progress_message: Callable[[str], None] | None = None,
    ) -> AgentInstance:
        """Execute a spawned sub-agent through the shared agent loop."""
        instance = self.agents.get(agent_id)
        if instance is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        if instance.status != "running":
            raise ValueError(f"Agent {agent_id} is not runnable (status={instance.status}).")

        registry = self._filter_tools_for_agent(instance, tools)
        messages = self._ensure_task_prompt(instance)
        worker_permissions = (
            permissions.fork_for_subagent()
            if permissions is not None and hasattr(permissions, "fork_for_subagent")
            else permissions
        )

        try:
            result_messages = run_agent_turn(
                model=model,
                tools=registry,
                messages=messages,
                cwd=cwd,
                permissions=worker_permissions,
                max_steps=max_steps or instance.definition.max_turns,
                on_tool_start=on_tool_start,
                on_tool_result=on_tool_result,
                on_assistant_message=on_assistant_message,
                on_progress_message=on_progress_message,
                context_manager=instance.context_manager,
            )
        except Exception as error:
            instance.messages = messages
            self.fail_agent(agent_id, str(error))
            self._refresh_result_summary(instance)
            raise

        instance.messages = result_messages
        instance.turn_count += 1

        last_tool_result = next(
            (
                message
                for message in reversed(result_messages)
                if message.get("role") == "tool_result"
            ),
            None,
        )
        assistant_messages = [
            message
            for message in result_messages
            if message.get("role") == "assistant"
        ]
        final_output = assistant_messages[-1]["content"] if assistant_messages else ""
        if last_tool_result is not None and last_tool_result.get("isError"):
            failure_output = final_output or str(last_tool_result.get("content", "Agent execution failed."))
            self.fail_agent(agent_id, failure_output)
        else:
            self.complete_agent(agent_id, final_output)
        self._refresh_result_summary(instance)
        return instance
    
    def complete_agent(self, agent_id: str, result: str) -> bool:
        """Mark agent as completed with result."""
        instance = self.agents.get(agent_id)
        if not instance:
            return False
        
        instance.status = "completed"
        instance.result = result
        instance.completed_at = time.time()
        self._refresh_result_summary(instance)

        return True
    
    def fail_agent(self, agent_id: str, error: str) -> bool:
        """Mark agent as failed."""
        instance = self.agents.get(agent_id)
        if not instance:
            return False
        
        instance.status = "failed"
        instance.error = error
        instance.completed_at = time.time()
        self._refresh_result_summary(instance)

        return True
    
    def cancel_agent(self, agent_id: str, reason: str = "") -> bool:
        """Cancel a running agent."""
        instance = self.agents.get(agent_id)
        if not instance:
            return False
        
        instance.status = "cancelled"
        instance.error = reason or None
        instance.completed_at = time.time()
        self._refresh_result_summary(instance)

        return True

    def is_agent_terminal(self, agent_id: str) -> bool:
        """Return whether an agent has reached a final lifecycle state."""
        instance = self.agents.get(agent_id)
        return bool(instance and instance.status in TERMINAL_AGENT_STATUSES)
    
    def get_agent(self, agent_id: str) -> AgentInstance | None:
        """Get agent instance by ID."""
        return self.agents.get(agent_id)
    
    def get_active_agents(self) -> list[AgentInstance]:
        """Get all running agents."""
        return [
            agent for agent in self.agents.values()
            if agent.status == "running"
        ]

    def compile_merge_report(self) -> dict[str, Any]:
        """Build structured status for parent-side reporting and merge decisions."""
        total = len(self.agents)
        active = len(self.get_active_agents())
        completed = sum(agent.status == "completed" for agent in self.agents.values())
        failed = sum(agent.status == "failed" for agent in self.agents.values())
        cancelled = sum(agent.status == "cancelled" for agent in self.agents.values())

        return {
            "total": total,
            "active": active,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "terminal": completed + failed + cancelled,
            "ready_to_merge": total > 0 and active == 0 and failed == 0 and cancelled == 0,
            "has_failures": failed > 0,
            "has_cancellations": cancelled > 0,
        }
    
    def format_agent_status(self) -> str:
        """Format status report for all agents."""
        if not self.agents:
            return "No sub-agents spawned."
        
        lines = ["Sub-Agents Status", "=" * 50, ""]
        
        for agent_id, instance in self.agents.items():
            status_icon = {
                "running": "◐",
                "completed": "✓",
                "failed": "✗",
                "cancelled": "⊘",
            }.get(instance.status, "?")
            
            duration = time.time() - instance.started_at
            if instance.completed_at:
                duration = instance.completed_at - instance.started_at
            
            lines.extend([
                f"{status_icon} {instance.definition.name} ({agent_id})",
                f"  Task: {instance.task_description[:60]}",
                f"  Status: {instance.status}",
                f"  Turns: {instance.turn_count}/{instance.definition.max_turns}",
                f"  Duration: {duration:.0f}s",
            ])
            
            if instance.result:
                result_preview = instance.result[:100]
                lines.append(f"  Result: {result_preview}...")
            
            if instance.error:
                lines.append(f"  Error: {instance.error}")
            
            lines.append("")
        
        active = len(self.get_active_agents())
        lines.append(f"Active: {active} | Total: {len(self.agents)}")
        
        return "\n".join(lines)
    
    def compile_result_summary(self, agent_id: str) -> str:
        """Compile a summary of agent execution for parent context."""
        instance = self.agents.get(agent_id)
        if not instance:
            return f"Agent {agent_id} not found."

        summary = instance.result_summary or self._build_result_summary(instance)
        status_label = summary["status"]

        lines = [
            f"[Sub-agent {instance.definition.name} {status_label}]",
            f"  Turns: {summary['turn_count']}",
            f"  Status: {status_label}",
        ]

        if summary["final_output"]:
            lines.append(f"  Result: {summary['final_output'][:200]}")

        if summary["error"]:
            lines.append(f"  Error: {summary['error']}")

        lines.append(f"  Tokens used: {summary['token_usage']:,}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Integration helpers
# ---------------------------------------------------------------------------

def should_use_sub_agent(
    task_complexity: str,
    available_context: float,
) -> bool:
    """Decide if a task should be delegated to a sub-agent.
    
    Args:
        task_complexity: "simple", "moderate", "complex"
        available_context: Percentage of context window available
    
    Returns:
        True if should use sub-agent
    """
    # Use sub-agent for complex tasks or when context is limited
    if task_complexity == "complex":
        return True
    if task_complexity == "moderate" and available_context < 50:
        return True
    return False


def choose_agent_type(task_description: str) -> AgentType:
    """Choose appropriate agent type based on task.
    
    Args:
        task_description: User's task description
    
    Returns:
        Recommended AgentType
    """
    desc_lower = task_description.lower()
    
    # Exploration tasks
    exploration_keywords = ["explore", "search", "find", "understand", "explain"]
    if any(kw in desc_lower for kw in exploration_keywords):
        return AgentType.EXPLORE
    
    # Planning/context-gathering tasks
    planning_keywords = ["plan", "analyze", "review", "audit", "survey"]
    if any(kw in desc_lower for kw in planning_keywords):
        return AgentType.PLAN
    
    # Default to general-purpose
    return AgentType.GENERAL
