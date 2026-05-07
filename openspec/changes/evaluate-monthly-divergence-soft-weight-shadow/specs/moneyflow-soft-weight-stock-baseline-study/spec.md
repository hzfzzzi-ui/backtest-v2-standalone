## ADDED Requirements

### Requirement: `v10/moneyflow_monthly_soft_weight_s1` MUST define the minimal monthly divergence soft-weight baseline study
系统 MUST 提供正式 study `v10/moneyflow_monthly_soft_weight_s1`，用于在 `baseline_V10_1` 壳上评估 `monthly_divergence_rate` 的月度辅助权重接法。

#### Scenario: load the study definition
- **WHEN** 系统加载 `v10/moneyflow_monthly_soft_weight_s1`
- **THEN** study MUST 声明 `study_id`、`baseline_id`、`asset_scope`、`hypothesis`、`variants`、`windows`、`required_outputs`
- **THEN** `baseline_id` MUST 等于 `baseline_V10_1`
- **THEN** 变体 MUST 只包含 `B0`、`SCORE_WEIGHT_BASE`、`MF_SOFT_10`、`MF_SOFT_20`

### Requirement: the study MUST use runtime-config-backed modern moneyflow snapshots
`v10/moneyflow_monthly_soft_weight_s1` MUST 通过 `runtime_config_path` 与 `runtime_config_json` 驱动 backend runtime，并使用现代 `daily_factor_snapshot` 作为 moneyflow 数据源。

#### Scenario: build the 1226 soft-weight payload
- **WHEN** 系统构建 `1226` 窗口 `MF_SOFT_10` 的 payload
- **THEN** payload MUST 包含 `runtime_config_path`
- **THEN** payload MUST 包含 `runtime_config_json.asset_context.moneyflow_overlay`
- **THEN** overlay source MUST 指向 `moneyflow_factor_real_mainline_s2/1226/A_H20_CONTROL/machine/factor_snapshot.csv`
- **THEN** payload SHALL NOT 退回 `workbench_config_path`

### Requirement: the study MUST separate sizing-mode effect from moneyflow effect
系统 MUST 通过独立 control 变体区分“只是启用 score-weighted sizing”与“moneyflow soft-weight 真正带来的差异”。

#### Scenario: score-weight base control
- **WHEN** 运行 `SCORE_WEIGHT_BASE`
- **THEN** payload MUST 设置 `sizing.weight_mode = score_weighted`
- **THEN** payload SHALL NOT 开启 `moneyflow_overlay`

#### Scenario: moneyflow soft-weight variants
- **WHEN** 运行 `MF_SOFT_10` 或 `MF_SOFT_20`
- **THEN** payload MUST 设置 `sizing.weight_mode = score_weighted`
- **THEN** payload MUST 开启 `moneyflow_overlay.enabled = true`
- **THEN** payload MUST 设置 `moneyflow_overlay.mode = soft_weight`

### Requirement: soft-weight study SHALL adjust only the planned candidate band
`v10/moneyflow_monthly_soft_weight_s1` 的 soft-weight 研究 SHALL 只影响计划买入范围内的候选权重，不得改变 baseline 主排序顺序。

#### Scenario: run the soft-weight variant
- **WHEN** 运行 `MF_SOFT_10`
- **THEN** 候选顺序 MUST 继续服从 baseline 主排序
- **THEN** 只有计划买入范围内的候选可以收到 `score_weight_scale` 调整
- **THEN** order sizing MUST 落在给定 band 内

### Requirement: the study MUST remain on the official study execution surface
`v10/moneyflow_monthly_soft_weight_s1` MUST 提供 generated thin script，并通过 `study_run` 执行。

#### Scenario: run generated thin script
- **WHEN** 用户执行 `backend/scripts/generated/run_v10_moneyflow_monthly_soft_weight_s1.py`
- **THEN** 脚本 MUST 转发到 `study_run v10/moneyflow_monthly_soft_weight_s1`
- **THEN** 脚本 SHALL NOT 内嵌业务逻辑
