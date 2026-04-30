from __future__ import annotations


def render_banner(runtime: dict | None, cwd: str, permission_summary: list[str], counts: dict[str, int]) -> str:
    model = runtime["model"] if runtime else "unconfigured"
    max_output_tokens = runtime.get("maxOutputTokens") if runtime else None
    max_tokens_text = str(max_output_tokens) if max_output_tokens else "unknown"
    max_tool_steps = runtime.get("maxToolSteps") if runtime else None
    max_tool_steps_text = str(max_tool_steps) if max_tool_steps else "unknown"
    model_timeout = runtime.get("modelTimeoutSeconds") if runtime else None
    model_timeout_text = str(model_timeout) if model_timeout else "unknown"
    mem_count = counts.get("memoryCount", 0)
    lines = [
        "+" + "-" * 60 + "+",
        "|  Astrid - Your Terminal Coding Assistant                |",
        "+" + "-" * 60 + "+",
        f"|  Model: {model:<49}|",
        f"|  Max output tokens: {max_tokens_text:<37}|",
        f"|  Max tool steps: {max_tool_steps_text:<40}|",
        f"|  Model timeout seconds: {model_timeout_text:<32}|",
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


def render_quick_start() -> str:
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
