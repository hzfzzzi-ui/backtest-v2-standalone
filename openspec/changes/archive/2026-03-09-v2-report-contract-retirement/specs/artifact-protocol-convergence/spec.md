## MODIFIED Requirements

### Requirement: report.html 不再属于当前 artifact 主契约

系统当前 artifact 主契约 MUST 以 `manifest.json`、`perf.json`、`nav.csv`、`run_meta.json`、`audit.json`、Markdown 分析报告等产物为核心。`report.html` 若存在，仅可视为 legacy artifact，当前主契约 SHALL NOT 继续依赖它。

#### Scenario: 新实验稳定化
- **WHEN** 系统稳定化一个新实验目录
- **THEN** manifest SHALL NOT 将 `report.html` 标记为当前标准产物

#### Scenario: 历史实验目录仍保留 report.html
- **WHEN** 历史实验目录中仍存在 `report.html`
- **THEN** 系统 MAY 兼容保留文件
- **THEN** 当前前端与门禁 SHALL NOT 依赖该文件
