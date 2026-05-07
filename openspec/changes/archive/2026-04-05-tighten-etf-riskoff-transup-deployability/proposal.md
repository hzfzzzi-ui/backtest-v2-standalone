## Why

当前 `etf/cn_broad_based_research_mainline_r1` 在 `2012-01-01` 到 `2026-03-24` 的回测里，`TRANS_UP` 平均目标暴露约为 `0.9`，平均实际暴露只有约 `0.013`；`BULL` 平均目标暴露为 `1.0`，平均实际暴露只有约 `0.49`。现有 ETF 单腿 research mainline 的主要瓶颈已经不是资产池或过滤器，而是 `RISK_OFF / TRANS_UP` 的部署合同过于保守，且 provider 在非调仓日几乎不做 live 补仓，导致 approved target 无法转成实际暴露。

## What Changes

- 调整 `governed_broad_based_standalone_mainline` 路径下 `TRANS_UP` 的部署合同，使其允许在非调仓日把已批准的 `TRANS_UP` target 转成 live deployable target，而不是继续退化为 `hold_until_rebalance`。
- 调整同一路径下 `RISK_OFF` 的部署合同，使其允许小幅、core-only 的受控累积，不再把 `RISK_OFF` 默认压成 `deployment_pace = 0`。
- 允许 ETF provider 在上述两个状态下对已有持仓执行补仓型 BUY path，以缩小 `target_exposure / actual_exposure` 的长期偏差。
- 增加最小审计证据，明确区分 `monthly/biweekly rebalance` 与 `inter_rebalance_deploy`，并记录对应的 reason code 与 execution path。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-etf-beta-sleeve`: 修改 research standalone mainline 在 `RISK_OFF / TRANS_UP` 下的部署合同与非调仓日部署路径。

## Impact

- 影响代码：
  - `backend/core/config/etf_beta/common.py`
  - `backend/core/config/etf_beta/exposure_semantics.py`
  - `backend/core/config/etf_beta/defaults.py`
  - `backend/core/config/etf_beta/normalization.py`
  - `backend/core/engine_vector/etf_beta/execution_paths.py`
  - `backend/core/engine_vector/etf_beta/selection.py`
  - `backend/core/stage_pipeline/adapters/etf_beta_accounting.py`
  - 相关 ETF contract/provider/accounting 单测
- 影响产物：
  - `run_meta.json`
  - `audit.json`
  - `orders.csv`
  - `portfolio_daily.csv`
- 不在本次范围：
  - 不改 ETF 资产池
  - 不改 BULL 的纸面 target 设定
  - 不改前端
  - 不改 stock+ETF combo
