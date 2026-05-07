## MODIFIED Requirements

### Requirement: V2 runtime compatibility MUST 仅作为迁移期兼容层
系统 MUST 保留 `v2` canonical 之上的 runtime compatibility 层，用于旧 baseline 与旧脚本的迁移期兼容，但 runtime compatibility SHALL NOT 再被定义为长期正式默认市场数据消费层。compat 层 MUST 明确表达其消费的 canonical 状态、字段来源与可置信范围，并继续与正式 `canonical_market` 入口区分。

#### Scenario: 旧 baseline 迁移使用 compat
- **WHEN** 旧 baseline 或旧脚本显式指定使用 compat 入口
- **THEN** 系统 MAY 读取 runtime compatibility 层
- **THEN** 运行产物 MUST 明确记录其为迁移期 compat 消费，而非正式默认入口

#### Scenario: 新默认入口不再落到 compat
- **WHEN** 用户继续使用当前正式默认运行配置
- **THEN** 系统 MUST 以 `canonical_market` 作为正式默认市场数据入口
- **THEN** 系统 SHALL NOT 把 runtime compatibility 层作为长期正式默认消费层
