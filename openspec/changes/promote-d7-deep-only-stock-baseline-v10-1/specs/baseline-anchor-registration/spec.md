## ADDED Requirements

### Requirement: D7 deep-only stock promotion MUST rebind baseline_V10_1 to the audited full-cycle experiment

当用户明确要求把 D7 deep-only stock-only 结果升格为正式 A 股 stock baseline 时，系统 MUST 将 `baseline_V10_1` 的正式 baseline truth 重挂到已经完成全周期审计的 D7 实验，而不是只更新展示层摘要。

#### Scenario: promote D7 deep-only to baseline_V10_1

- **WHEN** 操作方执行 D7 deep-only stock baseline 升格
- **THEN** `outputs/baselines/baseline_V10_1/baseline.json` MUST 记录 `linked_exp_id = exp_20260512_063520440_82bb`
- **THEN** `outputs/baselines/baseline_V10_1/baseline.json` MUST 记录对应 `execution_contract_ref`
- **THEN** `outputs/baselines/baseline_V10_1/config.json` 与 `baseline_config_snapshot.json` MUST 切换为 D7 全周期正式配置快照
- **THEN** `outputs/baselines/index.json` MUST 反映新的 `linked_exp_id`、`config_hash` 和 linked experiment 指标摘要

### Requirement: stock baseline promotion MUST NOT mutate combo baseline truth

当系统执行 D7 deep-only stock baseline 升格时，系统 MUST 将影响范围限定在 `baseline_V10_1`，不得顺带改写任何 combo baseline 的正式法源或状态。

#### Scenario: stock-only promotion does not alter combo baseline

- **WHEN** 操作方升格 `baseline_V10_1`
- **THEN** `CN_STOCK_ETF_COMBO_BASELINE_V3` SHALL NOT 被重挂、降级或覆盖
- **THEN** 本次 promotion 的法源范围 MUST 仅限 `cn_a_equity`
