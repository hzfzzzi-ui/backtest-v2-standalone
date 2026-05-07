## MODIFIED Requirements

### Requirement: 配置工作区 MUST 归入 `config_workspace`
系统 MUST 将多阶段配置工作区正式归入 `config_workspace`。阶段式思路 MAY 保留，但具体 `S1-S9` 结构 SHALL NOT 被冻结为长期正式 UI 合同。

#### Scenario: 用户编辑配置
- **WHEN** 用户在桌面端编辑回测配置
- **THEN** 配置编辑、校验与预览 MUST 由 `config_workspace` 承担
- **THEN** 旧 stage rail 结构 MAY 作为迁移期交互存在，但 SHALL NOT 被定义为不可变正式结构
