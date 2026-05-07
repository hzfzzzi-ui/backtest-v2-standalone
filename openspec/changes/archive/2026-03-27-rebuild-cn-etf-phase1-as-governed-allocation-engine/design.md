## Context

当前 ETF 子系统已经通过正式对齐审计，明确只有 [cn_etf_first_wave_core.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_first_wave_core.study.yaml) 可以继续视为 `formal_mainline`。同时，多轮已归档研究线已经证明，继续在 ETF 上叠加 `TopN`、绝对过滤、排序链和研究分支资产，并不能稳定解决低 CAGR 问题，反而持续偏离根目录正式文档 [A股ETF子系统策略思路md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股ETF子系统策略思路md) 定义的 Phase 1 配置语义。

当前主要约束：

- ETF 仍然必须受统一 `market_regime_engine -> global_portfolio_governor -> cn_etf_beta -> attribution_audit` 链路约束。
- Phase 1 正式资产池必须收敛到 `510300.SH`、`510500.SH`、`510050.SH`、`512100.SH`，limited defense candidate 只允许 `512890.SH`。
- 本轮只重建 ETF 独立主线，不研究行业 ETF，不与个股 alpha 混跑，不扩展 unified runtime。

## Goals / Non-Goals

**Goals:**

- 将 `cn_etf_beta` Phase 1 从筛票型 beta sleeve 重建为 Governor 约束下的 ETF 配置引擎。
- 将 ETF 决策改为四层结构：状态映射、总预算承接、三桶分配、桶内低自由度配置。
- 统一输出正式配置 contract，包括 `requested_budget`、`applied_budget`、`targets`、`cash_weight`、`defense_weight`、`reason_codes`。
- 在 audit 中显式区分 Governor 下发边界、三桶预算和最终实际落地，避免前端或研究报告继续把 ETF 解释成“筛票器”。

**Non-Goals:**

- 不引入行业 ETF。
- 不恢复或升级任何 `do_not_promote` 研究资产，如 `159915.SZ`、`588000.SH`、`511010.SH`。
- 不继续优化旧的 `MA200/RET12/Top2` 研究线。
- 不和个股 alpha 组合做配比实验。

## Decisions

### 决策 1：正式 ETF 主线以“分配”为中心，不再以“筛票”为中心

选择：

- 正式主线先由 Governor 下发总 ETF sleeve 预算。
- ETF 本地只负责把这份预算拆成：
  - `equity_core_bucket`
  - `defense_tilt_bucket`
  - `cash_buffer_bucket`

原因：

- 这与正式文档对 ETF Phase 1 的定义一致。
- 过去多轮实验已经证明，把 ETF 当成“个股趋势策略的 ETF 壳”无法稳定达到目标收益区间。

备选但不采用：

- 继续沿用 `TopN` 排序主导，再在末端补解释字段。
  - 否决原因：这会继续强化筛票逻辑，而不是配置逻辑。

### 决策 2：正式池固定，不再让研究资产混入主线

选择：

- 正式权益桶只允许 `510300.SH`、`510500.SH`、`510050.SH`、`512100.SH`
- limited defense 只允许 `512890.SH`

原因：

- 正式资产边界已经由 formal alignment change 明确。
- 继续混入 `159915.SZ`、`588000.SH`、`511010.SH` 只会把主线再次拉回研究分支。

备选但不采用：

- 保留 proxy/增强资产作为“临时正式池”。
  - 否决原因：会重新污染 `formal_mainline` 口径。

### 决策 3：桶内配置采用低自由度规则，而不是高自由度排名器

选择：

- 在 `equity_core_bucket` 内部，只允许有限模板权重或有限倾斜规则。
- `512100.SH` 仅作为成长增强器，必须有上限，不得重新变成主导资产。
- `defense_tilt_bucket` 只允许分配给 `512890.SH`。
- `cash_buffer_bucket` 明确保留为未部署预算，而不是通过“无票可买”被动形成。

原因：

- ETF Phase 1 的目标是配置稳定性和资本承接，而不是构造更复杂的择时筛票器。

备选但不采用：

- 在桶内继续用 `Top2/Top1` 选择链。
  - 否决原因：这会把桶内分配重新退化成选择链。

### 决策 4：把旧绝对过滤与排序逻辑降级为研究兼容层

选择：

- 正式 Phase 1 引擎不再把旧的强绝对过滤作为主策略语义。
- 如果需要保留旧字段兼容研究产物，只允许作为兼容层或对照输出，不作为正式主决策入口。

原因：

- 主矛盾已经证明不在简单调参数，而在策略语义本身。

备选但不采用：

- 再开一轮更细的 `MA150/180/200` 或动量窗口对照。
  - 否决原因：这仍然是在旧语义上做局部优化。

## Risks / Trade-offs

- [风险] 正式配置引擎与现有 provider 中的筛票分支耦合较深，重构时容易让兼容逻辑与正式主线再次混杂。  
  → Mitigation：在 contract 层显式区分 `formal_phase1_allocation_engine` 与历史研究 profile，研究 profile 只保留兼容入口。

- [风险] 只靠正式资产池和三桶分配重建后，收益可能短期仍然不理想。  
  → Mitigation：本轮先把目标定义为“口径正确、配置连续、审计可追溯”，不把收益提升作为单轮完成标准。

- [风险] 现有前端/报告可能仍默认把 ETF 结果理解成“选中哪些 ETF”。  
  → Mitigation：在产物字段和 audit 里显式增加 bucket/targets/cash/defense 语义，避免前端自行反推。

- [风险] 旧研究线很多，若不明确降级，会再次被误用成正式主线。  
  → Mitigation：formal alignment 继续保留，正式 study 只允许 `cn_etf_first_wave_core` 走新引擎。
