## Why

当前 `A_STOCK_ETF_V1` 的正确回放语义已经重新校准到 `exp_20260404_074403089_e18e` 这一组结果，但系统对 unified combo 组件来源的表达仍停留在 `research_custom_sleeves` 这类研究型 provenance 口径上。这个口径足以支撑当前回放与审计，但还不是正式共享运行时合同，继续直接把它写成“已收口完成”会造成设计漂移。

现在需要在不破坏既有回放锚点的前提下，补出显式的 component source contract，把“正式合同”和“过渡 provenance”分层表达，为后续真正清理 `research_custom_sleeves` 留出可验证的迁移路径。

## What Changes

- 为 unified combo 增加显式的 component source contract 元数据对象，用于表达组件来源的正式字段集合与过渡状态。
- 保留当前 `research_custom_sleeves` 回放链路，但将其明确降级为 transitional provenance，而不是正式共享执行合同。
- 约束统一运行时组合在编译、运行与产物阶段都输出相同的 component source contract，供后续 cleanup 与前端消费。
- 记录并保护 `A_STOCK_ETF_V1` 的正确回放锚点，避免后续“更正式”的改动再次把系统锁到错误版本。

## Capabilities

### New Capabilities
- `unified-combo-component-source-contract`: 定义 unified combo 组件来源的正式元数据合同与过渡状态表达

### Modified Capabilities
- `runtime-boundary-contracts`: 新增 unified combo 组件来源合同与 provenance 分层要求
- `post-refactor-residual-cleanup`: 新增 cleanup 前必须复现已验证回放锚点的约束

## Impact

- 后端编译与运行组装：`backend/api/backtest_v2/runner_config_bundle.py`
- unified combo 运行产物：`backend/core/services/cn_stock_etf_unified_runtime_service.py`
- 正式规格与 cleanup 约束：`openspec/specs/runtime-boundary-contracts/spec.md`、`openspec/specs/post-refactor-residual-cleanup/spec.md`
- 可能影响后续前端结果工作台对 component source 元数据的读取，但本 change 第一阶段不要求修改前端行为
