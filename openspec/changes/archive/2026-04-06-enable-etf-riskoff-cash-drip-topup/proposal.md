## Why

当前 ETF 弱势目标结构已经调整为“债 + 少量核心宽基”，但最新回放显示弱势实际持仓行为并未改善：`RISK_OFF` 非零持仓率没有提升，主失败原因仍然是 `ETF_BETA_WEAK_STATE_INTER_REBALANCE_DEFENSE_REDEPLOY_REJECT_EXECUTION_CONSTRAINT`。这说明当前主问题已不是目标映射，而是执行约束仍然把弱势承接卡成“不下单”。

在“个人多资产趋势配置系统”的定位下，`RISK_OFF` 不应长期表现为接近空仓；如果存在可用现金，系统应允许 ETF 弱势承接腿以小额、频繁、债优先的方式持续累积，而不是要求一次性满足较大的 deploy gap 才允许交易。

## What Changes

- 为 ETF 在 `RISK_OFF` 下新增正式的 `cash-drip top-up` 执行能力。
- 将弱势 inter-rebalance 执行约束从“必须满足较大 deploy gap 才允许下单”改为“只要有现金且满足最小可执行单位，就允许小额补仓”。
- 明确 `RISK_OFF` 下的小额补仓顺序：先补债，再补核心宽基。
- 为弱势小额补仓输出单独 explain 与原因码，区分“已执行 drip top-up”“现金不足最小单位”“已满足目标无需继续补仓”等情形。
- 本轮不修改 `TRANS_DOWN`、不修改弱势 target map、不修改 stock、regime、组合 `50/50`、也不扩大到其他执行路径。

## Capabilities

### New Capabilities
- `etf-riskoff-cash-drip-topup`: 定义 ETF 在 `RISK_OFF` 下基于可用现金进行小额频繁补仓的正式执行合同与审计语义。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 增加 `RISK_OFF` 下 ETF 弱势小额补仓的正式行为要求与 explain 要求。
- `etf-weak-state-inter-rebalance-defense-redeploy`: 将弱势非再平衡日 redeploy 的 `RISK_OFF` 分支扩展为支持 cash-drip top-up，而不是仅停留在 posture 检查与执行约束拒绝。

## Impact

- 影响代码：`backend/core/engine_vector/etf_beta/*`、`backend/core/stage_pipeline/adapters/*`、必要时 `backend/core/config/etf_beta/*` 的 explain 输出。
- 影响产物：ETF standalone 与 `A_STOCK_ETF_V1` 组合的 `run_meta.json`、formal/research explain、原因码与弱势状态持仓行为。
- 不影响：stock 腿、regime 定义、组合主结构、弱势目标权重映射。
