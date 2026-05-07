## ADDED Requirements

### Requirement: research audit 必须给出正式 ETF Phase 1 的零交易根因摘要
当实验属于正式 ETF Phase 1 主线时，`research_audit` MUST 输出零交易或低 CAGR 的主瓶颈层、关键证据计数和结论摘要，而不是仅输出笼统的 PASS/WARN/FAIL。

#### Scenario: 正式 ETF Phase 1 出现零交易
- **WHEN** 正式 ETF Phase 1 实验完成且 `orders=0` 或 `closed_trades=0`
- **THEN** `research_audit` MUST 输出主瓶颈层
- **THEN** `research_audit` MUST 输出最主要的拒绝原因计数、空仓占比和实际仓位利用率

### Requirement: research audit 必须汇总信号到成交的链路计数
当实验属于正式 ETF Phase 1 主线时，`research_audit` MUST 汇总信号数、订单数、成交数、未成交数和未成交原因统计，以便直接定位链路中断位置。

#### Scenario: 链路计数可定位中断
- **WHEN** 用户查看正式 ETF Phase 1 的 `research_audit`
- **THEN** 审计结果 MUST 能回答信号、订单和成交分别有多少
- **THEN** 审计结果 MUST 能回答未成交主要发生在什么原因上
