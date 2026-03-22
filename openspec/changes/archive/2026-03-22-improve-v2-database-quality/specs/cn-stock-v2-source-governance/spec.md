## ADDED Requirements

### Requirement: V2 MUST 维护字段级 source matrix
系统 MUST 为 `pams_ohlcv_daily_v2` 与 `pit_stock_moneyflow_v2` 维护字段级 source matrix，明确每个字段的主源、补源、审计源、适用交易所和适用阶段边界。source matrix MUST 至少覆盖 `daily`、`adj_factor`、`daily_basic`、`stk_limit`、`suspend_d`、`moneyflow` 以及 `AkShare`、`巨潮资讯` 等补源候选。

#### Scenario: 输出字段级 source matrix
- **WHEN** 系统对 `v2` 数据源治理进行发布或重建
- **THEN** 系统 MUST 产出字段级 source matrix 文档或结构化产物
- **THEN** 每个关键字段 MUST 标明主源、补源、审计源与适用交易所/阶段

#### Scenario: 新增或替换补源
- **WHEN** 系统为 `v2` 新接入免费补源或调整补源优先级
- **THEN** source matrix MUST 同步更新
- **THEN** 变更 MUST 说明该补源影响哪些字段、哪些交易所与哪些阶段

### Requirement: BJ source governance MUST 区分正式开市前后
系统 MUST 将 `BJ` 数据源治理分为 `2021-11-15` 之前和 `2021-11-15` 之后两个阶段。前者 MUST 视为历史映射治理问题，后者 MUST 视为正式北交所数据源覆盖问题；系统 SHALL NOT 将两类问题混为同一类缺失统计。

#### Scenario: 审计 BJ 缺失
- **WHEN** 系统生成 `BJ` 相关异常审计
- **THEN** 审计 MUST 分别输出 `2021-11-15` 前后的异常计数与覆盖率
- **THEN** 审计 MUST 能区分历史映射污染与正式开市后的真实源缺失

#### Scenario: 报告 BJ 数据质量
- **WHEN** 系统生成 `v2` 质量报告
- **THEN** 报告 MUST 单列 `BJ pre-2021-11-15` 与 `BJ post-2021-11-15`
- **THEN** 报告 SHALL NOT 直接把全部 `bj%` 异常解释为“北交所数据源失败”

### Requirement: Source governance MUST 区分源缺失与构建缺失
系统 MUST 在 `v2` 审计与异常分类中区分“源本身缺失”和“构建阶段未正确消费源”。对于 `eligible_no_source`、`turnover_rate_imputed_zero` 等异常，系统 MUST 能说明该异常是由于所有候选源均无数据、主源缺失但补源可得、映射失败，还是构建规则拒绝落行。

#### Scenario: 生成异常分类
- **WHEN** 系统为 `v2` 生成 exceptions
- **THEN** 每条异常 MUST 至少能归入一种来源解释分类
- **THEN** 异常汇总 MUST 能按来源解释分类聚合输出
