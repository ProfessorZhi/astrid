from astrid.tui import render_banner, render_panel, render_permission_prompt, render_transcript, render_markdownish
from astrid.tui.companion import cycle_companion_species, render_companion_preview
from astrid.tui import chrome
from astrid.tui.chrome import get_worker_accent
from astrid.tui.transcript import render_transcript_simple
from astrid.tui.buddy import (
    BUDDY_SPECIES,
    cycle_buddy_species,
    get_buddy_frame,
    normalize_buddy_species,
    render_buddy_block,
    render_buddy_profile_block,
    render_buddy_overlay,
)
from astrid.tui.buddy_state import BuddyRuntimeState, build_buddy_profile
from astrid.tui.input import render_input_prompt
from astrid.tui.welcome_hero import render_welcome_hero_profile_block
from astrid.tui.types import OrchestrationWorker, TranscriptEntry


def test_render_panel_contains_title() -> None:
    rendered = render_panel("Demo", "body")
    assert "Demo" in rendered
    assert "body" in rendered


def test_render_welcome_workbench_shows_sections_in_boxed_layout() -> None:
    rendered = chrome.render_welcome_workbench(
        app_name="astrid",
        version="v0.test",
        model_name="MiniMax-M2.7",
        workspace="F:/demo",
        buddy_block="duck frame",
        tips=["Run /init to create project guidance"],
        recent_items=["No recent activity"],
    )

    assert "Welcome back" in rendered
    assert "tips" in rendered
    assert "recent" in rendered
    assert "MiniMax-M2.7" in rendered
    assert "F:/demo" in rendered
    assert "model" in rendered
    assert "duck frame" in rendered
    plain = chrome.strip_ansi(rendered)
    assert "+" in plain
    assert "|" in plain


def test_render_welcome_workbench_respects_custom_width_with_box_chrome() -> None:
    wide = chrome.render_welcome_workbench(
        app_name="astrid",
        version="v0.test",
        model_name="MiniMax-M2.7",
        workspace="F:/demo",
        buddy_block="duck frame",
        tips=["Run /init to create project guidance"],
        recent_items=["No recent activity"],
        width=96,
    )
    narrow = chrome.render_welcome_workbench(
        app_name="astrid",
        version="v0.test",
        model_name="MiniMax-M2.7",
        workspace="F:/demo",
        buddy_block="duck frame",
        tips=["Run /init to create project guidance"],
        recent_items=["No recent activity"],
        width=54,
    )

    wide_plain = chrome.strip_ansi(wide)
    narrow_plain = chrome.strip_ansi(narrow)

    assert "Welcome back" in wide_plain
    assert "tips" in wide_plain
    assert "Welcome back" in narrow_plain
    assert "tips" in narrow_plain
    assert "recent" in narrow_plain
    assert any(line.strip().startswith("|") for line in narrow_plain.splitlines())
    assert any(line.strip().startswith("+") for line in wide_plain.splitlines())


def test_render_welcome_workbench_renders_full_builtin_pet_sprite() -> None:
    rendered = chrome.render_welcome_workbench(
        app_name="astrid",
        version="v0.test",
        model_name="MiniMax-M2.7",
        workspace="F:/demo",
        buddy_block=render_buddy_block("turtle", 0),
        tips=["Run /pet next to switch buddies"],
        recent_items=["No recent activity"],
        width=126,
    )

    plain = chrome.strip_ansi(rendered)
    assert "_,--._" in plain
    assert "( o  o )" in plain
    assert "/[______]\\\\" in plain
    assert "turtle buddy" in plain
    assert "{##} turtle buddy" not in plain


def test_render_welcome_workbench_stacks_full_pet_on_narrow_width() -> None:
    rendered = chrome.render_welcome_workbench(
        app_name="astrid",
        version="v0.test",
        model_name="MiniMax-M2.7",
        workspace="F:/demo",
        buddy_block=render_buddy_block("turtle", 0),
        tips=["Run /pet next to switch buddies"],
        recent_items=["No recent activity"],
        width=54,
    )

    plain = chrome.strip_ansi(rendered)
    assert "_,--._" in plain
    assert "( o  o )" in plain
    assert "/[______]\\\\" in plain
    assert "Welcome back" in plain
    assert "{##} turtle buddy" not in plain


def test_render_input_prompt_uses_single_line_compact_layout() -> None:
    rendered = chrome.strip_ansi(render_input_prompt("", 0, compact=False))

    assert "[Enter] send" not in rendered
    assert "Type a message or /help for commands" not in rendered
    assert "astrid>" in rendered
    assert rendered.startswith("astrid>")


def test_render_markdownish_inline_code_uses_muted_foreground_without_background() -> None:
    rendered = render_markdownish("Path: `C:\\Users\\Administrator`")

    assert "\u001b[48;5;236m" not in rendered
    assert "\u001b[38;5;180m" in rendered


def test_render_welcome_workbench_keeps_left_hero_near_the_top_in_wide_mode() -> None:
    buddy_block = "\n".join(["duck hero", "badge"])
    wide = chrome.strip_ansi(
        chrome.render_welcome_workbench(
            app_name="astrid",
            version="v0.test",
            model_name="MiniMax-M2.7",
            workspace="F:/demo",
            buddy_block=buddy_block,
            tips=["Run /init to create project guidance"],
            recent_items=["No recent activity"],
            width=100,
        )
    )
    lines = wide.splitlines()
    hero_index = next(i for i, line in enumerate(lines) if "badge" in line)
    assert hero_index <= 4


def test_render_welcome_workbench_keeps_box_dividers_stable_in_wide_mode() -> None:
    wide = chrome.strip_ansi(
        chrome.render_welcome_workbench(
            app_name="astrid",
            version="v0.test",
            model_name="MiniMax-M2.7",
            workspace="F:/demo",
            buddy_block="duck hero\nbadge",
            tips=["Run /init to create project guidance"],
            recent_items=["No recent activity"],
            width=140,
        )
    )

    assert "badge" in wide
    assert any(line.strip().startswith("|") for line in wide.splitlines())


def test_render_transcript_simple_adds_round_separator_before_new_user_turn() -> None:
    transcript = [
        TranscriptEntry(id=1, kind="welcome", body="welcome"),
        TranscriptEntry(id=2, kind="user", body="first"),
        TranscriptEntry(id=3, kind="assistant", body="reply"),
        TranscriptEntry(id=4, kind="user", body="second"),
    ]

    transcript_rendered = chrome.strip_ansi(render_transcript_simple(transcript))
    assert "--------------------------" in transcript_rendered


def test_render_banner_includes_model() -> None:
    rendered = render_banner(
        {"model": "claude-test", "baseUrl": "https://api.anthropic.com"},
        "/tmp/demo",
        ["cwd: /tmp/demo"],
        {"transcriptCount": 1, "messageCount": 2, "skillCount": 3, "mcpCount": 4},
    )
    assert "claude-test" in rendered
    assert "api.anthropic.com" in rendered


def test_render_banner_can_include_companion_preview() -> None:
    rendered = render_banner(
        {"model": "claude-test", "baseUrl": "https://api.anthropic.com"},
        "/tmp/demo",
        ["cwd: /tmp/demo"],
        {"transcriptCount": 0, "messageCount": 0, "skillCount": 3, "mcpCount": 4},
        companion_preview=render_companion_preview("duck"),
    )

    assert "duck companion" in rendered
    assert "/pet next" in rendered


def test_render_transcript_shows_tool_entry() -> None:
    transcript = [
        TranscriptEntry(id=1, kind="user", body="hi"),
        TranscriptEntry(
            id=2,
            kind="tool",
            body="done",
            toolName="read_file",
            status="success",
            actionSummary="readme.md",
        ),
    ]
    rendered = render_transcript(transcript, scroll_offset=0)
    assert "read_file" in rendered
    assert "result" in rendered
    assert "readme.md" in rendered


def test_render_transcript_shows_detailed_progress_line() -> None:
    transcript = [
        TranscriptEntry(
            id=1,
            kind="progress",
            body="",
            phaseVerb="Scanning",
            actionSummary="searching project files",
        ),
    ]

    rendered = render_transcript(transcript, scroll_offset=0)

    assert "Scanning" in rendered
    assert "searching project files" in rendered


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
            animationFrame=2,
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
    assert "[" in rendered
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


def test_render_transcript_shows_dynamic_spinner_for_running_orchestration() -> None:
    transcript = [
        TranscriptEntry(
            id=1,
            kind="orchestration",
            body="",
            narrativeLine="Reviewing worker output...",
            phaseLabel="reviewing",
            phaseVerb="Inspecting",
            animationFrame=1,
            workers=[
                OrchestrationWorker(
                    name="Hegel",
                    role="review agent",
                    mission="validating regression risk",
                    status="running",
                    colorKey="blue",
                ),
            ],
        ),
    ]

    rendered = render_transcript(transcript, scroll_offset=0)

    assert "Inspecting" in rendered
    assert any(frame in rendered for frame in (".", "o", "O"))


def test_render_transcript_uses_stable_ascii_labels() -> None:
    transcript = [
        TranscriptEntry(id=1, kind="user", body="浣犲ソ"),
        TranscriptEntry(id=2, kind="progress", body="", phaseVerb="Planning", actionSummary="next step"),
        TranscriptEntry(id=3, kind="assistant", body="done"),
    ]

    rendered = render_transcript(transcript, scroll_offset=0)

    assert "you" in rendered
    assert "progress" in rendered
    assert "assistant" in rendered
    assert "??" not in rendered


def test_render_transcript_uses_worker_specific_spinner_verbs() -> None:
    transcript = [
        TranscriptEntry(
            id=1,
            kind="orchestration",
            body="",
            narrativeLine="Spawning workers for search and review...",
            phaseLabel="dispatching",
            phaseVerb="Dispatching",
            animationFrame=0,
            workers=[
                OrchestrationWorker(
                    name="Russell",
                    role="context scout",
                    mission="mapping auth and routing flow",
                    status="running",
                    colorKey="teal",
                    latestEvent="Inspecting auth router",
                    spinnerVerb="Inspecting",
                ),
            ],
        ),
    ]

    rendered = render_transcript(transcript, scroll_offset=0)

    assert "Inspecting" in rendered


def test_render_footer_bar_includes_busy_status_text() -> None:
    rendered = chrome.render_footer_bar(
        status="[==>     ] Running write_file...",
        tools_enabled=True,
        skills_enabled=True,
        background_tasks=[],
    )

    assert "Running write_file..." in rendered


def test_cycle_companion_species_wraps() -> None:
    assert cycle_companion_species("duck", 1) != "duck"
    assert cycle_companion_species("chonk", 1) == "duck"


def test_render_companion_preview_contains_species_and_hint() -> None:
    rendered = render_companion_preview("robot")

    assert "robot companion" in rendered
    assert "/pet switch <species>" in rendered


def test_buddy_species_matches_v2_source_set() -> None:
    assert BUDDY_SPECIES == (
        "duck",
        "goose",
        "blob",
        "cat",
        "dragon",
        "octopus",
        "owl",
        "penguin",
        "turtle",
        "snail",
        "ghost",
        "axolotl",
        "capybara",
        "cactus",
        "robot",
        "rabbit",
        "mushroom",
        "chonk",
    )


def test_normalize_and_cycle_buddy_species() -> None:
    assert normalize_buddy_species(" Goose ") == "goose"
    assert normalize_buddy_species("unknown") == "duck"
    assert cycle_buddy_species("chonk", 1) == "duck"
    assert cycle_buddy_species("duck", -1) == "chonk"


def test_each_buddy_species_has_three_distinct_frames() -> None:
    for species in BUDDY_SPECIES:
        frames = {
            get_buddy_frame(species, animation_tick=0),
            get_buddy_frame(species, animation_tick=1),
            get_buddy_frame(species, animation_tick=2),
        }
        assert len(frames) == 3, species


def test_render_buddy_block_uses_species_frame() -> None:
    rendered_a = render_buddy_block("duck", animation_tick=0)
    rendered_b = render_buddy_block("duck", animation_tick=1)

    assert "duck" in rendered_a
    assert rendered_a != rendered_b


def test_key_buddy_species_have_distinct_sprite_shapes() -> None:
    duck = render_buddy_block("duck", animation_tick=0)
    goose = render_buddy_block("goose", animation_tick=0)
    robot = render_buddy_block("robot", animation_tick=0)

    assert "<(o )___" in duck
    assert "_(__)_" in goose
    assert ".[||]." in robot


def test_builtin_duck_sprite_keeps_curated_shape_in_all_frames() -> None:
    frames = [render_buddy_block("duck", animation_tick=i) for i in range(3)]

    assert "    __" in frames[0]
    assert "<(o )___" in frames[0]
    assert "`--'" in frames[0]
    assert "`--'~" in frames[1]
    assert "(  .__>" in frames[2]


def test_render_buddy_profile_block_supports_bubble_and_hearts() -> None:
    profile = build_buddy_profile("demo-seed", species_override="robot")
    runtime = BuddyRuntimeState(
        reaction_text="Ready for review",
        reaction_until=9999999999.0,
        pet_until=9999999999.0,
    )

    rendered = render_buddy_profile_block(profile, runtime, animation_tick=0)

    assert "Ready for review" in rendered
    assert rendered
    assert profile.soul.name in rendered
    assert "robot buddy" in rendered
    assert "Star Buddy" in rendered or "Mythic Buddy" in rendered or "Field Buddy" in rendered or "Trusted Buddy" in rendered or "Cosmic Buddy" in rendered


def test_render_buddy_profile_block_hero_mode_scales_sprite() -> None:
    profile = build_buddy_profile("demo-seed", species_override="duck")
    runtime = BuddyRuntimeState()

    normal = render_buddy_profile_block(profile, runtime, animation_tick=0)
    hero = render_buddy_profile_block(profile, runtime, animation_tick=0, hero=True)

    assert len(hero.splitlines()) > len(normal.splitlines())
    plain = chrome.strip_ansi(hero)
    assert "<(o )___" in plain
    assert "<(oo )" not in plain
    assert "<<((" not in hero


def test_render_buddy_profile_block_hero_mode_does_not_duplicate_hat_line() -> None:
    profile = build_buddy_profile("demo-seed", species_override="duck")
    runtime = BuddyRuntimeState()

    hero = render_buddy_profile_block(profile, runtime, animation_tick=0, hero=True)

    if profile.bones.hat != "none":
        hat_line = "\\^^^/" if profile.bones.hat == "crown" else "[___]" if profile.bones.hat == "tophat" else "(___)" if profile.bones.hat == "beanie" else "(   )"
        assert hero.count(hat_line) == 0


def test_render_buddy_profile_block_hero_mode_uses_compact_metadata() -> None:
    profile = build_buddy_profile("demo-seed", species_override="duck")
    runtime = BuddyRuntimeState()

    hero = render_buddy_profile_block(profile, runtime, animation_tick=0, hero=True)

    assert "hat crown" not in hero
    assert "eye " not in hero
    assert profile.soul.persona not in hero
    assert profile.soul.name in hero


def test_render_buddy_profile_block_hero_mode_drops_idle_blank_hat_slot() -> None:
    profile = build_buddy_profile("demo-seed", species_override="robot")
    runtime = BuddyRuntimeState()

    hero = render_buddy_profile_block(profile, runtime, animation_tick=0, hero=True)
    meaningful = [line for line in hero.splitlines() if line.strip()]

    assert "[||" in meaningful[0]


def test_render_buddy_profile_block_hero_mode_trims_excess_left_padding() -> None:
    profile = build_buddy_profile("demo-seed", species_override="goose")
    runtime = BuddyRuntimeState()

    hero = chrome.strip_ansi(render_buddy_profile_block(profile, runtime, animation_tick=0, hero=True))
    meaningful = [line for line in hero.splitlines() if line.strip()]

    leading_spaces = len(meaningful[0]) - len(meaningful[0].lstrip(" "))
    assert leading_spaces <= 4


def test_render_buddy_profile_block_hero_mode_uses_compact_badge_line() -> None:
    profile = build_buddy_profile("demo-seed", species_override="duck")
    runtime = BuddyRuntimeState()

    hero = chrome.strip_ansi(render_buddy_profile_block(profile, runtime, animation_tick=0, hero=True))

    assert f"{profile.soul.name} /" in hero
    assert "Star Buddy" not in hero


def test_render_buddy_profile_block_hero_mode_keeps_original_duck_shape() -> None:
    profile = build_buddy_profile("demo-seed", species_override="duck")
    runtime = BuddyRuntimeState()

    hero = chrome.strip_ansi(render_buddy_profile_block(profile, runtime, animation_tick=0, hero=True))

    assert "<(o )___" in hero
    assert "`--'" in hero
    assert "oo" not in hero


def test_render_welcome_hero_profile_block_uses_builtin_ascii_pet_for_duck() -> None:
    profile = build_buddy_profile("demo-seed", species_override="duck")
    runtime = BuddyRuntimeState()

    hero = render_welcome_hero_profile_block(profile, runtime, animation_tick=0)

    plain = chrome.strip_ansi(hero)
    assert "<(o )___" in plain
    assert "Duck" in plain
    assert "Drift" not in plain


def test_render_buddy_overlay_supports_active_work_view_reaction() -> None:
    profile = build_buddy_profile("demo-seed", species_override="duck")
    runtime = BuddyRuntimeState(
        reaction_text="Need your approval",
        reaction_until=9999999999.0,
    )

    rendered = render_buddy_overlay(profile, runtime)

    assert "Need your approval" in rendered
    assert profile.soul.name in rendered


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
