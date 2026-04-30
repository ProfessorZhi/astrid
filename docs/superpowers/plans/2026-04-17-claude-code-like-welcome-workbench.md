# Astrid Claude Code 风格 Welcome Workbench 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Astrid 落地一版默认橙色欢迎工作台，包含双栏 welcome 首页、18 种 buddy、welcome/work 视图切换，以及更接近 Claude Code 气质的输入区与底栏。

**Architecture:** 保持现有 `tty_app.py` 作为主入口，不推翻当前 transcript/orchestration 主工作流；在其上新增 `idle / welcome view` 分支、独立 buddy 渲染模块和橙色主题 token。welcome 视图只服务于空闲态，进入真实对话或多 agent 运行后回到现有 work view。

**Tech Stack:** Python 3.11+、现有 ANSI TUI 渲染层（`src/astrid/tui/*.py`）、pytest

---

## 文件结构

- 新建：`src/astrid/tui/buddy.py`
  - 负责 18 个 species、sprite 帧定义、idle/fidget/blink 动画选择、buddy 预览与 workbench 左栏渲染
- 修改：`src/astrid/tui/chrome.py`
  - 新增橙色 welcome theme token、welcome workbench 卡片渲染、顶部品牌线/底部状态线样式收口
- 修改：`src/astrid/tui/types.py`
  - 为 transcript/orchestration 条目补充 welcome/work 视图需要的轻状态字段
- 修改：`src/astrid/tui/transcript.py`
  - 保留现有 orchestration 主体，但让 active work view 的颜色和动态 phase 与新主题更协调
- 修改：`src/astrid/ui/full/tty_app.py`
  - 增加 idle/work 视图切换逻辑、buddy 命令处理、动画心跳同步、recent activity 数据来源
- 修改：`src/astrid/cli/cli_commands.py`
  - 将 `/pet` 系列命令注册为正式 slash command，补说明文案
- 修改：`tests/test_tui.py`
  - 覆盖 welcome card、buddy species、orange theme、动态 phase 文案和双栏布局关键文本
- 修改：`tests/test_tty_app.py`
  - 覆盖 idle/work 切换、`/pet` 命令、`/clear` 返回 welcome 页、recent activity 基本行为
- 可选修改：`README.md`
  - 若实现完成后体验稳定，再补 welcome/buddy 能力说明

---

### 任务 1：建立 Buddy v2 数据与多帧动画内核

**Files:**
- Create: `src/astrid/tui/buddy.py`
- Test: `tests/test_tui.py`

- [ ] **Step 1: 写 buddy species 与多帧行为的失败测试**

```python
from astrid.tui.buddy import (
    BUDDY_SPECIES,
    cycle_buddy_species,
    get_buddy_frame,
)


def test_buddy_species_matches_claude_code_source_set() -> None:
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


def test_cycle_buddy_species_wraps_from_last_to_first() -> None:
    assert cycle_buddy_species("chonk", 1) == "duck"


def test_get_buddy_frame_returns_different_idle_frames() -> None:
    frame_a = get_buddy_frame("duck", animation_tick=0)
    frame_b = get_buddy_frame("duck", animation_tick=3)
    assert frame_a != frame_b
```

- [ ] **Step 2: 运行测试，确认 buddy 模块尚不存在**

Run: `python -m pytest tests/test_tui.py::test_buddy_species_matches_claude_code_source_set -q`

Expected: `ModuleNotFoundError: No module named 'astrid.tui.buddy'`

- [ ] **Step 3: 最小实现 buddy species、循环切换和多帧选择**

```python
# src/astrid/tui/buddy.py
from __future__ import annotations

BUDDY_SPECIES = (
    "duck", "goose", "blob", "cat", "dragon", "octopus", "owl", "penguin",
    "turtle", "snail", "ghost", "axolotl", "capybara", "cactus",
    "robot", "rabbit", "mushroom", "chonk",
)

_DUCK_FRAMES = (
    ("  __", "<(o )___", " ( ._> /", "  `---'"),
    ("  __", "<(o )___", " ( .__>/", "  `---'"),
    ("  __", "<(- )___", " ( ._> /", "  `---'"),
)

_BUDDY_FRAMES = {"duck": _DUCK_FRAMES}

def normalize_buddy_species(species: str | None) -> str:
    candidate = (species or "").strip().lower()
    return candidate if candidate in BUDDY_SPECIES else BUDDY_SPECIES[0]

def cycle_buddy_species(current: str | None, step: int = 1) -> str:
    species = normalize_buddy_species(current)
    index = BUDDY_SPECIES.index(species)
    return BUDDY_SPECIES[(index + step) % len(BUDDY_SPECIES)]

def get_buddy_frame(species: str | None, animation_tick: int) -> tuple[str, ...]:
    pet = normalize_buddy_species(species)
    frames = _BUDDY_FRAMES.get(pet, _DUCK_FRAMES)
    return frames[animation_tick % len(frames)]
```

- [ ] **Step 4: 补齐 18 个 species 的最小帧集**

```python
_BUDDY_FRAMES.update(
    {
        "goose": (
            ("   __", " _(o )", " \\_  )", "   /_/ "),
            ("   __", " _(o )", " \\__ )", "   /_/ "),
            ("   __", " _(- )", " \\_  )", "   /_/ "),
        ),
        "blob": (
            ("  .----.", " ( o  o )", " (  --  )", "  `----'"),
            ("  .----.", " ( o  o )", " (  ~~  )", "  `----'"),
            ("  .----.", " ( -  o )", " (  --  )", "  `----'"),
        ),
    }
)
```

- [ ] **Step 5: 运行测试并确认转绿**

Run: `python -m pytest tests/test_tui.py -q`

Expected: 新增 buddy 相关测试通过

- [ ] **Step 6: Commit**

```bash
git add src/astrid/tui/buddy.py tests/test_tui.py
git commit -m "feat: add buddy species and animation core"
```

---

### 任务 2：重做 welcome workbench 双栏首页

**Files:**
- Modify: `src/astrid/tui/chrome.py`
- Test: `tests/test_tui.py`

- [ ] **Step 1: 先写 welcome workbench 渲染失败测试**

```python
from astrid.tui.chrome import render_welcome_workbench


def test_render_welcome_workbench_shows_two_column_sections() -> None:
    rendered = render_welcome_workbench(
        app_name="astrid",
        version="v0.test",
        model_name="MiniMax-M2.7",
        workspace="F:/demo",
        buddy_block="duck frame",
        tips=["Run /init to create project guidance"],
        recent_items=["No recent activity"],
    )

    assert "Welcome back" in rendered
    assert "Tips for getting started" in rendered
    assert "Recent activity" in rendered
    assert "MiniMax-M2.7" in rendered
    assert "F:/demo" in rendered
```

- [ ] **Step 2: 运行测试，确认 `render_welcome_workbench` 尚不存在**

Run: `python -m pytest tests/test_tui.py::test_render_welcome_workbench_shows_two_column_sections -q`

Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: 在 chrome 层新增最小双栏 welcome card 渲染**

```python
def render_welcome_workbench(
    *,
    app_name: str,
    version: str,
    model_name: str,
    workspace: str,
    buddy_block: str,
    tips: list[str],
    recent_items: list[str],
) -> str:
    left = "\n".join(
        [
            "Welcome back",
            "",
            buddy_block,
            "",
            f"{model_name}",
            f"{workspace}",
        ]
    )
    right = "\n".join(
        [
            "Tips for getting started",
            *tips,
            "",
            "Recent activity",
            *recent_items,
        ]
    )
    body = f"{left}\n\n{right}"
    return render_panel(f"{app_name} {version}", body)
```

- [ ] **Step 4: 把最小实现升级为真正双栏布局与橙色边框**

```python
WELCOME_BORDER = "\x1b[38;5;209m"
WELCOME_ACCENT = "\x1b[38;5;208m"
WELCOME_MUTED = "\x1b[38;5;245m"

def _split_columns(left_lines: list[str], right_lines: list[str], left_width: int, right_width: int) -> list[str]:
    height = max(len(left_lines), len(right_lines))
    rows: list[str] = []
    for i in range(height):
        left = left_lines[i] if i < len(left_lines) else ""
        right = right_lines[i] if i < len(right_lines) else ""
        rows.append(f"{left:<{left_width}} │ {right:<{right_width}}")
    return rows
```

- [ ] **Step 5: 运行测试并确认 welcome 视图基础渲染通过**

Run: `python -m pytest tests/test_tui.py -q`

Expected: welcome workbench 相关测试通过

- [ ] **Step 6: Commit**

```bash
git add src/astrid/tui/chrome.py tests/test_tui.py
git commit -m "feat: add orange welcome workbench renderer"
```

---

### 任务 3：接入 idle/work 视图切换

**Files:**
- Modify: `src/astrid/ui/full/tty_app.py`
- Test: `tests/test_tty_app.py`

- [ ] **Step 1: 先写 idle/work 切换失败测试**

```python
from astrid.ui.full.tty_app import ScreenState, _should_show_welcome_view


def test_should_show_welcome_view_when_transcript_empty_and_idle() -> None:
    state = ScreenState(history=[])
    assert _should_show_welcome_view(state) is True


def test_should_hide_welcome_view_after_user_message() -> None:
    state = ScreenState(history=[])
    state.transcript.append(type("Entry", (), {"kind": "user"})())
    assert _should_show_welcome_view(state) is False
```

- [ ] **Step 2: 运行测试，确认切换函数尚不存在**

Run: `python -m pytest tests/test_tty_app.py::test_should_show_welcome_view_when_transcript_empty_and_idle -q`

Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: 在 `ScreenState` 中补充 welcome/buddy 状态字段**

```python
@dataclass
class ScreenState:
    ...
    buddy_enabled: bool = True
    buddy_species: str = "duck"
    animation_tick: int = 0
```

- [ ] **Step 4: 增加最小 welcome/work 判定函数**

```python
def _should_show_welcome_view(state: ScreenState) -> bool:
    if state.pending_approval:
        return False
    if state.is_busy:
        return False
    if state.orchestration is not None:
        return False
    return len(state.transcript) == 0
```

- [ ] **Step 5: 在 `_render_screen_simple` 和主屏渲染中接入 welcome workbench**

```python
if _should_show_welcome_view(state):
    buddy_block = render_buddy_block(
        species=state.buddy_species,
        animation_tick=state.animation_tick,
    )
    buf.append(
        render_welcome_workbench(
            app_name="astrid",
            version="v0.dev",
            model_name=model_name,
            workspace=args.cwd,
            buddy_block=buddy_block,
            tips=_welcome_tips(),
            recent_items=_recent_activity_lines(state),
        )
    )
else:
    buf.append(render_transcript_simple(transcript_snapshot))
```

- [ ] **Step 6: 运行测试并确认 welcome/work 切换逻辑通过**

Run: `python -m pytest tests/test_tty_app.py -q`

Expected: 相关视图切换测试通过

- [ ] **Step 7: Commit**

```bash
git add src/astrid/ui/full/tty_app.py tests/test_tty_app.py
git commit -m "feat: switch between welcome and work views"
```

---

### 任务 4：把 `/pet` 系列命令接成正式工作流

**Files:**
- Modify: `src/astrid/cli/cli_commands.py`
- Modify: `src/astrid/ui/full/tty_app.py`
- Test: `tests/test_tty_app.py`

- [ ] **Step 1: 先写 `/pet` 指令失败测试**

```python
def test_handle_input_pet_next_cycles_species_and_renders_preview() -> None:
    ...
    should_exit = _handle_input(args, state, lambda: None, submitted_raw_input="/pet next")
    assert should_exit is False
    assert state.buddy_species == "goose"
    assert "goose" in state.transcript[-1].body


def test_handle_input_pet_switch_unknown_species_returns_error() -> None:
    ...
    _handle_input(args, state, lambda: None, submitted_raw_input="/pet switch unknown")
    assert "Unknown companion" in state.transcript[-1].body
```

- [ ] **Step 2: 运行测试，确认当前行为不完整或字段不匹配**

Run: `python -m pytest tests/test_tty_app.py -q`

Expected: `/pet` 相关测试失败

- [ ] **Step 3: 注册 `/pet` 命令并补说明**

```python
SLASH_COMMANDS.extend(
    [
        SlashCommand("/pet", "/pet list", "List available buddy species."),
        SlashCommand("/pet", "/pet next", "Switch to the next buddy."),
        SlashCommand("/pet", "/pet switch <species>", "Switch to a specific buddy."),
        SlashCommand("/pet", "/pet hide", "Hide the welcome buddy."),
        SlashCommand("/pet", "/pet show", "Show the welcome buddy."),
    ]
)
```

- [ ] **Step 4: 在 `tty_app.py` 中实现统一 `/pet` 命令分发**

```python
def _handle_buddy_command(state: ScreenState, input_text: str) -> str | None:
    if input_text == "/pet next":
        state.buddy_species = cycle_buddy_species(state.buddy_species)
        state.buddy_enabled = True
        return render_buddy_preview(state.buddy_species)
    if input_text == "/pet hide":
        state.buddy_enabled = False
        return "Buddy hidden from welcome view."
    if input_text == "/pet show":
        state.buddy_enabled = True
        return render_buddy_preview(state.buddy_species)
    if input_text.startswith("/pet switch "):
        ...
```

- [ ] **Step 5: 运行测试并确认 `/pet` 路径通过**

Run: `python -m pytest tests/test_tty_app.py -q`

Expected: `/pet` 相关测试通过

- [ ] **Step 6: Commit**

```bash
git add src/astrid/cli/cli_commands.py src/astrid/ui/full/tty_app.py tests/test_tty_app.py
git commit -m "feat: add buddy slash commands"
```

---

### 任务 5：让欢迎页和 orchestration 都有真正的多帧动态感

**Files:**
- Modify: `src/astrid/tui/buddy.py`
- Modify: `src/astrid/tui/transcript.py`
- Modify: `src/astrid/ui/full/tty_app.py`
- Test: `tests/test_tui.py`
- Test: `tests/test_tty_app.py`

- [ ] **Step 1: 写 buddy 跳帧和 orchestration spinner 的失败测试**

```python
def test_render_transcript_shows_dynamic_spinner_for_running_orchestration() -> None:
    transcript = [
        TranscriptEntry(
            id=1,
            kind="orchestration",
            body="",
            narrativeLine="Reviewing worker output...",
            phaseLabel="reviewing",
            animationFrame=1,
            workers=[...],
        ),
    ]
    rendered = render_transcript(transcript, scroll_offset=0)
    assert any(frame in rendered for frame in ("◜", "◠", "◝", "◞", "◡", "◟"))
```

- [ ] **Step 2: 运行测试，确认当前动态信息不足**

Run: `python -m pytest tests/test_tui.py tests/test_tty_app.py -q`

Expected: 动态帧相关测试失败

- [ ] **Step 3: 在 `tty_app.py` 中加入统一动画心跳**

```python
_last_animation_tick = time.monotonic()

if now - _last_animation_tick >= 0.25:
    state.animation_tick += 1
    _sync_orchestration_entry(state)
    throttled.request()
    _last_animation_tick = now
```

- [ ] **Step 4: 用动画 tick 驱动 buddy 帧和 orchestration spinner**

```python
def render_buddy_block(*, species: str, animation_tick: int) -> str:
    frame = get_buddy_frame(species, animation_tick)
    return "\n".join(frame)

_SPINNER_FRAMES = ("◜", "◠", "◝", "◞", "◡", "◟")
spinner = _SPINNER_FRAMES[entry.animationFrame % len(_SPINNER_FRAMES)]
```

- [ ] **Step 5: 运行测试并确认多帧动态效果通过**

Run: `python -m pytest tests/test_tui.py tests/test_tty_app.py -q`

Expected: buddy/orchestration 动态测试通过

- [ ] **Step 6: Commit**

```bash
git add src/astrid/tui/buddy.py src/astrid/tui/transcript.py src/astrid/ui/full/tty_app.py tests/test_tui.py tests/test_tty_app.py
git commit -m "feat: animate buddy and orchestration progress"
```

---

### 任务 6：统一首页橙色主题与轻底栏

**Files:**
- Modify: `src/astrid/tui/chrome.py`
- Modify: `src/astrid/tui/input.py`
- Test: `tests/test_tui.py`

- [ ] **Step 1: 先写橙色主题关键文本的失败测试**

```python
def test_render_welcome_workbench_uses_orange_branding_copy() -> None:
    rendered = render_welcome_workbench(...)
    assert "Welcome back" in rendered
    assert "Tips for getting started" in rendered
```

- [ ] **Step 2: 运行测试，确认 welcome 文案/布局仍不稳定**

Run: `python -m pytest tests/test_tui.py -q`

Expected: 新增 welcome 主题测试失败或不完整

- [ ] **Step 3: 在 `chrome.py` 中统一 welcome theme token**

```python
WELCOME_ORANGE = "\x1b[38;5;208m"
WELCOME_ORANGE_DIM = "\x1b[38;5;209m"
WELCOME_TEXT_MUTED = "\x1b[38;5;245m"
WELCOME_BORDER = "\x1b[38;5;209m"
```

- [ ] **Step 4: 调整输入区与底栏文案风格，使 idle 页更像 Claude Code**

```python
def render_idle_footer(mode: str, effort: str, permission_mode: str) -> str:
    return f"{WELCOME_TEXT_MUTED}{permission_mode}{RESET}  ·  {effort}  ·  {mode}{RESET}"
```

- [ ] **Step 5: 运行测试并确认 welcome 风格转绿**

Run: `python -m pytest tests/test_tui.py -q`

Expected: theme/welcome 相关测试通过

- [ ] **Step 6: Commit**

```bash
git add src/astrid/tui/chrome.py src/astrid/tui/input.py tests/test_tui.py
git commit -m "feat: add orange welcome shell theme"
```

---

### 任务 7：最终验证与手工自测

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-04-17-dynamic-multi-agent-tui-design.md`
- Modify: `docs/superpowers/plans/2026-04-17-claude-code-like-welcome-workbench.md`

- [ ] **Step 1: 跑完整回归测试**

Run: `python -m pytest tests/test_orchestration.py tests/test_tui.py tests/test_agent_loop.py tests/test_tty_app.py tests/test_mock_model.py -q`

Expected: `... all selected tests pass ...`

- [ ] **Step 2: 跑语法检查**

Run: `python -m py_compile src/astrid/tui/buddy.py src/astrid/tui/chrome.py src/astrid/tui/transcript.py src/astrid/ui/full/tty_app.py src/astrid/cli/cli_commands.py`

Expected: 无输出、退出码 0

- [ ] **Step 3: 手工启动 mock 模式检查 welcome 首页**

Run: `python -X utf8 -m astrid.main`

Expected:
- 默认看到 orange workbench
- 左侧是 buddy 和 welcome 文案
- 右侧是 tips / recent activity
- 输入 `/pet next` 后 species 切换
- 输入普通自然语言后切到 work view

- [ ] **Step 4: 自查 spec 对齐**

Checklist:
- 仅重做 idle welcome shell，不推翻 active transcript 主流
- 18 个 buddy species 已全部接入
- 多帧 buddy 和 orchestration progress 均可见
- 宠物不常驻工作态

- [ ] **Step 5: 更新 README 的能力说明**

```markdown
- Claude-Code-like orange welcome workbench for idle sessions
- 18-species animated buddy system with slash-command control
- Dynamic orchestration progress for multi-agent work view
```

- [ ] **Step 6: Commit**

```bash
git add README.md docs/superpowers/specs/2026-04-17-dynamic-multi-agent-tui-design.md docs/superpowers/plans/2026-04-17-claude-code-like-welcome-workbench.md
git commit -m "docs: add welcome workbench implementation plan"
```

---

## 自检

### Spec Coverage

- welcome workbench 双栏首页：任务 2、3、6
- idle/work 视图切换：任务 3
- 18 个 buddy species：任务 1
- 多帧 idle/fidget/blink：任务 1、5
- `/pet` 系列命令：任务 4
- 橙色 shell 主题：任务 2、6
- orchestration 动态进度继续保留并增强：任务 5

### Placeholder Scan

- 未使用 `TODO` / `TBD`
- 每个任务都给了精确文件、测试入口和命令
- 每个实现步骤都给了最小代码骨架

### Type Consistency

- welcome 页统一使用 `buddy_*` 命名，避免和旧 `companion_*` 混用
- 动画统一使用 `animation_tick` / `animationFrame`
- 视图切换统一使用 `welcome view` / `work view`

---

Plan complete and saved to `docs/superpowers/plans/2026-04-17-claude-code-like-welcome-workbench.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
