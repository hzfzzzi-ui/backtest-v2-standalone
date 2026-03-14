## MODIFIED Requirements

### Requirement: API 请求模型包含选股排序字段
`BacktestV2ExperimentRequest` Pydantic 模型 SHALL 包含以下可选字段：
- `enable_strength_rank: bool | None`
- `strength_ma: int | None`
- `strength_top_k_mode: str | None`
- `enable_multifactor_rank: bool | None`
- `mf_topk: int | None`
- `signal_generation: dict | None`
- `signal_composition: dict | None`

其中：
- `signal_generation` SHALL 用于声明 alpha 模块列表及其参数
- `signal_composition` SHALL 用于声明组合模式、同股冲突策略和持仓所有权策略

#### Scenario: API 请求携带选股字段
- **WHEN** HTTP POST 请求 body 包含 `"enable_strength_rank": true`
- **THEN** 请求验证通过，字段值传入 overrides builder

#### Scenario: API 请求携带组合字段
- **WHEN** HTTP POST 请求 body 包含 `signal_generation.modules` 与 `signal_composition.compose_mode`
- **THEN** 请求验证 SHALL 通过
- **THEN** 组合配置 SHALL 传入后端编译链路

#### Scenario: API 请求未携带组合字段
- **WHEN** HTTP POST 请求 body 未包含 `signal_generation` 与 `signal_composition`
- **THEN** 请求验证通过，这两个字段为 `None`
- **THEN** 单次回测 SHALL 继续沿用现有单策略默认行为

## ADDED Requirements

### Requirement: 单次回测主路径支持多 alpha 组合编译
单次回测主路径 SHALL 能够将前端提交的组合配置编译为运行时配置，并驱动公开运行路径执行多 alpha 组合回测。

运行时配置 MUST 至少保留以下信息：
- `signal_generation.modules`
- `signal_composition.compose_mode`
- `signal_composition.same_symbol_policy`
- `signal_composition.holding_ownership`

#### Scenario: 编译 breakout 与 RSI 组合
- **WHEN** 单次回测请求同时声明 `breakout_55`、`rsi_reversal`，并设置 `compose_mode = regime_route`
- **THEN** 编译后的运行时配置 SHALL 包含两个独立模块及其 `alpha_id`
- **THEN** 公开运行路径 SHALL 使用该组合配置启动回测

#### Scenario: baseline 请求保持兼容
- **WHEN** 单次回测请求未声明任意组合配置
- **THEN** 运行时配置 SHALL 不注入组合层默认值
- **THEN** 回测结果 SHALL 与现有 baseline 单策略语义兼容
