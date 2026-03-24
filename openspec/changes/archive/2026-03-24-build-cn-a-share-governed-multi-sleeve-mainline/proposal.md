## Why

当前 A 股主线已经同时存在三个事实：`baseline_V10.1` 是成熟的个股 alpha 主干、`cn_etf` research entry 已打通、市场状态与风险预算逻辑已经分散存在于多个运行时模块中；但这三者仍未形成统一的总控 contract。若不先固化 `market_regime_engine + global_portfolio_governor + attribution_audit` 的上游边界，后续接入 ETF beta、防守层与保险 overlay 时，系统会继续演化成多个局部策略并列运行，而不是一个统一仓位管理的 A 股配置子系统。

## What Changes

- 新增 A 股 Phase 1 正式模块合同：`market_regime_engine`、`global_portfolio_governor`、`cn_stock_trend_alpha_core`、`cn_etf_beta`、`attribution_audit`。
- 把当前 `baseline_V10.1` 正式重定位为 `cn_stock_trend_alpha_core`，明确其是股票 alpha sleeve，而不是整个 A 股系统本身。
- 为 `market_regime_engine` 补齐可归因状态输出 contract，明确 `base_state / effective_state`、`reason_codes`、`subscores`、`manual_override` 和状态稳定性语义。
- 为 `global_portfolio_governor` 补齐全组合总控 contract，统一 total risk budget、sleeve budget、drawdown ladder、recovery/cooldown 和 defense floor。
- 将 `cn_etf_beta` 正式定义为 Governor 约束下的低频 beta sleeve，Phase 1 范围限于 `510300.SH / 510500.SH / 510050.SH / 512100.SH`，并允许 `512890.SH` 作为 limited defense candidate。
- 新增 `attribution_audit`，统一输出 regime、budget、sleeve、manual override 的解释链，不再只散落在 `run_meta`、`audit` 和局部 debug 产物中。
- **BREAKING**：A 股主线文义上不再把 `V10.1` 描述为完整系统，而是 `cn_stock_trend_alpha_core`。
- **BREAKING**：A 股市场状态 Phase 1 正式主状态保留现有五状态技术骨架，三状态只作为派生视图。
- **BREAKING**：全组合总风险预算语义正式上移到 Governor；股票 sleeve 和 ETF sleeve 不得再各自定义全组合总仓位。

## Capabilities

### New Capabilities
- `cn-a-portfolio-governor`: 定义 A 股子系统唯一合法的全组合总控层，包括 total risk budget、sleeve budget、drawdown ladder、recovery/cooldown、defense floor 和 governor 审计输出。
- `cn-a-attribution-audit`: 定义 A 股子系统横切归因与审计层，统一输出 state logs、budget logs、sleeve logs、manual override logs、reason code summary。
- `cn-stock-trend-alpha-core`: 定义 `baseline_V10.1` 作为股票 alpha sleeve 的正式边界、输入输出、预算权限和与 Governor 的交互合同。
- `cn-etf-beta-sleeve`: 定义 Governor 约束下的 A 股 ETF beta sleeve，基于现有 `cn_etf` 数据链和 research entry，只表达 core beta 与 limited defense candidate。

### Modified Capabilities
- `market-regime-framework`: 将正式市场状态框架扩展为可归因状态 contract，新增五状态主状态、三状态派生视图、`base/effective` 双轨、subscores 和可审计 manual override 语义。
- `risk-budget-sizing`: 将风险预算从单策略预算逻辑扩展为可供 Governor 消费的总预算与 sleeve 预算 contract，明确参数上移边界。
- `backtest-research-audit`: 让 research audit 接入 regime / budget / sleeve / manual override 的统一证据链。
- `cn-etf-research-entry`: 明确 `cn_etf` 研究入口在 Phase 1 中服务于 `cn_etf_beta` sleeve，而不是孤立的 ETF research entry。
- `results-workbench-snapshot-boundary`: 让结果工作台 snapshot 正式承载 regime、governor、sleeve 和 attribution 摘要，而不是只散落在运行产物中。

## Impact

- 影响后端主路径：
  - `backend/core/engine_vector`
  - `backend/core/stage_pipeline/adapters`
  - `backend/core/portfolio`
  - `backend/core/audit`
  - `backend/core/tools`
  - `backend/api/backtest_v2`
- 影响前端主路径：
  - `frontend/app/results-workbench`
  - 与 snapshot 相关的页面壳和兼容桥接层
- 影响研究入口与产物：
  - `baseline_V10.1` 的正式语义
  - `cn_etf` preset 的正式角色
  - `run_meta.json`
  - `audit.json`
  - `portfolio_daily.csv`
  - 新增或统一的 regime/governor/attribution 摘要字段
- 不改变当前股票 `V2 canonical` 数据口径，也不在本 change 中把 `value_bluechip_satellite` 和 `insurance_overlay` 纳入正式交付。
