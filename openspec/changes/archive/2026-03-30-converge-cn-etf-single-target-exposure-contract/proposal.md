## Why

当前 formal `cn_etf_beta` Phase 1 同时存在两套彼此冲突的目标仓位语义：日终审计与 `portfolio_daily.csv` 记录的是 Governor notional cap，而实际下单与 `orders.csv` meta 已经在消费另一条 risk-budget / provisional budget 链。结果是同一实验里 `avg_target_exposure` 与真实执行目标不一致，导致审计、归因和后续策略研究都不可靠。

现在需要先收敛这条 L3 合同，再讨论 denominator、月频节奏或收益优化。否则继续研究 `CAGR`、`actual_exposure` 或 `RISK_OFF` 行为，都会混入字段口径漂移。

## What Changes

- 收敛 formal ETF Phase 1 的单一目标仓位合同，只允许存在一套执行与审计共用的 `target_exposure` 语义。
- 明确 `target_exposure` 的单位必须是 ETF sleeve 的已批准 notional exposure，占 `NAV` 的比例，范围必须在 `0.0-1.0`。
- 禁止把 upstream `risk_budget_multiplier`、provisional slot fallback 或其他解释性预算量继续写成 `target_exposure`、`requested_budget` 或任何会进入下单 sizing 的目标字段。
- 要求 formal ETF Phase 1 的 provider、order sizing、`portfolio_daily.csv`、`rebalance_day_summary.csv`、`audit.json` 和研究审计都回写同一份目标仓位值。
- 要求保留解释性预算证据时，必须改为独立字段或 reason code，不得再与唯一目标仓位同名。

## Capabilities

### New Capabilities

### Modified Capabilities

- `cn-etf-beta-sleeve`: formal Phase 1 的目标仓位合同、下单 sizing 输入和产物输出需要收敛为单一 notional exposure 语义。
- `backtest-research-audit`: ETF 相关 target exposure 审计必须与实际执行目标对齐，并在发现双口径漂移时输出明确失败或告警。

## Impact

- 影响 [backend/core/config/etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)、[backend/core/engine_vector/cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)、[backend/core/stage_pipeline/adapters/daily_accounting.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/stage_pipeline/adapters/daily_accounting.py)、[backend/core/portfolio/portfolio_runtime.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/portfolio/portfolio_runtime.py) 与 [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)。
- 影响 `orders.csv`、`portfolio_daily.csv`、`rebalance_day_summary.csv`、`audit.json` 中 ETF target 相关字段语义。
- 不改 ETF 正式资产池，不改上游 regime 真相，不改 Governor denominator，不在本 change 中研究月频再平衡优化或收益提升。
