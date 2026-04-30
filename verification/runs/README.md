# Runs

这里放各 agent 平台和模型的测试产物。

这里的 run 目录是某个 agent 的交作业文件夹。`workspace/` 是被测 agent 的答卷。默认流程是 Codex 打开 Codex 桌面内置终端进入 `workspace/`，启动对应 agent，粘贴 `prompts/round-01.md` 原文；Codex 主持后续轮次、验收、记录和分析，但不替 agent 写答卷。

建议结构：

```text
<agent-platform>/<model>/<run-name>/
  results.md
  instructions.md
  prompts/
  workspace/
  transcripts/
  acceptance/
  diffs/
  artifacts/
```

轮次记录规则：

- `prompts/round-01.md`：从 suite `prompt.md` 复制而来，是该 agent 第一轮实际收到的 prompt。
- `prompts/round-02.md` 及以后：只能由 Codex 根据真实验收失败、真实 transcript 或人工试玩问题生成，不增加新需求。
- `transcripts/round-XX.txt`：保存该轮真实终端输出。
- `acceptance/round-XX.txt`：保存该轮外部验收输出。
- `artifacts/`：保存试玩截图、录屏、浏览器控制台记录等证据。
- `results.md`：逐轮记录第一轮结果、多轮修复后结果、严格结论和失败原因。
- `evaluation.md`：最终评分。必须包含任务完成度、人工体验、代码质量、执行效率/成本、证据完整性。
- `human-review.md`：可选但推荐。保存用户或人工试玩者的原始反馈摘要，以及 Codex 整理后的优缺点和评分影响。

Codex 的主持动作也要留下痕迹：每一轮给了什么 prompt、为什么给、验收输出是什么，都必须能从 run 目录还原。

不要把 Codex 通过 stdin、脚本或 API 自动喂给被测 agent 的结果，直接当成真实终端编程能力结论。那只能标注为非 TTY/eval 模式专项。

执行成本记录规则：

- 能拿到精确 token usage 时，记录 input tokens、output tokens、total tokens。
- 拿不到精确 token usage 时，写 `未采集`，并记录可用代理数据：transcript 字节数、max output tokens 配置、轮次数、是否超时。
- 每轮记录开始/结束时间或耗时；如果由外部命令运行，优先在 transcript 或 results 中保存 `ELAPSED_SECONDS`。
- 代码规模至少记录核心源码文件行数和字节数。代码越长不代表越好；如果简单题写出臃肿代码，要在代码质量分扣分。
