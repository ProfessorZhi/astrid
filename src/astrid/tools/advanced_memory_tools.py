"""Advanced memory tools for Astrid.

Exposes the advanced memory system capabilities as tools that the Agent can invoke.
"""
from __future__ import annotations

import json
from astrid.core.tooling import ToolDefinition, ToolResult

# 全局引用，由 main.py 注入
_advanced_memory_mgr = None
_skill_engine = None
_bootstrap_system = None


def initialize(advanced_memory_mgr, skill_engine=None, bootstrap_system=None):
    """注入高级记忆系统实例（由 main.py 调用）"""
    global _advanced_memory_mgr, _skill_engine, _bootstrap_system
    _advanced_memory_mgr = advanced_memory_mgr
    _skill_engine = skill_engine
    _bootstrap_system = bootstrap_system


# ---------------------------------------------------------------------------
# 记忆搜索工具
# ---------------------------------------------------------------------------

def _memory_search_validate(input_data: dict) -> dict:
    query = input_data.get("query", "")
    if not query:
        raise ValueError("query is required")
    return {
        "query": query,
        "scope": input_data.get("scope"),
        "limit": min(input_data.get("limit", 10), 50),
    }


def _memory_search_run(input_data: dict, context) -> ToolResult:
    if not _advanced_memory_mgr:
        return ToolResult(ok=False, output="Advanced memory system not initialized")

    from astrid.advanced_memory import MemoryScope
    query = input_data["query"]
    scope = None
    if input_data.get("scope"):
        try:
            scope = MemoryScope(input_data["scope"])
        except ValueError:
            return ToolResult(ok=False, output=f"Invalid scope: {input_data['scope']}")

    try:
        results = _advanced_memory_mgr.search_memories(
            query=query,
            scope=scope,
            limit=input_data.get("limit", 10),
        )
        if not results:
            return ToolResult(ok=True, output="No memories found matching the query.")

        output_lines = [f"Found {len(results)} memory entries:\n"]
        for entry in results:
            output_lines.append(
                f"- [{entry.scope.value}/{entry.type.value}] {entry.content[:200]}"
            )
            if entry.tags:
                output_lines.append(f"  Tags: {', '.join(entry.tags[:5])}")
        return ToolResult(ok=True, output="\n".join(output_lines))
    except Exception as e:
        return ToolResult(ok=False, output=f"Memory search error: {e}")


memory_search_tool = ToolDefinition(
    name="memory_search",
    description="Search the advanced memory system for relevant information. "
                "Use this to find past decisions, learned patterns, or stored knowledge.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "scope": {
                "type": "string",
                "description": "Memory scope: session, local, project, user, system",
            },
            "limit": {"type": "integer", "description": "Max results (default 10)"},
        },
        "required": ["query"],
    },
    validator=_memory_search_validate,
    run=_memory_search_run,
)


# ---------------------------------------------------------------------------
# 记忆存储工具
# ---------------------------------------------------------------------------

def _memory_store_validate(input_data: dict) -> dict:
    content = input_data.get("content", "")
    if not content:
        raise ValueError("content is required")
    return {
        "content": content,
        "scope": input_data.get("scope", "project"),
        "memory_type": input_data.get("memory_type", "decision"),
        "tags": input_data.get("tags", []),
    }


def _memory_store_run(input_data: dict, context) -> ToolResult:
    if not _advanced_memory_mgr:
        return ToolResult(ok=False, output="Advanced memory system not initialized")

    from astrid.advanced_memory import MemoryScope, MemoryType, MemoryPriority

    try:
        scope = MemoryScope(input_data["scope"])
        memory_type = MemoryType(input_data["memory_type"])
    except ValueError as e:
        return ToolResult(ok=False, output=f"Invalid parameter: {e}")

    try:
        entry_id = _advanced_memory_mgr.store_memory(
            content=input_data["content"],
            scope=scope,
            memory_type=memory_type,
            priority=MemoryPriority.MEDIUM,
            tags=input_data.get("tags", []),
            source="agent_tool",
        )
        return ToolResult(ok=True, output=f"Memory stored successfully. ID: {entry_id}")
    except Exception as e:
        return ToolResult(ok=False, output=f"Memory store error: {e}")


memory_store_tool = ToolDefinition(
    name="memory_store",
    description="Store information in the advanced memory system for future reference. "
                "Use this to save important decisions, learned patterns, or key insights.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Content to store"},
            "scope": {
                "type": "string",
                "description": "Memory scope: session, local, project, user, system (default: project)",
            },
            "memory_type": {
                "type": "string",
                "description": "Type: decision, pattern, context, collaboration, documentation, workflow (default: decision)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for categorization",
            },
        },
        "required": ["content"],
    },
    validator=_memory_store_validate,
    run=_memory_store_run,
)


# ---------------------------------------------------------------------------
# 技能执行工具
# ---------------------------------------------------------------------------

def _skill_execute_validate(input_data: dict) -> dict:
    skill_name = input_data.get("skill_name", "")
    if not skill_name:
        raise ValueError("skill_name is required")
    return {
        "skill_name": skill_name,
        "params": input_data.get("params", {}),
    }


def _skill_execute_run(input_data: dict, context) -> ToolResult:
    if not _skill_engine:
        return ToolResult(ok=False, output="Skill engine not initialized")

    try:
        result = _skill_engine.execute_skill(
            skill_name=input_data["skill_name"],
            parameters=input_data.get("params", {}),
        )
        output = f"Skill: {result.skill_name}\n"
        output += f"Status: {result.status.value}\n"
        output += f"Result type: {result.result_type.value}\n"
        output += f"Execution time: {result.execution_time:.3f}s\n"
        if result.output:
            output += f"Output: {str(result.output)[:1000]}\n"
        if result.error:
            output += f"Error: {result.error}\n"
        return ToolResult(ok=result.is_success(), output=output)
    except Exception as e:
        return ToolResult(ok=False, output=f"Skill execution error: {e}")


skill_execute_tool = ToolDefinition(
    name="skill_execute",
    description="Execute a registered skill from the skill engine. "
                "Use this to leverage learned workflows and patterns.",
    input_schema={
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Name of the skill to execute"},
            "params": {
                "type": "object",
                "description": "Parameters for skill execution",
            },
        },
        "required": ["skill_name"],
    },
    validator=_skill_execute_validate,
    run=_skill_execute_run,
)


# ---------------------------------------------------------------------------
# 技能列表工具
# ---------------------------------------------------------------------------

def _skill_list_validate(input_data: dict) -> dict:
    return {"category": input_data.get("category")}


def _skill_list_run(input_data: dict, context) -> ToolResult:
    if not _advanced_memory_mgr:
        return ToolResult(ok=False, output="Advanced memory system not initialized")

    try:
        skills = _advanced_memory_mgr.list_skills()
        if not skills:
            return ToolResult(ok=True, output="No skills registered.")

        category = input_data.get("category")
        if category:
            skills = [s for s in skills if s.category == category]

        output_lines = [f"Registered skills ({len(skills)}):\n"]
        for skill in skills:
            output_lines.append(f"- {skill.name}: {skill.description[:100]}")
            if skill.dependencies:
                output_lines.append(f"  Dependencies: {', '.join(skill.dependencies)}")

        return ToolResult(ok=True, output="\n".join(output_lines))
    except Exception as e:
        return ToolResult(ok=False, output=f"Skill list error: {e}")


skill_list_tool = ToolDefinition(
    name="skill_list",
    description="List all registered skills in the skill engine. "
                "Use this to discover available skills before executing them.",
    input_schema={
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Filter by skill category"},
        },
    },
    validator=_skill_list_validate,
    run=_skill_list_run,
)


# ---------------------------------------------------------------------------
# 自举状态工具
# ---------------------------------------------------------------------------

def _bootstrap_status_validate(input_data: dict) -> dict:
    return {}


def _bootstrap_status_run(input_data: dict, context) -> ToolResult:
    if not _bootstrap_system:
        return ToolResult(ok=False, output="Bootstrap system not initialized")

    try:
        records = _bootstrap_system.bootstrap_records
        output_lines = ["Bootstrap System Status:\n"]
        output_lines.append(f"  Total bootstrap cycles: {len(records)}")

        if records:
            last = records[-1]
            # BootstrapRecord is a dataclass, access attributes directly
            status_str = last.phase.value if hasattr(last, 'phase') else 'unknown'
            success_str = "success" if last.success else "failed"
            output_lines.append(f"  Last cycle phase: {status_str}")
            output_lines.append(f"  Last cycle result: {success_str}")

        # 获取统计
        stats = _advanced_memory_mgr.get_statistics() if _advanced_memory_mgr else {}
        output_lines.append(f"\n  Memory entries: {stats.get('total_memories', 'N/A')}")
        output_lines.append(f"  Registered skills: {stats.get('total_skills', 'N/A')}")
        output_lines.append(f"  Terminology entries: {stats.get('total_terminologies', 'N/A')}")

        return ToolResult(ok=True, output="\n".join(output_lines))
    except Exception as e:
        return ToolResult(ok=False, output=f"Bootstrap status error: {e}")


bootstrap_status_tool = ToolDefinition(
    name="bootstrap_status",
    description="Get the current status of the self-bootstrapping system. "
                "Use this to check system improvement history and statistics.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    validator=_bootstrap_status_validate,
    run=_bootstrap_status_run,
)
