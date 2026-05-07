## ADDED Requirements

### Requirement: formal ETF Phase 1 必须只暴露一套目标仓位合同
当 `cn_etf_beta` 以 formal `phase1_allocation_engine` 运行时，系统 MUST 只存在一套执行与审计共用的 `target_exposure` 真相。该值 MUST 表示 ETF sleeve 当天已批准的 notional exposure，占 `NAV` 的比例；它 SHALL 同时成为 provider、下单 sizing、`portfolio_daily.csv`、`rebalance_day_summary.csv` 和 `audit.json` 中 ETF 目标仓位的来源。

#### Scenario: 同一决策日的 ETF 目标仓位在各产物中一致
- **WHEN** formal ETF Phase 1 在某个决策日生成 BUY/SELL 决策并输出 orders、daily 和 audit 产物
- **THEN** 系统 MUST 在这些产物中回写同一份 ETF `target_exposure`
- **THEN** 该值 MUST 不得在同一决策日里同时表现为 `0.2` 与 `1.8` 这类不同量纲的目标

#### Scenario: 目标仓位必须是 notional exposure 而不是 multiplier
- **WHEN** formal ETF Phase 1 输出 `target_exposure`、`requested_budget`、`applied_budget` 或 `target_exposure_per_symbol`
- **THEN** 这些进入执行合同的目标字段 MUST 以 ETF sleeve 的 `NAV` 占比表达
- **THEN** 这些字段 MUST 不得大于 `1.0`，除非系统显式判定为合同错误并拒绝将其用于执行

### Requirement: explanatory risk budget 不得冒充 ETF 目标仓位
formal ETF Phase 1 若需要保留 upstream `risk_budget_multiplier`、legacy runtime budget、slot-cap fallback 或其他解释性预算证据，系统 MUST 将其作为独立解释字段、reason code 或 audit evidence 输出。此类值 SHALL NOT 被命名为 `target_exposure`，也 SHALL NOT 被用作 BUY signal 的目标仓位输入。

#### Scenario: upstream multiplier 大于 1 时不得进入执行 target
- **WHEN** provider 或 contract 收到 `1.8`、`0.9` 或其他 upstream risk-budget multiplier
- **THEN** 系统 MUST 将其视为解释性预算证据而不是 ETF 执行目标仓位
- **THEN** 下单 sizing MUST 继续消费唯一的 notional `target_exposure`

#### Scenario: provisional fallback 不得重写唯一目标仓位
- **WHEN** formal ETF Phase 1 因 Governor snapshot 缺口、slot-cap fallback 或等价 provisional path 生成临时预算证据
- **THEN** 系统 MAY 保留相关 fallback 证据
- **THEN** 系统 SHALL NOT 让这些 provisional 值覆盖或重命名为唯一的 ETF `target_exposure`

### Requirement: ETF 下单 sizing 必须只消费统一目标仓位
formal ETF Phase 1 的 BUY signal 与 order sizing MUST 从唯一目标仓位推导 `target_exposure_per_symbol` 与下单金额。执行层 SHALL NOT 再通过 legacy risk budget multiplier、全局默认 `base_order_value` 或其他旁路预算恢复出与统一目标不一致的 ETF 目标金额。

#### Scenario: BUY signal 按统一目标仓位推导下单金额
- **WHEN** formal ETF Phase 1 为某只 ETF 生成 BUY signal
- **THEN** signal meta 中的 `target_exposure_per_symbol` MUST 来源于唯一 ETF `target_exposure`
- **THEN** order sizing MUST 依据该 notional target 计算目标金额，而不是依据另一路 multiplier 预算放大仓位

#### Scenario: 目标仓位缺失或越界时视为合同失败
- **WHEN** formal ETF Phase 1 的执行链缺少唯一 ETF `target_exposure`，或该值越界、与同日 artifact 合同不一致
- **THEN** 系统 MUST 将其视为 formal ETF target contract failure
- **THEN** 系统 MUST 输出明确的 reason code、审计证据或测试失败，而不是静默回退到旧的 sizing 语义
