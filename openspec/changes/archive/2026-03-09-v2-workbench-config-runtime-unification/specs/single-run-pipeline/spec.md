## MODIFIED Requirements

### Requirement: API 请求模型包含选股排序字段
`BacktestV2ExperimentRequest` Pydantic 模型 SHALL 包含以下可选字段：
- `enable_strength_rank: bool | None`
- `strength_ma: int | None`
- `strength_top_k_mode: str | None`
- `enable_multifactor_rank: bool | None`
- `mf_topk: int | None`

同时，单次运行与执行预览的请求语义 MUST 服从“单一运行真相”规则：
- 请求 SHALL 提交一份 resolved runtime config json 作为唯一编译输入
- `config_id` 若存在 SHALL 仅作为 provenance
- 后端 MUST NOT 再以 `config_id` 静默覆盖已提交的 runtime config json

#### Scenario: API 请求携带选股字段
- **WHEN** HTTP POST 请求 body 包含 `"enable_strength_rank": true`
- **THEN** 请求验证通过，字段值传入 overrides builder

#### Scenario: API 请求未携带选股字段
- **WHEN** HTTP POST 请求 body 未包含 `enable_strength_rank`
- **THEN** 请求验证通过，该字段为 `None`，overrides 中不设置该键

#### Scenario: 运行请求提交 resolved runtime config
- **WHEN** 前端或脚本发起单次运行请求
- **THEN** 后端 SHALL 以请求中的 resolved runtime config json 作为唯一编译输入
- **THEN** `config_id` 若存在 SHALL 只写入运行来源元信息，不得改变已解析配置

#### Scenario: 执行预览提交 resolved runtime config
- **WHEN** 前端发起 execution preview
- **THEN** 后端 SHALL 使用与 run_async 完全相同的 runtime config resolver
- **THEN** preview 返回的来源信息 SHALL 与正式运行保持同构
