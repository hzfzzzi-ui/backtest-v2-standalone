# csi800-tushare-pit-history Specification

## Purpose
TBD - created by archiving change add-csi800-tushare-pit-data-source. Update Purpose after archive.
## Requirements
### Requirement: CSI800 正式 PIT 历史必须基于 Tushare 实际 trade_date 变化重建
系统 MUST 为 `000906.SH` 提供一条正式 `Tushare` PIT 历史链，基于 `index_weight` 的实际 `trade_date` 成分集合变化重建 snapshots 和 changes，而不是继续把月末重建结果当作正式历史。

系统 MUST 为 `000906.SH` 提供一条正式 `Tushare` PIT 历史链，基于 `index_weight` 的实际 `trade_date` 成分集合变化重建 snapshots 和 changes，而不是继续把月末重建结果当作正式历史。

#### Scenario: 基于实际 trade_date 生成 snapshots
- **WHEN** 系统执行 `CSI800` 正式 PIT 抓取脚本
- **THEN** 系统 MUST 从 `Tushare index_weight(index_code='000906.SH')` 读取 `trade_date` 和成分集合
- **THEN** 系统 MUST 只对有效 trade_date 生成可复核的 snapshots 和 changes 文件

#### Scenario: 部分 trade_date 不得冒充正式快照
- **WHEN** 某个 `trade_date` 的成分集合不完整，或无法构成完整的 800 成分快照
- **THEN** 系统 MUST 将该日期排除出正式 snapshots
- **THEN** 系统 MUST 在摘要中记录被跳过的日期统计，而不是静默并入正式历史### Requirement: CSI800 正式 Tushare 链必须输出结构化抓取摘要
系统 MUST 在 `CSI800` 正式 PIT 抓取完成后输出结构化摘要，便于人工核验覆盖情况、source label 和可用 trade_date 质量。

#### Scenario: 抓取摘要包含关键统计
- **WHEN** `CSI800` 正式 PIT 抓取脚本成功完成
- **THEN** 系统 MUST 输出至少包含 `snapshot_dates`、`usable_trade_dates`、`skipped_trade_dates`、`changes_rows` 和 `source_label` 的摘要

#### Scenario: 无法形成正式历史时显式失败
- **WHEN** 指定区间内没有任何可用的完整 trade_date
- **THEN** 系统 MUST 终止正式抓取并返回错误
- **THEN** 系统 MUST NOT 生成伪造的正式 changes 文件

### Requirement: CSI800 正式 Tushare 链必须输出结构化抓取摘要
系统 MUST 在 `CSI800` 正式 PIT 抓取完成后输出结构化摘要，便于人工核验覆盖情况、source label 和可用 trade_date 质量。

#### Scenario: 抓取摘要包含关键统计
- **WHEN** `CSI800` 正式 PIT 抓取脚本成功完成
- **THEN** 系统 MUST 输出至少包含 `snapshot_dates`、`usable_trade_dates`、`skipped_trade_dates`、`changes_rows` 和 `source_label` 的摘要

#### Scenario: 无法形成正式历史时显式失败
- **WHEN** 指定区间内没有任何可用的完整 trade_date
- **THEN** 系统 MUST 终止正式抓取并返回错误
- **THEN** 系统 MUST NOT 生成伪造的正式 changes 文件

