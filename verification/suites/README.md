# Suites

这里放标准测试题。每个 suite 是试卷，不是答卷。

Codex 在这里的职责是出题、定义验收和保存首轮 prompt，不是替被测 agent 写程序。第一轮 prompt 必须是可以原样复制到 Astrid / Claude Code / Codex CLI 真实终端里的完整提示词。

建议结构：

```text
<suite>/
  README.md
  problem.md
  prompt.md
  acceptance.md
  seed-workspace/
  expected-files.md
  results-summary.md
  comparison.md
```

suite 是标准试卷，只放跨 agent 共享的材料：

- `README.md`：题目背景、要测的能力、自由度和不适合测什么。
- `problem.md`：正式题目文档。写给评测主持人和读者看，说明这道题是什么、为什么这么设计、交付什么、限制什么、如何评测。
- `prompt.md`：Round 01 原始提示词。
- `acceptance.md`：验收方式、禁止事项、评分口径。
- `seed-workspace/`：初始工作区，作为试卷复制到各 run。
- `results-summary.md`：横向汇总，只写结论摘要和链接，不放某个 agent 的完整作业。
- `comparison.md`：可选但推荐，写各答卷 100 分制评分、排名、主要优缺点和严格对比结论。

不要把某个 agent 的作业、Round 02 prompt、transcript、验收输出、截图或人工修补记录放进 suite。它们属于对应 run 目录。

`seed-workspace/` 是每个 agent 开始答题前拿到的初始 workspace 模板。它可以是空项目，也可以包含验收脚本、样例数据、初始代码、图片素材或接口说明。正式 run 时应复制它，而不是让 agent 直接在 suite 目录里作答。

设计 suite 前先写清楚这道题测什么。测试题可以很多元：

- **精确规格题**：指定窗口尺寸、文件结构、测试断言，甚至 UI 到像素级别。适合测严格服从验收标准。
- **开放功能题**：只给功能目标和文字描述，让各 agent 自由设计实现。适合测产品感、架构取舍和自动规划能力。
- **混合题**：核心逻辑和验收测试固定，UI、文档、交互和工程组织允许自由发挥。适合真实 coding-agent 横向对比。

每道题需要明确：

- 测试目标
- 输入材料
- 交付物
- 禁止事项
- 验收方式
- 自由度：哪些必须严格一致，哪些允许 agent 大显神通

浏览器类 suite 要写清楚 Codex 内置浏览器辅助验收口径。网页、小游戏、工具页、仪表盘等都应尽量打开真实页面，模拟点击、输入、键盘、鼠标、窗口缩放，保存截图和控制台错误；但视觉审美、游戏手感、产品判断仍要保留人工评分。

每个答卷 run 应有自己的 `evaluation.md`，记录 Codex 对该答卷的 100 分制评价。suite 层的 `results-summary.md` 或 `comparison.md` 只做横向汇总，不替代 run 里的详细评价。

suite 的 `acceptance.md` 或 `comparison.md` 里必须写清楚本题的评分权重。开放题不能只看自动验收；还要把完成时间、token 消耗、代码质量、代码规模和人工试玩反馈纳入评分。

推荐 suite 汇总表至少包含：

- 第一轮结果和最终结果。
- 最终评分和分项评分。
- 轮次数和总耗时。
- token 消耗；没有精确 usage 时标注 `未采集`。
- 主要代码规模，例如核心源码行数/字节数。
- 人工评价摘要。

每个 suite 的 `comparison.md` 不应只给一个总排名。默认至少拆成这些横向表：

- **结果质量对比**：任务完成度、人工体验、代码质量、效率成本、证据完整性和总分。
- **执行成本对比**：轮次、首轮结果、已记录耗时、精确 token usage、成本代理和成本判断。
- **代码规模对比**：主要源码组织、agent 代码行数、agent 代码字节数和质量判断。
- **人工体验对比**：用户/人工试玩反馈、主要优缺点、对分数的影响。

如果旧 run 缺少耗时或 token 记录，表格里写 `未采集`，同时说明该 run 不能在效率成本维度严格比较。

人工评价不要求用户写成正式报告。用户给出“感觉还行”“这个地方出不来”“炮台转动很怪”这类反馈时，Codex 应整理为 `human-review.md` 或写入 `evaluation.md`，并反映到分项扣分里。

如果需要自动化脚本，脚本默认只能用于创建 run 骨架、复制 seed、跑外部验收、生成结果模板；不要默认替被测 agent 执行编程任务。
