# csi800-formal-history-materialization Specification

## Purpose
TBD - created by archiving change restore-csi800-formal-history-coverage. Update Purpose after archive.
## Requirements
### Requirement: CSI800 正式历史链物化
系统 MUST 提供 `CSI800/000906.SH` 正式历史链物化能力，能够从覆盖 `2007+` 的长历史 seed 和可选尾部 patch 生成单一 formal chain，并输出可审计的 provenance/coverage 摘要。

#### Scenario: 用长历史 seed 物化正式链
- **WHEN** 运维提供覆盖 `2007+` 的 `000906.SH` seed CSV 以生成正式历史链
- **THEN** 系统 MUST 输出可直接导入 `pit_index_constituents` 的 `changes.csv`
- **THEN** 输出记录的 `source` MUST 统一为单一 formal source label
- **THEN** summary MUST 包含 seed/patch 来源、最早起点、最晚终点和是否覆盖 `required_start`

#### Scenario: 用 patch 替换 seed 尾部
- **WHEN** 运维同时提供 seed CSV 和 patch CSV
- **THEN** 系统 MUST 仅从 patch 最早 `start_date` 起替换 seed 尾部
- **THEN** 系统 MUST 保留 patch 边界之前的长历史记录
- **THEN** summary MUST 明确输出 patch 边界和最终正式链统计

