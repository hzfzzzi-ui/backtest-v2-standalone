# cn-stock-v2-audit-and-gate-governance Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements

### Requirement: V2 审计 MUST 同时输出 canonical gate 与 runtime gate
系统 MUST 为 `v2` 数据质量提供两层门禁：`canonical gate` 用于判断 `v2` 是否可作为正式数据库底座，`runtime gate` 用于判断给定 baseline 是否可安全消费 `v2` 数据。系统 SHALL NOT 再只输出单一总门禁结论。

#### Scenario: 生成全历史审计总结
- **WHEN** 系统完成 `v2` 全历史审计
- **THEN** 审计总结 MUST 同时输出 canonical gate 与 runtime gate 结论
- **THEN** 两类门禁 MUST 分别列出阻塞项

### Requirement: 审计 MUST 按市场与阶段拆分
系统 MUST 将 `v2` 审计结果至少拆分为 `SH`、`SZ`、`BJ pre-2021-11-15`、`BJ post-2021-11-15` 四个维度，并输出各维度的 coverage、unresolved、补值、exception 分布。系统 SHALL NOT 仅依赖全市场总量来判断 `v2` 质量。

#### Scenario: 输出 BJ 审计
- **WHEN** 系统输出 `BJ` 相关质量审计
- **THEN** 审计 MUST 同时给出正式开市前后的分段结果
- **THEN** 审计 MUST 能显示各分段的主问题类型

#### Scenario: 输出全市场门禁
- **WHEN** 系统计算全市场升格门禁
- **THEN** 门禁 MUST 可追溯到各市场/阶段分解
- **THEN** 报告 MUST 能说明是哪个市场或阶段阻塞了门禁

### Requirement: 异常汇总 MUST 可追溯到样本与原因分类
系统 MUST 让每类关键异常都能追溯到 symbol-date 样本、来源分类和汇总统计。对于 `eligible_no_source`、`turnover_rate_imputed_zero`、`pre_close_imputed_zero` 等异常，系统 MUST 能输出按年份、交易所、阶段、symbol 的分解结果。

#### Scenario: 审计异常 drill-down
- **WHEN** 用户或治理脚本检查 `v2` 某类异常
- **THEN** 系统 MUST 能输出该异常的样本明细与聚合视角
- **THEN** 系统 MUST 能区分是源缺失、映射污染还是构建规则导致
