from __future__ import annotations

import asyncio

from astrid.core.async_context import AsyncContextCollector, collect_context, invalidate_context


def test_collect_context_includes_project_agents_md(tmp_path):
    root = tmp_path / "repo"
    child = root / "src"
    child.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("root async instruction", encoding="utf-8")
    (child / "AGENTS.md").write_text("child async instruction", encoding="utf-8")
    invalidate_context()

    context = asyncio.run(collect_context(str(child)))

    assert "project_instructions" in context
    assert "root async instruction" in context["project_instructions"]
    assert "child async instruction" in context["project_instructions"]
    assert context["project_instructions"].index("root async instruction") < context["project_instructions"].index("child async instruction")


def test_collect_context_includes_claude_md_compatibility(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("claude async instruction", encoding="utf-8")
    invalidate_context()

    context = asyncio.run(collect_context(str(tmp_path)))

    assert "project_instructions" in context
    assert "claude async instruction" in context["project_instructions"]


def test_format_context_for_prompt_uses_neutral_project_instructions_title(tmp_path):
    collector = AsyncContextCollector(str(tmp_path))

    formatted = collector.format_context_for_prompt({
        "project_instructions": "instruction body",
    })

    assert "### Project Instructions" in formatted
    assert "CLAUDE.md" not in formatted
    assert "instruction body" in formatted
