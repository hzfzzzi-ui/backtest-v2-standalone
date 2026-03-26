## 1. Change 收口

- [x] 1.1 收口 ETF 主线范围，只覆盖 `runtime truth`、`audit/governor` 语义和 `smoke` 路径，不扩首波 ETF 名单

## 2. Runtime Truth

- [x] 2.1 修正 `cn_etf` 运行时的 benchmark truth，避免 ETF 运行静默继承 `000300.SH`
- [x] 2.2 修正 ETF provider/read path 的产物暴露，确保 `daily_table / coverage_start / coverage_end / price_series_semantics` 保持 ETF 真值

## 3. Governor 与 Audit 对齐

- [x] 3.1 修正 `audit.json.governor_budget.latest` 的 ETF 资产语义，确保 `asset_scope / budget_consumer_sleeve_id / sleeve_budgets` 与 ETF 主线一致
- [x] 3.2 确认 `research_audit` 的 ETF 主线解释明确输出 ETF entry、coverage 与 sleeve 摘要，不再混入股票 PIT 语义

## 4. Smoke 固化

- [x] 4.1 使用现有 `etf/cn_etf_first_wave_core` 运行一次最小 smoke，并生成新 experiment artifacts
- [x] 4.2 输出最小 smoke 结论，明确“路径通过，不以成交为条件”

## 5. 验证与回退

- [x] 5.1 跑定向单测并重新校验 change
- [x] 5.2 在 close-out 中说明受影响文件、风险和回退方法
