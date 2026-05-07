## Why

当前正式 ETF stabilizer 的主瓶颈已经从 `TRANS_UP` 的 seat 合同冲突收敛到 `BULL` 的 `deployment_pace` 保守定义。最新正式实验 [exp_20260329_080608247_fd57](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260329_080608247_fd57) 显示，`BULL` 日均 `target_exposure=0.2`，但 `deployment_pace` 只有 `0.108`，`avg_pace_policy_gap=0.092`，说明当前 `BULL` 的 approved overlay 长期停留在纸面上，已经成为 ETF `CAGR` 的首要合同瓶颈。

现在应先做最小、可归因的 L3：只调整 `BULL` 的 `deployment_pace`，让它在不触碰 Governor、seat、月频 rebalance 和 ETF 池的前提下，允许一部分 approved overlay 进入即时部署节奏。这样可以先验证“pace 合同保守”是否真的是 ETF 收益受限的主因，再决定是否继续推进更大的节奏或语义改动。

## What Changes

- 将正式 ETF stabilizer 在 `BULL` 状态下的 `deployment_pace` 从“仅等于 `strategic_floor_cap`”调整为“`strategic_floor_cap + partial_overlay_cap`”。
- 新增正式的 `bull_partial_overlay_pace_ratio` 合同参数，用于约束 `BULL` 状态下有多少 `tactical_overlay_cap` 可以进入 `deployment_pace`。
- 保持 `TRANS_UP` 的 `single-seat core recovery` 不变；`TRANS_UP` 不引入 overlay pace，也不恢复 second-seat live target。
- 保持 Governor 预算、slot/seat 合同、月频 rebalance、ETF 池和 RS 排序不变。
- 扩展审计和日级证据，使 `BULL` 的 `pace_policy_gap` 能与变更前后实验直接对照。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-etf-beta-sleeve`: 修改正式 ETF stabilizer 在 `BULL` 状态下的 `deployment_pace` 合同，使其允许按受控比例吸收 approved overlay。
- `backtest-research-audit`: 修改 ETF sleeve 审计要求，要求显式对照 `BULL` 状态下 partial overlay pace 生效前后的 `pace_policy_gap / actual_exposure` 变化。

## Impact

- 影响代码：
  - `backend/core/config/etf_beta_contract.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/core/audit/research_audit.py`
  - `backend/core/tools/experiment_runner.py`
  - 对应单测与正式 ETF study 重跑
- 不影响：
  - Governor 预算合同
  - `TRANS_UP` seat 合同
  - ETF 资产池与 RS 排序
  - 月频 rebalance 主节奏
