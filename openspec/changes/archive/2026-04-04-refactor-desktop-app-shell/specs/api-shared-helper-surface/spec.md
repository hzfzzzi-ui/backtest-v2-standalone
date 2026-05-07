## MODIFIED Requirements

### Requirement: UI 层 MUST 通过统一 API adapter 消费后端
桌面端和移动端 UI 层 MUST 通过统一 API adapter / data service 消费后端接口。UI 组件 SHALL NOT 直接 `fetch` 后端，也 SHALL NOT 自行定义 config/runtime 真相。

#### Scenario: 结果工作区加载实验数据
- **WHEN** 结果工作区需要加载实验数据
- **THEN** 它 MUST 通过统一 API adapter 或由 `run_orchestration` hydrate 的状态读取结果
- **THEN** 它 SHALL NOT 直接在 UI 组件内部发起正式 API 请求
