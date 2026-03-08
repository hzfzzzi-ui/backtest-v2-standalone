## ADDED Requirements

### Requirement: audit 必须记录 stage 壳执行摘要
系统 SHALL 在 `audit.json` 中记录本次回测使用的 stage 壳信息、stage 顺序和 T+1 执行模式。

#### Scenario: audit summary 记录 stage 壳
- **WHEN** 一次 stage pipeline 回测完成并生成 `audit.json`
- **THEN** `audit.summary` SHALL 包含 `execution_shell`
- **THEN** `audit.summary` SHALL 包含 `stage_order`
- **THEN** `audit.summary` SHALL 包含 `t_plus_one_mode`

### Requirement: audit 必须记录 stage 级异常摘要
系统 SHALL 在审计产物中记录 stage 级告警与异常摘要，以便识别编排错误或口径漂移。

#### Scenario: stage 输出异常被记录
- **WHEN** 任一 stage 返回缺失必需字段、同日成交违规、不可解释的空输出或顺序异常
- **THEN** `audit.flags` SHALL 追加对应 stage 的告警记录

#### Scenario: stage 级计数异常被汇总
- **WHEN** 回测完成
- **THEN** `audit.summary` SHALL 包含 stage 级异常计数摘要
