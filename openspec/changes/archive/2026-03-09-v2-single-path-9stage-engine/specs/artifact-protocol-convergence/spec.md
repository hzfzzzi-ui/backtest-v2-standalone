## ADDED Requirements

### Requirement: 实验目录必须输出 stage pipeline 稳定摘要
系统 SHALL 在 stage pipeline shell 完成一次受治理回测后输出 `stage_summary.json`，用于表达 stage 编排与摘要计数。

#### Scenario: stage_summary.json 正常生成
- **WHEN** 一次回测运行成功完成 stage pipeline shell
- **THEN** 实验目录 SHALL 包含 `stage_summary.json`
- **THEN** 该文件 SHALL 至少包含 `schema_version`、`execution_shell`、`stage_order`、`enabled_stages`、`buy_pipeline_counts`、`sell_pipeline_counts` 和 `warnings`

#### Scenario: manifest 暴露 stage 摘要
- **WHEN** `manifest.json` 写盘完成
- **THEN** `artifacts` SHALL 包含 `"stage_summary": "stage_summary.json"`

### Requirement: run_meta 必须携带 stage pipeline 精简摘要
系统 SHALL 在 `run_meta.json` 中记录 stage pipeline 的精简元信息，便于前端和治理脚本快速识别执行壳。

#### Scenario: run_meta 记录 stage pipeline
- **WHEN** 一次 stage pipeline 回测写出 `run_meta.json`
- **THEN** `run_meta.json` SHALL 包含 `stage_pipeline` 对象
- **THEN** 该对象 SHALL 至少包含 `execution_shell`、`stage_order`、`enabled_stages` 和 `daily_loop_mode`
