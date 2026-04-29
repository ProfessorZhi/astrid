# Astrid Agent Guidance

These instructions are the working ledger for agents improving Astrid.

## First Principles

- Start from the actual repository state. Read the code before comparing Astrid with Codex, Claude Code, or analysis sites.
- Treat Astrid as an existing coding-agent runtime, not as a blank prototype. It already has tools, permissions, sessions, memory, MCP, sub-agents, orchestration, and TUI behavior.
- Keep each PR to one verifiable improvement. Do not mix runtime rewrites, metadata cleanup, and unrelated refactors.
- Do not revert user or agent changes from other branches/worktrees. If a file is outside your assigned ownership, leave it alone.

## Current Optimization Ledger

1. **TUI runtime architecture**
   - Gap: the TUI has historically coupled transcript rendering, input, status, and terminal writes too tightly.
   - Direction: separate transcript viewport, input chrome, status/progress, and renderer ownership. Only the renderer should write terminal output.

2. **Permission and sandbox governance**
   - Gap: Astrid has permission approval and sub-agent permission forks, but not Codex-level platform sandbox policy.
   - Direction: define policy boundaries first, then add enforcement. Do not promise system sandbox parity before the threat model exists.

3. **Multi-agent runtime productization**
   - Gap: Astrid has `SubAgentManager` and orchestration, but the flow is still closer to a fixed first version than a configurable runtime.
   - Direction: improve worker lifecycle, failure/cancel handling, result merging, isolated context, and observable state before adding more roles.

4. **Mid-turn steering**
   - Gap: Astrid can queue the next turn while busy, but queueing is not the same as steering the current task.
   - Direction: distinguish `queued next turn` from `steer current turn`. Prefer interrupt-and-replan first; avoid complex mid-token injection until the simpler model is stable.

5. **Context and memory long-session stability**
   - Gap: Astrid has context compaction and memory modules, but long-session resume/compact behavior needs stronger guarantees.
   - Direction: preserve the active user task, recent tool results, and recovery state across compact/resume. Add tests before changing heuristics.

6. **Repository trustworthiness**
   - Gap: public-facing metadata must match the actual Python project. Stale Codex/OpenAI package metadata or inaccurate dependency claims hurt credibility.
   - Direction: keep README, `pyproject.toml`, `package.json`, tests, and benchmark claims aligned with the code.

## Terminology Rules

- Do not call Astrid's extension surfaces a "plugin system" unless there is a real plugin manifest/loader/package flow. The current practical extension surfaces are skills, MCP, and hooks.
- Do not call busy input queueing "steering". Steering means changing or interrupting the current in-flight task.
- Do not describe Astrid as single-agent only. It has sub-agents and orchestration; the gap is product-grade runtime behavior.
- Do not describe Astrid as zero-dependency while `pyproject.toml` lists runtime dependencies.

## PR Split Rules

- PR 0: finish the current TUI performance branch before further `tty_app.py` work.
- PR 1: documentation and repository credibility only (`AGENTS.md`, README, metadata).
- PR 2: steering v1. Own input/queue behavior and tests; avoid unrelated TUI rendering changes.
- PR 3: multi-agent runtime. Own `orchestration.py`, `sub_agents.py`, and related tests.
- PR 4: context/memory stability. Own context, memory, session code, and related tests.
- PR 5: permission/sandbox design. Start with threat model and policy tests before platform sandbox work.
- PR 6: TUI runtime split. Start only after PR 0 is merged or rebased.

## Verification Defaults

- For TUI changes: `python -m pytest tests/test_screen.py tests/test_tty_app.py tests/test_tui.py -q`
- For multi-agent changes: `python -m pytest tests/test_orchestration.py tests/test_sub_agents.py -q`
- For context/memory/session changes: run the narrow affected tests plus `python -m pytest tests -q -k "context or memory or session"`
- For docs/metadata changes: run `python -m pytest tests/test_cli_commands.py tests/test_screen.py -q`
