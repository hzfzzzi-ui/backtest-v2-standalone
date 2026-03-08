## Why

上一轮 change 已经把 `legacy_adapter.py` 里的 route、candidate flow、holding flow 和 `S7` 规划胶水拆出去了，但这个文件仍然同时承担开盘成交、仓位现金更新、日度 NAV 快照、daily row 组装和结果指标桥接。现在如果继续把新逻辑留在这里，`legacy_adapter.py` 会重新变成新的单体执行壳，后续就很难安全收敛和删除旧编排。

## What Changes

- 把 `legacy_adapter.py` 中剩余的 accounting-facing 责任拆到独立内部模块，重点包括开盘成交与持仓/现金更新、日度 NAV 与 daily row 组装、结果指标桥接。
- 保持公开主链不变，继续使用单一入口：
  `config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`
- 明确 `legacy_adapter.py` 的收敛目标：只保留兼容边界和少量编排，不再承载成交会计、日度快照和结果组装细节。
- 为 accounting、daily snapshot、result bridge 增加聚焦测试，并继续以 `exp_20260308_021045840_cde0` 做锁定基线回归门禁。
- 补充冻结文档，明确哪些责任已经迁出、哪些残余责任仍允许继续拆分。

## Capabilities

### New Capabilities
- `legacy-accounting-boundary-shrink`: 后端必须在保持公开单路径和基线结果不变的前提下，将 stage adapter 中剩余的 accounting、daily snapshot 和 result bridge 责任拆到独立内部模块。

### Modified Capabilities
- 无。

## Impact

- 影响代码主要集中在 [legacy_adapter.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/legacy_adapter.py)、`backend/core/stage_pipeline/adapters/` 下新增的 accounting/daily/result 模块，以及相关单测。
- 不改变前端配置协议、不新增公开执行路径、不改变交易数学、成交时点、成本口径或实验产物名称。
- 所有实现步骤都必须继续通过：
  `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`
