## ADDED Requirements

### Requirement: cleanup 批次完成后必须复核文档漂移与主工作流
系统在完成一批残留清理后 MUST 重新执行最小系统审计，确认该批 cleanup 没有重新引入文档漂移、没有破坏正式主工作流、且已删除对象不再以低频 spec/test/comment 形式残留在正式主路径描述中。

#### Scenario: 删除一批前端 compat 文件
- **WHEN** 系统完成一批前端 compat 文件删除
- **THEN** cleanup 验收 MUST 复核桌面端主工作流是否仍可运行
- **THEN** cleanup 验收 MUST 复核前端主文档、相关 spec 和边界测试是否仍在描述已删除对象

#### Scenario: 清理一批主引擎 compat 合同读取面
- **WHEN** 系统完成一批执行边界 compat 读取面清理
- **THEN** cleanup 验收 MUST 复核主引擎正式合同面是否已与 spec 对齐
- **THEN** cleanup 验收 SHALL NOT 允许旧合同读取路径只从代码里删除、却继续残留在正式 spec 或测试断言中
