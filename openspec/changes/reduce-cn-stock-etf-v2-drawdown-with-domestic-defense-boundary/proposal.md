## Why

`CN_STOCK_ETF_COMBO_BASELINE_V2` 相对 `CN_STOCK_ETF_FORMAL_V1` 已经证明扩展 ETF 池能提升收益，但同时最大回撤明显劣化，说明当前 ETF sleeve 在组合语境下存在“收益有效但防守边界不够硬”的问题。

下一轮研究必须先把跨境 beta 剔除，把国内 ETF 池明确拆成 beta、defense、行业主题和风格/Smart Beta，再只在 ETF sleeve 弱状态配置上做最小改动，避免误改 stock alpha 主线。

## What Changes

- 新增 research-only 的 V2 回撤修正研究，研究对象限定为最近 99 ETF 扩展池的国内子集。
- 明确剔除跨境 ETF；跨境部分后续由独立接入口研究，不纳入本轮 A 股组合研究。
- 对当前 ETF 池做显式角色分类：
  - 国内宽基 / 成长 beta
  - 风格 / Smart Beta
  - 行业 / 主题卫星
  - 防守仓：黄金、债券、现金替代
  - 待剔除跨境
- 固定 stock leg，不修改 `baseline_V10.1` / stock alpha 选股、退出、成交与预算消耗逻辑。
- 只研究 ETF sleeve 在 `TRANS_DOWN / RISK_OFF` 下的国内防守边界和 beta 暴露收缩。
- 三窗口执行顺序保持：`2016-2026` 主开发、`2012-2017` 硬门槛、`2012-2026` 全周期审计。
- **BREAKING**: 无。该变更不直接升级正式 baseline，也不改变 `CN_STOCK_ETF_FORMAL_V1` 或 `CN_STOCK_ETF_COMBO_BASELINE_V2` 的既有产物。

## Capabilities

### New Capabilities

- `cn-stock-etf-v2-domestic-defense-drawdown-study`: 定义 stock+ETF V2 国内 ETF 防守边界回撤修正研究的范围、三窗口验收、产物和禁止事项。

### Modified Capabilities

- `cn-etf-beta-sleeve`: 增加 research-only 国内 ETF 子池与跨境剔除要求；弱状态实验必须只使用国内 beta/defense 角色，不得把跨境 ETF 当作 A 股 beta。
- `etf-defense-core-beta-budgets`: 强化研究实验中 defense 与 core beta 的角色分离要求，要求产物显式披露目标、实际暴露和偏差。

## Impact

- 预计影响路径：
  - `openspec/changes/reduce-cn-stock-etf-v2-drawdown-with-domestic-defense-boundary/`
  - `research/studies/etf/*`
  - `research/studies/cn_stock_etf/*`
  - `backend/research/cn_stock_etf_expanded_pool_shadow_study.py` 或新增 research-only runner/helper
  - `backend/core/data/cn_etf_catalog.py` 的角色审计消费，不改变正式池定义
  - 相关单测与 Docker study run
- 不影响路径：
  - stock alpha 主逻辑
  - baseline 主逻辑
  - 信号时点、成交时点
  - benchmark / regime 定义
  - 账户层主真相和正式防守层合同
  - `outputs/` 作为运行产物的边界
