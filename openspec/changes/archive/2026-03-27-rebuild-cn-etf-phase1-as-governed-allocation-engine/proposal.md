## Why

当前 ETF 子系统的多轮实验已经证明，继续沿着“个股趋势筛票器 + ETF 标的池”的方向调参数，无法稳定达到目标 CAGR 区间，也持续偏离根目录正式文档 [A股ETF子系统策略思路md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股ETF子系统策略思路md) 定义的 Phase 1 口径。现在需要停止继续扩展研究分支，改为按正式文档把 ETF Phase 1 重建成受统一 Governor/CTA 管控的配置引擎。

## What Changes

- 重建 `cn_etf_beta` 的 Phase 1 正式主线语义：从“筛票/TopN 轮动”改为“预算承接 + 三桶分配 + 桶内低自由度配置”。
- 固定 Phase 1 正式资产池与 limited defense candidate，只允许正式文档定义的宽基 ETF 和 `512890.SH` 参与主线。
- 重构 ETF 输出 contract，使其显式输出 `requested_budget`、`applied_budget`、`targets`、`cash_weight`、`defense_weight`、`reason_codes` 等正式配置字段。
- 为 ETF Phase 1 引入正式的三桶配置与 Governor 边界审计，明确记录总预算、权益桶、防守倾向桶、现金缓冲桶以及各自原因码。
- 将现有 `formal_mainline` study 收敛到新的配置引擎口径；历史研究线继续保留归档，但不再作为主线继续扩展。

## Capabilities

### New Capabilities
- `cn-etf-phase1-allocation-engine`: 定义受统一 Governor/CTA 管控的 ETF Phase 1 正式配置引擎，包括三桶分配、桶内低自由度配置和正式输出 contract。

### Modified Capabilities
- `cn-etf-beta-sleeve`: 正式 ETF 主线从筛票型 beta sleeve 改为配置型 Phase 1 引擎，收紧资产池和职责边界。
- `cn-a-portfolio-governor`: 明确 Governor 对 ETF Phase 1 下发的预算、暴露上限、防守偏置和执行约束的正式消费边界。
- `backtest-research-audit`: 增加 ETF Phase 1 正式配置引擎的预算承接、三桶分配和配置连续性审计字段。
- `cn-etf-research-entry`: 正式 ETF study 入口从研究轮动模板收敛到 Phase 1 配置引擎入口，研究分支显式区分于正式主线。

## Impact

- 影响后端 ETF contract、provider、Governor 消费层和 audit 输出。
- 影响正式 ETF study 定义与实验入口。
- 影响 ETF 结果产物字段和后续前端/报告消费的正式 contract。
- 不涉及行业 ETF、不涉及个股 alpha 组合、不涉及 unified runtime。
