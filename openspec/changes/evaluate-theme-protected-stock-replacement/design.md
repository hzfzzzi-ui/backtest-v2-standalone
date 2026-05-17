## Context

当前已有 V3 组合基线和一轮只读行业/主题归因产物，路径为 `outputs/studies/cn_stock_etf/sr_20260510_v3_industry_theme_etf_index_attribution`。该产物包含 B0 shadow 和 B0.1 protected shadow 的 CSV 与报告，但生成逻辑仍是研究过程中的临时脚本，不能直接等同正式 study。

本设计把这轮研究推进到正式 study 层：由 `study_run` 调度、由 runner 校验证据输入、由 conclusion registry 写入正式结论、由 study journal 给前端展示。

## Goals / Non-Goals

**Goals:**

- 建立 B0.1 保护替换规则的正式 research-only study 入口。
- 审计 protected shadow 是否仍有足够触发密度，以及是否避免卖出核心科技、强趋势和目标相关主题。
- 把结果写入标准 study 输出和 study journal，便于前端检查。
- 对三窗口覆盖不足风险给出明确标注。

**Non-Goals:**

- 不实现真实 B1 成交回测。
- 不把 shadow plan 注入 runtime 或 account allocator。
- 不修改 V3 baseline、股票池、ETF 池、排序主因子、买入规则、退出规则或组合权重。
- 不用前端重算研究逻辑。

## Decisions

1. **先做 formal shadow，不直接做 runtime AB。**
   - 原因：B0.1 当前验证的是“是否值得进入 B1”，不是“B1 已经改善 NAV”。
   - 替代方案：直接在交易引擎中实现 replacement order。拒绝原因是风险等级更高，且当前还缺少三窗口正式审计。

2. **runner 消费上一轮 V3 attribution bundle，并重新生成正式摘要。**
   - 原因：上一轮产物已经包含完整候选、持仓、主题代理和 shadow 计划；本轮目标是正式审计与登记，不应重复扩散临时脚本。
   - 约束：runner 必须校验输入文件存在，并在输出中声明 `source_artifact_dir`、V3 baseline、stock component 和 ETF component。

3. **conclusion verdict 表达研究结论，不表达 baseline 接受。**
   - `confirmed` 只表示“B0.1 protected shadow 值得进入 B1 AB”，不表示可提升为 baseline。
   - 覆盖不足或证据不足窗口必须给 `inconclusive`。

4. **输出路径仍在 `outputs/studies`，源码逻辑放在 `backend/research`。**
   - 原因：`outputs/` 是运行产物，不承接源码逻辑。

## Risks / Trade-offs

- [Risk] 用户误把 shadow rows 当成真实收益改善。  
  Mitigation: study 标题、metadata、报告和 verdict reason 全部声明“不成交、不重算 NAV、不代表收益改善”。

- [Risk] 2012-2017 与 2012-2026 早期覆盖不完整。  
  Mitigation: runner 对 source coverage 做窗口检查，早期窗口给 `inconclusive`，不能作为 baseline 升级依据。

- [Risk] 结果依赖上一轮 artifact，而不是直接从 runtime 重新跑。  
  Mitigation: 输出 source manifest 和 required file audit；下一步 B1 才进入真实 runtime AB。

- [Risk] study journal 自动摘要没有收益指标。  
  Mitigation: 本轮没有 NAV compare，结论以触发密度、保护规则和证据链为核心，不伪造收益指标。
