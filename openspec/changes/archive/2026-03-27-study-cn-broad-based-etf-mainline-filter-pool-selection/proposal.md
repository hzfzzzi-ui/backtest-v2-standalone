## Why

当前宽基 ETF 主线已经连续几轮证明：单独调 `target_exposure`、`controlled_accumulation` 和 fallback 语义，无法把结果拉到目标区间。现有研究证据更像是在提示主瓶颈落在 `绝对过滤过严`、`候选池偏弱或代理失真`、`选择链路把强 ETF 过滤掉` 这三点上，需要把研究顺序正式收口，停止继续混入暴露语义变量。

## What Changes

- 新增一条“宽基 ETF 主线主瓶颈研究”能力，只允许围绕 `绝对过滤`、`候选池`、`选择链路` 三条线做顺序化研究。
- 固定当前 Governor/CTA 边界与 ETF 本地暴露语义为控制条件，本轮 **不再** 研究新的 exposure policy family。
- 为宽基 ETF 主线定义三组最小 AB：
  - 绝对过滤族
  - 候选池族
  - 选择链路族
- 扩展研究入口和 research audit，使实验能够显式回答：
  - 多少天被绝对过滤挡掉
  - 当前候选池 profile 是什么
  - 最终是谁在排序链路里胜出、谁被淘汰、为什么
- **BREAKING** 当前 ETF 主线研究优先级从“继续调暴露语义”切换为“先打绝对过滤/候选池/选择链路三个主瓶颈”；后续 ETF 研究不得再把这三类改动和新的 exposure policy 绑定在同一轮实验里。

## Capabilities

### New Capabilities
- `cn-broad-based-etf-mainline-bottleneck-study`: 定义宽基 ETF 独立主线的主瓶颈研究顺序、控制条件和最小 AB 矩阵，只研究绝对过滤、候选池与选择链路。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 增加宽基 ETF 主线的绝对过滤 profile、候选池 profile、选择链路 profile 以及对应的可审计输出。
- `cn-etf-research-entry`: 增加宽基 ETF 主线的研究 profile 入口，并禁止在本轮研究中混入行业 ETF。
- `backtest-research-audit`: 增加 `absolute_filter / candidate_pool / selection_chain` 维度的证据链和瓶颈统计。

## Impact

- 影响后端 ETF 配置合同、ETF signal provider、ETF study 定义和 research audit。
- 影响的主路径预计包括：
  - `backend/api/backtest_v2/semantic_config_schema.py`
  - `backend/core/config/etf_beta_contract.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/audit/research_audit.py`
  - `research/studies/etf/*`
- 不修改个股 alpha 主线，不研究行业 ETF，不进入 unified runtime 组合口径。
