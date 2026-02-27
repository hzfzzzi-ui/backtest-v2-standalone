## MODIFIED Requirements

### Requirement: 导出回测报告按钮
工作台 SHALL 提供"导出报告"按钮，点击后在新浏览器标签页中打开后端已生成的 report.html。如果后端 report.html 不存在（旧实验），fallback 到前端本地生成。

#### Scenario: 回测完成后导出（后端报告存在）
- **WHEN** 用户点击"导出报告"按钮且当前实验有后端生成的 report.html
- **THEN** 系统 SHALL 在新标签页中打开 `/api/backtest_v2/experiments/{exp_id}/report`

#### Scenario: 后端报告不存在时 fallback
- **WHEN** 用户点击"导出报告"按钮但后端 report.html 不存在（404）
- **THEN** 系统 SHALL fallback 到前端 generateReport() 本地生成并在新标签页展示

#### Scenario: 无回测结果时导出
- **WHEN** 用户点击"导出报告"按钮但无已完成的回测结果
- **THEN** 系统 SHALL 提示"请先运行回测"
