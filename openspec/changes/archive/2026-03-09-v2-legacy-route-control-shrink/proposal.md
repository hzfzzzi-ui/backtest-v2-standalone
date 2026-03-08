## Why

`v2-legacy-accounting-boundary-shrink` 完成后，`legacy_adapter.py` 已经不再承载成交会计、日度快照和结果桥接，但它仍然集中持有 route 选择后的日度控制逻辑，包括 stage 可用性判断、`_compute_day_controls(...)`、provider signal 后处理和 route 诊断计数更新。继续把这些逻辑留在单体 adapter 中，会让它继续承担 route-specific orchestration，后续仍然难以彻底收敛。

## What Changes

- 把 `legacy_adapter.py` 剩余的 route/day-control/provider diagnostics 责任拆到专用内部模块。
- 保持公开主链不变，继续复用单一入口：
  `config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`
- 明确 `legacy_adapter.py` 的下一阶段收敛目标：只保留 runtime 容器、少量时序组织和 helper 委托。
- 为 route control、day control、provider signal postprocess 增加聚焦测试，并继续以 `exp_20260308_021045840_cde0` 做锁定基线门禁。
- 补充冻结文档，明确 route/day-control 迁出后的剩余 adapter 责任。

## Capabilities

### New Capabilities
- `legacy-route-control-boundary-shrink`: 后端必须在保持公开单路径和锁定基线等价的前提下，将 stage adapter 中剩余的 route/day-control/provider diagnostics 责任拆到独立内部模块。

### Modified Capabilities
- 无。

## Impact

- 影响代码主要集中在 [legacy_adapter.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/legacy_adapter.py)、`backend/core/stage_pipeline/adapters/` 下新增的 route/day-control 模块，以及相关单测和冻结文档。
- 不改变前端配置协议、不新增公开执行路径、不改变交易数学、成交时点、成本口径或实验产物名称。
- 所有实现步骤都必须继续通过：
  `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`
