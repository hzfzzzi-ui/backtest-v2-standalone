## ADDED Requirements

### Requirement: runtime service 必须支持 unified runtime 多 sleeve 实验
核心 runtime service MUST 支持单次实验请求同时运行 `cn_stock_trend_alpha_core` 与 `cn_etf_beta`。该服务 MUST 负责统一编排配置编译结果、两条 sleeve 的执行、Governor 预算裁决和组合级产物汇总，而不是要求调用方拆成两次实验。

#### Scenario: API 发起 unified runtime
- **WHEN** 客户端提交启用股票 alpha 与 ETF beta 的 governed A股请求
- **THEN** runtime service MUST 在一次调用内完成两条 sleeve 的运行编排
- **THEN** runtime service MUST 返回单一实验 ID 与统一 results_dir

#### Scenario: 单 sleeve 请求保持兼容
- **WHEN** 客户端提交旧的单 sleeve 请求
- **THEN** runtime service MUST 继续按当前单实验路径运行
- **THEN** unified runtime 支持 SHALL NOT 破坏既有实验入口
