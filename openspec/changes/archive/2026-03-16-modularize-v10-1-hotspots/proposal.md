## Why

当前仓库的主架构已经完成重构，但仍有 5 个热点文件同时承担 façade、配置编译、运行时状态、产物稳定化和具体路由逻辑，已经开始阻碍后续继续扩展多资产能力。既然当前正式锚点已经明确为 `baseline_V10.1 -> exp_20260314_144548534_7db9`，就应以该锚点为唯一回归门，对这些热点做结构化模块拆分，而不是继续在单文件里累积逻辑。

现在做这件事的原因很直接：`strict_runtime_default.py` 仍是单函数大编排，`regime_router_signal_provider.py` 和 `breakout_signal_provider.py` 仍把 provider façade、配置和运行时状态揉在一起，`runner_config_helpers.py` 与 `artifacts_impl.py` 仍分别像万能编译器和万能产物厨房。继续拖延，只会让后续接入新资产时把复杂度继续压回这些文件。

## What Changes

- 将 `strict_runtime_default.py` 收口为默认 route 的薄 façade，并按阶段拆出输入、基准、信号、逐日循环和结果汇总模块。
- 将 `regime_router_signal_provider.py` 与 `breakout_signal_provider.py` 收口为 provider façade，并把参数快照、运行时状态、precompute 和 day route 逻辑外提到专用模块。
- 将 `runner_config_helpers.py` 按配置域拆分为 `universe / signal / risk-exit / bundle` 编译模块，保留 façade 负责总装配。
- 将 `artifacts_impl.py` 按产物职责拆分为 `io / manifest / stage-summary / diagnostics / finalize` 模块，保留 façade 暴露外部入口。
- **BREAKING** 本轮不为旧单文件结构保留兼容约束；正式主路径以后只面向新的模块边界维护，不允许继续把新逻辑堆回这 5 个热点文件。
- 本轮所有拆分必须保证 `baseline_V10.1 -> exp_20260314_144548534_7db9` 结果不漂移，不得改动执行时点、成交规则、统计口径或 surface 语义。

## Capabilities

### New Capabilities
- `core-hotspot-modularization`: 约束默认 runtime route 与 signal provider 热点必须拆为 façade + config/state + stage/route 模块。
- `api-runtime-config-compilation`: 约束 workbench/runtime 配置编译必须按配置域拆分，不再由单一 helper 文件承载。
- `artifact-finalization-pipeline`: 约束实验产物稳定化必须按 manifest、summary、diagnostics 和 finalize 分层，不再由单一实现文件承载。

### Modified Capabilities
- `signal-provider-protocol`: provider 实现需要继续遵守既有协议，同时允许 façade 调度外部 state/precompute/route 模块。
- `experiment-artifact-service`: artifact service 继续保持既有产物契约，但底层 owner 必须切换到分层 finalize pipeline。
- `execution-shell-unification`: 默认 route 的 façade 拆分后，执行入口仍必须保持统一，不得因拆分重新引入并行执行壳。

## Impact

- 影响代码：
  - `backend/core/engine_vector/strict_runtime_default.py`
  - `backend/core/engine_vector/regime_router_signal_provider.py`
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/api/backtest_v2/artifacts_impl.py`
  - `backend/api/backtest_v2/runner_config_helpers.py`
- 影响边界：默认 route 编排方式、provider 内部实现边界、runtime config 编译层、artifact finalize 层。
- 不影响的内容：`baseline_V10.1` 的输入口径、执行时点、成交规则、统计口径、surface 契约。
- 风险边界：`strict_runtime_default.py` 与 provider 层拆分最接近回测主链，必须按“机械拆分 -> 对照验证 -> 再继续”推进。
