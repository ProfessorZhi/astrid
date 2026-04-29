# Suites

这里放标准测试题。每个 suite 是试卷，不是答卷。

建议结构：

```text
<suite>/
  README.md
  prompt.md
  acceptance.md
  seed-workspace/
  expected-files.md
  results-summary.md
```

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
