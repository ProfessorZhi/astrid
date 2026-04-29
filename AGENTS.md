# Astrid Agent 工作准则

这个文档是后续 agent 改进 Astrid 时必须先读的工作总账。它记录当前项目真实状态、术语边界、剩余差距和本地测试规范。

## 第一性原则

- 先看本地代码，再做判断。不要只凭 Codex、Claude Code、学习网站或旧印象类比。
- 把 Astrid 当成一个已经存在的 coding-agent runtime，而不是从零开始的原型。它已经有 tools、permissions、sessions、memory、MCP、sub-agents、orchestration 和 TUI。
- 每个 PR 只做一个可验证闭环。不要把 runtime 重写、元数据清理、无关重构混在一起。
- 不要回滚用户或其他 agent 在别的分支/worktree 上的改动。文件不在你的任务边界内，就不要碰。
- 遇到问题先追根因，不做“看起来能缓解”的补丁。每个决策都要能回答为什么。

## 当前状态总账

原先对比 Codex / Claude Code 得出的六个差距，Astrid 已经完成第一轮产品化改进：

1. **TUI 性能和 shell 体验**
   - 已实现：transcript 缓存/窗口化渲染、行级 diff writer、Windows/Codex 内置终端默认 shell/native scrollback、recent 历史乱码过滤、小窗口 welcome 顶部显示修复。
   - 仍剩：继续拆 `tty_app.py`，把 renderer、input、status、transcript viewport 分离。拆分必须保持 prompt/footer pinned-bottom 行为。

2. **权限和沙箱治理**
   - 已实现：权限 policy snapshot、permission tests、更清楚的权限边界说明。
   - 仍剩：Astrid 当前仍是 policy-only，不是 OS sandbox。没有真实进程/文件系统隔离前，不要说它达到 Codex 级 sandbox。

3. **多 Agent runtime**
   - 已实现：worker lifecycle summary、failed/cancelled/reporting 状态、orchestration 相关测试。
   - 仍剩：更产品化的调度、可配置 worker roles、更强的结果合成，需要单独 PR 和单独测试。

4. **任务中 Steering**
   - 已实现：`queued next turn` 和 `steer current turn` 已经在第一版队列模型里区分。
   - 仍剩：当前 steering 是 interrupt-and-replan 风格，不是 mid-token injection。不要把它描述成复杂的实时 token 注入。

5. **Context / Memory 长会话稳定性**
   - 已实现：compact anchor 测试、active task preservation 检查。
   - 仍剩：长 live session 的 resume / compact 压力测试还需要用真实 transcript 验证。

6. **仓库可信度**
   - 已实现：AGENTS 指南、metadata 清理、本地 artifact ignore、CLI smoke 覆盖、临时分支/worktree 清理。
   - 仍剩：README、benchmark、功能声明必须绑定可复现命令，避免留下过期数字或夸张描述。

## 术语边界

- 不要把 Astrid 的扩展面叫成完整 plugin system，除非项目真的有 plugin manifest / loader / package flow。当前实际扩展面是 skills、MCP、hooks。
- 不要把 busy 时的输入排队叫 steering。Steering 指改变或打断当前正在执行的任务。
- 不要说 Astrid 只是 single-agent。它已经有 sub-agents 和 orchestration；差距在于产品级 runtime 行为。
- 不要说 Astrid 是 zero-dependency；`pyproject.toml` 已经列出运行时依赖。
- 不要把非 TTY 管道测试等同于真实 TUI 交互测试。管道模式无法弹出交互式权限确认。

## 本地 Coding Agent 评测规范

- 本地验证资产统一放在 `verification/`，该目录被 Git 忽略，不上传 GitHub。
- 不同 agent 按目录分开：
  - `verification/astrid/<日期-测试名>/`
  - `verification/codex/<日期-测试名>/`
  - `verification/claudecode/<日期-测试名>/`
- 每次测试目录应包含：
  - `workspace/`：隔离任务工作区。
  - `run_eval.*`：评测脚本或启动命令。
  - `*-transcript.txt`：终端/模型输出记录。
  - 可选 notes：记录 pass/fail、失败原因、二轮修复情况。
- 当前 Astrid 真实模型编程能力评测在：`verification/astrid/2026-04-29-real-model-coding-eval/`。
- 用 stdin 管道测试 Astrid 时要注意：这是 non-TTY 模式，写文件/改文件不会弹权限确认。除非临时把目标文件加入 `~/.astrid/permissions.json` 的 `allowedEditPatterns`，否则写入会失败。
- 临时预授权必须测试后恢复。原来没有 `permissions.json` 就删回不存在；原来有文件就恢复原始内容。
- 判断 coding ability 不要只看 assistant 文本。必须在 agent 之外跑 pytest 或验收脚本，并记录真实 pass/fail 输出。

## 验证默认命令

- TUI 改动：`python -m pytest tests/test_screen.py tests/test_tty_app.py tests/test_tui.py -q`
- 多 Agent 改动：`python -m pytest tests/test_orchestration.py tests/test_sub_agents.py -q`
- Context / memory / session 改动：先跑窄测试，再跑 `python -m pytest tests -q -k "context or memory or session"`
- 文档 / metadata 改动：`python -m pytest tests/test_cli_commands.py tests/test_screen.py -q`
- 真实 coding-agent 评测：在 `verification/<agent>/...` 下新建 run，保存 transcript，然后在 agent 外部运行 workspace 的验收测试。
