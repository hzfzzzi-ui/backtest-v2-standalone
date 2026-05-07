## Why

当前 `cn_etf_phase1_allocation_entry` 已完成正式 Phase 1 配置引擎的 contract、provider、audit 和 study 闭环，但最小正式实验仍然出现 `orders = 0 / closed_trades = 0 / CAGR = 0`。现在需要暂停继续改策略，先把“为什么 formal mainline 完全不交易”定位清楚，并给出可复现、可审计的根因证据。

## What Changes

- 为正式 ETF Phase 1 主线新增零交易根因诊断能力，按数据、信号、调仓、执行、风控、参数六层输出证据。
- 为每个调仓日输出候选池数量、通过绝对/配置约束数量、最终目标数量、订单数量和被过滤原因分布。
- 补充正式 ETF Phase 1 的仓位利用率、风险资产/防守资产/现金占比、调仓频率一致性、信号到订单到成交链路诊断。
- 增加 formal mainline 的逐层对照实验产物，至少覆盖 `buy_and_hold`、仅过滤、仅排序/配置、过滤+配置、完整策略五层。
- 明确输出“最可能导致 CAGR 只有 2.x% 或 0 交易”的前 5 个原因、对应代码位置、最小修复建议和最小验证实验建议。

## Capabilities

### New Capabilities
- `cn-etf-phase1-zero-trade-diagnostics`: 定义正式 ETF Phase 1 主线零交易/低 CAGR 根因排查所需的诊断产物、统计口径和结论输出。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 要求正式 ETF Phase 1 在调仓日、目标分配、订单生成和执行落地链路上输出可审计的逐层诊断信息。
- `backtest-research-audit`: 要求 research audit 为正式 ETF Phase 1 输出零交易根因、仓位利用率、过滤拒绝分布和调度一致性摘要。
- `cn-etf-research-entry`: 要求正式 ETF Phase 1 study 入口支持根因诊断模式和逐层对照实验，不改变正式策略口径。

## Impact

- 影响后端 ETF provider、audit、study runner 和诊断产物输出。
- 影响正式 ETF study 产物目录，新增根因排查明细与对照实验汇总。
- 不改变 ETF 正式资产池，不引入行业 ETF，不与个股 alpha 组合，不直接优化收益逻辑。
