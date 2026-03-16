## Why

当前系统的主骨架已经完成重构，但运行入口、study 定义、runtime compile、universe 解析、signal provider 路由、manifest/surface 和前端 snapshot 仍然默认以 A 股语义作为隐式前提。后续如果要正式接入美股 ETF、加密现货和防守层资产，必须先把“资产进入系统的边界”显式化，否则新资产只能继续以局部 if/else 的方式侵入核心路径。

## What Changes

- 新增统一的 `asset_scope -> asset_profile -> market_profile` 入口边界，要求桌面端、study、runtime compile、provider 路由和结果面都使用同一资产真相。
- 将当前隐式散落在 runtime、provider、universe、frontend 中的 A 股专有假设收口到显式的 market/asset adapter。
- 要求 study 定义、generated thin script 和运行请求显式声明资产范围，不再把 `CN_A` 当作未声明时的长期主语义。
- 要求 manifest、surface、runtime snapshot 和结果工作台 snapshot 都携带薄资产上下文，前端不再从 A 股特定字段倒推市场语义。
- **BREAKING**：正式多资产入口契约不再把“未声明资产范围”视为可接受的长期正式输入；所有主路径运行入口必须能解析出 canonical asset scope。

## Capabilities

### New Capabilities
- `multi-asset-entry-boundaries`: 定义 canonical asset scope、asset profile、market profile 和多资产入口收口规则。

### Modified Capabilities
- `runtime-boundary-contracts`: manifest、surface、runtime snapshot 和桌面主真相需要携带资产上下文。
- `signal-provider-protocol`: signal provider、route registry 和 runtime route 选择必须显式消费 asset profile，而不是隐式假设 A 股。
- `api-runtime-config-compilation`: runtime config compile 必须先编译 asset boundary，再编译 universe/signal/risk。
- `http-surface-boundary-split`: backtest 主 HTTP surface 必须暴露实验级资产上下文和能力摘要。
- `results-workbench-snapshot-boundary`: ResultsWorkbenchSnapshot 必须携带 assetContext，前端不得依赖 A 股隐式语义。
- `study-definition-runner`: `.study.yaml` 和 `study_run` 必须声明并透传 asset scope。
- `universe-resolver`: universe resolver 必须先按 asset family 路由，再进入 A 股或其他资产专属 resolver。

## Impact

- 影响代码：
  - `backend/api/backtest_v2/*`
  - `backend/core/tools/experiment_runtime_access.py`
  - `backend/core/engine_vector/*`
  - `backend/core/universe/*`
  - `backend/research/*`
  - `frontend/assets/js/state/*`
  - `frontend/assets/js/pages/*`
  - `frontend/app/results-workbench/*`
- 影响对象：
  - 运行请求
  - study 定义
  - manifest / surface / snapshot
  - provider 路由
  - universe 入口
- 不包含：
  - 新资产的正式交易逻辑落地
  - 新资产的收益优化
  - `baseline_V10.1` 执行口径变更
