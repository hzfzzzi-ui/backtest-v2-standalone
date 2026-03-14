## Why

前端结果工作台已经转向 Markdown/AI 分析报告，但后端仍保留 `report.html` 读取接口和 manifest 可选产物，导致报告协议处于双轨状态。这会持续增加历史兼容负担，也让脚本和回归门禁继续把 HTML 报告当作半主路径。

## What Changes

- 将报告主契约正式收口到 Markdown/AI 分析报告，不再以 `report.html` 作为公开消费面。
- 下线 `/api/backtest_v2/experiments/{exp_id}/report` 公开 HTML 报告接口。
- 从 manifest / artifact 协议中移除 `report.html` 的主契约地位，保留历史兼容策略但不再作为当前主线依赖。
- 更新前端历史/导出/分析链路，仅保留 Markdown 报告查看、复制和导出。
- 更新脚本和门禁，使其不再因为 `report.html` hash 漂移产生持续 WARN。

## Capabilities

### New Capabilities
- `markdown-analysis-report`: 定义适合 AI/agent 消费的 Markdown 报告产物与前端消费方式。

### Modified Capabilities
- `backtest-report-export`: 报告导出从 HTML 导出切换为 Markdown 导出。
- `experiment-history`: 历史实验不再提供 HTML 报告查看入口，而是通过 Markdown/结果工作台消费报告。
- `artifact-protocol-convergence`: `report.html` 不再是当前 artifact 契约的标准组成部分。

## Impact

- 报告生成与导出：`backend/core/report/**`, `frontend/assets/js/report.js`, `frontend/app/results-workbench/components/AgentReportPanel.vue`
- 实验历史与读取：`backend/api/endpoints/_experiment_history.py`, `frontend/assets/js/backtest_v2.js`
- 产物稳定化与 manifest：`backend/api/endpoints/backtest_v2_artifacts.py`
- 回归与 consistency 脚本：`backend/scripts/baseline_regression_check.py`, `backend/scripts/report_consistency_check.py`
