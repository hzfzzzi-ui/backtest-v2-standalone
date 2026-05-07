## Why

当前 `etf/cn_broad_based_research_mainline_r1` 在实跑里已经证明，`BULL / TRANS_UP / RISK_OFF` 的 standalone deployability 合同本身不再是主瓶颈；新的主问题转成了 standalone postprocess 与 fallback sizing 把“最终目标仓位”和“本次增量补仓量”混在一起，导致 fallback 标的获得错误正 `target_weight`、`research_audit` 误报 target contract drift，并持续放大 `actual_exposure` 与 approved target 的偏差解释噪声。这个问题必须现在收口，否则后续任何 ETF 主线优化都会继续被假 drift 和错误 sizing 污染。

## What Changes

- 为 ETF standalone research mainline 定义并落地独立的 target contract：显式区分 `final_target_weight` 与 emitted BUY signal 的增量 `target_weight`，禁止 fallback symbol 在 partial fallback fill 场景下继承正的 live target。
- 修正 standalone mainline 的 postprocess / fallback sizing，使 monthly rebalance、partial fallback fill、inter-rebalance deploy 各自保持一致的 target 语义，不再把 delta gap 与最终组合目标仓位混写。
- 修正 `research_audit` 对 standalone mainline 的 drift 检测与 gap 归因，改为比较最终目标合同而不是把增量 BUY order 误当成最终 target，并补最小审计证据。

## Capabilities

### New Capabilities

- `etf-standalone-target-contract`: 定义 ETF standalone research mainline 在 partial fallback fill、full fallback replacement 和 inter-rebalance deploy 下的 final target / delta target 合同、审计比较口径与最小证据。

### Modified Capabilities

- `cn-etf-beta-sleeve`: standalone research mainline 必须消费新的 target contract，保证 fallback sizing 与 emitted BUY target 语义一致。
- `backtest-research-audit`: standalone mainline 的 drift 检测与 gap 归因必须改为基于 final target contract，而不是把 delta BUY order 误判为 target contract drift。

## Impact

- 影响代码：
  - `backend/core/engine_vector/etf_beta/selection.py`
  - `backend/core/engine_vector/etf_beta/execution_paths.py`
  - `backend/core/stage_pipeline/adapters/order_planning.py`
  - `backend/core/audit/research_audit.py`
  - 相关 ETF provider / audit / artifacts 单测
- 影响产物：
  - `orders.csv`
  - `portfolio_daily.csv`
  - `audit.json`
  - `run_meta.json`
- 不在本次范围：
  - 不继续放宽 standalone deployability 合同
  - 不改 ETF 正式 Phase 1 formal stabilizer 主语义
  - 不改前端工作台
