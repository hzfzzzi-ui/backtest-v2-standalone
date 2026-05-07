## ADDED Requirements

### Requirement: 正式 baseline 锚点重挂必须留下可审计的 baseline 台账记录

当系统重挂既有正式 baseline 锚点时，系统 MUST 追加一条可审计的 baseline 台账记录到该 baseline 的 machine/human 资产中。该记录 MUST 写入 `experiment_ledger.jsonl`、`report_index.json`、`baseline_report.md` 和 `baseline_digest.md`；当重挂结果被登记为 `PASS` 时，系统 MUST 同步刷新 `latest_champion.json`。

#### Scenario: baseline_V10.1 官方锚点重挂成功

- **WHEN** `baseline_V10.1` 被正式重挂到新的 linked experiment，且本次重挂结果登记为 `PASS`
- **THEN** 系统 MUST 向 `outputs/baselines/baseline_V10_1/machine/experiment_ledger.jsonl` 追加一条 official rebase 记录
- **THEN** 系统 MUST 在 `outputs/baselines/baseline_V10_1/machine/report_index.json` 中追加对应条目
- **THEN** 系统 MUST 在 `outputs/baselines/baseline_V10_1/human/baseline_report.md` 与 `baseline_digest.md` 中追加对应摘要
- **THEN** 系统 MUST 将 `outputs/baselines/baseline_V10_1/machine/latest_champion.json` 更新为这次 official rebase 的 PASS 结果
