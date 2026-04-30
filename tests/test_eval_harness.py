from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_harness_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "create_eval_run.py"
    spec = importlib.util.spec_from_file_location("create_eval_run", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_suite_scaffold_writes_standard_templates(tmp_path: Path) -> None:
    harness = _load_harness_module()
    verification_root = tmp_path / "verification"

    result = harness.create_suite(
        verification_root=verification_root,
        suite="snake",
        title="Snake",
    )

    suite_dir = verification_root / "suites" / "snake"
    assert result.suite_dir == suite_dir
    assert (suite_dir / "README.md").read_text(encoding="utf-8").startswith("# Snake")
    assert (suite_dir / "problem.md").exists()
    assert (suite_dir / "prompt.md").exists()
    assert (suite_dir / "acceptance.md").exists()
    assert (suite_dir / "expected-files.md").exists()
    assert (suite_dir / "results-summary.md").exists()
    assert (suite_dir / "comparison.md").exists()
    assert (suite_dir / "seed-workspace").is_dir()


def test_create_run_copies_seed_workspace_and_writes_run_templates(tmp_path: Path) -> None:
    harness = _load_harness_module()
    verification_root = tmp_path / "verification"
    suite_dir = verification_root / "suites" / "snake"
    seed_dir = suite_dir / "seed-workspace"
    seed_dir.mkdir(parents=True)
    (seed_dir / "app.py").write_text("print('seed')\n", encoding="utf-8")
    (suite_dir / "prompt.md").write_text("Round 01 prompt\n", encoding="utf-8")

    result = harness.create_run(
        verification_root=verification_root,
        suite="snake",
        platform="astrid",
        model="minimax2.7",
        run_name="2026-05-01-snake",
    )

    run_dir = verification_root / "runs" / "astrid" / "minimax2.7" / "2026-05-01-snake"
    assert result.run_dir == run_dir
    assert (run_dir / "workspace" / "app.py").read_text(encoding="utf-8") == "print('seed')\n"
    assert (run_dir / "prompts" / "round-01.md").read_text(encoding="utf-8") == "Round 01 prompt\n"
    assert "workspace" in (run_dir / "instructions.md").read_text(encoding="utf-8")
    assert "100" in (run_dir / "evaluation.md").read_text(encoding="utf-8")
    assert (run_dir / "results.md").exists()
    assert (run_dir / "acceptance").is_dir()
    assert (run_dir / "transcripts").is_dir()
    assert (run_dir / "diffs").is_dir()
    assert (run_dir / "artifacts").is_dir()


def test_create_run_can_skip_missing_seed_workspace(tmp_path: Path) -> None:
    harness = _load_harness_module()
    verification_root = tmp_path / "verification"
    (verification_root / "suites" / "no-seed" / "prompt.md").parent.mkdir(parents=True)

    result = harness.create_run(
        verification_root=verification_root,
        suite="no-seed",
        platform="claudecode",
        model="minimax2.7",
        run_name="2026-05-01-no-seed",
    )

    assert (result.run_dir / "workspace").is_dir()
    assert (result.run_dir / "prompts" / "round-01.md").exists()
