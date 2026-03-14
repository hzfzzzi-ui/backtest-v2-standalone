## Why

后端第一阶段多 alpha 组合主链路已经可运行，但前端工作台仍停留在占位和旧口径控件状态，用户无法通过可视化界面稳定生成可运行的组合配置，只能手改 JSON。现在需要把研究台前端与已归档的组合运行时契约对齐，避免配置漂移、无效默认值和“页面可选但实际不可跑”的假上线。

## What Changes

- 在工作台中上线第一阶段多 alpha 组合控件，只暴露当前后端已支持的组合能力：`breakout_55`、`rsi_reversal`、`REGIME_ROUTE`、`PREFER_HIGHER_SCORE`、`SOURCE_ONLY`、`hard_sleeve_budget`。
- 让前端草稿构造、加载配置、导入历史实验三条链路统一生成并回填 canonical `signal_generation.modules`、`signal_composition` 和 `position_risk.portfolio_mode`。
- 为旧的组合占位值和不受支持的历史配置增加显式阻断与告警，禁止前端静默改写后继续运行。
- 在结果总览、分析报告和交易明细中展示组合摘要、组合审计计数以及来源归因字段。
- 保持 baseline 单策略默认行为不变；未进入第一阶段的组合模式和高级权重逻辑继续不开放。

## Capabilities

### New Capabilities
- `multi-alpha-workbench-ui`: 定义研究台中第一阶段多 alpha 组合的控件、配置回填、运行前校验以及结果展示行为。

### Modified Capabilities
- 无

## Impact

- 受影响前端模块：`frontend/index.html`、`frontend/assets/js/ui-controls.js`、`frontend/assets/js/backtest_v2.js`、`frontend/assets/js/report.js`、`frontend/assets/js/artifacts.js`、`frontend/app/results-workbench/**`
- 受影响数据契约：工作台 `config_json` 草稿、实验导入回填、结果摘要和交易来源字段展示
- 后端 API 与运行时契约沿用现有公开主路径，不新增后端服务；前端需要严格遵循已有 `single-run-pipeline`、`multi-alpha-signal-composition`、`source-aware-holdings` 和 `backtest-audit` 产物口径
