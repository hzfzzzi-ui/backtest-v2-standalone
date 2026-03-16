## ADDED Requirements

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
