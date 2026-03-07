## MODIFIED Requirements

### Requirement: API 请求模型包含选股排序字段
`BacktestV2ExperimentRequest` Pydantic 模型 SHALL 包含以下可选字段：
- `enable_strength_rank: bool | None`
- `strength_ma: int | None`
- `strength_top_k_mode: str | None`
- `enable_multifactor_rank: bool | None`
- `mf_topk: int | None`

#### Scenario: API 请求携带选股字段
- **WHEN** HTTP POST 请求 body 包含 `"enable_strength_rank": true`
- **THEN** 请求验证通过，字段值传入 overrides builder

#### Scenario: API 请求未携带选股字段
- **WHEN** HTTP POST 请求 body 未包含 `enable_strength_rank`
- **THEN** 请求验证通过，该字段为 None，overrides 不设置该键
