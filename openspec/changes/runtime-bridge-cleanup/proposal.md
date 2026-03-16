## Why

当前正式执行入口已经收口到 `foundation_shell` 和 `stage_pipeline`，但 `bridge_adapter.py`、`portfolio_builder.py`、`frozen_loop.py`、`strict_runtime_impl.py` 等过渡桥层仍在承接关键运行路径。若继续在这些桥层上叠加逻辑，执行边界会再次变脏，golden 对比、可审计性和回退路径都会持续变差，因此需要先把“桥层怎么退场”明确成正式合同。

## What Changes

- 定义 runtime bridge 退场合同，明确 `foundation_shell` / `stage_pipeline` 是唯一正式执行总线，`bridge_adapter`、`strict shim`、`frozen_loop` 仅允许承担过渡职责。
- 定义 bridge cleanup 的阶段门槛，包括可删除前提、golden 覆盖要求、漂移判定标准和回退要求。
- 定义 bridge cleanup 期间允许改动与禁止改动的代码面，防止新执行逻辑继续回流到过渡桥层。
- 定义 bridge cleanup 完成后的目标形态，明确哪些模块应被删除、哪些模块应保留为正式边界。
- **BREAKING**: 对内部运行时实现边界做约束收紧，后续执行相关新逻辑将不再允许进入 `strict_runtime_impl.py`、`bridge_adapter.py`、`portfolio_builder.py` 这类过渡层。

## Capabilities

### New Capabilities
- `runtime-bridge-retirement`: 定义 runtime bridge 的退场顺序、删除前提、验证标准和回退要求。

### Modified Capabilities
- `execution-shell-unification`: 补充 bridge adapter / frozen loop / strict shim 的正式退场约束，明确唯一正式执行入口与禁止新增逻辑的边界。
- `execution-contract-goldens`: 补充 runtime bridge 清理前后的 golden 覆盖要求、可接受漂移边界和失败判定。

## Impact

- 影响代码面：`backend/core/engine_runtime/*`、`backend/core/stage_pipeline/*`、`backend/core/engine_vector/strict_runtime_impl.py`、`backend/core/engine_vector/portfolio_simulator_strict.py`、`backend/core/portfolio/portfolio_builder.py`、`backend/core/portfolio/frozen_loop.py`
- 影响验证面：runtime golden、执行链 parity、结果计数器和审计输出
- 不直接变更 HTTP API、前端协议或研究口径，但会约束后续执行相关改动只能进入正式 runtime 边界
