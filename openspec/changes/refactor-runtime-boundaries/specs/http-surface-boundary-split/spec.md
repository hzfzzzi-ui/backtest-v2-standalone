## ADDED Requirements

### Requirement: 系统必须提供新的 backtest 和 mobile API 边界
系统 MUST 提供新的 `backend/api/backtest_v2/*` 和 `backend/api/mobile/*` 作为正式 API 边界。旧 `backend/api/endpoints/*` 文件结构可以删除，但旧 HTTP path MUST 保持兼容。

#### Scenario: 旧 path 请求继续可用
- **WHEN** 客户端继续调用既有 backtest HTTP path
- **THEN** 系统 MUST 返回与新边界一致的响应语义
- **THEN** 客户端 SHALL NOT 因文件结构迁移而被迫切换 path

#### Scenario: 新边界接管旧实现
- **WHEN** 新目录结构稳定并开始承担正式实现
- **THEN** 旧 `backend/api/endpoints/*` 文件实现 MAY 被删除
- **THEN** 系统 MUST 保持 path 兼容和主要用户可见行为兼容

### Requirement: 历史实验接口必须返回 manifest 加最小绩效摘要
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
