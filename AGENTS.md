# Astrid Agent 工作总账

运行时约束：Astrid 会读取项目内 `AGENTS.md` 作为项目指令链路，从 git root 到当前工作目录逐层读取，越靠近当前目录越具体。长期项目约束写进 `AGENTS.md`，不要为了记规则继续在项目根创建散乱的 `.astrid*` 状态目录。

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
- Codex 本地源码：`F:\agent_project\codingagent\codex\codex`
- Claude Code TypeScript 本地源码：`F:\agent_project\codingagent\claudecodes\claudecodets\claudecodets`
- Claude Code 学习网站：`https://claudecn.com/`
- Claude Code 代码学习站：`https://code.claudecn.com/`

参考方式：

- 做权限、自动化测试、TUI 重构前，必须先看本地 Codex 和 Claude Code 对应源码；不要只凭产品印象下判断。
- 做 TUI 时，重点参考 Codex 的 inline viewport/bottom pane 分层，以及 Claude Code 的 Ink/PromptInput 组件边界。
- 做 runtime、权限、sandbox、headless exec、MCP、自动化 eval 时，优先参考 Codex 本地源码；做 agent loop、Todo、Subagent、Skills、Hooks、Memory、Steering、权限模式时，同时参考 Claude Code 本地源码。
- 做 Astrid 代码改动前，先定位 Astrid 当前对应模块，再查参考项目里相近模块。结论必须写清楚“本地 Astrid 现状是什么、参考项目怎么做、这次只借鉴哪一部分”。
- 不要把参考项目的概念照搬成 Astrid 已实现能力。比如 Astrid 当前只有 skills/MCP/hooks 等扩展面，不要直接称为完整 plugin system；当前 steering 是 interrupt-and-replan，不要说成复杂 mid-token 注入。
- 如果参考资料来自网页，结论要标注来源 URL；如果来自本地 Claude Code 源码，结论要标注本地文件路径。

## 当前工作流

- 默认在 `master` 上保持可运行、可测试、可推送状态。
- 大功能先拆独立分支或 worktree；同一轮不要让多个 agent 同时大改 `astrid/tty_app.py`。
- 修改代码前先补能复现问题的测试；修改后跑窄测试，再按风险跑全量测试。
- 本地验证结果放在 `verification/`，该目录被 Git 忽略，不上传 GitHub。
- 保持仓库根目录干净。不要把截图、浏览器日志、临时 transcript、HTTP server 日志、pid、下载的临时 exe、playwright/mcp 临时状态、pytest cache 或手动测试输出散落在根目录；评测证据必须进入对应 `verification/runs/.../{artifacts,acceptance,transcripts}/`，零散 smoke 记录进入 `verification/ad-hoc-smoke/`，纯缓存直接清理或加入 `.gitignore`。`tests/` 是正式 pytest 测试目录，临时权限/手动读写测试不要写进 `tests/`，应使用 `test/`、`scratch/` 或 run workspace，并在结束后清理。
- 点号目录必须有明确归属：`.git/` 是版本库，不能动；`.astrid/`、`.astrid-memory/` 是 Astrid 本地状态，只有确认不再需要对应 skill/memory 时才清；`.superpowers/` 是本地 Superpowers 工作状态，可按需清理但不要提交；`.playwright-mcp/`、`.pytest_cache/`、`__pycache__/`、空的工具状态目录和 `.tmp*` 属于可清理缓存。不要新建来源不明的点号目录；如果工具自动生成，结束时判断是状态、证据还是缓存，并按本条归位或删除。
- Astrid skills 采用 Codex 风格的入口/实体分离：默认实体目录是 `F:\funnyskills\astrid-skills`，`C:\Users\Administrator\.astrid\skills` 只是指向它的用户入口链接；`ASTRID_SKILLS_ROOT` 可显式覆盖。不要再把新 skill 写到项目根 `.astrid/skills`；发现旧项目 `.astrid/skills` 时只作为迁移来源，迁到默认 skills 实体目录后备份旧目录。
- 做 coding-agent 横向对比前，必须先问用户要和谁对比。默认优先建议 Claude Code，因为本机可在终端输入 `claude` 运行，且接入 MiniMax，成本更低；Codex 可作为对比项，但成本更高。
- 横向对比里的 Codex 当前默认是**评测主持人**，不是被测 agent。Codex 负责设计 suite、写第一轮 prompt、准备 seed workspace / acceptance、把同一题投给各被测 agent、监督各轮产物、基于真实失败输出写下一轮修复 prompt、验收和总结；被测 agent 必须由 Astrid、Claude Code、Codex CLI 等各自真实终端会话执行。
- 真实 coding-agent 评测默认使用 Codex 桌面内置终端运行被测 agent，不要默认用外部 PowerShell/Windows Terminal 窗口。内置终端更容易保留当前 workspace、减少焦点污染，并方便 Codex 在旁边验收。
- 除非用户明确要求“自动化跑 agent”或“测试非 TTY/eval 模式”，不要用 Codex 通过 stdin 管道、脚本或 API 代替 Astrid / Claude Code 执行编程任务。真实编程能力评测应在内置终端打开对应 agent，把同一份 prompt 原文交给被测 agent。
- 不要用 `Start-Process` + `SendKeys`、窗口标题匹配、剪贴板焦点抢占等外部窗口自动化方式给 Astrid / Claude Code 喂 prompt。这会把“窗口焦点是否正确”混进评测，甚至污染当前 Codex 会话；如需便捷执行，只能生成 `run-round-XX.ps1` 这类内置终端辅助脚本，让人或当前终端明确粘贴。
- Codex 可以也应该按轮次主动主持评测：每轮把对应 `prompts/round-XX.md` 原文交给被测 agent，等待该轮完成后检查 `workspace/`、保存 transcript、跑外部验收、试玩或截图，再决定是否生成下一轮 prompt。不要把“Codex 不写答卷”误解成“Codex 不推进流程”。
- 如果用户明确让 Codex 客户端自己作为被测对象完成题目，Codex 客户端也必须使用独立的 `verification/runs/codex-client/<model>/<run>/` 交作业文件夹，并按普通 agent run 标准保存每轮 `prompts/round-XX.md`、workspace、验收输出、截图和 `results.md`。不能因为答卷来自当前聊天会话，就只写摘要或省略二轮/三轮提示词。
- 对浏览器类产物，Codex 主持验收时应优先使用 Codex 桌面内置浏览器做辅助验收。小游戏、网页、工具页、仪表盘等都要尽量打开真实页面，模拟人类点击、输入、键盘、鼠标、窗口缩放和截图；但浏览器辅助验收不能完全代替人工评分，尤其是游戏手感、审美、信息架构和产品判断。
- 横向对比时，Astrid、Claude Code、Codex 必须使用同一组 prompt、同一套初始 workspace、同一套外部验收命令。
- 所有测试 prompt、初始文件、agent 产物、transcript、pytest/验收输出，都必须保存到对应的 `verification/runs/<agent-platform>/<model>/<run-name>/` 目录。
- 建任何 `verification/runs/<agent-platform>/<model>/<run-name>/` 目录前，必须先确认被测 agent 当前真实模型，不能沿用上一次评测的旧模型目录名。Astrid 先启动后运行 `/model` 或 `/status`；Claude Code 先看启动页 model 行，如本地版本支持 `/model` 则优先运行 `/model`；Codex 客户端/CLI 记录顶部或启动信息显示的模型。当前如果用户已经切到 mimo，就必须用 `mimo` 作为 `<model>` 层，不要再建到 `minimax2.7`。
- 轻量 suite/run 骨架优先用 `python scripts/create_eval_run.py suite <suite>` 和 `python scripts/create_eval_run.py run <suite> --platform <platform> --model <model> --run-name <run> --model-confirmed --model-source "<如何确认模型>"` 创建。该脚本只复制 `seed-workspace/` 并生成 prompts、instructions、evaluation、comparison/results 模板；不要把它当作自动跑 agent 或自动验收工具。CLI 模式下缺少 `--model-confirmed` 必须拒绝创建 run。
- 评测目录命名要短，并同时包含英文和中文含义：suite 用 `snake-贪吃蛇` 这种名字；agent run 用 `YYYY-MM-DD-snake-贪吃蛇` 这种名字。平台和模型不要揉进 run 名字里，要放在上层目录。
- 评测材料默认中文优先。suite 里的题目说明、要求、验收标准、首轮 prompt、评分口径必须优先写中文；必要时可以保留英文标题或术语辅助识别。
- run 里的 `results.md`、`instructions.md`、人工试玩记录、失败原因和结论默认中文优先。真正发给 agent 的 prompt 和 transcript 是证据材料，原则上保留原文；如需要中文可另加说明或翻译文件，不要覆盖历史证据。
- 评测结论必须区分“第一轮结果”和“多轮修复后结果”。第一轮失败就是第一轮失败；如果二轮通过，要记录二轮修复过程，不能混成一次通过。
- 严格评测禁止把“改写验收测试后 pytest 通过”算作通过。除非 suite 明确允许改测试，否则 agent 修改、删除、弱化原始验收测试都算失败。
- 完成一个可验证闭环后再 commit / push。不要把临时验证目录、transcript、缓存文件提交进仓库。
- 结束评测或浏览器验收前先做根目录清洁检查：`Get-ChildItem -Force` 和 `git status --short --ignored`。发现根目录有新 PNG/TXT/LOG/YML/cache/temp 文件时，先判断是证据还是缓存：证据归入 `verification/` 对应子目录，缓存删除，不能留给下一个 agent 猜用途。

## 当前进度

原先对比 Codex / Claude Code 得出的六个差距，Astrid 已经完成第一轮产品化改进：

1. **TUI 性能和 shell 体验**
   - 已实现：transcript 缓存/窗口化渲染、行级 diff writer、Windows/Codex 内置终端默认 shell/native scrollback、recent 历史乱码过滤、小窗口 welcome 顶部显示修复；包内重组后 `tty_app` 已归入 `src/astrid/ui/full/`，普通 full TUI 模型回合已通过 `RuntimeController.execute_agent_turn(...)` 执行，多 agent 分支的 permission turn 也通过 `RuntimeController` 包住。
   - 仍剩：继续拆 `src/astrid/ui/full/tty_app.py` 的 renderer、input、status、transcript viewport。拆分必须保持 prompt/footer pinned-bottom 行为；多 agent orchestration 的 worker 执行和结果合成还要继续收拢到 runtime/controller。

2. **权限和沙箱治理**
   - 已实现：权限 policy snapshot、permission tests、更清楚的权限边界说明；四档权限模式 `default`、`accept-edits`、`eval-workspace`、`bypassPermissions` 已进入 runtime/permission 层，并支持 CLI 参数和环境变量选择。
   - 仍剩：Astrid 当前仍是 policy-only，不是 OS sandbox。没有真实进程/文件系统隔离前，不要说它达到 Codex 级 sandbox；后续要做的是更强隔离和更细的命令策略，不是重复实现四档模式。

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

## 2026-05-01 交付列车进度

- 已完成：默认 inline TUI 恢复共享 welcome pet；inline 权限请求显示数字选择面板；inline progress/tool status 通过回调节流到当前状态行，避免重复刷 prompt。
- 已完成：inline TUI 第一轮视觉打磨，新增 inline 专用多色渲染层，区分 prompt、assistant、status、tool、success/error、permission，并修复 inline 状态符号乱码。
- 已完成：full TUI 开始物理拆分，已抽出 `ui/full/renderer.py`、`input_box.py`、`viewport.py`、`status.py`、`writer.py`、`state.py`、`tool_progress.py`、`approval.py`；`tty_app.py` 仍是 orchestrator，后续继续缩小。
- 已完成：权限第二阶段的最小 policy-only 增强，新增 `ASTRID_WORKSPACE_ALLOWLIST`，并继续在 `eval-workspace` 中拒绝危险命令。
- 已完成：评测 harness 增加 acceptance 执行、`metrics.json`、transcript 字节数、轮次、源码行数/字节数、`token_usage: 未采集` 等成本代理。
- 已完成：CLI smoke 显式用 UTF-8 捕获输出，避免 Windows GBK reader warning；新增中文/长会话相关回归。
- 已完成：系统 prompt 强化 coding loop：先读测试、改代码、运行聚焦测试、失败继续修，不能把失败测试当完成。
- 仍剩：full TUI 多 agent worker 编排和结果合成还未收进 runtime/controller；inline 还不是完整 Codex Rust TUI 级别的 rich bottom pane；Astrid 仍是 policy-only，不是 OS sandbox。

## Astrid 近期重点

近期进入项目结构正规化阶段。第一、二阶段已经先在包内理清 runtime 和 UI 前端边界；第三阶段采用标准 `src/astrid` 布局，避免根目录源码包和测试/临时状态混在一起。

重组顺序固定为：`runtime/controller` → UI frontends → Codex-style inline TUI → Claude-style full TUI。不要继续把 runtime、权限、session、输入、渲染和 shell fallback 都塞进 `main.py` 或 `tty_app.py`。

第二阶段目标是瘦身 `main.py` 和形成四条前端边界：`shell`、`pipe`、`inline`、`full`。`main.py` 只保留 argparse、管理命令分发、终端模式选择、frontend dispatch 和 shutdown cleanup；runtime 初始化进入 `astrid/runtime/bootstrap.py`，pipe 输入进入 `astrid/ui/shell/pipe.py`，banner/quick start 进入 `astrid/ui/shell/banner.py`。

第三阶段已经把根部主体收敛到标准边界：`agent_loop/poly_commands` 进入 `core`，`advanced_memory` 进入 `state`，`permissions/auto_mode` 进入 `runtime`，`tty_app` 进入 `ui/full`。`src/astrid/` 根部只保留 `main.py` 和 `__init__.py`；不要再把功能模块加回根部。

第三阶段后续已经把项目内部 import 改到新路径，并删除根部兼容 shim。普通 full TUI turn 执行也已从 `src/astrid/ui/full/tty_app.py` 收拢到 `RuntimeController.execute_agent_turn(...)`；full TUI 现在只提供渲染和回调，不应再直接调用 `run_agent_turn`。多 agent 分支暂时仍在 full TUI 内编排 worker，但 permission turn 已经通过 `RuntimeController` 进入 runtime 边界。后续不要为了短期方便重新在 `src/astrid/` 根部添加 shim；如果确实需要外部兼容层，要单独说明 public API 兼容目标和删除计划。

目标边界：

- `src/astrid/core/`：agent loop、prompt、context、sub-agents、orchestration 等核心能力。
- `src/astrid/runtime/`：统一 controller、turn runner、事件模型、permission flow、queue/steer 协调。
- `src/astrid/ui/`：`shell/`、`inline/`、`full/` 三个终端前端，`common/` 放共享输入、approval、transcript 辅助。
- `src/astrid/ui/common/frontend.py` 定义三前端共享的最小 frontend contract。权限模式、turn 执行、history、transcript、steer/queue 应保持在 `RuntimeController` 和 runtime 层；不要在 shell、inline、full 三个前端各自复制权限逻辑。full TUI 普通模型回合已经走 `RuntimeController.execute_agent_turn(...)`，后续新增权限模式必须先改 runtime/controller，再让各前端只渲染对应状态。
- `src/astrid/cli/`：slash commands、management commands、installer 等命令行入口辅助。
- `src/astrid/state/`：session、history、memory、advanced memory 等持久状态。
- `src/astrid/integrations/`：Anthropic adapter、MCP、skills、hooks 和外部 provider。
- `src/astrid/tools/`：暂时保留原位，后续单独整理工具注册和工具实现。

近期不要平均用力，优先做三件事：继续打磨 inline TUI、产品化自动化测试、拆分 full TUI。每件事开工前都要先对照本地 Codex 和 Claude Code 源码。

1. **权限模式 / eval-workspace**
   - 已实现四档权限模式：`default`、`accept-edits`、`eval-workspace`、`bypassPermissions`。
   - `default`：交互确认，真实 TTY 使用默认模式。
   - `accept-edits`：自动允许当前 workspace 内文件编辑；命令仍按规则确认。
   - `eval-workspace`：自动允许当前 workspace 内读写文件和常见开发命令；拒绝 workspace 外写入，拒绝明显危险命令；作为 Astrid eval 推荐默认模式。
   - `bypassPermissions`：明确高风险模式，只给本机开发者手动启动使用；banner 和 transcript 必须醒目标记。
   - 后续剩余：补更多真实 TTY 文案 smoke、把命令 allowlist 做得更细、探索 Windows 下可落地的 OS 级隔离。不要把当前 policy-only 模式说成 Codex 级 sandbox。

2. **自动化测试 / eval harness 产品化**
   - 已实现：`scripts/create_eval_run.py` 提供轻量 suite/run 骨架创建，复制 seed workspace，生成 prompt/instructions/evaluation/results/comparison 模板，并能执行 suite acceptance、写入 acceptance 输出和 `metrics.json`。
   - 仍剩：真实终端 transcript 自动采集、横向 comparison 表的数据填充、非 TTY / eval-workspace 的自动化执行能力。
   - 同时补上非 TTY / eval-workspace 的自动化执行能力；不要把非 TTY 自动跑混成默认真实终端评测。

3. **TUI 重构**
   - 当前 `tty_app.py` 已开始拆分到 renderer、input box、transcript viewport、status/progress、terminal writer、state dataclasses、输入/粘贴 helper、tool progress helper、approval presenter，但还不是 thin orchestrator。
   - 继续对照 Codex inline viewport/bottom pane 和 Claude Code Ink/PromptInput，优先保持默认 inline 可滚动、可复制、权限面板清楚。
   - 目标是最终拥有稳定 controlled TUI；在此之前默认终端体验必须保持可用、可滚动、可复制。

1. **真实 coding-agent eval harness**
   - 目标：先把“Codex 主持评测闭环，被测 agent 在真实终端写答卷”的人工评测流程产品化，再考虑无人值守自动化。
   - 要做：一键创建 suite/run 目录、复制 seed workspace、保存首轮 prompt、生成内置终端执行说明、按轮记录 transcript、执行外部验收、基于真实失败输出生成下一轮 prompt、汇总第一轮/二轮结果。
   - 验收：一条命令能生成新 run 骨架和明确的内置终端操作说明；Codex 能按轮投 prompt、验收和记录；agent 仍由对应终端真实执行并写答卷。

2. **非 TTY / 自动化审批模式**
   - 目标：让 Astrid 可以安全地做无人值守 coding eval；这是第二阶段能力，不作为真实终端编程能力评测的默认路径。
   - 要做：增加显式 eval/auto approval 模式，只允许当前 eval workspace 内的文件编辑，并默认拒绝 workspace 外路径和危险命令。
   - 验收：管道输入真实 prompt 时，可以写 eval workspace 内目标文件；越界写入必须失败并有测试覆盖。

3. **TUI runtime 拆分**
   - 目标：降低 `tty_app.py` 复杂度，继续接近 Codex/Claude Code 的组件化 TUI runtime。
   - 已完成：`tty_app.py` 已移动到 `src/astrid/ui/full/tty_app.py`；普通 full TUI 模型回合已改为调用 `RuntimeController.execute_agent_turn(...)`，不再直接调用 `run_agent_turn`；多 agent 分支的 permission turn 已改为通过 `RuntimeController` 包装。
   - 已完成：第一批拆出 renderer、input box、status/progress、transcript viewport、screen writer 模块；第二批抽出 full TUI state dataclasses、输入/粘贴 buffer helper、tool progress/collapse helper、approval presenter。
   - 要做：继续把 `tty_app.py` 缩成 thin orchestrator；下一批优先抽 history/session command handlers、多 agent worker 编排和结果合成，逐步改成 runtime-owned flow + UI callback。
   - 验收：现有 TUI 测试全绿；长 transcript 下普通输入不触发全量 transcript render；prompt/footer 仍 pinned-bottom。

4. **中文输出编码修复**
   - 目标：修复真实模型 transcript 中中文 assistant 输出 mojibake 的问题。
   - 要做：定位是模型响应解码、stdout encoding、PowerShell 捕获、还是 transcript 写入链路导致。
   - 已完成：CLI smoke 子进程显式以 UTF-8 捕获 stdout/stderr，避免 Windows GBK reader warning。
   - 验收：中文 prompt 后 stdout 和 transcript 都保留正常中文；后续还要用真实模型 transcript 做手动验证。

5. **测试驱动的 agent loop**
   - 目标：让 Astrid 更像 coding agent，而不是只按 prompt 修改一次文件。
   - 已完成：系统 prompt 已强化“先读测试、改代码、运行测试、根据失败继续修”的闭环。
   - 要做：继续用真实 coding eval 验证是否降低多轮修复和 max tool steps 概率。
   - 验收：真实 eval 中需要二轮修复的任务比例下降；失败时 transcript 能清楚显示测试失败和修复依据。

6. **多 Agent 执行产品化**
   - 目标：让多 agent 不只是结构存在，而能稳定分工、汇总、失败恢复。
   - 要做：任务拆分策略、worker 结果合并、失败 worker 重试/降级、review agent 汇总。
   - 验收：新增多 agent eval，覆盖并行读代码、单 worker 改文件、review worker 验证，最终外部测试通过。

7. **Context / Memory 长会话评测**
   - 目标：验证长会话、compact、resume 后仍保留当前任务和关键工具结果。
   - 已完成：新增 compact 后保存 session、resume 后仍保留最新约束和失败测试的单元测试。
   - 要做：构造真实长 transcript、本地 resume、compact 前后继续同一 coding task 的手动/半自动实测。
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
- 不要把 Codex 自动喂 prompt 给 Astrid / Claude Code 的结果，直接当成真实终端使用体验结论。那测的是自动化链路 + agent 能力的混合结果。
- 不要把外部窗口焦点自动化失败算作 agent 能力失败。若发生误粘贴、焦点错乱、未进入 agent 输入框，应把 transcript 标注为 failed launch / setup failure，并重新用内置终端开始正式轮次。

## 本地 Coding Agent 评测规范

- 本地验证资产统一放在 `verification/`，该目录被 Git 忽略，不上传 GitHub。
- 根目录不是评测暂存区。suite/run 之外的临时输出只允许短暂存在于当前操作过程中；回合结束时必须移动到对应 run 的 `artifacts/`、`acceptance/`、`transcripts/`，或作为一次性缓存删除。不要让 `*.png`、`*.log`、`*-transcript.txt`、`.playwright-mcp/`、`.pytest_cache/`、`__pycache__/`、`.tmp*` 停在根目录。
- 角色边界：
  - `suite` 是 Codex 设计的标准试卷：题目描述、要求、第一轮 prompt、seed workspace、验收标准。
  - `run` 是某个被测 agent 的交作业文件夹：该 agent 的 workspace 答卷、每一轮实际收到的 prompt、真实终端 transcript、验收输出、截图和结果记录。
  - Codex 可以创建和维护 suite/run 骨架，可以按轮给被测 agent 发 prompt，可以在每轮完成后跑验收、试玩、截图、写下一轮修复 prompt 和总结；默认不替被测 agent 写程序、不修改答卷、不把自己生成的代码混进 Astrid / Claude Code 结果。
- 不同 agent 按目录分开：
  - `verification/suites/<英文-中文测试名>/`
  - `verification/runs/<agent-platform>/<model>/<日期-英文-中文测试名>/`
- 平台和模型分层，不要混成一个目录名。平台表示谁执行 agent workflow，模型表示背后的模型/供应商配置。
- 当前推荐平台名：
  - `astrid`
  - `claudecode`
  - `codex-client`
  - `codexcli`
- 当前推荐模型名：
  - `minimax2.7`
  - `chatgpt5.5-medium`
- 命名示例：
  - `verification/suites/snake-贪吃蛇/`
  - `verification/runs/astrid/minimax2.7/2026-04-29-snake-贪吃蛇/`
  - `verification/runs/claudecode/minimax2.7/2026-04-29-snake-贪吃蛇/`
  - `verification/runs/codex-client/chatgpt5.5-medium/2026-04-30-snake-贪吃蛇/`
  - `verification/runs/codexcli/chatgpt5.5-medium/2026-04-30-snake-贪吃蛇/`
- 每个 `verification/suites/<suite>/` 必须尽量包含：
  - `README.md`：题目背景、要测的能力、适合/不适合测什么。
  - `problem.md`：正式题目文档，写清楚题目背景、目标、交付物、限制、自由度和评测方式。不要只用 `prompt.md` 代替题目文档。
  - `prompt.md`：第一轮给 agent 的完整 prompt，默认中文。
  - `acceptance.md`：交付标准、禁止事项、外部验收命令、通过/失败判定。
  - `seed-workspace/`：初始工作区模板。这里的测试、样例、空项目和约束文件是标准试卷，会复制到每个 run 的 `workspace/`；不应被 run 反向覆盖。
  - `expected-files.md`：可选，说明理想产物应该有哪些文件、入口命令和目录结构。
  - `results-summary.md`：多平台/多模型横向结果摘要，记录每个 run 的第一轮结果、多轮结果和严格判定。
- suite 目录只放标准试卷材料。不要把某个 agent 的作业、某轮 transcript、验收输出或人工修补记录放进 suite；这些都必须进入对应 `verification/runs/<agent-platform>/<model>/<run>/`。
- 设计测试题时，先写清楚这道题到底测什么，不要只写“做一个东西”。可以覆盖 coding、TUI、UI、MCP、skills、多 agent、权限、context/memory、steering、长任务恢复等能力。
- 测试题可以很多元，但必须明确约束强度：
  - **精确规格题**：像刚才贪吃蛇那样，指定窗口尺寸、网格大小、文件结构、测试断言，甚至可以指定 UI 到像素级别。适合比较“能否严格服从验收标准”。
  - **开放功能题**：只给文字描述和功能目标，让各 agent 自由设计实现。适合比较产品感、架构取舍、UI 审美、自动规划和补全能力。
  - **混合题**：核心逻辑和验收测试严格固定，但 UI、交互、文档、工程组织允许自由发挥。适合真实 coding-agent 横向对比。
- UI/视觉类测试题必须说明是“像素级还原”还是“功能可用即可”。如果要求像素级，要给尺寸、颜色、间距、字体、状态截图/草图和可验收标准；如果允许自由发挥，要明确哪些地方可以自由设计。
- 每道题都要在 `README.md` 或 `acceptance.md` 中写明：
  - 测试目标：这题主要测哪类能力。
  - 输入材料：初始文件、图片、接口、MCP server、skill、已有测试等。
  - 交付物：必须产出哪些文件、命令、文档或截图。
  - 禁止事项：例如不能改验收测试、不能访问 workspace 外文件、不能引入重型依赖。
  - 验收方式：自动测试、静态检查、人工试玩、截图对比、性能阈值等。
  - 自由度：哪些必须严格一致，哪些允许 agent 大显神通。
- 每个 `verification/runs/<agent-platform>/<model>/<run>/` 必须尽量包含：
  - `README.md` 或 `results.md`：本次 run 的配置、命令、结果、失败原因和人工观察。
  - `evaluation.md`：Codex 对该答卷的评价和 100 分制评分，写清楚评分依据、扣分点、第一轮/最终状态和是否有人工修补。
  - `prompts/round-01.md`、`prompts/round-02.md`：每一轮实际发给 agent 的 prompt，必须是原文，不要只写摘要。
  - `instructions.md`：给人打开 Codex 桌面内置终端执行的步骤，包括进入哪个 workspace、输入哪个命令、粘贴哪个 prompt、如何保存 transcript。
  - `workspace/`：agent 的直接产物文件夹。所有生成/修改后的代码、文档、测试产物都放这里。
  - `transcripts/` 或 `*-transcript.txt`：每轮终端/模型输出记录。
  - `acceptance/` 或 `pytest-output*.txt`：外部验收命令输出、截图、运行日志、diff 检查结果。
  - `diffs/` 或 `test-diff*.txt`：与 `seed-workspace/` 的关键差异，尤其要记录验收测试是否被改。
  - `artifacts/`：可选，放截图、录屏、构建包等非源码产物。
- run 目录是交作业文件夹。每轮 Codex 发给被测 agent 的提示词都必须保存为 `prompts/round-XX.md`；每轮结果都必须保存 transcript、验收输出和 `results.md` 记录。Round 02 以后只能基于真实失败输出和试玩问题写修复 prompt，不要悄悄增加新需求。
- run 目录里的 `workspace/` 是答卷；suite 目录里的 `seed-workspace/` 是试卷。不要混用。
- 多轮测试必须一轮一个 prompt 文件、一轮一个 transcript。不要只保留最终产物，否则无法判断 agent 是第一轮通过、二轮修复，还是靠改验收测试通过。
- 浏览器类任务必须尽量有 Codex 内置浏览器验收记录：至少包括打开入口、关键用户操作、控制台错误、桌面或小窗口截图、以及“哪些地方由浏览器自动/辅助判断，哪些地方仍是人工主观评分”。如果是网页设计题，还要记录首屏、响应式、主要 CTA/表单/导航是否可用；如果是小游戏，还要记录开始、移动/输入、反馈、失败/胜利或重开。
- 每个 run 的 `evaluation.md` 使用 100 分制。默认必须同时评价结果和代价，不能只因“能跑”给高分。推荐默认权重：任务完成度 45、人工体验 20、代码质量和代码规模 15、执行效率和成本 15、证据完整性 5。具体 suite 可以调整，但必须显式写出权重。
- 执行效率和成本必须进入评分：记录每轮耗时、轮次数、token usage、超时、重试和人工介入。拿不到精确 token usage 时写 `未采集`，并记录 transcript 字节数、max output tokens 配置和轮次数作为成本代理，不能伪造成精确 token。
- 代码质量和代码规模必须进入评分：记录核心源码行数和字节数。功能简单但代码很长、结构臃肿、重复严重或难维护，应扣分；代码长本身不加分。
- 人工试玩反馈必须结构化保存。用户说“感觉还行”“很不错”“这里出不来”“炮台转动奇怪”这类模糊评价时，Codex 要整理成 `human-review.md` 或写入 `evaluation.md`：原话摘要、优点、缺点、严重程度、对分数的影响。
- suite 的 `results-summary.md` 或独立 `comparison.md` 必须横向汇总各 run 的评分、第一轮结果、最终结果、主要优缺点和严格结论。对比时要说明是否同题、同 prompt、同执行方式；不同执行方式的结果不能硬当作同一口径。
- 如果用户要求试玩或人工修补 run 产物，必须在 `results.md` 标注“人工修补后状态”，不要把它和 agent 原始产物混成同一个结论。
- 如果用户没有指定对比对象，先询问。推荐顺序：Claude Code 优先，Codex 其次。
- Astrid 测试方式：打开 Codex 桌面内置终端，进入对应 run 的 `workspace/`，运行 `astrid` 或项目指定的 Astrid 启动命令，把 `prompts/round-01.md` 原文交给 Astrid。不要默认用 stdin 管道代替真实终端。
- Claude Code 测试方式：打开 Codex 桌面内置终端，进入对应 run 的 `workspace/`，输入 `claude` 运行。当前本机 Claude Code 接入 MiniMax，成本相对低，适合作为默认横向对比对象。
- Codex 被测方式：只有用户确认要把 Codex 也作为被测 agent 时，才使用 Codex 终端/CLI 在同一 workspace 执行同样 prompt。Codex 成本更高；不要把当前 Codex 出题/验收会话算作 Codex 被测结果。
- Codex 客户端参考答卷方式：如果用户明确要求“当前 Codex 客户端/ChatGPT 也写一版”，可以把当前会话作为 `codex-client` 平台记录，但它仍然是一个正式 run：每一轮用户反馈或修复要求都要原文保存到 `prompts/round-XX.md`，每轮修复原因和验收结果写入 `results.md`，suite 汇总必须区分“自动底线通过”和“人工试玩后多轮修复通过”。
- 每次测试目录应包含：
  - `prompts/`：保存实际输入给 agent 的 prompt，不能只写摘要。
  - `workspace/`：隔离任务工作区和 agent 修改后的产物。
  - `instructions.md` 或 `run_eval.*`：Codex 桌面内置终端执行说明；`run_eval.*` 只能做目录准备、验收、记录，不应默认替被测 agent 完成编程任务。
  - `*-transcript.txt`：终端/模型输出记录。
  - `results.*` 或 notes：记录 pass/fail、失败原因、二轮修复情况、验收命令输出。
- PR4 轻量 harness 只负责骨架：`scripts/create_eval_run.py suite` 创建 suite 模板，`scripts/create_eval_run.py run` 创建 run 模板并复制 suite 的 `seed-workspace/`。它不会启动 Astrid/Claude/Codex，不会替 agent 修改 workspace，也不会把验收通过写入结果。
- 当前 Astrid 真实模型编程能力评测在：`verification/runs/astrid/minimax2.7/2026-04-29-coding-basic-编程基础/`。
- 当前 Astrid vs Claude Code 贪吃蛇对比评测在：`verification/runs/astrid/minimax2.7/2026-04-29-snake-贪吃蛇/` 和 `verification/runs/claudecode/minimax2.7/2026-04-29-snake-贪吃蛇/`。
- 当前 Codex 客户端 GPT-5.5 medium 参考产物在：`verification/runs/codex-client/chatgpt5.5-medium/2026-04-30-snake-贪吃蛇/`。它是 Codex 客户端生成/整理的参考答案，不等同于 Codex CLI 自主运行。
- 贪吃蛇这一轮的记录口径：Astrid 第一轮严格失败；二轮后 pytest 可过，但改写了验收测试，所以严格结果仍是失败。Claude Code 第一轮被预算截断，二轮后保留原验收测试并通过。
- 用 stdin 管道测试 Astrid 只适用于“非 TTY/eval 模式”专项，不适用于默认真实编程能力横向对比。非 TTY 模式写文件/改文件不会弹权限确认；除非临时把目标文件加入 `~/.astrid/permissions.json` 的 `allowedEditPatterns`，否则写入会失败。
- 如果必须临时写 `~/.astrid/permissions.json`，必须使用 UTF-8 no BOM。PowerShell `Set-Content -Encoding UTF8` 在部分环境会写 BOM，Astrid 当前权限读取可能把它当 corrupted JSON；优先用明确的 no-BOM 写入脚本，并在结果中记录。
- 临时预授权必须测试后恢复。原来没有 `permissions.json` 就删回不存在；原来有文件就恢复原始内容。
- 判断 coding ability 不要只看 assistant 文本。必须在 agent 之外跑 pytest 或验收脚本，并记录真实 pass/fail 输出。

## 验证默认命令

- TUI 改动：`python -m pytest tests/test_screen.py tests/test_tty_app.py tests/test_tui.py -q`
- 多 Agent 改动：`python -m pytest tests/test_orchestration.py tests/test_sub_agents.py -q`
- Context / memory / session 改动：先跑窄测试，再跑 `python -m pytest tests -q -k "context or memory or session"`
- 文档 / metadata 改动：`python -m pytest tests/test_cli_commands.py tests/test_screen.py -q`
- 评测 harness / 文档对齐改动：`python -m pytest tests/test_eval_harness.py tests/test_main_startup.py -q`
- 真实 coding-agent 评测：在 `verification/runs/<agent-platform>/<model>/...` 下新建 run，保存 prompt、workspace、产物、transcript、验收结果，然后在 agent 外部运行 workspace 的验收测试。
