from astrid.core.orchestration import (
    TaskRuntimeState,
    WorkerRole,
    WorkerRuntimeState,
    archive_worker,
    build_merge_summary,
    create_runtime,
    get_phase_label,
    get_phase_verb,
    mark_worker_cancelled,
    mark_worker_failed,
    mark_review_required,
    mark_worker_reported,
    request_spawn,
    sample_spinner_verb,
)
from astrid.core.orchestration_verbs import get_phase_verbs


def test_runtime_transitions_from_planning_to_spawning() -> None:
    runtime = create_runtime("Build dynamic multi-agent tui")

    assert runtime.task_state == TaskRuntimeState.PLANNING

    request_spawn(runtime)

    assert runtime.task_state == TaskRuntimeState.SPAWNING
    assert "Spawning" in runtime.narrative


def test_runtime_moves_to_reviewing_after_worker_reports() -> None:
    runtime = create_runtime("Patch worker lifecycle")
    worker = runtime.spawn_worker(
        name="Atlas",
        role=WorkerRole.CONTEXT_SCOUT,
        mission="inspect scheduler and routing",
        scope="read scheduler files only",
    )

    mark_worker_reported(runtime, worker.id, "found 3 relevant files")
    mark_review_required(runtime, reviewer_summary="review requested")

    assert runtime.task_state == TaskRuntimeState.REVIEWING
    assert runtime.review_required is True
    assert runtime.workers[worker.id].state == WorkerRuntimeState.REPORTING
    assert runtime.last_review_summary == "review requested"


def test_archive_worker_moves_runtime_to_done_when_all_workers_are_archived() -> None:
    runtime = create_runtime("Wrap up worker lifecycle")
    worker = runtime.spawn_worker(
        name="Meridian",
        role=WorkerRole.REVIEW_AGENT,
        mission="validate patch integrity",
        scope="review changed files only",
    )

    mark_worker_reported(runtime, worker.id, "looks good")
    archive_worker(runtime, worker.id)

    assert runtime.workers[worker.id].state == WorkerRuntimeState.ARCHIVED
    assert runtime.task_state == TaskRuntimeState.DONE


def test_worker_failed_marks_runtime_failed_and_exposes_merge_summary() -> None:
    runtime = create_runtime("Handle worker failure")
    worker = runtime.spawn_worker(
        name="Pascal",
        role=WorkerRole.CODE_WORKER,
        mission="patch lifecycle",
        scope="orchestration only",
    )

    mark_worker_failed(runtime, worker.id, "tool permission denied")

    assert runtime.task_state == TaskRuntimeState.FAILED
    assert runtime.workers[worker.id].state == WorkerRuntimeState.FAILED
    assert runtime.workers[worker.id].latest_event == "failed"
    assert runtime.workers[worker.id].error == "tool permission denied"
    assert build_merge_summary(runtime) == {
        "total": 1,
        "reported": 0,
        "archived": 0,
        "failed": 1,
        "cancelled": 0,
        "pending": 0,
        "ready_to_merge": False,
        "has_failures": True,
        "has_cancellations": False,
    }


def test_reported_workers_are_ready_for_merge_summary() -> None:
    runtime = create_runtime("Merge reported worker output")
    worker = runtime.spawn_worker(
        name="Curie",
        role=WorkerRole.CODE_WORKER,
        mission="summarize patch",
        scope="changed files",
    )

    mark_worker_reported(runtime, worker.id, "ready for parent merge")

    summary = build_merge_summary(runtime)

    assert summary["reported"] == 1
    assert summary["pending"] == 0
    assert summary["ready_to_merge"] is True
    assert summary["has_failures"] is False


def test_worker_cancelled_marks_runtime_failed_without_losing_reason() -> None:
    runtime = create_runtime("Handle cancellation")
    worker = runtime.spawn_worker(
        name="Noether",
        role=WorkerRole.CONTEXT_SCOUT,
        mission="inspect files",
        scope="read only",
    )

    mark_worker_cancelled(runtime, worker.id, "superseded by parent task")

    assert runtime.task_state == TaskRuntimeState.FAILED
    assert runtime.workers[worker.id].state == WorkerRuntimeState.CANCELLED
    assert runtime.workers[worker.id].latest_event == "cancelled"
    assert runtime.workers[worker.id].error == "superseded by parent task"
    assert build_merge_summary(runtime)["has_cancellations"] is True


def test_get_phase_label_maps_runtime_states_to_short_ui_labels() -> None:
    assert get_phase_label(TaskRuntimeState.PLANNING) == "unravelling"
    assert get_phase_label(TaskRuntimeState.SPAWNING) == "dispatching"
    assert get_phase_label(TaskRuntimeState.REVIEWING) == "reviewing"
    assert get_phase_label(TaskRuntimeState.DONE) == "standing by"


def test_phase_verbs_are_stable_and_contextual() -> None:
    assert get_phase_verb(TaskRuntimeState.PLANNING) != ""
    assert get_phase_verb(TaskRuntimeState.SPAWNING) != get_phase_verb(TaskRuntimeState.REVIEWING)
    assert get_phase_verb(TaskRuntimeState.DONE) == "Ready"


def test_phase_verb_uses_elapsed_for_enter_and_steady_transitions() -> None:
    assert get_phase_verb(TaskRuntimeState.SPAWNING, animation_frame=0, elapsed=0.1) == "Dispatching"
    assert get_phase_verb(TaskRuntimeState.SPAWNING, animation_frame=0, elapsed=1.0) == "Assigning"


def test_sample_spinner_verb_is_deterministic_per_seed() -> None:
    assert sample_spinner_verb(TaskRuntimeState.REVIEWING, "Hegel") == sample_spinner_verb(
        TaskRuntimeState.REVIEWING, "Hegel"
    )
    assert sample_spinner_verb(TaskRuntimeState.REVIEWING, "Hegel") != sample_spinner_verb(
        TaskRuntimeState.REVIEWING, "Russell"
    )


def test_phase_verbs_support_append_and_replace_overrides(monkeypatch) -> None:
    monkeypatch.setenv(
        "ASTRID_SPINNER_VERBS",
        '{"mode":"append","phases":{"reviewing":["Auditing"]}}',
    )
    reviewing = get_phase_verbs("reviewing")
    assert "Reviewing" in reviewing
    assert "Auditing" in reviewing

    monkeypatch.setenv(
        "ASTRID_SPINNER_VERBS",
        '{"mode":"replace","phases":{"reviewing":["Auditing"]}}',
    )
    assert get_phase_verbs("reviewing") == ("Auditing",)
