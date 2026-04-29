# Astrid Agent 工作总账

这个文档是后续 agent 改进 Astrid 时必须先读的项目总账。它记录 Astrid 当前工作流、已完成进度、后续功能路线图、本地评测规范和验证命令。

## 第一性原则

- 先看本地代码，再做判断。不要只凭 Codex、Claude Code、学习网站或旧印象类比。
- 把 Astrid 当成一个已经存在的 coding-agent runtime，而不是从零开始的原型。它已经有 tools、permissions、sessions、memory、MCP、sub-agents、orchestration 和 TUI。
- 每个 PR 只做一个可验证闭环。不要把 runtime 重写、元数据清理、无关重构混在一起。
- 不要回滚用户或其他 agent 在别的分支/worktree 上的改动。文件不在你的任务边界内，就不要碰。
- 遇到问题先追根因，不做“看起来能缓解”的补丁。每个决策都要能回答为什么。

## 参考源码和资料

后续改 Astrid 时，必须多参考 Claude Code 和 Codex 的真实实现，不要只凭产品印象或二手总结下判断。

- Codex 官方源码：`https://github.com/openai/codex`
- Claude Code TypeScript 源码本地路径：`F:\agent_project\codingagent\claudecodes\claudecodets`
- Claude Code 学习网站：`https://claudecn.com/`
- Claude Code 代码学习站：`https://code.claudecn.com/`

参考方式：

- 做 TUI 时，要重点参考本地 Claude Code TypeScript 源码里的终端 UI 组织方式，尤其是输入区、transcript、状态区、滚动、copy-friendly 行为和组件边界；同时参考 Codex 的 Rust/Ratatui 分层来理解 renderer/runtime 纪律。
- 做 runtime/权限/sandbox/headless exec/MCP 时，优先看 Codex 的 Rust CLI/runtime 分层。
- 做 agent loop、Todo、Subagent、Skills、Hooks、Memory、Steering、权限模式时，优先看本地 Claude Code TypeScript 源码和 Claude Code 学习站。
- 做 Astrid 代码改动前，先定位 Astrid 当前对应模块，再查参考项目里相近模块。结论必须写清楚“本地 Astrid 现状是什么、参考项目怎么做、这次只借鉴哪一部分”。
- 不要把参考项目的概念照搬成 Astrid 已实现能力。比如 Astrid 当前只有 skills/MCP/hooks 等扩展面，不要直接称为完整 plugin system；当前 steering 是 interrupt-and-replan，不要说成复杂 mid-token 注入。
- 如果参考资料来自网页，结论要标注来源 URL；如果来自本地 Claude Code 源码，结论要标注本地文件路径。

## 当前工作流

- 默认在 `master` 上保持可运行、可测试、可推送状态。
- 大功能先拆独立分支或 worktree；同一轮不要让多个 agent 同时大改 `astrid/tty_app.py`。
- 修改代码前先补能复现问题的测试；修改后跑窄测试，再按风险跑全量测试。
- 本地验证结果放在 `verification/`，该目录被 Git 忽略，不上传 GitHub。
- 做 coding-agent 横向对比前，必须先问用户要和谁对比。默认优先建议 Claude Code，因为本机可在终端输入 `claude` 运行，且接入 MiniMax，成本更低；Codex 可作为对比项，但成本更高。
- 横向对比时，Astrid、Claude Code、Codex 必须使用同一组 prompt、同一套初始 workspace、同一套外部验收命令。
- 所有测试 prompt、初始文件、agent 产物、transcript、pytest/验收输出，都必须保存到对应的 `verification/<agent>/<run-name>/` 目录。
- 评测目录命名要短，并同时包含英文和中文含义：suite 用 `snake-贪吃蛇` 这种名字；agent run 用 `YYYY-MM-DD-snake-贪吃蛇` 这种名字。
- 评测结论必须区分“第一轮结果”和“多轮修复后结果”。第一轮失败就是第一轮失败；如果二轮通过，要记录二轮修复过程，不能混成一次通过。
- 严格评测禁止把“改写验收测试后 pytest 通过”算作通过。除非 suite 明确允许改测试，否则 agent 修改、删除、弱化原始验收测试都算失败。
- 完成一个可验证闭环后再 commit / push。不要把临时验证目录、transcript、缓存文件提交进仓库。

## 当前进度

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

## 后续功能路线图

后续不要平均用力，优先做能被真实评测验证的功能。

1. **真实 coding-agent eval harness**
   - 目标：把 `verification/astrid/2026-04-29-real-model-coding-eval/` 里的临时脚本沉淀成可复用本地评测模板。
   - 要做：支持多任务、多轮失败反馈、权限临时预授权/恢复、transcript 保存、pytest 验收、结果摘要。
   - 验收：一条命令能生成新 run 目录，并输出每个任务 pass/fail、耗时、失败原因。

2. **非 TTY / 自动化审批模式**
   - 目标：让 Astrid 可以安全地做无人值守 coding eval，而不是靠手工改 `~/.astrid/permissions.json`。
   - 要做：增加显式 eval/auto approval 模式，只允许当前 eval workspace 内的文件编辑，并默认拒绝 workspace 外路径和危险命令。
   - 验收：管道输入真实 prompt 时，可以写 eval workspace 内目标文件；越界写入必须失败并有测试覆盖。

3. **TUI runtime 拆分**
   - 目标：降低 `tty_app.py` 复杂度，继续接近 Codex/Claude Code 的组件化 TUI runtime。
   - 要做：拆出 renderer、input box、status/progress、transcript viewport、screen writer。
   - 验收：现有 TUI 测试全绿；长 transcript 下普通输入不触发全量 transcript render；prompt/footer 仍 pinned-bottom。

4. **中文输出编码修复**
   - 目标：修复真实模型 transcript 中中文 assistant 输出 mojibake 的问题。
   - 要做：定位是模型响应解码、stdout encoding、PowerShell 捕获、还是 transcript 写入链路导致。
   - 验收：中文 prompt 后 stdout 和 transcript 都保留正常中文；新增 Windows 编码回归测试。

5. **测试驱动的 agent loop**
   - 目标：让 Astrid 更像 coding agent，而不是只按 prompt 修改一次文件。
   - 要做：在模型策略和工具提示中强化“先读测试、改代码、运行测试、根据失败继续修”的闭环。
   - 验收：真实 eval 中需要二轮修复的任务比例下降；失败时 transcript 能清楚显示测试失败和修复依据。

6. **多 Agent 执行产品化**
   - 目标：让多 agent 不只是结构存在，而能稳定分工、汇总、失败恢复。
   - 要做：任务拆分策略、worker 结果合并、失败 worker 重试/降级、review agent 汇总。
   - 验收：新增多 agent eval，覆盖并行读代码、单 worker 改文件、review worker 验证，最终外部测试通过。

7. **Context / Memory 长会话评测**
   - 目标：验证长会话、compact、resume 后仍保留当前任务和关键工具结果。
   - 要做：构造长 transcript、本地 resume、compact 前后继续同一 coding task。
   - 验收：compact/resume 后能继续完成任务；不会忘记目标文件、失败测试和用户最新约束。

8. **权限 / 沙箱第二阶段**
   - 目标：从 policy-only 走向更强隔离，但不要直接承诺 Codex 级 sandbox。
   - 要做：先定义 Windows 下可落地的最小隔离策略，例如 workspace allowlist、命令 denylist、危险命令强制确认。
   - 验收：越界文件读写、危险命令、未知命令都有清晰测试和用户提示。

9. **README 和 benchmark 对齐**
   - 目标：公开文档可信，不夸大、不滞后。
   - 要做：把功能声明和本地验证命令绑定，标注哪些是已实现、实验性、计划中。
   - 验收：README 中的核心命令可跑；性能/能力数字都有对应脚本或 transcript。

## 术语边界

- 不要把 Astrid 的扩展面叫成完整 plugin system，除非项目真的有 plugin manifest / loader / package flow。当前实际扩展面是 skills、MCP、hooks。
- 不要把 busy 时的输入排队叫 steering。Steering 指改变或打断当前正在执行的任务。
- 不要说 Astrid 只是 single-agent。它已经有 sub-agents 和 orchestration；差距在于产品级 runtime 行为。
- 不要说 Astrid 是 zero-dependency；`pyproject.toml` 已经列出运行时依赖。
- 不要把非 TTY 管道测试等同于真实 TUI 交互测试。管道模式无法弹出交互式权限确认。

## 本地 Coding Agent 评测规范

- 本地验证资产统一放在 `verification/`，该目录被 Git 忽略，不上传 GitHub。
- 不同 agent 按目录分开：
  - `verification/suites/<英文-中文测试名>/`
  - `verification/astrid/<日期-英文-中文测试名>/`
  - `verification/claudecode/<日期-英文-中文测试名>/`
  - `verification/codex/<日期-英文-中文测试名>/`
- 命名示例：
  - `verification/suites/snake-贪吃蛇/`
  - `verification/astrid/2026-04-29-snake-贪吃蛇/`
  - `verification/claudecode/2026-04-29-snake-贪吃蛇/`
- 如果用户没有指定对比对象，先询问。推荐顺序：Claude Code 优先，Codex 其次。
- Claude Code 测试方式：在终端输入 `claude` 运行。当前本机 Claude Code 接入 MiniMax，成本相对低，适合作为默认横向对比对象。
- Codex 测试方式：使用 Codex 终端/CLI 运行同样任务。Codex 成本更高，只有用户确认需要对比时再跑。
- 每次测试目录应包含：
  - `prompts/`：保存实际输入给 agent 的 prompt，不能只写摘要。
  - `workspace/`：隔离任务工作区和 agent 修改后的产物。
  - `run_eval.*`：评测脚本或启动命令。
  - `*-transcript.txt`：终端/模型输出记录。
  - `results.*` 或 notes：记录 pass/fail、失败原因、二轮修复情况、验收命令输出。
- 当前 Astrid 真实模型编程能力评测在：`verification/astrid/2026-04-29-coding-basic-编程基础/`。
- 当前 Astrid vs Claude Code 贪吃蛇对比评测在：`verification/astrid/2026-04-29-snake-贪吃蛇/` 和 `verification/claudecode/2026-04-29-snake-贪吃蛇/`。
- 贪吃蛇这一轮的记录口径：Astrid 第一轮严格失败；二轮后 pytest 可过，但改写了验收测试，所以严格结果仍是失败。Claude Code 第一轮被预算截断，二轮后保留原验收测试并通过。
- 用 stdin 管道测试 Astrid 时要注意：这是 non-TTY 模式，写文件/改文件不会弹权限确认。除非临时把目标文件加入 `~/.astrid/permissions.json` 的 `allowedEditPatterns`，否则写入会失败。
- 临时预授权必须测试后恢复。原来没有 `permissions.json` 就删回不存在；原来有文件就恢复原始内容。
- 判断 coding ability 不要只看 assistant 文本。必须在 agent 之外跑 pytest 或验收脚本，并记录真实 pass/fail 输出。

## 验证默认命令

- TUI 改动：`python -m pytest tests/test_screen.py tests/test_tty_app.py tests/test_tui.py -q`
- 多 Agent 改动：`python -m pytest tests/test_orchestration.py tests/test_sub_agents.py -q`
- Context / memory / session 改动：先跑窄测试，再跑 `python -m pytest tests -q -k "context or memory or session"`
- 文档 / metadata 改动：`python -m pytest tests/test_cli_commands.py tests/test_screen.py -q`
- 真实 coding-agent 评测：在 `verification/<agent>/...` 下新建 run，保存 prompt、workspace、产物、transcript、验收结果，然后在 agent 外部运行 workspace 的验收测试。
