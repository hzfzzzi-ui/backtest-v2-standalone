## ADDED Requirements

### Requirement: 结果工作台必须区分未单独计数与真实零值
结果工作台在渲染交易漏斗时 MUST 保留后端提供的 `available` 与 `null` 语义。对于 `available=false` 或阶段计数为 `null` 的阶段，结果工作台 MUST 显示“未单独计数”或等价状态，并 MUST NOT 将该阶段格式化为数值 `0`。对于 `available=true` 且阶段计数真实为 `0` 的阶段，结果工作台 MUST 按真实零值显示。

#### Scenario: 渲染 unavailable 阶段
- **WHEN** 结果工作台收到某个漏斗阶段 `available=false`，或 `input_count / output_count / filtered_count` 为 `null`
- **THEN** 该阶段 SHALL 显示 unavailable 或未单独计数状态
- **THEN** 该阶段的数值位 SHALL NOT 渲染为 `0`

#### Scenario: 渲染真实零值阶段
- **WHEN** 结果工作台收到某个漏斗阶段 `available=true` 且计数值真实为 `0`
- **THEN** 该阶段 SHALL 直接显示 `0`
- **THEN** 该阶段 SHALL NOT 被标记为 unavailable 或 missing

#### Scenario: view model 不得吞掉空值语义
- **WHEN** 结果工作台 helper 或 view model 构造漏斗面板数据
- **THEN** helper SHALL 保留 `available=false` 与 `null` 语义到最终渲染层
- **THEN** helper SHALL NOT 通过数值格式化或 `Number()` 收敛把空值阶段改写成 `0`
