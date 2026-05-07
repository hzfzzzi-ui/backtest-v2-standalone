## ADDED Requirements

### Requirement: `v10/moneyflow_monthly_shadow_s1` MUST define the minimal monthly divergence stock-baseline shadow study
系统 MUST 提供正式 study `v10/moneyflow_monthly_shadow_s1`，用于在 `baseline_V10_1` 上评估 `monthly_divergence_rate` 的最小 shadow A/B。该 study MUST 以 `baseline_V10_1` 作为 compare 对象，且 SHALL NOT 自动 append baseline。

#### Scenario: load the study definition
- **WHEN** 系统加载 `v10/moneyflow_monthly_shadow_s1`
- **THEN** study MUST 声明 `study_id`、`baseline_id`、`asset_scope`、`hypothesis`、`variants`、`windows`、`required_outputs`
- **THEN** `baseline_id` MUST 等于 `baseline_V10_1`
- **THEN** `required_outputs` MUST 只包含 `machine_bundle`、`human_bundle` 和 `study_conclusion`

### Requirement: the study MUST use modern moneyflow daily factor snapshots
`v10/moneyflow_monthly_shadow_s1` MUST 使用现代 `daily_factor_snapshot` 作为 moneyflow overlay 输入，且 SHALL NOT 依赖 legacy monthly factor panel 或 coverage ledger。

#### Scenario: build the 1217 window payload
- **WHEN** 系统构建 `1217` 窗口的研究请求
- **THEN** payload MUST 指向 `outputs/studies/factors/moneyflow_factor_real_mainline_s2/1217/A_H20_CONTROL/machine/factor_snapshot.csv`
- **THEN** overlay source MUST 使用 `factor_id = monthly_divergence_rate`
- **THEN** overlay source MUST 使用 `score_field = rank_value`
- **THEN** overlay source MUST 使用 `available_column = availability_flag`

#### Scenario: build the 1226 window payload
- **WHEN** 系统构建 `1226` 窗口的研究请求
- **THEN** payload MUST 指向 `outputs/studies/factors/moneyflow_factor_real_mainline_s2/1226/A_H20_CONTROL/machine/factor_snapshot.csv`
- **THEN** overlay source MUST 保持 `source_kind = daily_factor_snapshot`
- **THEN** overlay source MUST 保持 `lower_is_better = false`

### Requirement: window-level runtime source metadata and variant-level overlay mode MUST compose without loss
当 `v10/moneyflow_monthly_shadow_s1` 的 window base runtime config 已提供 `moneyflow_overlay` 的路径与分数字段时，variant 追加 `enabled / mode / factor_role / apply_layer` SHALL NOT 覆盖掉这些 source 元数据。

#### Scenario: merge shadow variant on top of a window base runtime config
- **WHEN** 系统为某个窗口加载 base runtime config，并再叠加 `SHADOW` variant 的 overlay override
- **THEN** 最终 payload MUST 同时保留 `factor_snapshot_path`、`score_source`、`factor_id`、`score_field`
- **THEN** 最终 payload MUST 额外包含 `enabled = true` 与 `mode = shadow`

### Requirement: the study MUST use runtime-config-backed execution truth
`v10/moneyflow_monthly_shadow_s1` MUST 通过 `runtime_config_path` 与 `runtime_config_json` 驱动 backend runtime；系统 SHALL NOT 依赖 semantic workbench config 去承载 baseline-like runtime 参数。

#### Scenario: build the 1226 bull-only tiebreak payload
- **WHEN** 系统构建 `1226` 窗口 `BULL_ONLY_TIEBREAK` 的 study payload
- **THEN** payload MUST 包含 `runtime_config_path`
- **THEN** payload MUST 递归物化 `runtime_config_json.asset_context.moneyflow_overlay`
- **THEN** payload MUST 将 `mode` 设为 `bull_only_tiebreak`
- **THEN** payload SHALL NOT 退回 `workbench_config_path`

### Requirement: the study MUST expose only the minimal three-variant matrix
`v10/moneyflow_monthly_shadow_s1` MUST 只暴露 `B0`、`SHADOW` 和 `BULL_ONLY_TIEBREAK` 三个变体，避免把多种接法混在同一轮研究里。

#### Scenario: control variant
- **WHEN** 运行 `B0`
- **THEN** payload SHALL NOT 开启 `moneyflow_overlay`

#### Scenario: shadow variant
- **WHEN** 运行 `SHADOW`
- **THEN** payload MUST 开启 `moneyflow_overlay.enabled = true`
- **THEN** payload MUST 设置 `moneyflow_overlay.mode = shadow`
- **THEN** stock baseline 的主排序行为 SHALL NOT 因此改变

#### Scenario: bull-only tiebreak variant
- **WHEN** 运行 `BULL_ONLY_TIEBREAK`
- **THEN** payload MUST 开启 `moneyflow_overlay.enabled = true`
- **THEN** payload MUST 设置 `moneyflow_overlay.mode = bull_only_tiebreak`
- **THEN** overlay SHALL 只在 `BULL` 状态内参与并列打破

### Requirement: the study MUST remain on the official study execution surface
`v10/moneyflow_monthly_shadow_s1` MUST 具备 generated thin script 入口，并通过 `study_run` 执行；thin script SHALL NOT 内嵌研究循环或结果判定逻辑。

#### Scenario: run generated thin script
- **WHEN** 用户执行 `backend/scripts/generated/run_v10_moneyflow_monthly_shadow_s1.py`
- **THEN** 脚本 MUST 转发到 `study_run v10/moneyflow_monthly_shadow_s1`
- **THEN** 脚本 SHALL NOT 引入额外业务逻辑
