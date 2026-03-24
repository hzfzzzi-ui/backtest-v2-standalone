# cn-etf-beta-sleeve Specification

## Purpose
定义 A 股 governed multi-sleeve 主线中的 ETF beta sleeve 边界、Phase 1 范围与最小可审计输出。

## Requirements

### Requirement: A股子系统必须定义正式的ETF beta sleeve
系统 MUST 提供 `cn-etf-beta-sleeve` 能力，将 A 股 ETF 正式纳入 Governor 约束下的低频 beta sleeve。该能力 SHALL 复用现有 `cn_etf` 数据链与研究入口，但 SHALL NOT 被定义为复制股票 breakout 壳的第二套 alpha 引擎。

#### Scenario: ETF beta sleeve 作为独立 sleeve 运行
- **WHEN** A 股子系统启用 ETF beta sleeve
- **THEN** 系统 MUST 将其视为独立于股票 alpha 的 sleeve
- **THEN** 该 sleeve MUST 在 Governor 下发的预算内运行

### Requirement: ETF beta sleeve 的 Phase 1 范围必须受控
Phase 1 中，`cn-etf-beta-sleeve` MUST 仅将以下 ETF 视为正式 core beta 范围：
- `510300.SH`
- `510500.SH`
- `510050.SH`
- `512100.SH`

Phase 1 MAY 允许 `512890.SH` 作为 limited defense candidate，但 SHALL NOT 把 `518880.SH`、`511010.SH`、`588000.SH`、`159915.SZ` 并入正式 core beta sleeve。

#### Scenario: 正式 core beta 资产受控
- **WHEN** 系统构建 `cn_etf_beta` 的正式 Phase 1 候选池
- **THEN** 候选池 MUST 至少受限于四只 core beta ETF
- **THEN** `512890.SH` MAY 在 Governor 或策略配置允许时作为 limited defense candidate

#### Scenario: 非 Phase 1 范围 ETF 不得被伪装成正式 core beta
- **WHEN** 研究入口包含 `518880.SH`、`511010.SH`、`588000.SH` 或 `159915.SZ`
- **THEN** 系统 SHALL 将其标记为超出 `cn_etf_beta` Phase 1 正式范围
- **THEN** 系统 SHALL NOT 把这些资产静默纳入正式 beta sleeve 真相

### Requirement: ETF beta sleeve 必须输出低频、可解释的beta证据
`cn-etf-beta-sleeve` MUST 输出最小可解释证据，包括 `eligible_etfs`、`selected_etfs`、`selection_reason_codes`、`sleeve_budget_used` 和 ETF 资产覆盖摘要。该 sleeve SHALL 优先采用低频调仓与趋势/相对强弱框架，而 SHALL NOT 依赖股票 PIT、资金流排序或个股式 ATR breakout 壳。

#### Scenario: ETF beta sleeve 运行后可解释
- **WHEN** ETF beta sleeve 完成一次调仓或拒单决策
- **THEN** 产物 MUST 能回答“为什么是这些 ETF”
- **THEN** 产物 MUST 能回答“为什么当前 ETF sleeve 预算是这个水平”
