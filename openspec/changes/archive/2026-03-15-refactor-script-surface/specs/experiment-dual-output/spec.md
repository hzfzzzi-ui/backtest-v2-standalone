## ADDED Requirements

### Requirement: 每个实验必须产出 machine bundle
系统 MUST 为每次正式实验生成 machine bundle。第一版 machine bundle MUST 至少包含 `manifest.json`、`nac.json`、`perf.json`、`audit.json`、`compare.json`、`surface.json`、`config_snapshot.json` 和 `run_meta.json`。

#### Scenario: 正常完成一次实验
- **WHEN** 实验运行完成
- **THEN** 系统 MUST 在 `outputs/experiments/<exp_id>/machine/` 下写入完整 machine bundle
- **THEN** 缺少任一强制文件 SHALL 被视为实验产物不完整

#### Scenario: 读取机器读结论
- **WHEN** 下游流程需要消费实验结论
- **THEN** 系统 MUST 提供 `nac.json` 作为机器读判断包
- **THEN** 机器流程 SHALL NOT 依赖 human-only 文本结论

### Requirement: NAC 必须作为机器读实验判断包
系统 MUST 将 `NAC` 定义为机器读实验判断包。`nac.json` MUST 至少包含 `schema_version`、`exp_id`、`baseline_id`、`study_id`、`hypothesis`、`change_scope`、`audit`、`robustness`、`verdict` 和 `next_action`。

#### Scenario: 实验审计通过但稳健性失败
- **WHEN** 实验通过时间对齐审计但未通过稳健性门槛
- **THEN** `nac.json` MUST 能分别表达 `audit` 和 `robustness` 状态
- **THEN** `verdict` 和 `next_action` MUST 明确该实验不能直接晋级

#### Scenario: 机器流程需要决定下一步
- **WHEN** 自动化流程读取 `nac.json`
- **THEN** 系统 MUST 提供可机读的 `verdict` 和 `next_action`
- **THEN** 下游 SHALL 能区分 `promote`、`iterate`、`archive` 和 `block`

### Requirement: 每个实验必须产出 human bundle
系统 MUST 为每次正式实验生成 human bundle。第一版 human bundle MUST 至少包含 `conclusion.md` 和 `summary.txt`，并 MUST 明确本轮只改什么、审计是否通过、稳健性是否通过以及是否进入下一轮。

#### Scenario: 用户查看实验结论
- **WHEN** 用户打开某次实验的人读结论
- **THEN** 系统 MUST 提供结论优先、简洁可读的 `conclusion.md`
- **THEN** 结论 MUST 明确 `通过 / 不通过 / 待复核`

#### Scenario: 缺少人读结论
- **WHEN** 实验只产出 machine bundle 而未产出 human bundle
- **THEN** 系统 SHALL 将该实验判定为输出不完整
- **THEN** 该实验 SHALL NOT 被视为正式研究结论
