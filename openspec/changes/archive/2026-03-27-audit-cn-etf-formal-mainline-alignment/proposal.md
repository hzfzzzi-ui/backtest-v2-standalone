## Why

当前 `cn_etf_beta` 的代码实现、研究 study 与较优实验线，已经明显偏离根目录正式策略文档 [A股ETF子系统策略思路md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股ETF子系统策略思路md) 定义的 Phase 1 口径。继续直接优化收益，会在一条已偏离正式定义的研究线上越走越远，因此必须先完成一次“正式口径对齐审计”，明确哪些实现属于正式主线，哪些只能保留为 `research_only`。

## What Changes

- 新增 ETF 正式口径对齐审计能力，以根目录正式策略文档作为 Phase 1 合法口径来源。
- 为 ETF 运行时 profile、study 与实验结果增加正式分类：
  - `formal_mainline`
  - `research_only`
  - `do_not_promote`
- 显式审计当前 ETF 资产池、limited defense candidate、信号语义、输出 contract 是否符合正式文档。
- 要求 research audit 与 run_meta 暴露 ETF 正式对齐状态和偏离原因，而不是继续把所有 ETF 实验都伪装成同一条正式主线。
- 要求 `cn_etf` 研究入口显式区分“正式主线入口”与“研究分支入口”，避免 `159915`、`588000`、`511010` 这类研究资产继续隐式混入正式主线语义。

## Capabilities

### New Capabilities
- `cn-etf-formal-mainline-alignment-audit`: 定义 ETF Phase 1 正式口径对齐审计、正式分类和偏离原因输出。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 收紧 ETF 正式主线的资产池、职责边界和允许输出。
- `cn-etf-research-entry`: 要求 ETF 研究入口显式区分正式主线与研究分支，不得继续混淆。
- `cn-a-portfolio-governor`: 明确 Governor 只为 ETF 正式主线提供上游约束，不替 ETF 研究分支背书为正式口径。
- `backtest-research-audit`: 要求 research audit 输出 ETF 正式口径对齐状态与偏离证据。

## Impact

- 影响后端 ETF contract、provider、audit 与 study metadata：
  - `backend/core/config/etf_beta_contract.py`
  - `backend/core/engine_vector/cn_etf_beta_signal_provider.py`
  - `backend/core/audit/research_audit.py`
- 影响 ETF 研究入口与 study 目录：
  - `research/studies/etf`
- 影响 ETF 运行时与实验产物的正式分类字段：
  - `run_meta.json`
  - `audit.json`
