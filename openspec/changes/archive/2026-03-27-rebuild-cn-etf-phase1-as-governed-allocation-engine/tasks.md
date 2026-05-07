## 1. 正式 contract 与配置入口
- [x] 1.1 在 ETF contract 与配置 schema 中新增 Phase 1 配置引擎字段，明确 `requested_budget`、`applied_budget`、三桶预算和正式 `targets` 的唯一真相源。
- [x] 1.2 收口正式 ETF study/entry，仅允许 `cn_etf_first_wave_core` 走 Phase 1 配置引擎口径，并保留历史研究线为兼容层。

## 2. Phase 1 配置引擎实现
- [x] 2.1 在 ETF provider 中实现 “Governor 预算承接 -> 三桶分配 -> 桶内低自由度配置” 的正式主路径，并将旧筛票链降级为兼容层。
- [x] 2.2 固定正式资产池与 limited defense candidate，确保正式 `targets` 只来自 `510300/510500/510050/512100/512890`。

## 3. 审计与产物可观测性
- [x] 3.1 在 `research_audit` 和稳定化产物中新增 ETF 三桶分配、预算承接和现金缓冲的正式审计字段。
- [x] 3.2 增加最小诊断输出，显式区分 Governor 边界导致的未部署与 ETF 本地配置导致的未部署。

## 4. 正式 Phase 1 最小实验与回归
- [x] 4.1 基于正式资产池重跑 ETF Phase 1 最小实验，产出正式配置 contract 与实验产物。
- [x] 4.2 完成最小回归验证并补 `implementation_notes.md`，明确影响模块、验证命令和回退路径。
