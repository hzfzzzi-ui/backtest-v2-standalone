## MODIFIED Requirements

### Requirement: artifact 稳定化 owner 必须集中到核心 service

artifact 协议的稳定化和标准产物补齐 MUST 由核心 artifact service 统一负责。endpoint 层 MAY 提供 HTTP 包装，但 SHALL NOT 成为稳定化的唯一 owner。

#### Scenario: manifest 写入
- **WHEN** 实验完成并需要写入 manifest
- **THEN** manifest SHALL 由核心 artifact service 生成

#### Scenario: 标准产物补齐
- **WHEN** 系统需要补齐 `perf.json`、`nav.csv`、`run_meta.json`、`audit.json`
- **THEN** 这些动作 SHALL 由核心 artifact service 负责
