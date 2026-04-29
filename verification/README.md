# Verification

本目录是本地 coding-agent 评测区，不上传 GitHub。

结构：

```text
verification/
  suites/   # 标准试卷：题目、prompt、验收标准、seed workspace
  runs/     # 各平台/模型答卷：workspace、transcript、acceptance、diffs、artifacts
```

运行结果按下面结构保存：

```text
verification/runs/<agent-platform>/<model>/<YYYY-MM-DD-suite-name>/
```
