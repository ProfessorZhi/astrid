"""Runtime state helpers for Astrid's multi-agent orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import itertools


class TaskRuntimeState(str, Enum):
    """Top-level runtime states for a multi-agent task."""

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
    """Lifecycle states for a spawned worker."""

    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    REPORTING = "reporting"
    ARCHIVED = "archived"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerRole(str, Enum):
    """Initial worker roles for the first multi-agent runtime."""

    CONTEXT_SCOUT = "context scout"
    CODE_WORKER = "code worker"
    REVIEW_AGENT = "review agent"


_PHASE_LABELS: dict[TaskRuntimeState, str] = {
    TaskRuntimeState.IDLE: "standing by",
    TaskRuntimeState.PLANNING: "unravelling",
    TaskRuntimeState.SPAWNING: "dispatching",
    TaskRuntimeState.RUNNING: "running",
    TaskRuntimeState.COLLECTING: "gathering",
    TaskRuntimeState.REVIEWING: "reviewing",
    TaskRuntimeState.MERGING: "merging",
    TaskRuntimeState.DONE: "standing by",
    TaskRuntimeState.FAILED: "blocked",
}


_WORKER_IDS = itertools.count(1)


@dataclass(slots=True)
class WorkerRuntimeRecord:
    """Runtime metadata for a spawned worker."""

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
    """Top-level state container for a multi-agent orchestration run."""

    root_goal: str
    task_state: TaskRuntimeState = TaskRuntimeState.PLANNING
    narrative: str = "Unravelling task graph..."
    workers: dict[str, WorkerRuntimeRecord] = field(default_factory=dict)
    review_required: bool = False
    last_review_summary: str = ""

    def spawn_worker(
        self,
        *,
        name: str,
        role: WorkerRole,
        mission: str,
        scope: str,
        color: str = "cyan",
    ) -> WorkerRuntimeRecord:
        """Create a worker record and attach it to the runtime."""

        worker_id = f"worker-{next(_WORKER_IDS)}"
        record = WorkerRuntimeRecord(
            id=worker_id,
            name=name,
            role=role,
            mission=mission,
            scope=scope,
            color=color,
            state=WorkerRuntimeState.QUEUED,
            latest_event="spawned",
        )
        self.workers[worker_id] = record
        self.task_state = TaskRuntimeState.RUNNING
        self.narrative = f"{name} queued for {role.value}."
        return record


def create_runtime(root_goal: str) -> OrchestratorState:
    """Create a new orchestration runtime."""

    return OrchestratorState(root_goal=root_goal)


def request_spawn(runtime: OrchestratorState) -> None:
    """Move the runtime into spawn planning."""

    runtime.task_state = TaskRuntimeState.SPAWNING
    runtime.narrative = "Spawning workers for the task graph..."


def mark_worker_reported(runtime: OrchestratorState, worker_id: str, result: str) -> None:
    """Record a worker report and move runtime into collection."""

    worker = runtime.workers[worker_id]
    worker.state = WorkerRuntimeState.REPORTING
    worker.result = result
    worker.latest_event = "reported"
    runtime.task_state = TaskRuntimeState.COLLECTING
    runtime.narrative = f"Collecting reports from {worker.name}..."


def mark_review_required(runtime: OrchestratorState, reviewer_summary: str = "") -> None:
    """Mark the collected work as requiring review."""

    runtime.review_required = True
    runtime.last_review_summary = reviewer_summary
    runtime.task_state = TaskRuntimeState.REVIEWING
    runtime.narrative = "Reviewing worker output..."


def archive_worker(runtime: OrchestratorState, worker_id: str) -> None:
    """Archive a worker after its output has been collected."""

    worker = runtime.workers[worker_id]
    worker.state = WorkerRuntimeState.ARCHIVED
    worker.latest_event = "archived"

    if all(record.state == WorkerRuntimeState.ARCHIVED for record in runtime.workers.values()):
        runtime.task_state = TaskRuntimeState.DONE
        runtime.narrative = "All workers archived."


def get_phase_label(task_state: TaskRuntimeState) -> str:
    """Return the short lowercase label used by the TUI header line."""

    return _PHASE_LABELS.get(task_state, "coordinating")


__all__ = [
    "OrchestratorState",
    "TaskRuntimeState",
    "WorkerRole",
    "WorkerRuntimeRecord",
    "WorkerRuntimeState",
    "archive_worker",
    "create_runtime",
    "get_phase_label",
    "mark_review_required",
    "mark_worker_reported",
    "request_spawn",
]
