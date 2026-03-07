## MODIFIED Requirements

### Requirement: 实验运行器支持完整参数透传
现有 `batch_runner.py` / `experiment_runner.py` 的 overrides 字典 SHALL 支持透传 `enable_strength_rank`、`strength_ma`、`strength_top_k_mode`、`enable_multifactor_rank`、`mf_topk` 到 `run_portfolio_backtest()`。

#### Scenario: 通过 overrides 启用 strength_rank
- **WHEN** 调用 `run_experiment(base_cfg, overrides={"enable_strength_rank": True, "strength_ma": 120})`
- **THEN** 引擎执行时 `enable_strength_rank=True` 且动量排序生效

#### Scenario: 通过 overrides 设置成本参数
- **WHEN** 调用时 overrides 包含 costs 配置覆盖
- **THEN** `cfg_obj.costs` 使用覆盖值而非配置文件默认值
