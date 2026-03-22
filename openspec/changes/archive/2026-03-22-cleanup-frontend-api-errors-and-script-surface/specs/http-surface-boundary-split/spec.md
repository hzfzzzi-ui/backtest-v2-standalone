## ADDED Requirements

### Requirement: 旧 endpoints 目录必须退化为薄 shim
系统 MUST 将 `backend/api/endpoints/*` 退化为 path 兼容用的薄 shim。旧目录 SHALL NOT 继续承载重型实现、新的编排逻辑或新的领域规则。

#### Scenario: 旧 path 继续可用
- **WHEN** 客户端继续访问旧 HTTP path
- **THEN** 系统 MUST 保持 path 兼容
- **THEN** 旧 `endpoints/*` 文件内部 SHALL 仅执行薄转发或兼容映射

#### Scenario: 新增 API 行为
- **WHEN** 需要新增或调整 API 行为
- **THEN** 实现 MUST 落在 `backend/api/backtest_v2/*` 或 `backend/api/mobile/*`
- **THEN** 旧 `endpoints/*` SHALL NOT 成为新行为的正式落点

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
