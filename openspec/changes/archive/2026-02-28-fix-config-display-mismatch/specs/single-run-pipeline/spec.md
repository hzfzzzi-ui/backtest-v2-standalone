## ADDED Requirements

### Requirement: run_config.json 包含 resolved universe 摘要
`run_config.json` SHALL 在 universe 解析完成后追加 `_resolved_universe` 字段，记录实际运行的 universe 信息。

#### Scenario: 非 CUSTOM 模式写入 resolved 摘要
- **WHEN** `universe_mode` 为 `ALL_A`、`HS300_ZZ500` 或 `INDUSTRY`
- **THEN** `run_config.json` SHALL 包含 `_resolved_universe` 对象
- **THEN** `_resolved_universe.mode` SHALL 等于实际使用的 universe_mode 字符串
- **THEN** `_resolved_universe.resolved_count` SHALL 等于 `resolve_universe_by_mode()` 返回的 symbols 列表长度
- **THEN** `_resolved_universe.raw_count` SHALL 等于 `universe_meta.raw_count`（限制前的原始数量）

#### Scenario: CUSTOM 模式同样写入 resolved 摘要
- **WHEN** `universe_mode` 为 `CUSTOM`
- **THEN** `run_config.json` SHALL 同样包含 `_resolved_universe` 字段
- **THEN** `_resolved_universe.resolved_count` SHALL 等于用户提供的 symbols 归一化去重后的数量

#### Scenario: 原始输入配置保留
- **WHEN** `run_config.json` 写入完成
- **THEN** `universe.symbols` 字段 SHALL 保留用户原始输入值（不被 resolved symbols 覆盖）
- **THEN** 可通过 `_resolved_universe` 与 `universe.symbols` 的对比区分"输入"与"实际"

### Requirement: 前端标的数量展示使用 resolved 值
前端"标的数量"展示 SHALL 优先使用 `run_meta.universe` 中的实际解析数量，回退到 `config.universe.symbols.length`。

#### Scenario: 摘要栏展示 resolved 数量
- **WHEN** `renderSummaryBar()` 渲染且 `run_meta.universe` 存在
- **THEN** "标的 N 个"中的 N SHALL 等于 `run_meta.universe.raw_count`（或 `resolved_count`）
- **THEN** 不再使用 `config_draft.universe.symbols.length`

#### Scenario: 实验详情展示 resolved 数量
- **WHEN** 实验配置详情表渲染"标的数量"行
- **THEN** 展示值 SHALL 优先取 `run_meta.universe.raw_count`
- **THEN** 若 `run_meta` 不存在（旧实验），回退到 `symbols.length`（行为不变）

#### Scenario: 回退行为
- **WHEN** `run_meta.json` 缺失或 `universe` 字段不存在
- **THEN** 前端 SHALL 回退到 `config.universe.symbols.length`
- **THEN** 用户体验与修复前一致（不会更差）
