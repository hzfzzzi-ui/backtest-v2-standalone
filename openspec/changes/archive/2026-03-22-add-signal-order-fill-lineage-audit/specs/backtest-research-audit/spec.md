## ADDED Requirements

### Requirement: timing_alignment 必须优先消费显式 lineage 证据
系统 MUST 在实验提供 execution lineage 证据时，优先依据 `signal_date`、`scheduled_date`、`fill_date` 和终态记录判断时间对齐风险，而不是仅依赖配置推断。

#### Scenario: 明确发现同日生成同日成交
- **WHEN** lineage 证据显示某条以收盘后信号为前提的交易在同一交易日完成成交
- **THEN** `research_audit.gates.timing_alignment.status` SHALL 为 `FAIL`

#### Scenario: 明确证明 next-day contract 成立
- **WHEN** lineage 证据显示信号在 T 日生成、订单在 T+1 排程并以符合合同的方式终结，且其他 PIT-safe 条件成立
- **THEN** `research_audit.gates.timing_alignment` SHALL 可以基于显式 lineage 证据给出 `PASS`

#### Scenario: lineage 证据缺失或不完整
- **WHEN** 当前实验没有 lineage 证据，或证据不足以证明完整链路
- **THEN** `timing_alignment` SHALL 回退到既有推断路径或输出 `UNKNOWN`
- **THEN** 系统 SHALL NOT 因缺少显式 lineage 证据而伪造 `PASS`
