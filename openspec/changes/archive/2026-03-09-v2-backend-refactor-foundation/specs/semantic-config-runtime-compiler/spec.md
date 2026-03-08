## ADDED Requirements

### Requirement: 前端语义配置必须是唯一执行输入
系统 SHALL 只接受前端语义 `config_json` 作为公开运行入口的执行真相。

#### Scenario: 使用语义配置运行
- **WHEN** 前端或脚本发起一次新的回测运行
- **THEN** 请求体 SHALL 包含一份 `config_json`
- **THEN** 后端 SHALL 仅基于该 `config_json` 生成运行时配置

#### Scenario: 旧字段仅作为兼容来源
- **WHEN** 请求中同时出现 `config_id`、`preset`、`workbench_config`、`runtime_config_json` 或 `config_path`
- **THEN** 这些字段 SHALL 仅用于兼容适配或 provenance 记录
- **THEN** 它们 SHALL NOT 与 `config_json` 并行争夺执行真相

### Requirement: 编译器必须执行严格字段校验
系统 SHALL 对前端语义 `config_json` 执行严格 schema 校验，并拒绝未知字段或非法字段组合。

#### Scenario: 未知字段被拒绝
- **WHEN** `config_json` 包含未声明字段
- **THEN** 编译器 SHALL 返回明确的校验错误
- **THEN** 系统 SHALL NOT 启动回测执行

#### Scenario: 非法字段组合被拒绝
- **WHEN** `config_json` 中存在互斥配置同时开启或缺失必要字段
- **THEN** 编译器 SHALL 返回结构化错误
- **THEN** 错误响应 SHALL 指向具体字段路径

### Requirement: 编译过程必须输出三层配置快照
系统 SHALL 在实验目录中同时保存 `input_config.json`、`resolved_config.json` 和 `compiled_plan.json`。

#### Scenario: 成功编译写盘
- **WHEN** 一次回测编译成功
- **THEN** 实验目录 SHALL 包含前端原始语义配置快照 `input_config.json`
- **THEN** 实验目录 SHALL 包含规范化后的 `resolved_config.json`
- **THEN** 实验目录 SHALL 包含仅供执行层消费的 `compiled_plan.json`

### Requirement: 预览与正式运行必须共享同一编译器
系统 SHALL 要求 execution preview 与正式回测运行使用同一个配置编译器实现。

#### Scenario: 同配置预览与运行
- **WHEN** 同一份 `config_json` 先执行 preview 再执行正式运行
- **THEN** 两者 SHALL 生成语义一致的 `resolved_config.json`
- **THEN** 两者 SHALL 生成语义一致的 `compiled_plan.json`

### Requirement: 编译器必须记录配置来源与内容标识
系统 SHALL 为每次编译生成稳定的配置来源元信息和内容标识，便于回放与审计。

#### Scenario: 生成配置标识
- **WHEN** 编译器完成 `config_json` 处理
- **THEN** `resolved_config.json` 或 `run_meta.json` SHALL 包含 `schema_version`、`config_hash` 和 `config_source`
- **THEN** `config_source` SHALL 明确表示该次运行来自前端语义配置而非旧入口
