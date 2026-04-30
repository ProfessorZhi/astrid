from __future__ import annotations

from pathlib import Path

from astrid.core.project_instructions import format_project_instructions, load_project_instructions


def _engineering_governance_rules() -> str:
    r"""Return engineering governance rules as system prompt section.
    
    These rules are mandatory and apply to all code generation activities.
    Based on: D:\Desktop\engineering-governance
    """
    return """## Engineering Governance Rules (MANDATORY)

These rules apply to ALL code you write. No exceptions.

### Iron Laws
1. **Theory first**: Read theory before any engineering activity
2. **Requirements first**: No code without design, no design without requirements
3. **1:1 binding**: Requirements and knowledge always appear in pairs
4. **Design-driven**: Code implements design, not independent creation
5. **Audit loop**: Execute audit after each phase, fail → fix → re-audit
6. **Single sink**: business/src/ must have exactly ONE sink file
7. **One-way dependencies**: All dependency flow is unidirectional, zero cycles
8. **No skipping**: Each phase's exit signals must be met before next phase

### Package Structure (Six Areas)
Every package must have:
- `port/port_entry/` — Entry points (can import anything)
- `wrap/src/` — External library adapters (import: port_entry, wrap/config, wrap/src)
- `business/src/` — Business logic (import: wrap sinks, business/config, business/src)
- `test/src/` — Tests (import: business/src, test/config, test/src)
- `business/config/` — Business config (zero dependencies)
- `wrap/config/` — Adapter config (zero dependencies)
- `test/config/` — Test config (zero dependencies)

### Dependency Direction Rules
- `business/src/` → `wrap/src/` sinks → `port/port_entry/` → `vendor/`
- `business/src/` CANNOT import vendor/, external libs directly
- `wrap/src/` CANNOT import business/src/
- Config imports always come LAST in import statements
- Cross-package: port_exit → port_entry (same language to same language)

### Sink Rule
- `business/src/`: EXACTLY ONE sink (file not imported by other business/src/ files)
- `wrap/src/`: Can have multiple sinks (each must be used by business/src/)
- `test/src/`: Can have multiple sinks (all must be used by port_exit)
- Multiple sinks in business/src/ = MUST split package

### Documentation System
- Requirements → Knowledge → Design → Code (strict one-way flow)
- Each requirement scenario has exactly one matching knowledge file (1:1 path mirror)
- Each design file cites: satisfied requirements, depended knowledge
- Code file paths must be isomorphic to design file paths

### Import Sorting Example
```python
# Non-config imports first
from package.wrap/src/adapter import Adapter
from package.business/src/service import Service

# Config imports LAST
from package.business/config import settings
```

### Audit Checklist (Execute After Code Changes)
Audit 0: Knowledge ↔ Requirements 1:1
Audit 1: Design ← Requirements + Knowledge coverage
Audit 2: Code ← Design isomorphism + Dependency compliance
Audit 3: business/src/ single sink + Package DAG

### Boundary Packaging (Legacy Code)
- When introducing legacy code: only through port_entry → wrap/src/ ([LEGACY] tag)
- Each [LEGACY] file must have expected cleanup date
- Legacy code can reference governance area via port_exit directly

### Repository Rules
- ZERO compositional dependencies between repositories
- Cross-repository needs: copy to local vendor/
- Vendor only imported by port_entry/"""


def build_system_prompt(
    cwd: str,
    permission_summary: list[str] | None = None,
    extras: dict | None = None,
) -> str:
    cwd_path = Path(cwd)
    permission_summary = permission_summary or []
    extras = extras or {}
    project_instructions = load_project_instructions(cwd_path)

    parts = [
        "You are Astrid, a terminal coding assistant.",
        "Default behavior: inspect the repository, use tools, make code changes when appropriate, and explain results clearly.",
        "Prefer reading files, searching code, editing files, and running verification commands over giving purely theoretical advice.",
        f"Current cwd: {cwd}",
        "You can inspect or modify paths outside the current cwd when the user asks, but tool permissions may pause for approval first.",
        "When making code changes, keep them minimal, practical, and working-oriented.",
        "For coding tasks, follow the verification loop: inspect relevant files and tests first, make the smallest useful change, run the focused test or command, and continue fixing if the command fails. Do not report completion while a relevant test is still failing.",
        "If you reach a tool-step or time limit, summarize the last failing command, touched files, and the exact next verification step instead of implying the task is complete.",
        "If the user clearly asked you to build, modify, optimize, or generate something, do the work instead of stopping at a plan.",
        "If you need user clarification, call the ask_user tool with one concise question and wait for the user reply. Do not ask clarifying questions as plain assistant text.",
        "Do not choose subjective preferences such as colors, visual style, copy tone, or naming unless the user explicitly told you to decide yourself.",
        "When using read_file, pay attention to the header fields. If it says TRUNCATED: yes, continue reading with a larger offset before concluding that the file itself is cut off.",
        "If the user names a skill or clearly asks for a workflow that matches a listed skill, call load_skill before following it.",
        "Structured response protocol:",
        "- When you are still working and will continue with more tool calls, start your text with <progress>.",
        "- Only when the task is actually complete and you are ready to hand control back, start your text with <final>.",
        "- Use ask_user when clarification is required; that tool ends the turn and waits for user input.",
        "- Do not stop after a progress update. After a <progress> message, continue the task in the next step.",
        "- Plain assistant text without <progress> is treated as a completed assistant message for this turn.",
    ]

    # Engineering governance rules (MANDATORY)
    parts.append(_engineering_governance_rules())

    if permission_summary:
        parts.append("Permission context:\n" + "\n".join(permission_summary))

    skills = extras.get("skills", [])
    if skills:
        parts.append(
            "Available skills:\n"
            + "\n".join(f"- {skill['name']}: {skill['description']}" for skill in skills)
            + "\n\n"
            + "SKILL USAGE GUIDE:\n"
            + "- When user asks for creative brainstorming, use 'brainstorming' skill\n"
            + "- When writing implementation plans, use 'writing-plans' skill\n"
            + "- When debugging systematically, use 'systematic-debugging' skill\n"
            + "- When doing TDD, use 'test-driven-development' skill\n"
            + "- When reviewing code in Chinese, use 'chinese-code-review' skill\n"
            + "- When user asks about workflows, check 'using-superpowers' skill first\n"
            + "- For complex multi-step tasks, consider 'subagent-driven-development'\n"
            + "- Before completing, ALWAYS use 'verification-before-completion'"
        )
    else:
        parts.append(
            "Available skills:\n"
            + "- none discovered\n"
            + "Tip: Install skills via `npx superpowers-zh` in your project directory"
        )

    mcp_servers = extras.get("mcpServers", [])
    if mcp_servers:
        parts.append(
            "Configured MCP servers:\n"
            + "\n".join(
                "- "
                + server["name"]
                + f": {server['status']}, tools={server['toolCount']}"
                + (f", resources={server['resourceCount']}" if server.get("resourceCount") is not None else "")
                + (f", prompts={server['promptCount']}" if server.get("promptCount") is not None else "")
                + (f", protocol={server['protocol']}" if server.get("protocol") else "")
                + (f" ({server['error']})" if server.get("error") else "")
                for server in mcp_servers
            )
        )
        if any(server.get("status") == "connected" for server in mcp_servers):
            parts.append(
                "Connected MCP tools are already exposed in the tool list with names prefixed like mcp__server__tool. Use list_mcp_resources/read_mcp_resource and list_mcp_prompts/get_mcp_prompt when a server exposes those capabilities."
            )
        sequential_servers = [
            server
            for server in mcp_servers
            if "sequential" in server.get("name", "").lower()
            or "branch-thinking" in server.get("name", "").lower()
            or "think" in server.get("name", "").lower()
        ]
        if any(server.get("status") == "connected" for server in sequential_servers):
            parts.append(
                "\nSEQUENTIAL THINKING MCP SERVER IS CONNECTED!\n"
                "When to use sequential_thinking tool:\n"
                "- Breaking down complex implementation problems\n"
                "- Multi-step debugging or investigation\n"
                "- Architectural decisions requiring structured analysis\n"
                "- Migration or refactoring planning\n"
                "- Any situation requiring step-by-step reasoning\n\n"
                "Usage: Call 'sequential_thinking' with structured thoughts before complex tool sequences"
            )

    # Add bootstrap system capabilities information
    parts.append("## Bootstrap (Self-Bootstrapping) System Capabilities")
    parts.append("""
The system has self-bootstrapping capabilities that enable continuous improvement:

### Core Self-Bootstrapping Features:
1. **Performance Analysis**: Automatically analyzes skill execution performance and identifies bottlenecks
2. **Skill Generation**: Creates new skills from frequently observed patterns and sequences
3. **Knowledge Expansion**: Extracts knowledge from interactions and integrates it into memory
4. **Meta-Learning**: Learns how to learn better through strategy adaptation
5. **Dependency Optimization**: Analyzes and optimizes skill dependency relationships

### Available Self-Improvement Mechanisms:
- **Performance Optimizer**: Monitors execution metrics, identifies slowdowns, suggests improvements
- **Pattern Recognizer**: Detects repetitive workflows for skill automation
- **Knowledge Extractor**: Mines valuable information from user interactions
- **Terminology Learner**: Standardizes and maintains consistent terminology
- **Workflow Optimizer**: Improves execution sequences based on historical data

### How to Leverage Self-Bootstrapping:
1. The system automatically runs bootstrap cycles periodically
2. Performance issues trigger optimization suggestions
3. Frequent patterns are converted into reusable skills
4. New knowledge is integrated into the memory system
5. Learning strategies adapt based on effectiveness

### Integration Points:
- Memory system integration for persistent learning
- Skill engine integration for performance monitoring
- Terminology governance for consistency maintenance
- Context management for adaptive behavior

The system continuously improves itself based on usage patterns, making it more effective over time.
""")

    if project_instructions:
        parts.append(format_project_instructions(project_instructions))

    # 注入高级记忆上下文
    advanced_memory_context = extras.get("advanced_memory_context", "")
    if advanced_memory_context:
        parts.append(f"## Active Memory Context\n\n{advanced_memory_context}")

    memory_context = extras.get("memory_context", "")
    if memory_context:
        parts.append(
            "## Project Memory & Context\n\n"
            "The following information has been accumulated from Astrid memory:\n\n"
            f"{memory_context}"
        )

    return "\n\n".join(parts)
