## Why

当前 `A_STOCK_ETF_V1` 在弱势环境下经常出现 stock 腿与 ETF 腿同时接近空仓的结果，组合缺少明确、防守型、可解释的承接层。最新主验收结果显示 ETF 腿在 `RISK_OFF` 下虽然存在目标暴露，但运行期会被 `NO_DEPLOYABLE_SLOTS` 与 `total_exposure_cap=0.0` 压成不可部署，导致系统在弱势阶段更像“被动空仓”而不是“主动防守配置”。

## What Changes

- 为 ETF 腿新增正式的弱势承接策略合同，明确 `TRANS_DOWN` 与 `RISK_OFF` 的目标不是追收益，而是提供可部署、可审计的防守承接。
- 将 ETF 弱势状态的资产优先级、最小 deployable seat、最小可落地暴露、可承接资产范围收敛成单一合同，不再依赖隐式 layering/fallback 行为。
- 明确 `RISK_OFF` 与 `TRANS_DOWN` 的 ETF 防守部署不得通过放宽 stock 腿、放大权益 beta 或引入长期反向 ETF 来达成。
- 修改 ETF sleeve 规范，要求弱势状态在满足防守资产可交易时必须形成可执行承接，而不是因为 slot/cap 规则直接退化为零部署。

## Capabilities

### New Capabilities
- `etf-weak-state-defense-policy`: 定义 ETF 腿在 `TRANS_DOWN` 与 `RISK_OFF` 下的正式防守承接合同、可部署性约束与资产优先级。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 调整 ETF beta sleeve 的弱势状态要求，使其在不改变进攻段逻辑的前提下，必须遵守正式弱势承接合同并保证防守部署可执行。

## Impact

- Affected code:
  - `backend/core/services/*` 中 ETF sleeve 弱势预算与部署路径
  - `backend/core/stage_pipeline/*` 中 ETF 选中结果与 deployability 约束
  - `backend/api/backtest_v2/*` 中 ETF runtime/审计快照输出
- Affected artifacts:
  - `run_meta.json`
  - `portfolio_daily.csv`
  - ETF sleeve explain/audit surfaces
- APIs: 无主 API 结构变更，但 ETF 弱势状态解释字段与原因码会更明确。
- Dependencies: 依赖现有 `market-regime-framework` 输出的 `TRANS_DOWN / RISK_OFF` 状态，不修改 regime 定义本身。
