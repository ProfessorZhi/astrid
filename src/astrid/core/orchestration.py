"""Runtime state helpers for Astrid's multi-agent orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import itertools
import time

from astrid.core.orchestration_verbs import get_phase_verbs


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
    error: str = ""
    spinner_verb: str = "Working"


@dataclass(slots=True)
class OrchestratorState:
    """Top-level state container for a multi-agent orchestration run."""

    root_goal: str
    task_state: TaskRuntimeState = TaskRuntimeState.PLANNING
    narrative: str = "Unravelling task graph..."
    workers: dict[str, WorkerRuntimeRecord] = field(default_factory=dict)
    review_required: bool = False
    last_review_summary: str = ""
    phase_started_at: float = field(default_factory=time.monotonic)

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
            spinner_verb=sample_spinner_verb(self.task_state, name),
        )
        self.workers[worker_id] = record
        set_phase(self, TaskRuntimeState.RUNNING, f"{name} queued for {role.value}.")
        return record


def create_runtime(root_goal: str) -> OrchestratorState:
    """Create a new orchestration runtime."""

    return OrchestratorState(root_goal=root_goal)


def request_spawn(runtime: OrchestratorState) -> None:
    """Move the runtime into spawn planning."""

    set_phase(runtime, TaskRuntimeState.SPAWNING, "Spawning workers for the task graph...")


def mark_worker_reported(runtime: OrchestratorState, worker_id: str, result: str) -> None:
    """Record a worker report and move runtime into collection."""

    worker = runtime.workers[worker_id]
    worker.state = WorkerRuntimeState.REPORTING
    worker.result = result
    worker.latest_event = "reported"
    set_phase(runtime, TaskRuntimeState.COLLECTING, f"Collecting reports from {worker.name}...")


def mark_worker_failed(runtime: OrchestratorState, worker_id: str, error: str) -> None:
    """Record a failed worker and mark the orchestration as failed."""

    worker = runtime.workers[worker_id]
    worker.state = WorkerRuntimeState.FAILED
    worker.error = error
    worker.latest_event = "failed"
    set_phase(runtime, TaskRuntimeState.FAILED, f"{worker.name} failed: {error}")


def mark_worker_cancelled(runtime: OrchestratorState, worker_id: str, reason: str = "") -> None:
    """Record a cancelled worker and mark the orchestration as stopped."""

    worker = runtime.workers[worker_id]
    worker.state = WorkerRuntimeState.CANCELLED
    worker.error = reason
    worker.latest_event = "cancelled"
    suffix = f": {reason}" if reason else "."
    set_phase(runtime, TaskRuntimeState.FAILED, f"{worker.name} cancelled{suffix}")


def mark_review_required(runtime: OrchestratorState, reviewer_summary: str = "") -> None:
    """Mark the collected work as requiring review."""

    runtime.review_required = True
    runtime.last_review_summary = reviewer_summary
    set_phase(runtime, TaskRuntimeState.REVIEWING, "Reviewing worker output...")


def archive_worker(runtime: OrchestratorState, worker_id: str) -> None:
    """Archive a worker after its output has been collected."""

    worker = runtime.workers[worker_id]
    worker.state = WorkerRuntimeState.ARCHIVED
    worker.latest_event = "archived"

    if all(record.state == WorkerRuntimeState.ARCHIVED for record in runtime.workers.values()):
        set_phase(runtime, TaskRuntimeState.DONE, "All workers archived.")


def build_merge_summary(runtime: OrchestratorState) -> dict[str, bool | int]:
    """Return structured report/merge status for orchestration consumers."""

    workers = list(runtime.workers.values())
    reported = sum(worker.state == WorkerRuntimeState.REPORTING for worker in workers)
    archived = sum(worker.state == WorkerRuntimeState.ARCHIVED for worker in workers)
    failed = sum(worker.state == WorkerRuntimeState.FAILED for worker in workers)
    cancelled = sum(worker.state == WorkerRuntimeState.CANCELLED for worker in workers)
    pending = len(workers) - reported - archived - failed - cancelled

    return {
        "total": len(workers),
        "reported": reported,
        "archived": archived,
        "failed": failed,
        "cancelled": cancelled,
        "pending": pending,
        "ready_to_merge": bool(workers) and pending == 0 and failed == 0 and cancelled == 0,
        "has_failures": failed > 0,
        "has_cancellations": cancelled > 0,
    }


def set_phase(runtime: OrchestratorState, task_state: TaskRuntimeState, narrative: str) -> None:
    runtime.task_state = task_state
    runtime.narrative = narrative
    runtime.phase_started_at = time.monotonic()


def get_phase_label(task_state: TaskRuntimeState) -> str:
    """Return the short lowercase label used by the TUI header line."""

    return _PHASE_LABELS.get(task_state, "coordinating")


def get_phase_verb(task_state: TaskRuntimeState, animation_frame: int = 0, elapsed: float | None = None) -> str:
    """Return the user-facing progress verb for a task state."""

    verbs = get_phase_verbs(task_state.value)
    if not verbs:
        return "Coordinating"
    if elapsed is None:
        return verbs[animation_frame % len(verbs)]
    if elapsed < 0.75:
        return verbs[0]
    if len(verbs) == 1:
        return verbs[0]
    if elapsed < 2.0:
        return verbs[min(1, len(verbs) - 1)]
    if len(verbs) == 2:
        return verbs[1]
    tail = verbs[2:]
    return tail[animation_frame % len(tail)]


def sample_spinner_verb(task_state: TaskRuntimeState, seed: str) -> str:
    """Pick a stable verb for a runtime or worker based on a seed."""

    verbs = get_phase_verbs(task_state.value)
    digest = hashlib.sha256(f"{task_state.value}:{seed}".encode("utf-8")).digest()
    return verbs[digest[0] % len(verbs)]


__all__ = [
    "OrchestratorState",
    "TaskRuntimeState",
    "WorkerRole",
    "WorkerRuntimeRecord",
    "WorkerRuntimeState",
    "archive_worker",
    "build_merge_summary",
    "create_runtime",
    "get_phase_label",
    "get_phase_verb",
    "mark_worker_cancelled",
    "mark_worker_failed",
    "mark_review_required",
    "mark_worker_reported",
    "request_spawn",
    "sample_spinner_verb",
    "set_phase",
]
