## Why

当前正式 ETF stabilizer 在 `TRANS_UP` 状态下同时保留了 `tactical_overlay_cap` 与 `single-seat` 执行合同，形成了“模板上批准 overlay、执行上永远只有 1 个 seat”的自相矛盾。这个矛盾会把一部分预算长期留在纸面上，破坏审计解释力，也让 `TRANS_UP` 的恢复期行为不可靠。

## What Changes

- 将 formal ETF stabilizer 的 `TRANS_UP` 状态明确定义为 `single-seat core recovery`。
- 收敛 `TRANS_UP` 的 live 合同，只保留 `core_accumulator` 可部署语义，不再保留需要第二个 seat 的独立 `tactical_satellite` overlay 目标。
- 保持现有 `deployment_pace`、Governor 预算合同、月频 rebalance 与 `TRANS_UP` 状态切换 floor redeploy 不变。
- 增加最小审计与日级证据，明确 `TRANS_UP` 是单 seat 恢复状态，而不是“纸面 core + satellite overlay”。

## Capabilities

### New Capabilities
- 无

### Modified Capabilities
- `cn-etf-beta-sleeve`: formal ETF stabilizer 在 `TRANS_UP` 状态下的 live 合同改为单 seat core recovery，审计输出必须与该合同一致。
- `backtest-research-audit`: ETF 正式审计在 `TRANS_UP` 状态下必须反映单 seat core recovery，不得继续输出需要第二个 seat 的纸面 overlay 解释。

## Impact

- 受影响模块：
  - `backend/core/config/etf_beta_contract.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/core/audit/research_audit.py`
  - `tests/unit/test_etf_beta_contract.py`
  - `tests/unit/test_cn_etf_beta_signal_provider.py`
  - `tests/unit/test_bridge_adapter_accounting.py`
  - `tests/unit/test_research_audit_contract.py`
- 受影响产物：
  - `portfolio_daily.csv`
  - `orders.csv`
  - `audit.json`
- 不在本次范围：
  - 不改 Governor exposure/seat 合同
  - 不改 ETF 池与 RS 排序
  - 不改 `controlled_accumulation` 语义
  - 不把月频 rebalance 升级成更高频主逻辑
