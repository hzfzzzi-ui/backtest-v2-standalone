## ADDED Requirements

### Requirement: D7 stock baseline promotion MUST append an auditable official promotion record

当系统将 D7 deep-only 结果正式升格进 `baseline_V10_1` 时，系统 MUST 追加一条可审计的 promotion 记录，而不是只静默改写 baseline 目录。

#### Scenario: append official promotion ledger entry for baseline_V10_1

- **WHEN** `baseline_V10_1` 被重挂到 `exp_20260512_063520440_82bb`
- **THEN** 系统 MUST 向 `outputs/baselines/baseline_V10_1/machine/experiment_ledger.jsonl` 追加一条 official promotion 记录
- **THEN** 系统 MUST 在 `outputs/baselines/baseline_V10_1/machine/report_index.json` 中追加对应条目
- **THEN** 系统 MUST 在 `outputs/baselines/baseline_V10_1/human/baseline_report.md` 与 `baseline_digest.md` 中追加对应摘要
- **THEN** 该次 promotion 若登记为 `PASS`，系统 MUST 同步刷新 `outputs/baselines/baseline_V10_1/machine/latest_champion.json`
