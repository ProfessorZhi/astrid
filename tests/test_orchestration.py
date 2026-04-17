from astrid.orchestration import (
    TaskRuntimeState,
    WorkerRole,
    WorkerRuntimeState,
    archive_worker,
    create_runtime,
    get_phase_label,
    mark_review_required,
    mark_worker_reported,
    request_spawn,
)


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


def test_get_phase_label_maps_runtime_states_to_short_ui_labels() -> None:
    assert get_phase_label(TaskRuntimeState.PLANNING) == "unravelling"
    assert get_phase_label(TaskRuntimeState.SPAWNING) == "dispatching"
    assert get_phase_label(TaskRuntimeState.REVIEWING) == "reviewing"
    assert get_phase_label(TaskRuntimeState.DONE) == "standing by"
