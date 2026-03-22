## MODIFIED Requirements

### Requirement: 系统必须提供新的 backtest 和 mobile API 边界
系统 MUST 提供 `backend/api/backtest_v2/*`、`backend/api/mobile/*` 和必要的共享 helper 作为唯一正式 API 边界。旧 `backend/api/endpoints/*` 文件结构与其 path 兼容层 SHALL NOT 再作为长期要求保留。

#### Scenario: 主应用挂载正式 API 边界
- **WHEN** 系统启动并挂载 backtest、mobile 或 transactions 相关路由
- **THEN** 主应用 MUST 只从正式 API 目录挂载这些路由
- **THEN** 系统 SHALL NOT 要求继续保留 `backend/api/endpoints/*` 作为主路径或 path 兼容层

#### Scenario: 清理旧 endpoints 载体
- **WHEN** 旧 `backend/api/endpoints/*` 文件只承担历史兼容或转发作用
- **THEN** 这些文件 MUST 可以被直接删除
- **THEN** 删除动作 SHALL NOT 被旧 path 兼容要求阻止

### Requirement: 桌面主路径必须优先消费 manifest、surface 与 section 接口
系统 MUST 让桌面研究页主路径只消费 `manifest`、`surface`、`surface/{section}` 和少量明确语义的专用接口。桌面研究页正常结果读取 SHALL NOT 继续依赖通用 `/api/backtest_v2/artifacts/read`。

#### Scenario: 桌面页加载实验结果
- **WHEN** 桌面研究页加载某个实验的结果工作台
- **THEN** 系统 MUST 先读取该实验的 `manifest`
- **THEN** 系统 MUST 再读取 `surface` 与按需的 `surface/{section}`

#### Scenario: 桌面页渲染结果区
- **WHEN** 前端主路径需要渲染 KPI、图表、阶段漏斗、交易明细或个股表现
- **THEN** 系统 SHALL 通过统一结果面或专用 section 获取数据
- **THEN** 前端 SHALL NOT 通过 `/api/backtest_v2/artifacts/read` 直接读取底层 artifact 文件

## REMOVED Requirements

### Requirement: 通用 artifact 读取接口必须退出桌面主路径
**Reason**: 该接口仍会让前端理解底层 artifact 物理布局，继续阻碍多资产扩展与结果面单 owner 收口。
**Migration**: 桌面主路径统一迁移到 `manifest`、`surface`、`surface/{section}` 和少量专用接口；运维和迁移工具如仍需读取物理 artifact，应迁到独立 tooling，不再作为正式 HTTP contract。

