## ADDED Requirements

### Requirement: audit.json 必须暴露 execution lineage 摘要与异常样本
系统 MUST 在现有 execution audit 结构中新增 execution lineage 摘要，至少覆盖生成信号数、排程订单数、成交数、终止数以及 dropped/missing/same-day 等异常计数。

#### Scenario: lineage 摘要写入 audit.json
- **WHEN** 一次实验完成并具备 lineage ledger 产物
- **THEN** `audit.json` SHALL 输出 execution lineage 摘要
- **THEN** `audit.json` SHALL 同时提供台账引用和受控异常样本

#### Scenario: 发现链路异常
- **WHEN** 某次实验存在 same-day fill、已生成但未排程、已排程但无终态或等价链路异常
- **THEN** execution audit SHALL 记录对应异常计数
- **THEN** 主审计文件 SHALL 保留受控样本供人工复核

### Requirement: lineage 明细不得污染主审计文件
系统 SHALL NOT 在 `audit.json` 中内联全量生命周期台账。

#### Scenario: 明细留在独立 artifact
- **WHEN** 某次实验的订单和成交数量较多
- **THEN** `audit.json` SHALL 仍保持摘要级结构
- **THEN** 全量 lineage 明细 SHALL 留在独立 ledger artifact 中
