## 实现范围

本次实现只覆盖前端布局与结果解释层重排，不修改研究口径、运行时 contract 或任何核心回测逻辑。

完成内容：

- 在桌面主壳顶部新增 `Global Control Strip`，承载资产范围、时间范围、Regime 摘要和 Governor 摘要。
- 将 `asset_scope` 切换后的左侧导航重组为资产特化抽屉：
  - `cn_a_equity` 使用股票 alpha 语义。
  - `cn_etf` 使用 ETF beta 语义。
- 将结果工作台拆成 `Performance / Regime / Governor / Attribution` 四类视图。
- 让 `Regime / Governor / Attribution` 面板只消费正式 snapshot/run_meta 字段，不再从旧的 `market_state/trade_mode` 反推。

## 影响文件

主要前端文件：

- `frontend/index.html`
- `frontend/assets/js/backtest_v2.js`
- `frontend/assets/js/ui-controls.js`
- `frontend/assets/js/artifacts.js`
- `frontend/assets/css/workbench.css`
- `frontend/app/results-workbench/App.vue`
- `frontend/app/results-workbench/components/ResultsOverview.vue`
- `frontend/app/results-workbench/components/RegimePanel.vue`
- `frontend/app/results-workbench/components/GovernorPanel.vue`
- `frontend/app/results-workbench/components/AttributionPanel.vue`
- `frontend/app/results-workbench/helpers/resultsFormatting.js`

相关测试：

- `tests/frontend/multi_alpha_workbench_harness.cjs`
- `tests/frontend/test_multi_alpha_workbench.cjs`
- `tests/frontend/test_results_workbench_multi_alpha.mjs`

## 验证

已通过：

- `node --test tests/frontend/test_multi_alpha_workbench.cjs`
- `node --test tests/frontend/test_results_workbench_multi_alpha.mjs`
- `npm run build:results-workbench`
- `openspec validate refactor-frontend-global-controls-and-asset-drawers --type change --strict`

说明：

- 双模式 smoke 通过前端 DOM/结果工作台测试完成，覆盖 `cn_a_equity` 与 `cn_etf` 的顶部 strip、左侧资产特化导航和结果工作台四类视图。
- 这轮没有改后端 contract，也没有引入新的实验回测。

## 风险

- 当前桌面主壳仍是过渡层，`frontend/assets/js/backtest_v2.js`、`ui-controls.js`、`artifacts.js` 继续承担兼容逻辑；这次只是把职责重排，并没有完成旧壳瘦身。
- 左侧仍保留 `S1-S9` 的兼容映射，只是正式页面语义不再以它为中心。
- 结果工作台新增三个只读面板，但还没有扩展成完整的手工 override 控制台。

## 回退

如果要回退本轮前端改造，建议按下面顺序撤回：

1. 先回退结果工作台新增面板与 `App.vue` tab 切分：
   - `frontend/app/results-workbench/App.vue`
   - `frontend/app/results-workbench/components/RegimePanel.vue`
   - `frontend/app/results-workbench/components/GovernorPanel.vue`
   - `frontend/app/results-workbench/components/AttributionPanel.vue`
   - `frontend/app/results-workbench/helpers/resultsFormatting.js`
   - `frontend/app/results-workbench/components/ResultsOverview.vue`
2. 再回退顶部 `Global Control Strip` 与资产特化导航：
   - `frontend/index.html`
   - `frontend/assets/js/backtest_v2.js`
   - `frontend/assets/js/ui-controls.js`
   - `frontend/assets/js/artifacts.js`
   - `frontend/assets/css/workbench.css`
3. 最后回退对应前端测试：
   - `tests/frontend/multi_alpha_workbench_harness.cjs`
   - `tests/frontend/test_multi_alpha_workbench.cjs`
   - `tests/frontend/test_results_workbench_multi_alpha.mjs`

回退不会影响后端数据口径和研究运行 contract。
