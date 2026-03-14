## Why

结果工作台虽然已经引入了 Vue 壳，但当前仍依赖 `window.*` legacy helper 生成漏斗、报告和部分结果区内容，同时折叠面板还存在多套状态控制逻辑。这样会让结果区继续处于“可用但不稳定”的过渡态，阻碍前端真正收口为单一 owner。

## What Changes

- 将结果工作台收口为 Vue 单一渲染 owner，覆盖结果概览、主图、个股排名、9 阶段漏斗、交易明细和 AI Markdown 报告。
- 将漏斗、报告、结果格式化逻辑从 `window.*` 全局 helper 迁移为结果工作台内部纯模块函数。
- 清理已迁移结果区的 legacy DOM 直写与双重 accordion 状态控制，仅保留“Vue 挂载失败时”的显式 fallback。
- 补齐 `baseline_V1` / `exp_20260308_021045840_cde0` 在 100% 缩放下的 smoke 验证要求，确保页面在标准桌面缩放下稳定可用。

## Capabilities

### New Capabilities
- `results-workbench-finalization`: 规定结果工作台的单一 owner、桥接快照边界、fallback 行为和 100% 缩放下的稳定性要求。

### Modified Capabilities
- `frontend-module-split`: 结果区模块拆分从“提取文件”升级为“单一 DOM ownership”，禁止多个原生脚本并行渲染同一结果区域。

## Impact

- 前端结果工作台：`frontend/app/results-workbench/**`
- 前端 legacy bridge：`frontend/assets/js/artifacts.js`
- 前端状态控制：`frontend/assets/js/backtest_v2.js`, `frontend/assets/js/ui-controls.js`
- 前端图表和报告桥接：`frontend/assets/js/charts.js`, `frontend/assets/js/report.js`
- 页面容器与挂载点：`frontend/index.html`
- 验证对象：`baseline_V1` 与 `exp_20260308_021045840_cde0`
