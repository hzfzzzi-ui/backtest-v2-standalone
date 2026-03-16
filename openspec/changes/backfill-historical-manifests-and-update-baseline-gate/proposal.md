## Why

最近一轮 `multi-asset-entry-boundaries` 已让新实验输出 canonical `asset_context`，但历史实验的 `manifest.json` 仍缺少这些字段，导致旧锚点实验只能靠查询层临时回填。与此同时，`baseline_V10.1` 的 regression gate 仍把新增的 `asset_scope`、`run_config_hash` 漂移和 `portfolio_daily.csv` 结构增量当成阻塞失败，无法正确区分“语义漂移”和“已批准的契约升级”。

## What Changes

- 为历史实验增加离线 `manifest.json` 回填流程，只补 canonical 资产上下文和缺失的标准 manifest 字段，不改回测结果本体。
- 更新 baseline regression gate 契约，显式接受本轮已批准的结构升级，并继续对 `perf`、`nav`、`portfolio_trades`、`portfolio_candidates` 和 manifest 关键语义做阻塞校验。
- 输出回填审计结果和 gate 更新后的对照结果，继续锚定 `baseline_V10.1 -> exp_20260314_144548534_7db9`。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `canonical-artifact-migration`: 要求历史实验通过离线回填补齐 canonical manifest 资产上下文，而不是长期依赖查询层临时推导。
- `execution-contract-goldens`: 要求 baseline gate 将已批准的 schema enrichment 从阻塞型行为漂移中分离，并更新 contract 以继续保护 `V10.1` 关键行为。

## Impact

- 影响代码：
  - `backend/api/backtest_v2/*manifest*`
  - `backend/cli/managed/baseline_regression_check.py`
  - `backend/scripts/ops/v2_backend_refactor_baseline_contract.json`
  - 必要的迁移/审计工具与对应测试
- 影响产物：
  - 历史 `outputs/experiments/*/manifest.json`
  - baseline compare 报告
- 不影响：
  - `V10.1` 信号时点
  - 成交时点
  - 收益、回撤、交易数口径
