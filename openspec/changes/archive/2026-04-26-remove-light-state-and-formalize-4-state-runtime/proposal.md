## Why

当前 `LIGHT` 状态在正式合同里存在，但在真实运行里没有稳定产出。三窗口回放中，账户层 `account_budget_effective_state_5` 不出现 `LIGHT`，组件层也没有可靠喂给账户层的 `LIGHT` 证据。继续保留会制造预算、解释、审计和前端展示噪音。

## What Changes

- 正式废弃 `LIGHT` 作为运行态，只保留兼容别名
- 账户层、状态机、ETF 正式映射统一收成 4-state：`BULL / TRANS_UP / TRANS_DOWN / RISK_OFF`
- `TREND_LIGHT` 和历史 `LIGHT` 输入统一映射到 `TRANS_UP`
- runtime、budget、transition、前端/审计输出不再把 `LIGHT` 视为正式状态

## Capabilities

### New Capabilities
- `four-state-runtime-formalization`: 正式 4-state runtime 合同

### Modified Capabilities
- `account-layer-state-transition-policy`
- `account-budget-control`
- `account-allocation-runtime-cutover`
- `cn-etf-beta-sleeve`

## Impact

- `backend/core/config/cn_a_governed_mainline.py`
- `backend/core/services/account_allocator_shadow.py`
- `backend/core/services/cn_stock_etf_unified_runtime_service.py`
- `backend/core/engine_vector/market_regime_engine.py`
- `backend/core/config/etf_beta/defaults.py`
- `backend/core/config/etf_beta/common.py`
- `frontend` 和 `audit/query` 中依赖正式状态集合的输出
