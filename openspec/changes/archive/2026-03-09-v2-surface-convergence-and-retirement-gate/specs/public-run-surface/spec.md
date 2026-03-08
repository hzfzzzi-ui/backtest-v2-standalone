## ADDED Requirements

### Requirement: 公开运行与 preview 只接受语义 `config_json`
系统公开暴露的单次回测运行接口与执行 preview 接口 MUST 只接受前端语义 `config_json` 作为配置输入真相。  
`config_id`、`runtime_config_json`、`workbench_config`、`config_path` 等历史配置变异字段 SHALL NOT 再参与公开请求的配置解析。

#### Scenario: 公开运行请求携带合法 `config_json`
- **WHEN** 客户端向公开运行接口提交一个通过 schema 校验的 `config_json`
- **THEN** 系统 SHALL 以 `config_json` 作为唯一配置来源进入编译与执行主链

#### Scenario: 公开运行请求混入历史配置变异字段
- **WHEN** 客户端向公开运行或 preview 接口同时提交 `config_json` 与 `config_id`、`runtime_config_json`、`workbench_config`、`config_path` 中任一字段
- **THEN** 系统 SHALL 返回 400，并显式指出被拒绝的历史字段名

#### Scenario: 公开运行请求缺少 `config_json`
- **WHEN** 客户端向公开运行接口提交请求但未提供 `config_json`
- **THEN** 系统 SHALL 返回 400，并提示公开运行接口必须提供语义配置 JSON

### Requirement: 公开实验读取入口以 `experiment_id` 为唯一锚点
系统 MUST 提供基于 `experiment_id` 的公开实验读取入口，用于读取 `manifest.json` 和 manifest 中声明的标准产物。  
公开消费流程 SHALL NOT 要求前端或脚本传入 `results_dir`。

#### Scenario: 按 `experiment_id` 读取 manifest
- **WHEN** 客户端请求某个已存在实验的 manifest
- **THEN** 系统 SHALL 返回该实验目录中的 `manifest.json`

#### Scenario: 按 `experiment_id` 读取 manifest 中声明的产物
- **WHEN** 客户端请求某个实验且产物路径存在于该实验 manifest 的标准产物或可选导出物列表中
- **THEN** 系统 SHALL 返回对应产物内容，而不要求调用方提供绝对目录路径

#### Scenario: 请求 manifest 未声明的产物
- **WHEN** 客户端尝试读取某个实验目录中未被 manifest 声明的相对路径
- **THEN** 系统 SHALL 返回 400 或 404，而不是透传任意文件读取能力
