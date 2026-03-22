# market-snapshot-daily Specification

## Purpose
TBD - created by archiving change add-a-share-market-snapshot. Update Purpose after archive.
## Requirements
### Requirement: 系统必须为指定交易日生成独立的全 A 股市场快照
系统 SHALL 支持按交易日生成独立于回测实验的 `market_snapshot.json`，并将产物写入 `outputs/market_snapshots/YYYY-MM-DD/`。该快照必须以单一 `trade_date` 为锚点，且所有字段默认只使用该交易日收盘后及历史可得数据。

系统 SHALL 支持按交易日生成独立于回测实验的 `market_snapshot.json`，并将产物写入 `outputs/market_snapshots/YYYY-MM-DD/`。该快照必须以单一 `trade_date` 为锚点，且所有字段默认只使用该交易日收盘后及历史可得数据。

#### Scenario: 为单个交易日生成快照
- **WHEN** 用户或系统请求构建某一交易日的市场快照
- **THEN** 系统必须在对应日期目录下生成 `market_snapshot.json`
- **AND** 产物不得写入现有回测实验目录

#### Scenario: 同一交易日重复构建
- **WHEN** 同一 `trade_date` 被再次构建
- **THEN** 系统必须以幂等方式重写该日期快照
- **AND** 不得改变无关日期目录的内容### Requirement: 市场快照必须覆盖六层市场状态字段
系统 SHALL 在 `market_snapshot.json` 中至少输出以下六层结构：`index_layer`、`style_layer`、`breadth_layer`、`liquidity_layer`、`sentiment_layer`、`risk_layer`。每层字段必须有固定语义，不得把不同层的指标混成单一匿名分数。

#### Scenario: 输出最小六层 schema
- **WHEN** 市场快照构建完成
- **THEN** `market_snapshot.json` 必须包含六层字段对象
- **AND** 缺失字段必须以 `warnings` 或覆盖率信息显式说明

#### Scenario: 使用历史滚动口径
- **WHEN** 某字段需要 zscore、quantile 或 heat 计算
- **THEN** 系统必须仅使用 `t` 日及之前的滚动窗口
- **AND** 不得使用全样本统计量

### Requirement: 系统必须输出可人工阅读的市场简报
系统 SHALL 基于同一份市场快照数据生成 `market_brief.md`，用于收盘后复盘和后续半自动化日更阅读。

系统 SHALL 基于同一份市场快照数据生成 `market_brief.md`，用于收盘后复盘和后续半自动化日更阅读。

#### Scenario: 生成市场简报
- **WHEN** 某日市场快照构建完成
- **THEN** 系统必须在同目录下生成 `market_brief.md`
- **AND** 简报至少包含今日结论、指数与风格、广度与成交、情绪状态、风险提示五个部分### Requirement: 系统必须记录数据来源、覆盖率和告警
系统 SHALL 为市场快照记录 `sources`、`warnings` 以及能够解释覆盖不足或发布时间滞后的辅助信息，以保证后续研究和 UI 可以判断该快照是否可靠。

#### Scenario: 来源可追溯
- **WHEN** 市场快照生成完成
- **THEN** 产物必须记录各层主要字段的数据来源
- **AND** 来源必须能够区分交易所/指数公司/本地派生计算等不同来源类型

#### Scenario: 数据不足时显式告警
- **WHEN** 某层字段缺失、滞后或覆盖不足
- **THEN** 系统必须在 `warnings` 中记录原因
- **AND** 不得静默写零或伪造可用状态

### Requirement: 首轮市场快照不得直接改变策略或 baseline 行为
系统 SHALL 将市场快照定位为独立的描述性与研究辅助产物，首轮实现不得直接改变现有 `baseline_V9.1` 交易逻辑、回测指标或 `run_meta` 主 schema。

系统 SHALL 将市场快照定位为独立的描述性与研究辅助产物，首轮实现不得直接改变现有 `baseline_V9.1` 交易逻辑、回测指标或 `run_meta` 主 schema。

#### Scenario: 构建市场快照不影响 baseline
- **WHEN** 开启或关闭市场快照构建
- **THEN** 现有回测实验的 `perf.json`、`run_meta.json`、`nav.csv` 口径必须保持不变
- **AND** `market_snapshot` 不得被写入现有 baseline 产物链作为必需字段### Requirement: 市场快照必须覆盖六层市场状态字段
系统 SHALL 在 `market_snapshot.json` 中至少输出以下六层结构：`index_layer`、`style_layer`、`breadth_layer`、`liquidity_layer`、`sentiment_layer`、`risk_layer`。每层字段必须有固定语义，不得把不同层的指标混成单一匿名分数。

#### Scenario: 输出最小六层 schema
- **WHEN** 市场快照构建完成
- **THEN** `market_snapshot.json` 必须包含六层字段对象
- **AND** 缺失字段必须以 `warnings` 或覆盖率信息显式说明

#### Scenario: 使用历史滚动口径
- **WHEN** 某字段需要 zscore、quantile 或 heat 计算
- **THEN** 系统必须仅使用 `t` 日及之前的滚动窗口
- **AND** 不得使用全样本统计量

### Requirement: 系统必须记录数据来源、覆盖率和告警
系统 SHALL 为市场快照记录 `sources`、`warnings` 以及能够解释覆盖不足或发布时间滞后的辅助信息，以保证后续研究和 UI 可以判断该快照是否可靠。

#### Scenario: 来源可追溯
- **WHEN** 市场快照生成完成
- **THEN** 产物必须记录各层主要字段的数据来源
- **AND** 来源必须能够区分交易所/指数公司/本地派生计算等不同来源类型

#### Scenario: 数据不足时显式告警
- **WHEN** 某层字段缺失、滞后或覆盖不足
- **THEN** 系统必须在 `warnings` 中记录原因
- **AND** 不得静默写零或伪造可用状态

