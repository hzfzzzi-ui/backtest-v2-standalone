## ADDED Requirements

### Requirement: artifact service 的 finalize owner 必须允许分层实现
系统 MUST 允许 experiment artifact service 通过分层 finalize pipeline 承担 manifest、summary、diagnostics 和 artifact stabilize 职责。底层 owner MAY 拆分为 `io`、`manifest`、`stage-summary`、`diagnostics` 和 `finalize` 模块，但对外 artifact service 契约 MUST 保持稳定。

#### Scenario: API 触发 artifact stabilize
- **WHEN** API 或 service 触发一次实验目录稳定化
- **THEN** 底层实现 MAY 调度分层 finalize 模块完成工作
- **THEN** artifact service 对外入口和标准产物协议 MUST 保持不变

#### Scenario: 新诊断产物进入 finalize pipeline
- **WHEN** 后续新增 symbol 或 reason diagnostics
- **THEN** 系统 MUST 在 diagnostics 层扩展
- **THEN** façade 文件 SHALL NOT 再重新成为唯一 owner
