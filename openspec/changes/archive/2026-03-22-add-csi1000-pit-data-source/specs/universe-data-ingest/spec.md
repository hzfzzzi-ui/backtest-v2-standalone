## ADDED Requirements

### Requirement: CSI1000 正式 PIT 数据导入必须以调样日历驱动
系统 MUST 为 `CSI1000` 提供正式的 PIT 数据导入链路，使用显式调样日历驱动快照抓取和变更重建，而不是默认按月采样或直接复用最新静态成分。

#### Scenario: 按调样日历生成快照
- **WHEN** 执行 `CSI1000` 正式 PIT 抓取脚本
- **THEN** 系统 MUST 按调样日历中的每个 `effective_date` 抓取对应成分快照
- **THEN** 系统 MUST 生成可复核的 snapshots 文件和 changes 文件

#### Scenario: 从相邻快照重建变更
- **WHEN** 系统拿到相邻两个 `CSI1000` 快照
- **THEN** 系统 MUST 通过 diff 重建 `in_date` 和 `out_date`
- **THEN** 最终 changes 文件 MUST 可直接导入 `pit_index_constituents` 的 `000852.SH` 分区

### Requirement: CSI1000 正式数据源必须标记来源与保真度
系统 MUST 在 `CSI1000` 导入链路中区分正式历史源、近似历史源和静态 fallback，并把来源标签写入导入结果。

#### Scenario: Tushare 正式来源标签
- **WHEN** `CSI1000` 快照由正式历史接口抓取
- **THEN** 导入记录 MUST 带有明确的 `source` 标签，例如 `tushare_csi1000_rebalance`

#### Scenario: 静态 fallback 来源标签
- **WHEN** 系统使用最新静态成分作为应急数据
- **THEN** 导入记录 MUST 带有 `static` 或等价的低保真来源标签
- **THEN** 系统 MUST NOT 将该结果默认为正式 PIT 历史

### Requirement: CSI1000 导入必须输出质量统计
系统 MUST 在导入或导入前检查阶段输出 `CSI1000` 成分历史的关键统计，便于审计和回滚。

#### Scenario: 输出导入统计
- **WHEN** `CSI1000` changes 文件被生成或导入完成
- **THEN** 系统 MUST 输出至少包含 `rows`、`distinct_symbols`、`distinct_start_dates`、`open_rows`、`min_start_date` 和 `max_start_date` 的统计摘要

#### Scenario: 导入只影响 000852.SH 分区
- **WHEN** 导入 `CSI1000` changes 文件
- **THEN** 系统 MUST 只替换 `pit_index_constituents` 中 `index_code='000852.SH'` 的记录
- **THEN** 系统 MUST NOT 修改其他指数代码的成分数据
