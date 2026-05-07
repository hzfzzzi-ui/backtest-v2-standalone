## Why

当前 `stock + ETF` 组合已经完成 `PIT`、`NEXT_OPEN`、`price_adj` 与 `accounting` 的执行口径审计，但仍未能晋升为正式主线。当前阻塞不在执行实现，而在 ETF sleeve 仍然沿用研究态资产池、研究态入口与研究态输出语义，导致组合最新审计中 `etf_beta_sleeve = FAIL`。

现在需要把这条组合从“研究态候选组合”收口成“正式主线组合合同”，明确 formal ETF stabilizer 的资产池版本、入口身份、weak-state/fallback 正式边界与输出合同，并以审计全 PASS 与收益不明显差于当前 `13.30% CAGR / 0.4908 Sharpe / -31.39% MaxDD` 作为晋升门槛。

## What Changes

- 将 `stock + ETF` 组合从 `research_combo_only` 路径升级为可晋升的正式主线组合合同。
- 将 ETF sleeve 正式定义为 `formal ETF stabilizer`，不再沿用 research-only broad-based rotation 语义。
- 为 ETF formal Phase 1 资产池引入版本化 formal pool 合同，当前 promotion 固定为 `formal_etf_pool_v1`。
- 明确 weak-state / fallback 的正式边界，只允许 formal defense / fallback 资产进入主线合同。
- 剥离 formal output contract 中的 research-only 字段、reason family 与 explain 语义。
- 调整 unified combo 组件来源合同与审计要求，使组合主线晋升以 `etf_beta_sleeve = PASS` 为必要条件。

## Capabilities

### New Capabilities
- `formal-etf-pool-versioning`: 为 ETF formal 主线定义可版本化的正式资产池合同，并约束 Phase 1 in-scope / excluded / defense 范围。

### Modified Capabilities
- `cn-stock-etf-unified-runtime-entry`: 将 unified combo 从 research-only 组合入口升级为可晋升正式主线的组合入口合同。
- `cn-etf-beta-sleeve`: 将 ETF beta sleeve 从研究态 broad-based sleeve 收口为 formal ETF stabilizer，并要求 formal alignment 通过后才能作为主线组件。
- `etf-defense-core-beta-budgets`: 将 weak-state / fallback 的 defense 与 core beta 正式边界纳入主线合同，禁止 research-only fallback 语义泄漏到正式主线。

## Impact

- 受影响源码：`backend/core/services/cn_stock_etf_unified_runtime_service.py`、`backend/core/audit/research_audit.py`、ETF sleeve 运行与 explain 相关模块。
- 受影响合同：unified combo component source contract、ETF sleeve formal alignment、ETF budget/defense contract、formal output contract。
- 受影响产物：组合 `audit.json`、ETF sleeve `run_meta.json` / `run_config.json` / explain surface。
- 受影响系统：A 股正式主线治理、组合晋升流程、ETF sleeve formal 审计与回归验证。
