## Why

当前主线已经把 `execution_contract` 定义为唯一正式执行真相，但实际产物和运行边界仍然残留明显的结构漂移：组件 `runtime_config` 仍夹带跨腿子树，`compiled_plan.json` 同时承担编译计划、来源装配和可执行输入，`run_meta.json` 混入运行事实、结果摘要、上下文和执行镜像，baseline 产物也还没有把“身份绑定”和“配置快照”彻底拆开。  
这些问题已经直接影响调试、审计和回滚效率。如果不继续把合同拓扑收口，后续任何策略诊断都会反复陷入“到底谁在决定结果”的边界混乱。

## What Changes

- 纯化组件级 `runtime_config`，禁止 stock / ETF 组件继续携带跨腿 governed 子树和无关 schema 映射。
- 拆分 `compiled_plan`、`execution_contract` 与 assembly/provenance 轨迹，禁止 `compiled_plan.json` 继续承担事实上的执行真相。
- 瘦身 `run_meta.json`，仅保留运行事实、`execution_contract_ref`、依赖索引和 provenance，迁出结果摘要、上下文容器与执行全文镜像。
- 重构 baseline 产物职责：`baseline.json` 只保留身份和绑定，基线配置快照降级为独立 snapshot 对象，`index.json` 明确为列表缓存。
- 为上述边界补强契约测试、goldens 和前端消费守门，确保执行层只认 `execution_contract`，结果层与编辑层不再越权。

## Capabilities

### New Capabilities
- `baseline-snapshot-topology`: 定义 baseline 身份对象、配置快照对象和列表缓存对象的正式边界。
- `compiled-plan-boundary`: 定义编译计划、执行合同与 assembly/provenance 轨迹的分层职责，禁止混写。

### Modified Capabilities
- `runtime-boundary-contracts`: 收紧 `execution_contract` 的纯参数约束，并要求组件执行合同不得携带跨腿子树或来源字段。
- `artifact-protocol-convergence`: 更新产物协议，明确 `compiled_plan`、`run_meta`、`manifest`、`execution_contract` 的职责边界与引用关系。
- `baseline-anchor-registration`: 调整 baseline 注册与重挂协议，使其显式绑定 `execution_contract_ref` 并降级配置快照。
- `results-workbench-snapshot-boundary`: 约束结果工作台只消费执行真相与 provenance，禁止把 `comboTruth`、旧 `component_source_contract` 或 `run_meta` 镜像再次当主真相。
- `single-run-pipeline`: 明确单次回测与 unified combo 在进入 pipeline 前必须产出纯组件执行合同与唯一 `execution_contract`。

## Impact

- 受影响源码：`backend/api/backtest_v2/runner_config_bundle.py`、`backend/core/config/cn_a_governed_mainline.py`、`backend/core/services/cn_stock_etf_unified_runtime_service.py`、artifact finalize/manifest/run_meta 相关模块、baseline 读写与前端结果消费层。
- 受影响产物：`execution_contract.json`、`compiled_plan.json`、`run_meta.json`、baseline 目录对象、结果工作台 snapshot。
- 受影响系统：A 股单腿回测、unified combo、baseline 回放链、结果工作台、契约测试与 goldens。
