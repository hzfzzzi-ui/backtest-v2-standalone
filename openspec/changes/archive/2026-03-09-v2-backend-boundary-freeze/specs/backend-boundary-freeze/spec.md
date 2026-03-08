## ADDED Requirements

### Requirement: 公开后端边界必须严格冻结
系统 SHALL 为公开回测运行、执行预览、产物读取提供严格的 request contract，并且 MUST 拒绝未声明字段。对非 locked candidate 的公开运行，请求真相 MUST 只来自 `config_json`；公开产物读取 MUST 只接受 `exp_id + manifest declared rel_path`。

#### Scenario: 公开运行拒绝 legacy 配置字段
- **WHEN** 客户端向 `/api/backtest_v2/experiment/run` 或 `/run_async` 发送 `config_id`、`runtime_config_json`、`workbench_config`、`results_dir` 等未声明字段
- **THEN** 系统拒绝请求，且不会把这些字段作为公开配置真相

#### Scenario: 公开产物读取不再接受 results_dir
- **WHEN** 客户端调用公开 `artifacts/read` 但缺少 `exp_id`，或者试图用 `results_dir` 读取实验目录
- **THEN** 系统拒绝该调用，并要求通过 `experiment_id + manifest` 访问产物

### Requirement: 四个后端冻结面必须模块化归属
系统 SHALL 把公开 API、foundation shell、数据库访问、审计归一化分别收敛到专属边界模块；公开路由与产物写盘 MUST 通过这些边界模块协作，而不是继续直接依赖 legacy provider/adapter 细节。

#### Scenario: 路由不再直接实例化 provider
- **WHEN** 公开 benchmark、symbol、validate_data 路由需要数据库访问
- **THEN** 它们通过共享数据库边界模块获取 provider 与 runtime universe 解析结果，而不是各自直接创建 `PostgresDataProvider`

#### Scenario: 审计写盘来自共享契约
- **WHEN** foundation shell 产出阶段摘要并由 artifact stabilize 写入 `audit.json`
- **THEN** 两侧使用同一套审计 contract helper 归一化 `stage_summary`、`stage_pipeline` 与 `audit`
