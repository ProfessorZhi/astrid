# Astrid 动态多 Agent TUI 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 为 Astrid 落地第一版可演示的动态多 Agent 编排闭环，包含真实 worker 执行、reviewer 复核、运行时状态机，以及 Claude-Code-like 轻量动态 TUI。

**架构：** 以现有 `run_agent_turn()` 为执行内核，在其外层新增 orchestrator runtime 和 agent graph 状态层；保留现有 TTY/TUI 主干，在 transcript 渲染前插入 narrative line 与 agent tree，并让多 agent 生命周期成为一等状态而不是仅有静态对象。

**技术栈：** Python 3.11+、现有 `ToolRegistry` / `ContextManager` / `tty_app.py`、ANSI TUI、pytest

---

## 文件结构

- 新建：`astrid/orchestration.py` - 定义 orchestrator runtime、任务状态机、worker 元数据、事件模型
- 新建：`tests/test_orchestration.py` - 覆盖状态流转、spawn 策略、review 触发、归档逻辑
- 修改：`astrid/sub_agents.py` - 从“惰性对象管理器”升级为可执行 worker manager，补齐 worker 运行入口与结构化结果
- 修改：`astrid/tty_app.py` - 接入 orchestrator 状态、后台 worker 执行、agent tree 与 narrative line 状态更新
- 修改：`astrid/tui/transcript.py` - 渲染 narrative line、agent tree、worker 事件摘要
- 修改：`astrid/tui/chrome.py` - 增加轻量状态条与 agent accent color 支持
- 修改：`astrid/tui/types.py` - 如有需要扩展 transcript entry/agent tree 渲染数据结构
- 修改：`tests/test_tui.py` - 验证 agent tree、narrative line、颜色/摘要显示
- 修改：`tests/test_agent_loop.py` - 补 worker 报告与 reviewer 回路相关回调集成测试

---

### 任务 1：建立多 Agent 运行时状态机

**文件：**
- 新建：`astrid/orchestration.py`
- 测试：`tests/test_orchestration.py`

- [ ] **步骤 1：先写运行时状态与事件的失败测试**

```python
from astrid.orchestration import (
    OrchestratorState,
    TaskRuntimeState,
    WorkerRuntimeState,
    WorkerRole,
    create_runtime,
    request_spawn,
    mark_worker_reported,
    mark_review_required,
)


def test_runtime_transitions_from_planning_to_spawning() -> None:
    runtime = create_runtime("Build dynamic multi-agent tui")

    assert runtime.task_state == TaskRuntimeState.PLANNING

    request_spawn(runtime)

    assert runtime.task_state == TaskRuntimeState.SPAWNING


def test_runtime_moves_to_reviewing_after_all_workers_report() -> None:
    runtime = create_runtime("Patch worker lifecycle")
    worker = runtime.spawn_worker(
        name="Atlas",
        role=WorkerRole.CONTEXT_SCOUT,
        mission="inspect scheduler and routing",
        scope="read scheduler files only",
    )

    runtime.task_state = TaskRuntimeState.COLLECTING
    mark_worker_reported(runtime, worker.id, "found 3 relevant files")
    mark_review_required(runtime)

    assert runtime.task_state == TaskRuntimeState.REVIEWING
    assert runtime.workers[worker.id].state == WorkerRuntimeState.REPORTING
```

- [ ] **步骤 2：运行测试，确认当前缺少运行时状态机实现**

运行：
```bash
pytest tests/test_orchestration.py -v
```

期望：
```text
FAIL ... ModuleNotFoundError: No module named 'astrid.orchestration'
```

- [ ] **步骤 3：实现最小运行时状态机与 worker 元数据**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import itertools


class TaskRuntimeState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    SPAWNING = "spawning"
    RUNNING = "running"
    COLLECTING = "collecting"
    REVIEWING = "reviewing"
    MERGING = "merging"
    DONE = "done"
    FAILED = "failed"


class WorkerRuntimeState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    REPORTING = "reporting"
    ARCHIVED = "archived"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerRole(str, Enum):
    CONTEXT_SCOUT = "context scout"
    CODE_WORKER = "code worker"
    REVIEW_AGENT = "review agent"


_worker_ids = itertools.count(1)


@dataclass(slots=True)
class WorkerRecord:
    id: str
    name: str
    role: WorkerRole
    mission: str
    scope: str
    color: str
    state: WorkerRuntimeState = WorkerRuntimeState.QUEUED
    latest_event: str = ""
    result: str = ""


@dataclass(slots=True)
class OrchestratorState:
    root_goal: str
    task_state: TaskRuntimeState = TaskRuntimeState.PLANNING
    narrative: str = "Unravelling task graph..."
    workers: dict[str, WorkerRecord] = field(default_factory=dict)
    review_required: bool = False

    def spawn_worker(self, *, name: str, role: WorkerRole, mission: str, scope: str, color: str = "cyan") -> WorkerRecord:
        worker_id = f"worker-{next(_worker_ids)}"
        record = WorkerRecord(
            id=worker_id,
            name=name,
            role=role,
            mission=mission,
            scope=scope,
            color=color,
        )
        self.workers[worker_id] = record
        return record


def create_runtime(root_goal: str) -> OrchestratorState:
    return OrchestratorState(root_goal=root_goal)


def request_spawn(runtime: OrchestratorState) -> None:
    runtime.task_state = TaskRuntimeState.SPAWNING
    runtime.narrative = "Spawning workers..."


def mark_worker_reported(runtime: OrchestratorState, worker_id: str, result: str) -> None:
    worker = runtime.workers[worker_id]
    worker.state = WorkerRuntimeState.REPORTING
    worker.result = result
    runtime.task_state = TaskRuntimeState.COLLECTING
    runtime.narrative = f"Collecting reports from {worker.name}..."


def mark_review_required(runtime: OrchestratorState) -> None:
    runtime.review_required = True
    runtime.task_state = TaskRuntimeState.REVIEWING
    runtime.narrative = "Reviewing worker output..."
```

- [ ] **步骤 4：重新运行测试，确认状态机最小骨架成立**

运行：
```bash
pytest tests/test_orchestration.py -v
```

期望：
```text
PASSED tests/test_orchestration.py::test_runtime_transitions_from_planning_to_spawning
PASSED tests/test_orchestration.py::test_runtime_moves_to_reviewing_after_all_workers_report
```

- [ ] **步骤 5：提交**

```bash
git add astrid/orchestration.py tests/test_orchestration.py
git commit -m "feat: add orchestrator runtime state machine"
```

---

### 任务 2：让 SubAgentManager 真的执行 worker

**文件：**
- 修改：`astrid/sub_agents.py`
- 测试：`tests/test_orchestration.py`

- [ ] **步骤 1：先写 worker 执行与结构化结果的失败测试**

```python
from astrid.sub_agents import AgentType, SubAgentManager
from astrid.agent_loop import run_agent_turn
from astrid.types import AgentStep


class SingleReplyModel:
    def next(self, messages):
        return AgentStep(type="assistant", content="worker finished")


def test_sub_agent_manager_executes_spawned_worker() -> None:
    manager = SubAgentManager(parent_session_id="session-1")
    agent = manager.spawn_agent(AgentType.EXPLORE, "inspect auth files")

    result = manager.execute_agent(
        agent.id,
        model=SingleReplyModel(),
        tools=[],
        cwd=".",
    )

    assert result.status == "completed"
    assert "worker finished" in (result.result or "")
```

- [ ] **步骤 2：运行测试，确认当前 manager 没有真正执行入口**

运行：
```bash
pytest tests/test_orchestration.py -v
```

期望：
```text
FAIL ... AttributeError: 'SubAgentManager' object has no attribute 'execute_agent'
```

- [ ] **步骤 3：为 SubAgentManager 增加最小 execute_agent 实现**

```python
from astrid.agent_loop import run_agent_turn
from astrid.tooling import ToolRegistry, ToolDefinition, ToolContext


def execute_agent(
    self,
    agent_id: str,
    *,
    model,
    tools,
    cwd: str,
):
    instance = self.agents[agent_id]
    registry = ToolRegistry(list(tools))
    messages = run_agent_turn(
        model=model,
        tools=registry,
        messages=list(instance.messages),
        cwd=cwd,
        context_manager=instance.context_manager,
    )
    instance.messages = messages
    assistant_messages = [m for m in messages if m.get("role") == "assistant"]
    result = assistant_messages[-1]["content"] if assistant_messages else ""
    self.complete_agent(agent_id, result)
    return instance


SubAgentManager.execute_agent = execute_agent
```

- [ ] **步骤 4：补一条 max_turns 与执行完成汇总测试**

```python
def test_compile_result_summary_includes_worker_result() -> None:
    manager = SubAgentManager(parent_session_id="session-2")
    agent = manager.spawn_agent(AgentType.GENERAL, "patch tui")
    manager.complete_agent(agent.id, "patched worker renderer")

    summary = manager.compile_result_summary(agent.id)

    assert "patched worker renderer" in summary
    assert "Status: completed" in summary
```

- [ ] **步骤 5：运行测试并提交**

运行：
```bash
pytest tests/test_orchestration.py -v
```

期望：
```text
PASSED tests/test_orchestration.py::test_sub_agent_manager_executes_spawned_worker
PASSED tests/test_orchestration.py::test_compile_result_summary_includes_worker_result
```

提交：
```bash
git add astrid/sub_agents.py tests/test_orchestration.py
git commit -m "feat: execute spawned sub-agents"
```

---

### 任务 3：接入 orchestrator 到 TTY 主流程

**文件：**
- 修改：`astrid/tty_app.py`
- 测试：`tests/test_agent_loop.py`

- [ ] **步骤 1：先写 TTY 层接入 orchestrator 的失败测试**

```python
from astrid.orchestration import create_runtime, TaskRuntimeState


def test_tty_runtime_marks_running_when_worker_thread_starts() -> None:
    runtime = create_runtime("design dynamic tui")

    runtime.task_state = TaskRuntimeState.SPAWNING
    runtime.narrative = "Spawning workers..."

    runtime.task_state = TaskRuntimeState.RUNNING

    assert runtime.task_state == TaskRuntimeState.RUNNING
    assert runtime.narrative == "Spawning workers..."
```

- [ ] **步骤 2：在 `ScreenState` 中增加 orchestration runtime 字段**

```python
from astrid.orchestration import OrchestratorState


@dataclass
class ScreenState:
    ...
    orchestration: OrchestratorState | None = None
```

- [ ] **步骤 3：在开始复杂任务时创建 runtime，并在工具/worker 回调里更新状态**

```python
from astrid.orchestration import (
    create_runtime,
    request_spawn,
    mark_worker_reported,
    mark_review_required,
    TaskRuntimeState,
)


def _ensure_orchestration_runtime(state: ScreenState, user_input: str) -> None:
    if state.orchestration is None:
        state.orchestration = create_runtime(user_input)


def _begin_multi_agent_run(state: ScreenState, user_input: str) -> None:
    _ensure_orchestration_runtime(state, user_input)
    request_spawn(state.orchestration)
    state.is_busy = True
    state.status = state.orchestration.narrative
```

- [ ] **步骤 4：在 agent 线程完成时把结果写回 runtime**

```python
def _report_worker_result(state: ScreenState, worker_id: str, result: str, needs_review: bool) -> None:
    if state.orchestration is None:
        return
    mark_worker_reported(state.orchestration, worker_id, result)
    if needs_review:
        mark_review_required(state.orchestration)
    else:
        state.orchestration.task_state = TaskRuntimeState.MERGING
        state.orchestration.narrative = "Merging worker output..."
    state.status = state.orchestration.narrative
```

- [ ] **步骤 5：运行关键测试并提交**

运行：
```bash
pytest tests/test_agent_loop.py tests/test_orchestration.py -v
```

期望：
```text
PASSED tests/test_agent_loop.py::test_agent_turn_executes_tool_and_returns_assistant
PASSED tests/test_orchestration.py::test_runtime_transitions_from_planning_to_spawning
```

提交：
```bash
git add astrid/tty_app.py tests/test_agent_loop.py tests/test_orchestration.py
git commit -m "feat: wire orchestration runtime into tty flow"
```

---

### 任务 4：实现 narrative line 和 agent tree 渲染

**文件：**
- 修改：`astrid/tui/transcript.py`
- 修改：`astrid/tui/chrome.py`
- 修改：`astrid/tui/types.py`
- 测试：`tests/test_tui.py`

- [ ] **步骤 1：先写 narrative line 与 agent tree 的失败测试**

```python
from astrid.orchestration import create_runtime, WorkerRole
from astrid.tui.transcript import render_orchestration_block


def test_render_orchestration_block_shows_narrative_and_worker_rows() -> None:
    runtime = create_runtime("build dynamic multi-agent tui")
    runtime.narrative = "Spawning workers for search, implementation, and review..."
    runtime.spawn_worker(
        name="Atlas",
        role=WorkerRole.CONTEXT_SCOUT,
        mission="mapping auth and routing flow",
        scope="read-only routing inspection",
        color="teal",
    )

    rendered = render_orchestration_block(runtime)

    assert "Spawning workers" in rendered
    assert "Atlas" in rendered
    assert "context scout" in rendered
```

- [ ] **步骤 2：运行测试，确认当前渲染函数不存在**

运行：
```bash
pytest tests/test_tui.py -v
```

期望：
```text
FAIL ... cannot import name 'render_orchestration_block'
```

- [ ] **步骤 3：在 transcript 渲染层增加 orchestration block**

```python
def render_orchestration_block(runtime) -> str:
    if runtime is None:
        return ""

    lines = [runtime.narrative, ""]
    for worker in runtime.workers.values():
        row = (
            f"{worker.name:<10} "
            f"{worker.role.value:<15} "
            f"{worker.mission:<40} "
            f"{worker.state.value}"
        )
        lines.append(row)
        if worker.latest_event:
            lines.append(f"  {worker.latest_event}")
    return "\n".join(lines)
```

- [ ] **步骤 4：在主 transcript 顶部插入 orchestration block，并补颜色映射**

```python
AGENT_COLOR_MAP = {
    "teal": BRIGHT_CYAN,
    "amber": BRIGHT_YELLOW,
    "steel": BRIGHT_BLUE,
    "coral": BRIGHT_RED,
}


def colorize_agent_name(name: str, color: str) -> str:
    prefix = AGENT_COLOR_MAP.get(color, BRIGHT_WHITE)
    return f"{prefix}{BOLD}{name}{RESET}"
```

- [ ] **步骤 5：补 archived 摘要测试、运行测试并提交**

```python
def test_render_orchestration_block_collapses_archived_workers() -> None:
    runtime = create_runtime("demo")
    worker = runtime.spawn_worker(
        name="Forge",
        role=WorkerRole.CODE_WORKER,
        mission="patching scheduler and renderer",
        scope="modify tty files only",
        color="amber",
    )
    worker.state = WorkerRuntimeState.ARCHIVED

    rendered = render_orchestration_block(runtime)

    assert "Forge" in rendered
    assert "archived" in rendered
```

运行：
```bash
pytest tests/test_tui.py -v
```

期望：
```text
PASSED tests/test_tui.py::test_render_orchestration_block_shows_narrative_and_worker_rows
PASSED tests/test_tui.py::test_render_orchestration_block_collapses_archived_workers
```

提交：
```bash
git add astrid/tui/transcript.py astrid/tui/chrome.py astrid/tui/types.py tests/test_tui.py
git commit -m "feat: render dynamic multi-agent narrative and tree"
```

---

### 任务 5：加入 reviewer 回路与归档行为

**文件：**
- 修改：`astrid/orchestration.py`
- 修改：`astrid/sub_agents.py`
- 修改：`astrid/tty_app.py`
- 测试：`tests/test_orchestration.py`

- [ ] **步骤 1：先写 reviewer 拒绝后重跑、通过后归档的失败测试**

```python
from astrid.orchestration import (
    create_runtime,
    WorkerRole,
    TaskRuntimeState,
    WorkerRuntimeState,
    mark_review_required,
)


def test_review_rejection_returns_runtime_to_running() -> None:
    runtime = create_runtime("patch tui")
    worker = runtime.spawn_worker(
        name="Meridian",
        role=WorkerRole.REVIEW_AGENT,
        mission="validating regression risk",
        scope="review changed files only",
    )

    mark_review_required(runtime)
    runtime.task_state = TaskRuntimeState.REVIEWING
    runtime.task_state = TaskRuntimeState.RUNNING

    assert runtime.task_state == TaskRuntimeState.RUNNING


def test_archive_worker_marks_worker_archived() -> None:
    runtime = create_runtime("patch tui")
    worker = runtime.spawn_worker(
        name="Forge",
        role=WorkerRole.CODE_WORKER,
        mission="editing scheduler",
        scope="modify scheduler only",
    )

    worker.state = WorkerRuntimeState.ARCHIVED

    assert runtime.workers[worker.id].state == WorkerRuntimeState.ARCHIVED
```

- [ ] **步骤 2：实现 reviewer 结果分支与 archive helper**

```python
def apply_review_result(runtime: OrchestratorState, *, accepted: bool, summary: str) -> None:
    if accepted:
        runtime.task_state = TaskRuntimeState.MERGING
        runtime.narrative = "Review accepted. Merging worker output..."
    else:
        runtime.task_state = TaskRuntimeState.RUNNING
        runtime.narrative = "Review requested changes. Respawning workers..."


def archive_worker(runtime: OrchestratorState, worker_id: str) -> None:
    worker = runtime.workers[worker_id]
    worker.state = WorkerRuntimeState.ARCHIVED
    worker.latest_event = "archived after merge"
```

- [ ] **步骤 3：在 TTY 流程中对 completed workers 调用归档**

```python
def _archive_completed_workers(state: ScreenState) -> None:
    runtime = state.orchestration
    if runtime is None:
        return
    for worker_id, worker in runtime.workers.items():
        if worker.state == WorkerRuntimeState.REPORTING:
            archive_worker(runtime, worker_id)
```

- [ ] **步骤 4：运行综合测试**

运行：
```bash
pytest tests/test_orchestration.py tests/test_tui.py tests/test_agent_loop.py -v
```

期望：
```text
PASSED tests/test_orchestration.py::test_review_rejection_returns_runtime_to_running
PASSED tests/test_orchestration.py::test_archive_worker_marks_worker_archived
PASSED tests/test_tui.py::test_render_orchestration_block_shows_narrative_and_worker_rows
```

- [ ] **步骤 5：提交**

```bash
git add astrid/orchestration.py astrid/sub_agents.py astrid/tty_app.py tests/test_orchestration.py tests/test_tui.py
git commit -m "feat: add reviewer loop and worker archival"
```

---

### 任务 6：验收、文档核对与手工演示验证

**文件：**
- 修改：`README.md`
- 修改：`docs/superpowers/specs/2026-04-17-dynamic-multi-agent-tui-design.md`

- [ ] **步骤 1：运行目标测试集**

运行：
```bash
pytest tests/test_orchestration.py tests/test_tui.py tests/test_agent_loop.py -v
```

期望：
```text
... all selected tests pass ...
```

- [ ] **步骤 2：手工启动 mock 模式验证 TUI**

运行：
```bash
$env:ASTRID_MODEL_MODE='mock'; python -m astrid.main
```

期望：
```text
TTY 启动成功，输入复杂任务后能看到：
- narrative line
- 至少一个自动命名 worker
- worker role / mission / status
- review / merge / archive 状态变化
```

- [ ] **步骤 3：更新 README 中关于 Astrid 核心能力的描述**

```markdown
- Dynamic multi-agent orchestration with named workers
- Reviewer-based validation loop
- Lightweight runtime agent tree in terminal TUI
- Windows-first multi-agent demo flow
```

- [ ] **步骤 4：核对 spec 与实现一致**

检查：
- 第一版是否仅实现 Phase 1
- 是否未混入 Task board
- 是否未混入 Swarm / handoff

- [ ] **步骤 5：最终提交**

```bash
git add README.md docs/superpowers/specs/2026-04-17-dynamic-multi-agent-tui-design.md docs/superpowers/plans/2026-04-17-dynamic-multi-agent-tui.md
git commit -m "docs: add implementation plan for dynamic multi-agent tui"
```

---

## 自检

### 规格覆盖

- 动态 worker 创建：任务 1、2、3
- reviewer 独立复核：任务 5
- 轻量 narrative + agent tree TUI：任务 4
- loop / state machine：任务 1、3、5
- Windows-first 第一版演示闭环：任务 6
- 第二阶段 Task board 与第三阶段 Swarm / handoff：保留在 spec 中，未纳入当前实现任务

### 占位符扫描

- 未使用 `TODO` / `TBD`
- 每个任务均包含明确文件、测试、命令和最小代码骨架

### 类型一致性

- 顶层状态：`TaskRuntimeState`
- worker 状态：`WorkerRuntimeState`
- worker 角色：`WorkerRole`
- 顶层运行时：`OrchestratorState`

这些名称在任务间保持一致。

---

计划完成并已保存到 `docs/superpowers/plans/2026-04-17-dynamic-multi-agent-tui.md`。两种执行方式：

**1. 子代理驱动（推荐）** - 每个任务调度新子代理，任务间审查

**2. 当前会话内联执行** - 在本会话里按计划逐步实现

你选哪种。 

