## Why

当前平台虽然已经有 snapshot-backed runtime，但真正的 moneyflow 因子仍然只能通过旧研究脚本或临时 proxy 方式分析，没有独立的 catalog、snapshot 与 study surface。现在需要把真正的 moneyflow 因子从 runtime 历史命名里拆出来，形成研究层单独可审计、可扩展的正式入口。

## What Changes

- 新增 moneyflow factor catalog，首版明确 `monthly_divergence_rate` 及相关元数据。
- 新增 moneyflow factor snapshots，支持从正式 moneyflow 研究面构建日频/观测频率快照与组合分数。
- 新增 moneyflow factor study surface，让 moneyflow 因子可以像 stock alpha/state score 一样通过 `study_run` 独立研究。
- 明确这条 change 仅属于研究层，不把 moneyflow 因子接入正式 runtime 排序或预算逻辑。

## Capabilities

### New Capabilities
- `moneyflow-factor-catalog`: 定义 moneyflow 因子的正式目录、元数据与解释边界。
- `moneyflow-factor-snapshots`: 定义 moneyflow 因子的快照产物与组合分数快照。
- `moneyflow-factor-study-surface`: 定义 moneyflow 因子的单因子/组合因子研究入口。

### Modified Capabilities
- 无

## Impact

- 受影响代码主要位于 `backend/research`、`research/studies/factors`、`tests` 和 `openspec`。
- 不改变当前 `baseline_V10.1` runtime 排序、仓位和状态逻辑。
- 后续如果要把 moneyflow 因子接到 runtime，应作为单独 change 处理。
