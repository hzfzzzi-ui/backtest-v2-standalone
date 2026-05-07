## Why

当前平台虽然已经有 `stock alpha factor snapshot` 和 `account state score snapshot` 两层研究产物，但研究 runtime 仍然主要依赖“现算现用”的输入方式。这样会继续造成研究口径与执行口径混杂、快照产物无法成为单一真相，也不利于后续把研究面平稳接到 runtime。现在需要把 research runtime 正式改成可消费快照产物的模式，让后续研究与回放都建立在已冻结的 factor/state snapshot 之上。

## What Changes

- 建立 research runtime 的 snapshot consumption 合同，允许研究运行直接消费已生成的 factor snapshot 和 state score snapshot。
- 建立 snapshot-backed study execution surface，统一研究 runner 如何声明、定位、读取和校验快照输入。
- 建立 runtime 级别的快照引用与 lineage 字段，使研究结果可以回溯到具体 snapshot、score 和窗口。
- 明确本次 change 只作用于 research runtime，不默认改写正式主线策略行为和正式执行链。

## Capabilities

### New Capabilities
- `research-runtime-snapshot-consumption`: 定义 research runtime 如何消费因子快照和状态分数快照。
- `snapshot-backed-study-execution-surface`: 定义 snapshot 驱动的研究执行入口、输入合同和最小输出合同。
- `research-snapshot-lineage-contract`: 定义 snapshot 输入、运行结果和研究结论之间的 lineage 与审计字段。

### Modified Capabilities
- 无

## Impact

- 主要影响 `backend/research`、`research/studies`、`tests`。
- 后续可能被 `backend/core` 的研究 runtime 消费，但本次不改正式主线预算与执行逻辑。
- 不新增外部依赖，优先复用现有 study runner、artifact 目录和审计约束。
