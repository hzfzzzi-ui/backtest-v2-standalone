## ADDED Requirements

### Requirement: HTTP API 透传 strength_rank 参数
`BacktestV2ExperimentRequest` SHALL 包含 `enable_strength_rank`、`strength_ma`、`strength_top_k_mode` 可选字段，并在 overrides builder 中透传到 `run_experiment()`。

#### Scenario: 启用 strength_rank 通过 API
- **WHEN** 客户端发送 `{"enable_strength_rank": true, "strength_ma": 120}` 到实验 API
- **THEN** 引擎在 `run_portfolio_backtest()` 中接收 `enable_strength_rank=True, strength_ma=120`

#### Scenario: 未设置时使用默认值
- **WHEN** 客户端未发送 `enable_strength_rank` 字段
- **THEN** 引擎使用默认值 `enable_strength_rank=False`

### Requirement: HTTP API 透传 multifactor_rank 参数
`BacktestV2ExperimentRequest` SHALL 包含 `enable_multifactor_rank`、`mf_topk` 可选字段，并在 overrides builder 中透传。

#### Scenario: 启用 multifactor_rank 通过 API
- **WHEN** 客户端发送 `{"enable_multifactor_rank": true, "mf_topk": 8}` 到实验 API
- **THEN** 引擎在 `run_portfolio_backtest()` 中接收 `enable_multifactor_rank=True, mf_topk=8`
