# Astrid Agent Guidance

These instructions are the working ledger for agents improving Astrid.

## First Principles

- Start from the actual repository state. Read the code before comparing Astrid with Codex, Claude Code, or analysis sites.
- Treat Astrid as an existing coding-agent runtime, not as a blank prototype. It already has tools, permissions, sessions, memory, MCP, sub-agents, orchestration, and TUI behavior.
- Keep each PR to one verifiable improvement. Do not mix runtime rewrites, metadata cleanup, and unrelated refactors.
- Do not revert user or agent changes from other branches/worktrees. If a file is outside your assigned ownership, leave it alone.

## Current State Ledger

Astrid already has the first-pass productization work for the original six gaps:

1. **TUI performance and shell UX**
   - Implemented: cached/windowed transcript rendering, line-diff writer, shell-mode native scrollback defaults, recent-history cleanup, and short-window welcome rendering fixes.
   - Remaining: continue splitting `tty_app.py` into renderer/input/status/transcript viewport modules only when a scoped PR can preserve pinned-bottom behavior.

2. **Permission and sandbox governance**
   - Implemented: policy snapshot/tests and clearer permission boundaries.
   - Remaining: Astrid is still policy-only, not an OS sandbox. Do not claim Codex-level sandbox parity until there is real process/filesystem isolation.

3. **Multi-agent runtime**
   - Implemented: lifecycle summaries, worker failure/cancel/reporting states, and clearer orchestration tests.
   - Remaining: product-grade scheduling, configurable worker roles, and richer result synthesis need separate verified PRs.

4. **Mid-turn steering**
   - Implemented: `queued next turn` and `steer current turn` are distinct in the first-pass queue model.
   - Remaining: current steering is interrupt-and-replan style. Do not describe it as mid-token injection.

5. **Context and memory stability**
   - Implemented: compaction anchor tests and active-task preservation checks.
   - Remaining: long live sessions still need real resume/compact stress tests with transcripts.

6. **Repository trustworthiness**
   - Implemented: agent guidance, metadata cleanup, local artifact ignore rules, CLI smoke coverage, and branch/worktree cleanup.
   - Remaining: keep claims tied to reproducible commands and avoid stale benchmark numbers.

## Terminology Rules

- Do not call Astrid's extension surfaces a "plugin system" unless there is a real plugin manifest/loader/package flow. The current practical extension surfaces are skills, MCP, and hooks.
- Do not call busy input queueing "steering". Steering means changing or interrupting the current in-flight task.
- Do not describe Astrid as single-agent only. It has sub-agents and orchestration; the gap is product-grade runtime behavior.
- Do not describe Astrid as zero-dependency while `pyproject.toml` lists runtime dependencies.

## Local Coding Agent Evaluation

- Local-only verification artifacts live under `verification/`, which is ignored by Git.
- Use this layout for coding-agent comparisons:
  - `verification/astrid/<date-and-run-name>/`
  - `verification/codex/<date-and-run-name>/`
  - `verification/claudecode/<date-and-run-name>/`
- Each run folder should keep the isolated `workspace/`, harness script, captured transcripts, and pass/fail notes together.
- Current Astrid coding eval: `verification/astrid/2026-04-29-real-model-coding-eval/`.
- When testing Astrid with piped stdin, remember it is non-TTY: write/edit approvals will fail unless the target files are temporarily pre-authorized in `~/.astrid/permissions.json` and restored afterward.
- Judge coding ability by external checks, not assistant text. Run pytest or explicit scripts against the generated workspace and record the exact pass/fail output.

## Verification Defaults

- TUI changes: `python -m pytest tests/test_screen.py tests/test_tty_app.py tests/test_tui.py -q`
- Multi-agent changes: `python -m pytest tests/test_orchestration.py tests/test_sub_agents.py -q`
- Context/memory/session changes: run the narrow affected tests plus `python -m pytest tests -q -k "context or memory or session"`
- Docs/metadata changes: `python -m pytest tests/test_cli_commands.py tests/test_screen.py -q`
- Real coding-agent evals: create a run under `verification/<agent>/...`, capture transcripts, then run the workspace acceptance tests outside the agent.
