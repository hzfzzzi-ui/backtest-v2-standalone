## ADDED Requirements

### Requirement: 桌面主路径必须优先消费 manifest、surface 与 section 接口
系统 MUST 让桌面研究页主路径优先使用 `manifest`、`surface`、`surface/{section}` 与少量专用接口。桌面研究页的正常结果读取 SHALL NOT 继续依赖通用 `/api/backtest_v2/artifacts/read`。

#### Scenario: 桌面页加载实验结果
- **WHEN** 桌面研究页加载某个实验的结果工作台
- **THEN** 系统 MUST 先读取该实验的 `manifest`
- **THEN** 系统 MUST 再读取 `surface` 与按需的 `surface/{section}`

#### Scenario: 桌面页渲染结果区
- **WHEN** 前端主路径需要渲染 KPI、图表、阶段漏斗、交易明细或个股表现
- **THEN** 系统 SHALL 通过统一结果面或专用 section 获取数据
- **THEN** 前端 SHALL NOT 通过 `/api/backtest_v2/artifacts/read` 直接读取底层 artifact 文件

### Requirement: 通用 artifact 读取接口必须退出桌面主路径
系统 MAY 保留通用 artifact 读取接口用于极少量运维、调试或迁移工具，但桌面研究页的主交互路径 MUST 不再把该接口当作正常读取面。

#### Scenario: 主交互路径调用 artifact 读取
- **WHEN** 桌面研究页的主路径触发实验加载、baseline 加载或结果刷新
- **THEN** 这些调用 MUST 不再依赖通用 artifact 读取接口

#### Scenario: 调试工具读取 artifact
- **WHEN** 运维、迁移脚本或显式调试工具需要读取物理 artifact
- **THEN** 系统 MAY 继续提供受限的通用读取能力
- **THEN** 该能力 SHALL NOT 重新回流到桌面研究页主路径
