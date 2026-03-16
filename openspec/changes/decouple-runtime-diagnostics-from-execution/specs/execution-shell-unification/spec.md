## ADDED Requirements

### Requirement: 正式执行总线中的 diagnostics adapter 必须成为唯一归一化层
系统 MUST 将正式执行总线中的 diagnostics adapter 视为最终 diagnostics 归一化的唯一 owner。`daily_accounting.py` 等执行 facade 可以产出原始 diagnostics input，但 SHALL NOT 重新承担最终 stage count 语义。

#### Scenario: stage pipeline 写入 daily row
- **WHEN** stage pipeline 在日循环结束后写入 daily row 或 accounting snapshot
- **THEN** 执行 facade MUST 仅写入原始执行事实和 diagnostics input
- **THEN** 最终 diagnostics 归一化 MUST 延后到 diagnostics adapter 或 builder

#### Scenario: provider 或 runtime 路由扩展
- **WHEN** 后续 provider 或 runtime route 扩展新的诊断字段
- **THEN** 系统 MUST 通过 diagnostics adapter 接线
- **THEN** 执行 facade SHALL NOT 因扩展诊断字段重新长回重型 diagnostics owner
