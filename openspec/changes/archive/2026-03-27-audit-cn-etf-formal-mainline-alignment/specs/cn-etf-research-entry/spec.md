## ADDED Requirements

### Requirement: ETF 研究入口必须显式区分正式主线与研究分支
`cn_etf` 研究入口 MUST 显式区分“正式 ETF 主线入口”和“ETF 研究分支入口”。研究入口 MAY 提供超出正式文档范围的 ETF 研究配置，但 MUST 同时暴露其正式分类，不得继续把研究分支静默冒充为正式主线入口。

#### Scenario: 正式主线入口暴露正式范围
- **WHEN** 用户选择 ETF 正式主线入口
- **THEN** 系统 MUST 显式暴露 Phase 1 正式 core beta universe 与 limited defense candidate
- **THEN** 系统 MUST 说明该入口受正式文档约束

#### Scenario: 研究分支入口显式披露偏离
- **WHEN** 用户选择包含 `159915`、`588000`、`511010` 或其他超范围资产的 ETF 研究入口
- **THEN** 系统 MUST 将该入口标记为 `research_only` 或 `do_not_promote`
- **THEN** 系统 MUST 显式披露该入口偏离正式主线的原因
