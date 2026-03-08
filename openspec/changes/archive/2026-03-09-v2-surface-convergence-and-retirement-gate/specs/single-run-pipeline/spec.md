## ADDED Requirements

### Requirement: 公开 run 与 preview 共享同一语义编译链
公开单次回测运行接口与执行 preview 接口 MUST 共享同一条语义配置编译链。  
对于同一份 `config_json`，两条路径 SHALL 产生一致的 `resolved_config_hash` 与等价的 `compiled_plan` 语义。

#### Scenario: 相同 `config_json` 同时用于 run 与 preview
- **WHEN** 客户端用同一份 `config_json` 分别调用公开 run 与 preview
- **THEN** 系统 SHALL 生成一致的 `resolved_config_hash`
- **THEN** 实验目录中的 `input_config.json`、`resolved_config.json`、`compiled_plan.json` SHALL 与 preview 返回的编译摘要一致

#### Scenario: preview 请求混入旧配置来源
- **WHEN** 客户端向 preview 接口提交 `config_id`、`runtime_config_json`、`workbench_config` 或 `config_path`
- **THEN** 系统 SHALL 按公开表面规则显式拒绝该请求，而不是回退到旧配置治理路径

### Requirement: 单次运行公开响应以 `experiment_id` 为主结果
公开单次运行成功后，系统 SHALL 将 `experiment_id` 作为主要结果锚点返回。  
后续实验读取、历史加载、产物获取与结果渲染 SHALL 可仅基于 `experiment_id` 完成。

#### Scenario: 同步运行成功
- **WHEN** 客户端调用同步运行接口且实验成功落盘
- **THEN** 响应 SHALL 包含 `experiment_id`
- **THEN** 调用方 SHALL 无需依赖 `results_dir` 才能继续读取实验产物

#### Scenario: 异步运行完成
- **WHEN** 客户端调用异步运行接口并在任务完成后获取最终结果
- **THEN** 最终结果 payload SHALL 包含 `experiment_id`
- **THEN** 该 `experiment_id` SHALL 可直接用于 manifest 与 artifact 读取入口
