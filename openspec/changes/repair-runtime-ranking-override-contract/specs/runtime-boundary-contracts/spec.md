## ADDED Requirements

### Requirement: legacy runtime-config 排序字段 MUST 规范化到唯一 execution override 真相

当 direct runtime-config path 进入正式 execution shell 时，系统 MUST 在构建 `execution_contract` / `RuntimePlan.execution_overrides` 时，把 legacy `runtime_config.strategy.params` 中声明的排序字段一次性规范化为正式执行覆盖参数。进入 execution shell 后，排序执行真相 MUST 只存在于 `execution_overrides`，不得让 `runtime_config.strategy.params` 与 `execution_overrides` 并列生效。

#### Scenario: residual 排序意图进入 direct runtime-config path
- **WHEN** `runtime_config.strategy.params.ranking_mode = "residual_only"` 且调用方未显式提供 `execution_overrides.enable_multifactor_rank`
- **THEN** 系统 MUST 在构建 `RuntimePlan` 时写出 `execution_overrides.enable_multifactor_rank = true`
- **THEN** stage pipeline MUST 只通过 `execution_overrides` 看到排序链已启用

#### Scenario: 显式 residual 开关进入 direct runtime-config path
- **WHEN** `runtime_config.strategy.params.enable_residual_ranking = true` 且调用方未显式提供 `execution_overrides.enable_multifactor_rank`
- **THEN** 系统 MUST 在构建 `RuntimePlan` 时写出 `execution_overrides.enable_multifactor_rank = true`

#### Scenario: 显式 execution override 优先于派生值
- **WHEN** `runtime_config.strategy.params.ranking_mode = "residual_only"` 但调用方显式提供 `execution_overrides.enable_multifactor_rank = false`
- **THEN** 系统 MUST 保留显式 override
- **THEN** 系统 SHALL NOT 用派生值覆盖显式关闭
