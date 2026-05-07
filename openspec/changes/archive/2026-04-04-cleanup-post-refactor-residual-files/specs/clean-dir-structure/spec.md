## MODIFIED Requirements

### Requirement: 目录清理 MUST 服务正式边界收口
系统 MUST 将目录清理视为正式边界收口的一部分，而不是独立的表面整理动作。

#### Scenario: 清理空目录与旧附录
- **WHEN** 系统发现某目录为空，或旧附录已被新文档完全吸收
- **THEN** 该目录或附录 MAY 被清理
- **THEN** 清理前 MUST 先确认没有正式入口继续指向它
