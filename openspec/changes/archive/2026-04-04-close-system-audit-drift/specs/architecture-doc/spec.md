## ADDED Requirements

### Requirement: 主架构文档必须显式标记已完成边界与 compat 现状
系统与数据库/前端主文档在描述重构后现状时 MUST 显式区分“已完成正式接管”的边界与“仍依赖 compat/过渡路径”的边界。文档 SHALL NOT 把仍在主装载链、主读取链或主写入链中的 compat 结构写成已经完全退出。

#### Scenario: 前端仍保留旧 bootstrap
- **WHEN** 桌面端仍在主装载链中保留旧 bootstrap 或 compat 宿主脚本
- **THEN** 前端架构文档 MUST 明确该结构仍处于 compat 过渡阶段
- **THEN** 文档 SHALL NOT 直接把前端宿主切换写成已彻底完成

#### Scenario: 事务域主写入已切到数据库
- **WHEN** 事务域对象已经切换到 DB 主读写而文件路径仅作为 compat 回退
- **THEN** 数据库主文档 MUST 明确 DB 已成为正式主真相路径
- **THEN** 文档 SHALL NOT 继续把 `outputs/mobile_ops/*` 或 `outputs/ops/sim_account/*` 描述为主要真相层
