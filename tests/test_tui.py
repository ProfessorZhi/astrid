from astrid.tui import render_banner, render_panel, render_permission_prompt, render_transcript
from astrid.tui.chrome import get_worker_accent
from astrid.tui.types import OrchestrationWorker, TranscriptEntry


def test_render_panel_contains_title() -> None:
    rendered = render_panel("Demo", "body")
    assert "Demo" in rendered
    assert "body" in rendered


def test_render_banner_includes_model() -> None:
    rendered = render_banner(
        {"model": "claude-test", "baseUrl": "https://api.anthropic.com"},
        "/tmp/demo",
        ["cwd: /tmp/demo"],
        {"transcriptCount": 1, "messageCount": 2, "skillCount": 3, "mcpCount": 4},
    )
    assert "claude-test" in rendered
    assert "api.anthropic.com" in rendered


def test_render_transcript_shows_tool_entry() -> None:
    transcript = [
        TranscriptEntry(id=1, kind="user", body="hi"),
        TranscriptEntry(id=2, kind="tool", body="done", toolName="read_file", status="success"),
    ]
    rendered = render_transcript(transcript, scroll_offset=0)
    assert "read_file" in rendered
    assert "ok" in rendered


def test_render_transcript_shows_intermediate_collapse_phase() -> None:
    transcript = [
        TranscriptEntry(
            id=1,
            kind="tool",
            body="full output here",
            toolName="run_command",
            status="success",
            collapsePhase=1,
        ),
    ]

    rendered = render_transcript(transcript, scroll_offset=0)

    assert "run_command" in rendered
    assert "collapsing" in rendered


def test_render_transcript_shows_collapsed_summary_when_fully_collapsed() -> None:
    transcript = [
        TranscriptEntry(
            id=1,
            kind="tool",
            body="full output here",
            toolName="run_command",
            status="success",
            collapsed=True,
            collapsedSummary="short summary",
            collapsePhase=3,
        ),
    ]

    rendered = render_transcript(transcript, scroll_offset=0)

    assert "run_command" in rendered
    assert "short summary" in rendered
    assert "full output here" not in rendered


def test_render_transcript_shows_orchestration_block() -> None:
    transcript = [
        TranscriptEntry(
            id=1,
            kind="orchestration",
            body="",
            narrativeLine="Spawning workers for search and review...",
            phaseLabel="dispatching",
            workers=[
                OrchestrationWorker(
                    name="Atlas",
                    role="context scout",
                    mission="mapping auth and routing flow",
                    status="running",
                    colorKey="teal",
                    latestEvent="thinking: inspecting auth router",
                ),
                OrchestrationWorker(
                    name="Meridian",
                    role="review agent",
                    mission="validating regression risk",
                    status="queued",
                    colorKey="blue",
                ),
            ],
        ),
    ]

    rendered = render_transcript(transcript, scroll_offset=0)

    assert "dispatching" in rendered
    assert "Spawning workers for search and review..." in rendered
    assert "Atlas" in rendered
    assert "context scout" in rendered
    assert "mapping auth and routing flow" in rendered
    assert "thinking: inspecting auth router" in rendered
    assert "Meridian" in rendered
    assert "review agent" in rendered
    assert "queued" in rendered


def test_render_transcript_collapses_archived_workers_into_summary() -> None:
    transcript = [
        TranscriptEntry(
            id=1,
            kind="orchestration",
            body="",
            narrativeLine="Merging worker output...",
            phaseLabel="merging",
            workers=[
                OrchestrationWorker(
                    name="Russell",
                    role="context scout",
                    mission="mapped code context",
                    status="done",
                    colorKey="teal",
                ),
                OrchestrationWorker(
                    name="Knuth",
                    role="code worker",
                    mission="patched renderer",
                    status="done",
                    colorKey="coral",
                ),
                OrchestrationWorker(
                    name="Hegel",
                    role="review agent",
                    mission="validated output",
                    status="running",
                    colorKey="blue",
                ),
            ],
        ),
    ]

    rendered = render_transcript(transcript, scroll_offset=0)

    assert "Hegel" in rendered
    assert "2 archived worker(s): Russell, Knuth" in rendered
    assert "Russell  " not in rendered


def test_get_worker_accent_supports_named_and_fallback_colors() -> None:
    teal = get_worker_accent("teal")
    blue = get_worker_accent("blue")
    fallback_a = get_worker_accent(None, index=0)
    fallback_b = get_worker_accent(None, index=1)

    assert teal.startswith("\x1b[")
    assert blue.startswith("\x1b[")
    assert teal != blue
    assert fallback_a != fallback_b


def test_render_permission_prompt_lists_choices() -> None:
    rendered = render_permission_prompt(
        {
            "summary": "Need approval",
            "details": ["target: demo.txt"],
            "choices": [{"key": "1", "label": "allow once"}],
        }
    )
    assert "Need approval" in rendered
    assert "allow once" in rendered
