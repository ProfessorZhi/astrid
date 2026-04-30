from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import NamedTuple


DEFAULT_VERIFICATION_ROOT = Path("verification")


class SuiteResult(NamedTuple):
    suite_dir: Path


class RunResult(NamedTuple):
    run_dir: Path


class AcceptanceResult(NamedTuple):
    output_path: Path
    metrics_path: Path
    returncode: int


def _write_new_file(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _copy_seed_workspace(source: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        return
    destination.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def _extract_acceptance_command(acceptance_path: Path) -> str | None:
    if not acceptance_path.exists():
        return None
    text = acceptance_path.read_text(encoding="utf-8")
    in_block = False
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            if in_block:
                break
            in_block = line.lower() in {"```bash", "```sh", "```powershell", "```ps1", "```"}
            continue
        if in_block:
            stripped = line.strip()
            if stripped and not stripped.startswith("TODO:"):
                lines.append(line)
    command = "\n".join(lines).strip()
    return command or None


def _count_source_metrics(workspace_dir: Path) -> dict[str, int]:
    extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".json"}
    files = 0
    lines = 0
    bytes_count = 0
    if not workspace_dir.exists():
        return {"source_files": 0, "source_lines": 0, "source_bytes": 0}
    for path in workspace_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if any(part in {"node_modules", ".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        files += 1
        data = path.read_bytes()
        bytes_count += len(data)
        lines += data.decode("utf-8", errors="replace").count("\n") + (1 if data else 0)
    return {"source_files": files, "source_lines": lines, "source_bytes": bytes_count}


def _transcript_metrics(run_dir: Path) -> dict[str, int | str]:
    transcript_dir = run_dir / "transcripts"
    files = sorted(transcript_dir.glob("*.txt")) if transcript_dir.exists() else []
    return {
        "rounds": len(list((run_dir / "prompts").glob("round-*.md"))) if (run_dir / "prompts").exists() else 0,
        "transcript_files": len(files),
        "transcript_bytes": sum(path.stat().st_size for path in files),
        "token_usage": "未采集",
    }


def write_run_metrics(run_dir: Path, *, started_at: float | None = None, ended_at: float | None = None) -> Path:
    started = started_at or time.time()
    ended = ended_at or time.time()
    metrics = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started)),
        "ended_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ended)),
        "duration_seconds": round(max(0.0, ended - started), 3),
        **_transcript_metrics(run_dir),
        **_count_source_metrics(run_dir / "workspace"),
    }
    path = run_dir / "metrics.json"
    path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def create_suite(*, verification_root: Path | str, suite: str, title: str | None = None) -> SuiteResult:
    root = Path(verification_root)
    suite_dir = root / "suites" / suite
    display_title = title or suite
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "seed-workspace").mkdir(exist_ok=True)

    _write_new_file(
        suite_dir / "README.md",
        f"""# {display_title}

## 测试目标

- TODO: 写清楚这道题主要测试哪类 coding-agent 能力。

## 输入材料

- `seed-workspace/`: 初始 workspace 模板。

## 自由度

- TODO: 说明哪些必须严格一致，哪些允许 agent 自由发挥。
""",
    )
    _write_new_file(
        suite_dir / "problem.md",
        f"""# {display_title} 题目

## 背景

TODO: 写清楚任务背景和真实目标。

## 目标

TODO: 写清楚最终要交付什么。

## 限制

- 不要访问 workspace 外文件，除非题目显式允许。
- 不要修改验收测试，除非 suite 显式允许。

## 评测方式

TODO: 写清楚自动验收、人工试玩或截图检查方式。
""",
    )
    _write_new_file(
        suite_dir / "prompt.md",
        f"""你在隔离 workspace 中完成 `{display_title}` 任务。

请先阅读当前目录文件，再实现题目要求。完成后运行可用的验收命令，并在结果中说明改了什么、测试怎么跑、还有什么风险。
""",
    )
    _write_new_file(
        suite_dir / "acceptance.md",
        """# 验收标准

## 自动验收

```bash
TODO: 写验收命令
```

## 禁止事项

- 不要弱化、删除或改写原始验收测试来制造通过。
- 不要把临时缓存、截图或日志散落在仓库根目录。

## 评分权重

- 任务完成度: 45
- 人工体验: 20
- 代码质量和代码规模: 15
- 执行效率和成本: 15
- 证据完整性: 5
""",
    )
    _write_new_file(
        suite_dir / "expected-files.md",
        """# 期望产物

- TODO: 列出理想文件、入口命令和目录结构。
""",
    )
    _write_new_file(
        suite_dir / "results-summary.md",
        """# 横向结果摘要

| 平台 | 模型 | run | 第一轮结果 | 最终结果 | 总分 | 备注 |
|---|---|---|---|---|---:|---|
""",
    )
    _write_new_file(
        suite_dir / "comparison.md",
        """# 横向对比

## 结果质量对比

| run | 任务完成度 | 人工体验 | 代码质量 | 效率成本 | 证据完整性 | 总分 |
|---|---:|---:|---:|---:|---:|---:|

## 执行成本对比

| run | 轮次 | 耗时 | token usage | 成本代理 | 判断 |
|---|---:|---|---|---|---|

## 代码规模对比

| run | 主要源码组织 | 行数 | 字节数 | 质量判断 |
|---|---|---:|---:|---|

## 人工体验对比

| run | 反馈摘要 | 主要优点 | 主要缺点 | 分数影响 |
|---|---|---|---|---|
""",
    )
    return SuiteResult(suite_dir=suite_dir)


def create_run(
    *,
    verification_root: Path | str,
    suite: str,
    platform: str,
    model: str,
    run_name: str,
) -> RunResult:
    root = Path(verification_root)
    suite_dir = root / "suites" / suite
    run_dir = root / "runs" / platform / model / run_name
    workspace_dir = run_dir / "workspace"

    for child in ("prompts", "acceptance", "transcripts", "diffs", "artifacts"):
        (run_dir / child).mkdir(parents=True, exist_ok=True)

    _copy_seed_workspace(suite_dir / "seed-workspace", workspace_dir)

    prompt_source = suite_dir / "prompt.md"
    prompt_text = (
        prompt_source.read_text(encoding="utf-8")
        if prompt_source.exists()
        else "# Round 01\n\nTODO: 粘贴首轮 prompt 原文。\n"
    )
    _write_new_file(run_dir / "prompts" / "round-01.md", prompt_text)

    _write_new_file(
        run_dir / "instructions.md",
        f"""# 执行说明

## 配置

- suite: `{suite}`
- platform: `{platform}`
- model: `{model}`
- run: `{run_name}`
- workspace: `{workspace_dir}`

## Round 01

1. 在 Codex 桌面内置终端进入 `workspace/`。
2. 启动被测 agent，例如 `astrid`、`claude` 或 suite 指定命令。
3. 将 `prompts/round-01.md` 原文粘贴给被测 agent。
4. 完成后保存 transcript 到 `transcripts/round-01.txt`。
5. 在 agent 外部运行 suite 的验收命令，把输出保存到 `acceptance/`。
""",
    )
    _write_new_file(
        run_dir / "results.md",
        f"""# Run 结果

## 配置

- suite: `{suite}`
- platform: `{platform}`
- model: `{model}`
- run: `{run_name}`

## 结果

- 第一轮结果: TODO
- 最终结果: TODO
- 严格判定: TODO

## 验证

- TODO: 记录验收命令和输出文件路径。

## 风险

- TODO
""",
    )
    _write_new_file(
        run_dir / "evaluation.md",
        """# 评价

## 100 分制评分

| 维度 | 权重 | 得分 | 依据 |
|---|---:|---:|---|
| 任务完成度 | 45 | TODO | TODO |
| 人工体验 | 20 | TODO | TODO |
| 代码质量和代码规模 | 15 | TODO | TODO |
| 执行效率和成本 | 15 | TODO | TODO |
| 证据完整性 | 5 | TODO | TODO |
| 总分 | 100 | TODO | TODO |

## 第一轮状态

TODO

## 最终状态

TODO

## 是否有人工修补

TODO
""",
    )
    write_run_metrics(run_dir)
    return RunResult(run_dir=run_dir)


def run_acceptance(*, verification_root: Path | str, suite: str, run_dir: Path | str) -> AcceptanceResult:
    root = Path(verification_root)
    resolved_run_dir = Path(run_dir)
    acceptance_command = _extract_acceptance_command(root / "suites" / suite / "acceptance.md")
    output_path = resolved_run_dir / "acceptance" / "acceptance-output.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    if not acceptance_command:
        output_path.write_text("No acceptance command configured.\n", encoding="utf-8")
        metrics_path = write_run_metrics(resolved_run_dir, started_at=started, ended_at=time.time())
        return AcceptanceResult(output_path=output_path, metrics_path=metrics_path, returncode=2)
    completed = subprocess.run(
        acceptance_command,
        cwd=resolved_run_dir / "workspace",
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    output_path.write_text(
        f"$ {acceptance_command}\n\n[stdout]\n{completed.stdout}\n[stderr]\n{completed.stderr}\n[returncode]\n{completed.returncode}\n",
        encoding="utf-8",
    )
    metrics_path = write_run_metrics(resolved_run_dir, started_at=started, ended_at=time.time())
    return AcceptanceResult(output_path=output_path, metrics_path=metrics_path, returncode=completed.returncode)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create lightweight Astrid eval suite/run scaffolds.")
    parser.add_argument("--verification-root", type=Path, default=DEFAULT_VERIFICATION_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    suite_parser = subparsers.add_parser("suite", help="Create a verification suite scaffold.")
    suite_parser.add_argument("suite")
    suite_parser.add_argument("--title")

    run_parser = subparsers.add_parser("run", help="Create a verification run scaffold.")
    run_parser.add_argument("suite")
    run_parser.add_argument("--platform", required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--run-name", required=True)

    acceptance_parser = subparsers.add_parser("acceptance", help="Run a suite acceptance command for a run.")
    acceptance_parser.add_argument("suite")
    acceptance_parser.add_argument("--run-dir", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "suite":
        result = create_suite(verification_root=args.verification_root, suite=args.suite, title=args.title)
        print(result.suite_dir)
        return 0
    if args.command == "run":
        result = create_run(
            verification_root=args.verification_root,
            suite=args.suite,
            platform=args.platform,
            model=args.model,
            run_name=args.run_name,
        )
        print(result.run_dir)
        return 0
    if args.command == "acceptance":
        result = run_acceptance(
            verification_root=args.verification_root,
            suite=args.suite,
            run_dir=args.run_dir,
        )
        print(result.output_path)
        return result.returncode
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
