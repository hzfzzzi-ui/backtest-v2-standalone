## 1. 负向条件上下文研究面
- [x] 1.1 新增 negative conditional context factor catalog，明确条件上下文字段、方向和解释边界
- [x] 1.2 新增 snapshot / factor score snapshot / study surface，并接入 `study_runner`
- [x] 1.3 新增真实三窗口 study，并成功跑出 `analysis.json`

## 2. 行业二阶段研究面
- [x] 2.1 新增 industry second stage factor catalog，收主线行业二阶段全族
- [x] 2.2 新增 snapshot / factor score snapshot / study surface，并接入 `study_runner`
- [x] 2.3 新增真实三窗口 study，并成功跑出 `analysis.json`

## 3. 执行压力研究面
- [x] 3.1 新增 execution pressure factor catalog，从 stock sleeve `portfolio_daily.csv` 构造 account-level pressure 因子
- [x] 3.2 新增 snapshot / factor score snapshot / study surface，并接入 `study_runner`
- [x] 3.3 新增真实三窗口 study，并成功跑出 `analysis.json`

## 4. 说明与回填
- [x] 4.1 回填 notes，明确三条线都是 `RESEARCH_ONLY`
