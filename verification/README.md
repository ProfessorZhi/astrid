# Verification

本目录是本地 coding-agent 评测区，不上传 GitHub。

默认角色边界：

- Codex 负责主持评测闭环：设计题目、第一轮 prompt、seed workspace、验收标准、把同一题投给各被测 agent、监督各轮产物、基于真实失败输出写下一轮修复 prompt、验收和结果汇总。
- Astrid、Claude Code、Codex CLI 等被测 agent 负责在各自真实终端里完成编程任务并产出答卷。
- 除非明确测试非 TTY/eval 模式，不要用脚本或 stdin 管道替被测 agent 执行任务。

结构：

```text
verification/
  suites/   # 标准试卷：题目描述、首轮 prompt、验收标准、seed workspace
  runs/     # 交作业文件夹：各平台/模型 workspace、各轮 prompt、transcript、acceptance、diffs、artifacts
```

运行结果按下面结构保存：

```text
verification/runs/<agent-platform>/<model>/<YYYY-MM-DD-suite-name>/
```

每个 run 里的 `instructions.md` 应写明如何打开 Codex 桌面内置终端、进入 `workspace/`、启动被测 agent、粘贴哪一轮 prompt，以及如何保存 transcript。

评测轮次：

1. suite 目录保存题目描述、要求、验收标准和首轮 prompt。
2. Codex 为每个被测 agent 创建独立 run 目录，并把 seed workspace 复制到该 run 的 `workspace/`。
3. Codex 把 `prompts/round-01.md` 原文交给对应 agent。
4. agent 完成后，Codex 保存 transcript、跑外部验收、试玩或截图，并把结果写入 `results.md`。
5. 如果需要下一轮，Codex 只根据真实失败输出和试玩问题生成 `prompts/round-02.md`，再交给同一个 agent 修复。
6. 最终结果必须区分第一轮结果和多轮修复后结果。

## 评分口径

每个测试都必须同时评估“结果”和“代价”。不能只因为最终能跑就给高分。

默认 100 分制：

- 45 分：任务完成度。是否真的满足题目目标，核心功能是否成立，自动验收和外部试玩是否通过。
- 20 分：人工体验评价。用户或人工试玩者的模糊反馈要整理成优点、缺点、严重程度和分数；例如“感觉还行”“很不错”“卡在初始位置”“炮台不跟鼠标”都要落成评价记录。
- 15 分：代码质量和可维护性。看结构、重复、命名、模块边界、可读性、是否为了简单功能写出过长或过复杂代码。功能简单但代码很长，要扣分。
- 15 分：执行效率和成本。完成时间、轮次数、token 消耗、超时、重试、人工介入次数都要计入。越慢、越费 token、越依赖多轮修复，分数越低。
- 5 分：证据完整性。prompt、transcript、验收输出、截图、人工评价和评分依据是否能从 run 目录还原。

每个 run 的 `evaluation.md` 必须记录：

- 首轮是否通过、最终是否通过。
- 每轮耗时；如果没有精确耗时，要说明缺失。
- 每轮 token 消耗；如果当前 agent 没有暴露 usage，要写 `未采集`，不要估算成事实。
- 代码规模：主要源码文件行数和字节数。
- 人工评价：原话摘要、结构化优缺点、对分数的影响。
- 代码质量判断：是否用过长代码解决简单问题，是否存在明显结构问题。

如果 agent 没有输出 token usage，主持人可以临时记录 transcript 字节数、配置的 max output tokens 和轮次数作为“成本代理”，但最终表格必须标注它不是精确 token 数。
