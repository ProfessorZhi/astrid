# Astrid Dynamic Multi-Agent TUI Design

**Date:** 2026-04-17
**Status:** Draft for review
**Scope:** Windows-first, first shippable demo of dynamic multi-agent orchestration with Claude-Code-like lightweight TUI

---

## 1. Problem

Astrid already has strong single-agent foundations:

- agent loop
- tool calling
- session persistence
- permissions
- TUI basics
- MCP integration

What is still weak is the part most likely to be challenged in demos, interviews, and resume review:

- true multi-agent runtime behavior
- visible role separation
- reviewer-based validation loop
- dynamic TUI that shows work unfolding in a lightweight, intentional way

The goal of this design is to turn Astrid from a "single coding agent with sub-agent scaffolding" into a demonstrable orchestrated system.

---

## 2. Product Goal

Build a first version of Astrid that:

- feels visually closer to Claude Code
- supports dynamic sub-agent creation like Codex-style orchestration
- keeps the main experience lightweight rather than dashboard-heavy
- makes each spawned worker visible, named, scoped, and color-identifiable
- uses a real orchestration loop instead of inert sub-agent objects

This is a **Windows-first** release. Cross-platform concerns are explicitly out of scope for this phase.

---

## 3. Non-Goals

The first version will not include:

- user-driven manual creation of runtime workers
- unrestricted peer-to-peer swarm behavior
- permanent long-lived worker agents
- a heavy sidebar/dashboard layout
- Linux/WSL parity
- generic multi-agent framework abstractions for every future pattern

---

## 4. Core Product Decisions

### 4.1 Runtime Model

Astrid v1 will use:

- **Supervisor-style orchestration**
- **dynamic worker creation**
- **independent reviewer validation**
- **loop/state-machine runtime**

The user gives a goal. The main agent decides whether decomposition is worth it. If yes, it spawns one or more temporary workers with clear scope boundaries, collects reports, routes through review, and merges or retries as needed.

### 4.2 Worker Creation

Workers are **created automatically by the main agent**, not manually by the user.

The user may express high-level intent such as:

- parallelize this
- add a reviewer
- split search and implementation

But the system owns:

- whether to spawn
- how many workers to create
- each worker's role
- each worker's scope
- each worker's name
- each worker's tool boundaries
- when each worker is archived

This keeps the workspace and division of labor coherent.

### 4.3 Naming

Workers are system-named by default using high-quality English names.

Example format:

- `Atlas  context scout     mapping auth and routing flow`
- `Forge  code worker       patching scheduler and renderer state`
- `Meridian  review agent   validating regression risk and missing tests`

Each runtime worker has:

- `name`
- `role`
- `one-line mission`
- `status`
- `color`
- `scope`

### 4.4 TUI Direction

The TUI direction is:

- **Structure like option B**
- **Visual lightness closer to option A**

This means:

- not a thick dashboard
- not large fixed panels
- not overly dense sidebars
- not full-width color blocks

Instead the TUI should feel like a living narrative surface with a visible agent tree.

---

## 5. Architecture

### 5.1 Main Components

#### Orchestrator

Responsible for:

- receiving user intent
- deciding whether to decompose
- spawning workers
- collecting worker reports
- deciding whether review is required
- merging accepted results
- retrying or respawning on rejection
- producing the final narrative output

#### WorkerAgent

A temporary runtime agent created for a scoped task.

Each worker:

- has isolated context
- has explicit scope
- has limited tool access depending on role
- does not own overall flow control
- reports structured results back to the orchestrator

#### ReviewerAgent

A distinct validation role that does not perform the main implementation task.

It checks:

- patch consistency
- regression risk
- missing tests
- scope drift
- whether the output actually satisfies the delegated mission

#### AgentGraph

A runtime structure tracking:

- parent-child relationships
- active and archived workers
- worker metadata
- worker states
- recent worker events
- merge/review transitions

This graph is the source of truth for the TUI.

---

## 6. Runtime Loop / State Machine

The first version will explicitly model runtime state rather than relying on prompt-only behavior.

### 6.1 Top-Level Task States

- `idle`
- `planning`
- `spawning`
- `running`
- `collecting`
- `reviewing`
- `merging`
- `done`
- `failed`

### 6.2 Worker States

- `queued`
- `running`
- `blocked`
- `reporting`
- `archived`
- `failed`
- `cancelled`

### 6.3 Canonical Loop

The first version will use this lifecycle:

`plan -> spawn -> run -> report -> review -> merge -> archive`

This is the minimal closed loop needed to make Astrid's multi-agent story real and visible.

### 6.4 Spawn Policy

Spawning is not default. The orchestrator should spawn only when useful.

Examples:

- the task has separable subproblems
- search and implementation can proceed independently
- review should be isolated from implementation
- context pressure suggests offloading a subtask

Simple tasks should stay single-agent.

---

## 7. TUI Design

### 7.1 Narrative Surface

The top-level interface should preserve a Claude-Code-like feeling of light, flowing progress.

Examples:

- `Unravelling task graph...`
- `Spawning workers for search, implementation, and review...`
- `Collecting reports from Atlas and Forge...`
- `Meridian is validating patch integrity...`

This line should be short and singular. It represents the system's current main story.

### 7.2 Agent Tree

The central visual element is a runtime agent tree, not a dashboard grid.

Each row should show:

- worker name
- role
- one-line mission
- status

Example:

- `Atlas     context scout    mapping auth and routing flow       running`
- `Forge     code worker      editing worker lifecycle hooks      running`
- `Meridian  review agent     validating patch scope and tests    queued`

### 7.3 Event Stream

Each active worker may show a small number of recent events:

- latest tool action
- latest progress phrase
- latest report milestone

This event stream should remain short-lived and compress into summaries over time.

### 7.4 Color System

Each worker has one accent color for identity.

Colors apply to:

- name
- tree marker / line
- small status indicator

Colors should not wash the entire row.

Role-based color families:

- context / exploration: teal / blue-green
- implementation: amber / orange / warm red
- review: cool blue / steel / silver-blue
- orchestration support: muted violet / graphite blue

### 7.5 Density Rules

The interface must remain light:

- active workers are prioritized
- archived workers collapse into compact summaries
- too many simultaneous workers are folded into `+N archived workers`
- logs are compressed aggressively

---

## 8. Interaction Rules

### 8.1 What Users Control

Users may influence orchestration at a high level:

- ask for parallel help
- ask for review
- prioritize a worker
- stop a worker
- retry a worker
- focus the view on a worker

### 8.2 What Users Do Not Control Directly in v1

Users do not directly:

- create runtime workers manually
- rename runtime workers
- rewrite worker prompts
- alter worker tool permissions in-session
- hand-wire task routing between workers

This avoids coordination chaos in the first version.

### 8.3 Review Trigger Policy

Reviewer involvement is required when:

- code changes were produced
- multiple worker outputs must be merged
- the change touches risky areas
- the user explicitly asks for review

The implementer does not self-certify completion.

---

## 9. Phase Plan

### Phase 1: First Shippable Demo

Build:

- orchestrator-driven dynamic worker creation
- real worker execution loop
- reviewer-based validation
- runtime state machine
- lightweight narrative TUI
- colored, named agent tree
- archival/collapse behavior

This phase is the main target of the current project.

### Phase 2: Task Board

After the state-machine runtime is stable, add:

- task board / shared task queue
- more natural task distribution
- worker pickup and completion semantics
- richer prioritization and scheduling

This is explicitly a later optimization target, not part of v1.

### Phase 3: Limited Swarm / Handoff

After the task board is stable, add:

- controlled agent-to-agent handoff
- limited peer delegation within approved boundaries
- constrained swarm behavior

This phase must remain bounded and should not allow uncontrolled free-form delegation.

---

## 10. Testing Strategy

The first version needs test coverage for:

- worker spawning rules
- runtime state transitions
- reviewer-trigger policy
- worker lifecycle transitions
- agent graph updates
- archived worker summarization
- TUI rendering of named/colorized workers
- merge/retry behavior after review rejection

Tests should validate behavior, not only string snapshots.

---

## 11. Why This Design

This design is chosen because it solves the real weakness in Astrid's current story:

- it turns multi-agent from resume language into runtime behavior
- it keeps the TUI light instead of becoming a monitoring console
- it borrows Claude Code's narrative feel without becoming a visual copy
- it borrows Codex's dynamic worker spirit without letting runtime coordination become chaotic

In short:

Astrid v1 should feel like a composed orchestrated coding system, not a single-agent shell with decorative sub-agent labels.

