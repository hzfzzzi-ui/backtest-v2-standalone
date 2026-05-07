## ADDED Requirements

### Requirement: 残留清理 MUST 以正式替代路径落地为前提
系统 MUST 仅在正式替代路径已经落地并通过回归后，才允许删除旧壳、旧 bridge、compat 入口、旧文档和空目录。

#### Scenario: 删除一个旧桌面壳文件
- **WHEN** 系统准备删除某个旧桌面壳文件
- **THEN** 必须先确认新 desktop app 已成为正式宿主
- **THEN** 必须先确认文档主入口已不再指向该旧文件

### Requirement: 残留清理 MUST 提供回退清单
系统 MUST 为每一批残留清理提供可执行的回退清单。

#### Scenario: 某批残留清理后出现回归
- **WHEN** 删除某批残留对象后出现主工作流回归
- **THEN** 系统 MUST 能根据回退清单恢复该批删除对象
- **THEN** 回退清单 SHALL NOT 依赖隐含记忆或临时人工判断
