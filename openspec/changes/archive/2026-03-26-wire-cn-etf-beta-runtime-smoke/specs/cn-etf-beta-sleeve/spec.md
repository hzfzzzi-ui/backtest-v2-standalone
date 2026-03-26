## ADDED Requirements

### Requirement: ETF beta sleeve 运行时必须命中 ETF 真值表并暴露 Phase 1 摘要
当 `cn_etf_beta` 作为 `asset_scope=cn_etf` 的正式运行入口被消费时，系统 MUST 使用 ETF 日线真值表与 ETF 研究入口摘要构建运行时上下文，并在产物中显式暴露 `selected_etfs`、`out_of_scope_etfs`、`daily_table`、`coverage_start` 和 `coverage_end`。

#### Scenario: ETF beta sleeve 从 ETF 真值表读取
- **WHEN** 用户运行 `cn_etf` 研究入口或 ETF beta 主线 smoke
- **THEN** 系统 MUST 从 `pams_cn_etf_daily` 构建行情读取路径
- **THEN** `run_meta.json` MUST 暴露 ETF Phase 1 摘要而不是股票 PIT 摘要

### Requirement: ETF beta 主线 smoke 通过条件必须以路径真相为准
系统 MUST 提供一条可复现的 `cn_etf_beta` 最小 smoke 路径，用于验证 ETF provider/read path、runtime truth 和产物完整性；该 smoke SHALL NOT 以“必须产生交易”作为通过条件。

#### Scenario: ETF smoke 无交易但路径正确
- **WHEN** `cn_etf_beta` smoke run 成功完成且结果为 `0 trades`
- **THEN** 系统 MUST 仍能将其判定为 provider/read path smoke 成功
- **THEN** 前提是 ETF 资产语义、ETF 日线表、ETF 覆盖窗口与 ETF sleeve 摘要全部一致
