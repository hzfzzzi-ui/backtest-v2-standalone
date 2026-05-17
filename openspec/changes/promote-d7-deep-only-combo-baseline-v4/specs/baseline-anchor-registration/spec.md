## ADDED Requirements

### Requirement: combo V4 promotion MUST bind the D7 deep-only full-cycle combo experiment

当用户明确要求将组合主线升级到 V4 时，系统 MUST 将新的正式 combo baseline truth 绑定到 D7 deep-only 的全周期 unified combo 实验，而不是只更新展示层标识。

#### Scenario: promote deep-only combo candidate to V4

- **WHEN** 操作方执行 `CN_STOCK_ETF_COMBO_BASELINE_V4` promotion
- **THEN** `outputs/baselines/CN_STOCK_ETF_COMBO_BASELINE_V4/baseline.json` MUST 记录 `linked_exp_id = exp_20260511_073506050_3d22`
- **THEN** `CN_STOCK_ETF_COMBO_BASELINE_V4` MUST 记录 `execution_contract_ref`
- **THEN** `CN_STOCK_ETF_COMBO_BASELINE_V4` MUST 成为 `cn_a_multi_sleeve:2012-2026` 的唯一 active baseline
- **THEN** `CN_STOCK_ETF_COMBO_BASELINE_V3` MUST 显式标记为 `superseded`

### Requirement: combo V4 promotion MUST preserve V3 as a rollback anchor

V4 promotion MUST 新建 baseline id，而不是静默重写 V3。

#### Scenario: preserve V3 after V4 promotion

- **WHEN** `CN_STOCK_ETF_COMBO_BASELINE_V4` 完成注册
- **THEN** `CN_STOCK_ETF_COMBO_BASELINE_V3` SHALL 继续保留 baseline 目录、config 快照和 linked experiment 引用
- **THEN** 系统 SHALL NOT 用 V4 内容覆盖 `CN_STOCK_ETF_COMBO_BASELINE_V3` 的 baseline truth
