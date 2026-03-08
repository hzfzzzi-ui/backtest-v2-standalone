## ADDED Requirements

### Requirement: run_meta 区间口径来自最终运行配置
单次回测产物中的 `run_meta.data.start/end/benchmark` MUST 来源于本次最终运行配置，而不是模板默认配置或仅由 request 覆盖推导。

#### Scenario: config_id 与前端草稿冲突
- **WHEN** 请求同时携带 `config_id` 与 `workbench_config`，且系统按策略选择脚本配置为生效源
- **THEN** `run_meta.data.start/end/benchmark` SHALL 与该生效配置编译后的 `run_config.json.universe` 一致

### Requirement: run_meta 记录报告口径来源
单次回测产物 MUST 提供报告关键字段的来源标记，以便后续报告生成与排障。

#### Scenario: 生成 run_meta
- **WHEN** stabilize 阶段写入 `run_meta.json`
- **THEN** 系统 SHALL 记录关键字段来源（至少覆盖区间、基准、Universe 统计、漏斗）
- **THEN** 若触发回退，系统 SHALL 记录 fallback 原因
