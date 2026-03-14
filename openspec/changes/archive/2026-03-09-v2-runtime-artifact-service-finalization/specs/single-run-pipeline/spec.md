## MODIFIED Requirements

### Requirement: 单次回测公开路径必须由 thin wrapper 调用核心运行服务

单次回测公开路径 MUST 保持 `config_json -> compiler -> DataBundle -> stage pipeline -> artifacts` 主线不变，但 API 层 SHALL 通过核心运行服务进入该主线，而不是由 endpoint 文件直接承载主要编排。

#### Scenario: 同步运行路径
- **WHEN** 用户调用同步实验运行接口
- **THEN** endpoint SHALL 仅负责请求校验、调用 service 与响应包装

#### Scenario: 异步运行路径
- **WHEN** 用户调用异步实验运行接口
- **THEN** job 执行线程最终 SHALL 调用同一核心运行服务
- **THEN** 同步与异步路径不得分叉成两套执行编排
