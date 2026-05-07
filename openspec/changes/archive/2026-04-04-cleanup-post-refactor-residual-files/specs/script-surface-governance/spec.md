## MODIFIED Requirements

### Requirement: 旧脚本与旧入口 MUST 显式标记退出条件
系统 MUST 为旧脚本、compat 入口和过渡 helper 显式标记退出条件。它们在正式替代路径落地后 MUST 进入清理清单。

#### Scenario: compat 脚本仍存在于仓库
- **WHEN** 某个 compat 脚本已不再承担正式主路径职责
- **THEN** 系统 MUST 将其标记为待删除残留对象
- **THEN** 后续 cleanup change MUST 将其纳入逐项核销清单
