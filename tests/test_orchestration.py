from astrid.orchestration import (
    TaskRuntimeState,
    WorkerRole,
    WorkerRuntimeState,
    archive_worker,
    create_runtime,
    get_phase_label,
    get_phase_verb,
    mark_review_required,
    mark_worker_reported,
    request_spawn,
    sample_spinner_verb,
)
from astrid.orchestration_verbs import get_phase_verbs


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
