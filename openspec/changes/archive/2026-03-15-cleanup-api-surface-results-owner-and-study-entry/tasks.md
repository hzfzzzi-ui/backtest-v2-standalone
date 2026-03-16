## 1. API Surface 收口

- [x] 1.1 盘点桌面前端主路径中的 `/api/backtest_v2/artifacts/read` 调用点，并建立“旧读取点 -> manifest/surface/section/专用接口”映射表
- [x] 1.2 为桌面主路径补齐缺失的 `surface/{section}` 或专用接口，确保 KPI、图表、阶段漏斗、交易明细不再依赖通用 artifact 读取
- [x] 1.3 改造 `artifacts.js`、`backtest_v2.js`、`desktop-load-controls.js` 的主路径读取逻辑，移除对 `/artifacts/read` 的主路径依赖
- [x] 1.4 补齐 API protocol / integration / frontend boundary 测试，验证桌面主路径只消费 canonical read model

## 2. 结果工作台单 Owner 化

- [x] 2.1 删除生产主路径中的 `wbResultsFallbackRoot` 结构和相关开关逻辑，保留单一 Vue workbench 结果区
- [x] 2.2 清理 `backtest_v2.js`、`artifacts.js`、`ui-controls.js` 中旧结果 DOM 写入路径，使结果更新统一走 `snapshot -> Vue workbench`
- [x] 2.3 收敛 `desktop-research-page` 为唯一结果协调层，并补齐 workbench ownership 边界测试

## 3. 配置核心抽离

- [x] 3.1 设计并创建独立的 config draft core 模块，承接“表单 -> config draft -> runtime request”的主路径编译逻辑
- [x] 3.2 从 `ui-controls.js` 中迁出配置核心逻辑，使旧文件只保留控件联动、显示提示和轻量 UI 同步
- [x] 3.3 调整桌面研究页状态模型，使页面主真相围绕 `experiment manifest / runtime snapshot`，而非长期围绕 `config_id`
- [x] 3.4 补齐 config draft core 的单测与页面边界测试，验证请求 payload 与现有运行口径一致

## 4. Study / Thin Script 主路径收口

- [x] 4.1 继续盘点高频主线研究脚本，确定下一批需要迁入 `.study.yaml` 的脚本清单和 generated thin script 映射
- [x] 4.2 将下一批高频主线脚本迁入 `study + backend.cli study_run + generated thin script` 主路径
- [x] 4.3 更新 `backend/scripts/inventory.json`、README 和 governance 测试，阻止新的顶层大型研究脚本回流

## 5. 回归与收口

- [x] 5.1 跑通 API surface、workbench ownership、config draft core、script governance 相关测试集
- [x] 5.2 以前后对照 `baseline_V10_1 -> exp_20260314_144548534_7db9` 复核 `perf/orders/trades/nav`，确认 `total_return/max_drawdown/cagr/sharpe/calmar/orders/closed_trades` 无漂移
