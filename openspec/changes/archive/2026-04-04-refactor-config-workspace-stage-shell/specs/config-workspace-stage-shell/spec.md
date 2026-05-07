## ADDED Requirements

### Requirement: config_workspace 拥有正式阶段目录
系统 SHALL 为 `config_workspace` 定义正式的主阶段目录与高级阶段目录，并将主阶段限制为高频核心配置入口。

#### Scenario: 主阶段只包含高频核心入口
- **WHEN** 用户进入配置工作区第一层
- **THEN** 系统 MUST 仅展示高频核心阶段入口

### Requirement: 阶段抽屉必须提供极简中文说明
系统 SHALL 为每个正式阶段提供极简中文的抽屉标题与用途说明，帮助用户理解当前配置区的含义。

#### Scenario: 切换阶段时说明同步变化
- **WHEN** 用户切换配置阶段
- **THEN** 系统 MUST 同步展示该阶段的标题与用途说明
