# cn-stock-v2-source-governance Specification

## Purpose
规范 V2 字段级 source matrix、BJ 分阶段治理、左截断锚点缺口与 terminal tail 源治理。

## Requirements

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
系统 MUST 在 `v2` 审计与异常分类中区分“源本身缺失”和“构建阶段未正确消费源”。对于 `eligible_no_source`、`turnover_rate_imputed_zero`、`pre_close_imputed_zero` 等异常，系统 MUST 能说明该异常是由于所有候选源均无数据、主源缺失但补源可得、历史左截断导致当前窗口内缺少价格/换手锚点，还是构建规则拒绝落行。

#### Scenario: 生成异常分类
- **WHEN** 系统为 `v2` 生成 exceptions
- **THEN** 每条异常 MUST 至少能归入一种来源解释分类
- **THEN** 异常汇总 MUST 能按来源解释分类聚合输出

#### Scenario: `pre_close` 左截断锚点缺口单独归类
- **WHEN** 某条非 `traded` 的 canonical 行无法从 `daily_pre_close`、`prev_close_carry`、`basic_close_anchor`、`daily_close_anchor` 获得正 `pre_close`
- **AND** 该行属于窗口起始连续缺锚点区段，而不是已有正锚点后的中段回归
- **THEN** 系统 MUST 将 `pre_close_imputed_zero` 归类为 `left_censored_anchor_gap`
- **THEN** 系统 SHALL NOT 继续将该样本记为泛化的 `source_present_low_confidence_fill`

#### Scenario: `turnover_rate` 左截断锚点缺口单独归类
- **WHEN** 某条非 `traded` 的 canonical 行无法从 `daily_basic.turnover_rate`、AkShare fallback、`float_share` 公式回填获得有效 `turnover_rate`
- **AND** 该行已同时命中窗口起始连续缺锚点的 `pre_close_imputed_zero`
- **THEN** 系统 MUST 将 `turnover_rate_imputed_zero` 归类为 `left_censored_turnover_gap`
- **THEN** 系统 SHALL NOT 继续将该样本记为泛化的 `fallback_available`

#### Scenario: 真无源 `turnover_rate` 不得并入左截断已知源缺口
- **WHEN** 行状态仍为 `source_unresolved`
- **THEN** 系统 SHALL NOT 仅因为该行也出现 `turnover_rate_imputed_zero` 就将其并入 `left_censored_turnover_gap`
- **THEN** 系统 MUST 继续保留其真无源语义

### Requirement: source governance MUST 区分 pre-window pause terminal tail 与真无源缺口
系统 MUST 能区分“formal window 起点已经落在暂停上市后的 terminal tail”与“整个窗口内都没有任何可审计证据的真无源缺口”。前者可以进入显式 override；后者 SHALL 继续保留为 `source_unresolved`。

#### Scenario: pre-window pause 证据不足时不得进入 override
- **WHEN** 某个 symbol 虽然在 `2007-01-04 ~ delist_date` 连续无源
- **BUT** formal window 起点之前没有正式暂停上市证据
- **THEN** 系统 SHALL NOT 仅凭 `delist_date` 就把这段窗口并入 `delist_tail_confirmed`
- **AND** 这些行 MUST 继续保留为 `source_unresolved`
