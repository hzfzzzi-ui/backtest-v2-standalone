## Why

当前 ETF 弱势承接合同和 deployability floor 已经建立，但最新验收显示在 `RISK_OFF` 非再平衡日，系统仍可能出现“有 defense target、有 buy slot、但因 `AWAIT_BIWEEKLY_REBALANCE` 最终 `NO_SELECTED_ORDERS`”的情形。这个问题已经不是预算压零，而是弱势防守合同无法在日内执行路径中及时落地。

## What Changes

- 为 ETF 弱势状态新增正式的 `inter-rebalance defense redeploy` 合同，只在 `TRANS_DOWN / RISK_OFF` 下生效。
- 当弱势防守 policy 已激活、目标暴露大于零、且正式防守资产可交易时，允许 ETF sleeve 在非再平衡日执行防守型补位/切换，而不是一律等待固定频率再平衡。
- 保持 `BULL / TRANS_UP` 的再平衡节奏不变，不修改 stock 腿、regime、50/50 组合结构，也不重新定义弱势目标暴露。
- 为 inter-rebalance defense redeploy 增加专门原因码和 explain 字段，区分“已满足防守持仓”“无可交易 defense 资产”“被执行约束拒绝”。

## Capabilities

### New Capabilities
- `etf-weak-state-inter-rebalance-defense-redeploy`: 定义 ETF 在 `TRANS_DOWN / RISK_OFF` 下的非再平衡日防守补位/切换合同、触发条件与审计语义。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 调整 ETF beta sleeve 的弱势执行路径，使正式弱势防守合同可以在非再平衡日落地，但不影响进攻段节奏。

## Impact

- Affected code:
  - `backend/core/engine_vector/etf_beta/*`
  - `backend/core/stage_pipeline/adapters/*`
  - `backend/api/backtest_v2/*` 中 ETF explain/audit 输出
- Affected artifacts:
  - `run_meta.json`
  - `audit.json`
  - ETF sleeve explain surfaces
- APIs: 无主 API 结构变更，仅新增 ETF 弱势 inter-rebalance explain 字段与原因码。
- Dependencies: 依赖现有 `etf-weak-state-defense-policy` 与 `market-regime-framework`，不修改它们的定义本身。
