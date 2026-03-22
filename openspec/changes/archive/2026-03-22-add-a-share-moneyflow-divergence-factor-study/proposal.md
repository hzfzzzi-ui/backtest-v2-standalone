## Why

当前仓库已经具备 A 股 `moneyflow` 与 `circ_mv` 的侧表基础，但“主力分歧率最小前十”的月频研究还没有正式的数据可用性合同、缺失处理规则和执行时点定义。若直接开启 `2016-2026` 十年回测，容易把 `moneyflow` 缺失误当成低分、把月频观察时点做成未来函数，导致结果不可审计也不可复现。

## What Changes

- 新增一个独立的 A 股月频研究专题，正式定义“主力分歧率”因子的口径、样本过滤、月频聚合和调仓时点。
- 为该专题新增数据可用性规则，明确 `net_mf_amount`、`circ_mv`、20 日窗口、月度白名单与缺失值处理要求。
- 为 `2016-2026` 十年回测新增正式执行合同，要求只在满足数据覆盖率门槛、月末观察口径和次月首个交易日开盘成交合同的前提下运行。
- 明确该研究专题与 `baseline_V10.1` 的边界：本次只新增独立研究入口和产物，不修改 baseline 主逻辑、不改变现有 A 股主线口径。
- 将当前实现缺口显式记录为任务，包括 side table 运行时读取、月频横截面排名、月度持仓执行和研究产物审计。

## Capabilities

### New Capabilities

- `a-share-moneyflow-divergence-study`: 定义 A 股“主力分歧率最小前十”月频研究的正式数据可用性规则、执行时点合同、十年回测窗口和必需产物。

### Modified Capabilities

- 无

## Impact

- 受影响路径主要在 `backend/research/*`、`research/studies/*`、`backend/core/data/*`、`backend/core/tools/data_bundle_builder.py`、`backend/core/tools/experiment_runner.py`、`backend/core/strategies/*` 与对应测试。
- 本次不新增对外 API，不修改 `baseline_V10.1` 默认配置，也不改变当前日频主线研究口径。
- 本次变更会约束 `pit_stock_moneyflow(_v2)`、`pams_ohlcv_daily(_v2)` 与研究执行层之间的边界，要求十年回测输出可复现的 study 产物、覆盖率证据和缺失排除记录。
