## ADDED Requirements

### Requirement: 前端 SHALL 只暴露一个配置入口
前端 workbench MUST 只向用户暴露一个统一的“配置中心”入口，用于查看、加载、切换当前草稿、已保存配置、内置模板与锁定 candidate。系统 MUST NOT 在顶栏同时暴露多个平行配置入口。

#### Scenario: 顶栏只保留一个配置入口
- **WHEN** 用户打开工作台首页
- **THEN** 顶栏 SHALL 只显示一个配置入口用于进入配置中心
- **THEN** 顶栏 MUST NOT 同时出现“preset 下拉 + 快速加载”两个并列入口

#### Scenario: 配置中心展示来源分组
- **WHEN** 用户展开配置中心
- **THEN** 系统 SHALL 按“当前草稿、已保存配置、内置模板、candidate”进行分组展示
- **THEN** 每项 SHALL 显示可读名称、来源标签、锁定状态与最近保存时间或说明

### Requirement: 前端 SHALL 明确显示当前配置来源状态
前端 MUST 在运行区持续显示当前运行真相来自“草稿”、“已保存配置”、“内置模板”或“锁定 candidate”，并在草稿偏离已加载配置时明确标注脏状态。

#### Scenario: 已加载配置且未修改
- **WHEN** 用户从配置中心加载一份配置且未再编辑
- **THEN** 页面 SHALL 显示“已加载配置”为当前来源
- **THEN** 页面 SHALL 显示对应可读名称与来源标签

#### Scenario: 加载后草稿被修改
- **WHEN** 用户加载一份配置后继续编辑任意字段
- **THEN** 页面 SHALL 显示“草稿已偏离”
- **THEN** 页面 SHALL 明确说明后续运行将基于当前草稿而非原始已加载配置
