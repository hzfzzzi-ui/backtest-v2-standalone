## 1. 结果工作台 owner 收口

- [x] 1.1 盘点结果工作台当前依赖的 `window.*` global helper，并建立“legacy global -> 新纯模块”的迁移映射。
- [x] 1.2 将漏斗、退出原因、AI Markdown 报告、结果格式化逻辑迁移到 `frontend/app/results-workbench/helpers/` 下的纯模块。

## 2. Vue 单一 owner 落地

- [x] 2.1 让结果工作台直接消费 bridge snapshot 和纯模块 view model，不再从 `window.*` 读取漏斗/报告构造函数。
- [x] 2.2 将结果概览、主图、个股排名、9 阶段漏斗、交易明细、AI Markdown 报告的可见渲染统一收归 Vue。

## 3. legacy fallback 与状态控制收口

- [x] 3.1 清理结果区 active legacy DOM 直写路径，仅保留 Vue mount 失败时的显式 fallback。
- [x] 3.2 收口 accordion/dock 状态控制，消除 `backtest_v2.js` 和 `ui-controls.js` 对同一结果区节点的双写。

## 4. 验证与清理

- [x] 4.1 使用 `baseline_V1` 和 `exp_20260308_021045840_cde0` 完成 100% 缩放 smoke，覆盖默认加载、实验加载以及标准桌面布局下的横向溢出检查。
- [x] 4.2 删除已迁移结果区的 legacy helper 死代码与无效 fallback，清掉 `sell_funnel` 假入口、`wbArtifacts/renderArtifacts` 调试残留和不存在节点的旧写入。
