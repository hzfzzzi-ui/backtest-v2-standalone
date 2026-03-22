## ADDED Requirements

### Requirement: backtest_v2 API 包必须将运行编排下沉为应用服务
系统 MUST 将 `backend/api/backtest_v2` 继续限制为公共路由、请求契约、响应适配和边界校验层。可复用的运行编排、snapshot 组装、实验真相构建和基线附加逻辑 MUST 下沉到 `backend/core/services` 或 `backend/core/tools`。

#### Scenario: 新增运行准备逻辑
- **WHEN** 系统需要新增运行前编排、runtime snapshot 构建或实验结果真相组装逻辑
- **THEN** 该逻辑 MUST 进入 `core.services` 或 `core.tools`
- **THEN** `backend/api/backtest_v2` SHALL NOT 继续吸收该实现作为长期宿主

#### Scenario: 公共路由继续存在
- **WHEN** 内部实现被下沉或拆分
- **THEN** 对外公共路由路径、请求契约和基础响应语义 MUST 保持稳定
- **THEN** 客户端 SHALL NOT 因内部模块迁移而被迫改动
