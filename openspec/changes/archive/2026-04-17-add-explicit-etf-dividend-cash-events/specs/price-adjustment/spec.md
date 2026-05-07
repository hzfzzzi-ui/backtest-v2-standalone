## ADDED Requirements

### Requirement: 显式 ETF 分红事件不得与 HFQ 估值重复计数
当 `cn_etf` 主线启用显式现金分红事件时，系统 MUST 在除息日对持仓估值基线做中性化处理，避免同一笔分红同时出现在 HFQ 估值和 `cash`/`dividend_receivable` 中。

#### Scenario: 除息日估值与现金分红只计一次
- **WHEN** 某 ETF 在日期 `D` 发生现金分红
- **AND** 组合在 `D` 日 open fills 之前持有该 ETF
- **THEN** 当日 market value 仅反映 ex-div 后市值
- **AND** 分红金额仅通过 `cash` 或 `dividend_receivable` 体现一次

### Requirement: 份额折算与现金分红必须分离处理
系统 MUST 将“大比例 adj_factor 变化 + 开盘跳空匹配”的份额折算与“小比例 adj_factor 变化”的现金分红分开处理。

#### Scenario: 小比例 adj_factor 变化不触发缩股扩股
- **WHEN** ETF `adj_factor` 发生小比例变化且不满足 share transform 判定
- **THEN** 系统不得调整持仓股数
- **AND** 如存在正式分红事件，则改走显式 dividend path
