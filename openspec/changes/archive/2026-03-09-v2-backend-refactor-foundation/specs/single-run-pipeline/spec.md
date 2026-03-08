## MODIFIED Requirements

### Requirement: API 请求模型包含单一语义配置字段
公开运行入口的请求模型 SHALL 以 `config_json` 作为唯一执行输入字段，并将其他历史字段降级为兼容或来源记录字段。

#### Scenario: 请求携带语义配置
- **WHEN** HTTP POST 运行请求 body 包含合法的 `config_json`
- **THEN** 请求验证 SHALL 通过
- **THEN** 后端 SHALL 使用该 `config_json` 进入统一编译与执行流程

#### Scenario: 请求缺失语义配置
- **WHEN** HTTP POST 运行请求 body 未包含 `config_json`
- **THEN** 请求验证 SHALL 失败
- **THEN** 系统 SHALL 返回缺失执行真相的明确错误

#### Scenario: 请求同时携带历史字段
- **WHEN** HTTP POST 运行请求 body 同时包含 `config_json` 和 `config_id`、`preset`、`runtime_config_json`、`workbench_config` 或 `config_path`
- **THEN** 编译器 SHALL 仅以 `config_json` 作为执行真相
- **THEN** 其他字段 SHALL 仅用于兼容或 provenance 记录

## ADDED Requirements

### Requirement: 单次运行的公开标识必须为 experiment_id
公开运行接口 SHALL 以 `experiment_id` 作为单次运行的唯一公开标识。

#### Scenario: 成功启动运行
- **WHEN** 一次回测运行成功进入实验目录写盘阶段
- **THEN** 系统 SHALL 返回 `experiment_id`
- **THEN** 前端 SHALL 通过该 `experiment_id` 读取实验目录中的标准产物

#### Scenario: 存在内部任务状态
- **WHEN** 系统内部仍保留异步任务状态或 `job_id`
- **THEN** `experiment_id` 仍 SHALL 是公开结果面的主标识
- **THEN** 内部任务标识 SHALL NOT 取代 `experiment_id` 成为前端主要消费字段
