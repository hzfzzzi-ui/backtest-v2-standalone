## Why

当前正式 ETF stabilizer 的低 `CAGR`，主瓶颈已经收敛到 `BULL/TRANS_UP` 的 `deployment_pace` 长期只部署到 `floor`。现在系统能看到 `approved target`、`floor`、`overlay` 和 `actual exposure`，但还不能把“为什么只到 floor、为什么实际没有跟上”明确拆成可审计的单一证据链，导致后续优化无法可靠归因。

## What Changes

- 新增一条独立研究变更，只研究 formal ETF stabilizer 在 `BULL/TRANS_UP` 下的 `deployment_pace` floor 瓶颈，不改策略行为。
- 要求 ETF 正式产物显式拆出 `approved target -> floor/overlay -> deployment_pace -> execution path -> actual exposure` 这条链。
- 要求 research audit 显式归因 `BULL/TRANS_UP` 的仓位缺口属于哪一层：`pace_policy_gap`、`rebalance_timing_gap` 或 `execution_residual_gap`。
- 要求正式研究结论按 `BULL` 和 `TRANS_UP` 分开输出，不再把两者混成单一“ETF 低部署”描述。
- 不改 Governor exposure 合同，不改 `deployment_pace` 公式，不改 ETF 池、RS、月频 rebalance。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-etf-beta-sleeve`: 新增 formal ETF stabilizer 在 `BULL/TRANS_UP` 下的 `deployment_pace` 诊断与缺口分解要求。
- `backtest-research-audit`: 新增 ETF `BULL/TRANS_UP` 缺口归因要求，必须把 `pace policy`、`timing` 和执行残差拆开。

## Impact

- 受影响源码：
  - `backend/core/config/etf_beta_contract.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/core/audit/research_audit.py`
  - `backend/core/tools/experiment_runner.py`
  - `tests/unit/test_etf_beta_contract.py`
  - `tests/unit/test_cn_etf_beta_signal_provider.py`
  - `tests/unit/test_bridge_adapter_accounting.py`
  - `tests/unit/test_research_audit_contract.py`
  - `tests/unit/test_experiment_runner_daily_schema.py`
- 受影响产物：
  - `portfolio_daily.csv`
  - `orders.csv`
  - `audit.json`
- 本次不在范围：
  - Governor budget/seat 合同
  - ETF universe 与 RS 排序
  - `deployment_pace` 公式本身
  - 月频 rebalance 主逻辑
