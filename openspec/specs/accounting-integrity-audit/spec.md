# accounting-integrity-audit Specification

## Purpose
TBD - created by archiving change add-formal-accounting-invariant-audit. Update Purpose after archive.
## Requirements
### Requirement: 主线会计审计必须基于正式记账快照
系统 MUST 从当前正式执行链的 canonical accounting snapshot 或等价正式快照生成会计审计证据，SHALL NOT 通过事后重放 `portfolio_trades.csv` 或复用历史旁路检查器作为唯一真相。

系统 MUST 从当前正式执行链的 canonical accounting snapshot 或等价正式快照生成会计审计证据，SHALL NOT 通过事后重放 `portfolio_trades.csv` 或复用历史旁路检查器作为唯一真相。

#### Scenario: stage pipeline 路径提供正式快照
- **WHEN** 当前正式 stage pipeline 完成某个交易日的 fill accounting 和 daily accounting
- **THEN** 会计审计 SHALL 使用该交易日的正式记账快照作为现金、持仓和 NAV 校验输入
- **THEN** 同一交易日的会计审计结果 SHALL 可被后续 `audit.json` 与 `research_audit` 复用### Requirement: 会计审计必须校验现金守恒与持仓守恒
系统 MUST 对每个交易日校验 `cash_before + sell_net - buy_net = cash_after`，并校验每个标的与组合层的持仓数量守恒关系。

#### Scenario: 现金与持仓守恒通过
- **WHEN** 某交易日的买卖成交、现金变动和收盘后持仓数量全部与正式记账快照一致
- **THEN** 该交易日 SHALL 被标记为现金守恒通过且持仓守恒通过
- **THEN** 会计审计摘要 SHALL 累加相应通过计数

#### Scenario: 现金或持仓守恒失败
- **WHEN** 某交易日的 `cash_after` 与期望现金不一致，或任一标的 `position_after != position_before + qty_buy - qty_sell`
- **THEN** 该交易日 SHALL 被标记为会计异常
- **THEN** 会计审计 SHALL 记录失败类型、日期和受控样本

### Requirement: 会计审计必须校验 NAV 一致性与硬边界
系统 MUST 校验 `nav = cash + market_value`，并把负现金、超出 `max_positions` 上限和非法 NAV 视为硬性异常。

系统 MUST 校验 `nav = cash + market_value`，并把负现金、超出 `max_positions` 上限和非法 NAV 视为硬性异常。

#### Scenario: NAV 一致且硬边界通过
- **WHEN** 某交易日的 `nav` 与 `cash + market_value` 在约定容差内一致，且 `cash >= 0`、持仓数未超过上限
- **THEN** 该交易日 SHALL 被标记为 NAV 校验通过

#### Scenario: 出现硬性异常
- **WHEN** 某交易日出现负现金、超仓上限、负 NAV、NaN NAV 或 NAV 恒等式不成立
- **THEN** 会计审计 SHALL 将该交易日标记为硬性失败
- **THEN** 会计审计摘要 SHALL 记录对应异常计数### Requirement: 会计审计必须输出受控摘要与失败样本
系统 MUST 输出可供正式审计消费的会计摘要，包括通过/失败计数、异常类别计数和受控失败样本；系统 SHALL NOT 将全量日级快照直接内联到主审计文件中。

#### Scenario: 写入受控摘要
- **WHEN** 一次实验完成并生成正式 execution audit
- **THEN** 会计审计输出 SHALL 包含现金守恒、持仓守恒、NAV 校验、负现金和超仓异常的摘要计数
- **THEN** 每类失败 SHALL 至少保留有限数量的样本记录供人工复核

### Requirement: 会计审计必须校验现金守恒与持仓守恒
系统 MUST 对每个交易日校验 `cash_before + sell_net - buy_net = cash_after`，并校验每个标的与组合层的持仓数量守恒关系。

#### Scenario: 现金与持仓守恒通过
- **WHEN** 某交易日的买卖成交、现金变动和收盘后持仓数量全部与正式记账快照一致
- **THEN** 该交易日 SHALL 被标记为现金守恒通过且持仓守恒通过
- **THEN** 会计审计摘要 SHALL 累加相应通过计数

#### Scenario: 现金或持仓守恒失败
- **WHEN** 某交易日的 `cash_after` 与期望现金不一致，或任一标的 `position_after != position_before + qty_buy - qty_sell`
- **THEN** 该交易日 SHALL 被标记为会计异常
- **THEN** 会计审计 SHALL 记录失败类型、日期和受控样本

### Requirement: 会计审计必须输出受控摘要与失败样本
系统 MUST 输出可供正式审计消费的会计摘要，包括通过/失败计数、异常类别计数和受控失败样本；系统 SHALL NOT 将全量日级快照直接内联到主审计文件中。

#### Scenario: 写入受控摘要
- **WHEN** 一次实验完成并生成正式 execution audit
- **THEN** 会计审计输出 SHALL 包含现金守恒、持仓守恒、NAV 校验、负现金和超仓异常的摘要计数
- **THEN** 每类失败 SHALL 至少保留有限数量的样本记录供人工复核

