# http-surface-boundary-split Specification

## Purpose
定义桌面与移动端 HTTP surface 的正式边界，确保结果读取统一收敛到 `manifest`、`surface` 与按需 `surface/{section}`，并让实验级资产上下文成为稳定输出的一部分。
## Requirements
### Requirement: 系统必须提供新的 backtest 和 mobile API 边界
系统 MUST 提供新的 `backend/api/backtest_v2/*` 和 `backend/api/mobile/*` 作为正式 API 边界。旧 `backend/api/endpoints/*` 文件结构可以删除，但旧 HTTP path MUST 保持兼容。

系统 MUST 提供 `backend/api/backtest_v2/*`、`backend/api/mobile/*` 和必要的共享 helper 作为唯一正式 API 边界。旧 `backend/api/endpoints/*` 文件结构与其 path 兼容层 SHALL NOT 再作为长期要求保留。

#### Scenario: 旧 path 请求继续可用
- **WHEN** 客户端继续调用既有 backtest HTTP path
- **THEN** 系统 MUST 返回与新边界一致的响应语义
- **THEN** 客户端 SHALL NOT 因文件结构迁移而被迫切换 path

#### Scenario: 新边界接管旧实现
- **WHEN** 新目录结构稳定并开始承担正式实现
- **THEN** 旧 `backend/api/endpoints/*` 文件实现 MAY 被删除
- **THEN** 系统 MUST 保持 path 兼容和主要用户可见行为兼容

#### Scenario: 主应用挂载正式 API 边界
- **WHEN** 系统启动并挂载 backtest、mobile 或 transactions 相关路由
- **THEN** 主应用 MUST 只从正式 API 目录挂载这些路由
- **THEN** 系统 SHALL NOT 要求继续保留 `backend/api/endpoints/*` 作为主路径或 path 兼容层

#### Scenario: 清理旧 endpoints 载体
- **WHEN** 旧 `backend/api/endpoints/*` 文件只承担历史兼容或转发作用
- **THEN** 这些文件 MUST 可以被直接删除
- **THEN** 删除动作 SHALL NOT 被旧 path 兼容要求阻止### Requirement: 历史实验接口必须返回 manifest 加最小绩效摘要
系统 MUST 将历史实验列表和加载弹窗统一为 `manifest + 少量 perf 摘要`。该接口 SHALL NOT 直接内联完整 `ExperimentSurface`。

#### Scenario: 历史实验列表展示对比信息
- **WHEN** 客户端请求历史实验列表
- **THEN** 系统 MUST 返回实验身份信息和最小绩效摘要
- **THEN** 最小绩效摘要 MUST 足以支持列表级比较，但 SHALL NOT 包含完整 `nav` 或 `symbol_stats`

#### Scenario: 客户端切换到实验详情
- **WHEN** 用户从历史列表进入具体实验
- **THEN** 客户端 SHALL 再按需读取主 surface 和懒加载子面
- **THEN** 系统 SHALL 保持列表接口和详情接口职责分离

### Requirement: 移动只读接口必须基于 surface 派生摘要对象
系统 MUST 为移动端提供基于 `ExperimentSurface` 派生的只读摘要对象。移动只读接口 SHALL 复用统一结果语义，但 SHALL NOT 暴露完整桌面工作台数据面。

#### Scenario: 移动端查看实验摘要
- **WHEN** 移动端请求移动摘要接口
- **THEN** 系统 MUST 从统一结果面派生摘要对象
- **THEN** 摘要对象 MUST 保留统一的 `summary`、`perf`、`audit` 语义

#### Scenario: 移动端不需要桌面重型字段
- **WHEN** 移动端未请求桌面重型字段
- **THEN** 系统 SHALL NOT 返回完整 `nav`、`symbol_stats` 或 `stage_funnel`
- **THEN** 移动端接口 MUST 保持薄读模型

### Requirement: 桌面主路径必须优先消费 manifest、surface 与 section 接口
系统 MUST 让桌面研究页主路径优先使用 `manifest`、`surface`、`surface/{section}` 与少量专用接口。桌面研究页的正常结果读取 SHALL NOT 继续依赖通用 `/api/backtest_v2/artifacts/read`。

系统 MUST 让桌面研究页主路径只消费 `manifest`、`surface`、`surface/{section}` 和少量明确语义的专用接口。桌面研究页正常结果读取 SHALL NOT 继续依赖通用 `/api/backtest_v2/artifacts/read`。

#### Scenario: 桌面页加载实验结果
- **WHEN** 桌面研究页加载某个实验的结果工作台
- **THEN** 系统 MUST 先读取该实验的 `manifest`
- **THEN** 系统 MUST 再读取 `surface` 与按需的 `surface/{section}`

#### Scenario: 桌面页渲染结果区
- **WHEN** 前端主路径需要渲染 KPI、图表、阶段漏斗、交易明细或个股表现
- **THEN** 系统 SHALL 通过统一结果面或专用 section 获取数据
- **THEN** 前端 SHALL NOT 通过 `/api/backtest_v2/artifacts/read` 直接读取底层 artifact 文件### Requirement: 通用 artifact 读取接口必须退出桌面主路径
系统 MAY 保留通用 artifact 读取接口用于极少量运维、调试或迁移工具，但桌面研究页的主交互路径 MUST 不再把该接口当作正常读取面。

#### Scenario: 主交互路径调用 artifact 读取
- **WHEN** 桌面研究页的主路径触发实验加载、baseline 加载或结果刷新
- **THEN** 这些调用 MUST 不再依赖通用 artifact 读取接口

#### Scenario: 调试工具读取 artifact
- **WHEN** 运维、迁移脚本或显式调试工具需要读取物理 artifact
- **THEN** 系统 MAY 继续提供受限的通用读取能力
- **THEN** 该能力 SHALL NOT 重新回流到桌面研究页主路径

### Requirement: backtest 主 HTTP surface 必须暴露实验级资产上下文
系统 MUST 在实验列表、manifest、surface 和相关摘要接口中返回实验级薄资产上下文，以便桌面端和移动端在不解析底层配置的前提下识别结果所属资产边界。

#### Scenario: 历史实验列表显示资产归属
- **WHEN** 客户端请求历史实验列表
- **THEN** 列表项 MUST 返回实验级薄资产上下文
- **THEN** 列表接口 SHALL NOT 要求前端重新读取底层 config 才能判断资产归属

#### Scenario: 读取单个实验结果
- **WHEN** 客户端请求某个实验的 manifest 或 surface
- **THEN** 响应 MUST 包含与该实验一致的资产上下文摘要
- **THEN** HTTP surface SHALL 对桌面端和移动端保持统一语义

### Requirement: 配置与运行入口必须显式拒绝未知 asset scope
系统 MUST 对 HTTP 层收到的未知或未正式支持的 `asset_scope` 进行显式校验失败，而 SHALL NOT 静默回退到当前 A 股 profile。

#### Scenario: 提交未知资产范围
- **WHEN** 客户端提交未知 `asset_scope`
- **THEN** HTTP 层 MUST 返回明确的 validation error
- **THEN** 系统 SHALL NOT 默认将其解释成 A 股运行

### Requirement: 桌面 HTTP surface 必须暴露最近一周资金不足拦截明细
系统 MUST 在实验 `surface` 中暴露 `cash_blocked_buys_recent` section，使桌面端和诊断工具可以通过统一 `surface/{section}` 读取最近 5 个交易日内的资金不足拦截买入明细。客户端 SHALL NOT 通过底层 artifact 路径自行推断该信息。

#### Scenario: 客户端请求资金不足拦截明细
- **WHEN** 客户端请求 `/api/backtest_v2/experiments/{id}/surface/cash_blocked_buys_recent`
- **THEN** 系统 MUST 返回最近 5 个交易日内的资金不足拦截明细列表
- **THEN** 每条记录 MUST 至少包含 `date`、`symbol`、`cash_available`、`estimated_qty`、`estimated_amount`

#### Scenario: 实验没有资金不足拦截记录
- **WHEN** 对应实验最近 5 个交易日没有 `SKIP_NO_CASH` 明细
- **THEN** 系统 MUST 返回空列表
- **THEN** `surface` 的 lazy section 元数据 MUST 标记该 section 可用

### Requirement: 旧 endpoints 目录必须退化为薄 shim
系统 MUST 将 `backend/api/endpoints/*` 退化为 path 兼容用的薄 shim。旧目录 SHALL NOT 继续承载重型实现、新的编排逻辑或新的领域规则。

系统 MUST 将 `backend/api/endpoints/*` 退化为 path 兼容用的薄 shim。旧目录 SHALL NOT 继续承载重型实现、新的编排逻辑或新的领域规则。

#### Scenario: 旧 path 继续可用
- **WHEN** 客户端继续访问旧 HTTP path
- **THEN** 系统 MUST 保持 path 兼容
- **THEN** 旧 `endpoints/*` 文件内部 SHALL 仅执行薄转发或兼容映射

#### Scenario: 新增 API 行为
- **WHEN** 需要新增或调整 API 行为
- **THEN** 实现 MUST 落在 `backend/api/backtest_v2/*` 或 `backend/api/mobile/*`
- **THEN** 旧 `endpoints/*` SHALL NOT 成为新行为的正式落点### Requirement: 新实现不得反向依赖 compat 模块
系统 MUST 逐步移除新实现对 compat 模块的反向 import。新目录下的正式实现 SHALL NOT 通过回跳 `backend/api/endpoints/*` 获取核心行为。

#### Scenario: mobile 或 backtest 新实现读取能力
- **WHEN** 新 API 目录中的实现需要复用能力
- **THEN** 它 MUST 复用 service、contract 或新目录内的路由实现
- **THEN** 它 SHALL NOT 反向 import compat module 以取得核心数据

#### Scenario: 兼容实现仍需要保留
- **WHEN** 某个 compat 模块尚未删除
- **THEN** 它 MAY 依赖新实现
- **THEN** 依赖方向 SHALL NOT 反过来

### Requirement: 新实现不得反向依赖 compat 模块
系统 MUST 逐步移除新实现对 compat 模块的反向 import。新目录下的正式实现 SHALL NOT 通过回跳 `backend/api/endpoints/*` 获取核心行为。

#### Scenario: mobile 或 backtest 新实现读取能力
- **WHEN** 新 API 目录中的实现需要复用能力
- **THEN** 它 MUST 复用 service、contract 或新目录内的路由实现
- **THEN** 它 SHALL NOT 反向 import compat module 以取得核心数据

#### Scenario: 兼容实现仍需要保留
- **WHEN** 某个 compat 模块尚未删除
- **THEN** 它 MAY 依赖新实现
- **THEN** 依赖方向 SHALL NOT 反过来
