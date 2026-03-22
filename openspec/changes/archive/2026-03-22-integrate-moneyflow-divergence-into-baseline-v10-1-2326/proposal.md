## Why

`baseline_V10.1` 目前的正式主壳仍是 `residual_only`，而主力资金分歧率研究只存在于独立月频 study，尚未形成一条受审计约束的 `23-26` 局部接入实验链路。用户已经确认要先在 `2023-2026` 高覆盖窗口验证该因子是否值得进入主线，因此需要先把接入边界、运行时合同和实验产物固定下来，再做最小实现与实验。

## What Changes

- 新增一条仅面向 `2023-07-03` 到 `2026-03-16` 的 `V10.1` moneyflow 接入实验能力，明确“月末观测、次交易日生效、月内冻结”的慢频合同。
- 新增三种实验模式：`shadow`、`tiebreak`、`soft_weight`，全部以 `baseline_V10.1` 现有残差主排序为锚点，不替换 `residual_only` 主排序。
- 新增 `moneyflow` 月频分数装载与冻结逻辑，允许从既有月频分歧率研究产物或同口径数据库查询生成日频可消费分数。
- 新增覆盖率门控与中性回退规则：仅当观察日满足覆盖率门槛时才启用因子；否则当月保持中性，不得把缺失当低分。
- 新增 `23-26` 实验定义、诊断产物和回归验证，比较 `shadow / tiebreak / soft_weight` 与 `baseline_V10.1` 的行为差异。

## Capabilities

### New Capabilities
- `baseline-moneyflow-overlay-experiment`: 定义 `V10.1` 在 `2023-2026` 高覆盖窗口内接入月频主力资金分歧率慢因子的运行时合同、门控规则和实验模式。
- `baseline-moneyflow-overlay-diagnostics`: 定义 overlay 实验必须输出的月份覆盖率、分数冻结、启用状态和组合排序诊断产物。

### Modified Capabilities
- 无

## Impact

- 受影响模块主要在 `backend/core/engine_runtime/*`、`backend/core/engine_vector/*`、`backend/core/portfolio/*`、`backend/research/*`、`research/studies/*` 与对应测试。
- 本次不修改 `outputs/baselines/baseline_V10_1/config.json` 的默认正式配置，只新增实验配置与可选运行时分支。
- 依赖当前已有的 `pit_stock_moneyflow` / `pit_stock_moneyflow_v2` 与月频分歧率研究代码，但 `23-26` 首轮实验默认优先使用当前已稳定可用的数据源。
