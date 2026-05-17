## ADDED Requirements

### Requirement: combo V4 promotion MUST append an auditable override-promotion record

当系统按用户批准把 D7 deep-only 组合候选升格为 V4 时，系统 MUST 保留一条明确说明“这是人工 override promotion”的可审计记录。

#### Scenario: append official promotion record for combo V4

- **WHEN** `CN_STOCK_ETF_COMBO_BASELINE_V4` 被正式注册
- **THEN** 系统 MUST 向 `outputs/baselines/CN_STOCK_ETF_COMBO_BASELINE_V4/machine/experiment_ledger.jsonl` 追加一条 promotion 记录
- **THEN** 系统 MUST 在 `report_index.json`、`baseline_report.md` 和 `baseline_digest.md` 中追加对应条目
- **THEN** promotion note MUST 明确写出：full-cycle combo headline 相对 V3 并未显著胜出，这次升格属于 user-approved override
- **THEN** 若该条记录登记为 `PASS`，系统 MUST 刷新 `latest_champion.json`
