## ADDED Requirements

### Requirement: 资产范围切换必须同时驱动全局控制与资产特化抽屉
桌面研究台 MUST 让 `asset_scope` 切换同时驱动两类 UI 边界：
- 顶部全局控制层中的资产摘要与时间/状态语义
- 左侧资产特化抽屉中的配置模块与文案

系统 SHALL NOT 再把 `asset_scope` 仅视为数据上下文切换，而不改变前端结构与模块语义。

#### Scenario: 从 A股个股切换到 A股ETF
- **WHEN** 用户将 `asset_scope` 从 `cn_a_equity` 切换到 `cn_etf`
- **THEN** 顶部全局控制层 MUST 更新资产摘要但保持同一公共控制结构
- **THEN** 左侧抽屉 MUST 切换为 ETF 特化配置而不是继续展示股票特化配置

### Requirement: 顶部全局控制与左侧资产特化抽屉不得互相伪装
桌面研究台 MUST 保持“顶层公共控制”和“左侧资产特化配置”的职责分离。全局控制字段 SHALL NOT 被复制成资产特化抽屉的默认编辑项，资产特化字段 SHALL NOT 被上移为顶层通用真相。

#### Scenario: Governor 字段不再混入资产特化抽屉
- **WHEN** 用户浏览股票 alpha 或 ETF beta 配置
- **THEN** 页面 MUST 将 Governor 视为顶层公共控制的一部分
- **THEN** 资产特化抽屉 SHALL NOT 把 Governor 当成局部参数重新暴露为主配置
