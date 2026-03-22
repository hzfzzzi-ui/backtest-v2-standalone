## ADDED Requirements

### Requirement: Universe filters MUST 支持可选科创板排除
系统 MUST 在共享 `universe.filters` 链路中支持布尔字段 `exclude_star_market`。当该字段为 `true` 时，resolver SHALL 在候选集合与股票代码集合两个层面排除科创板标的；当字段缺省或为 `false` 时，系统 SHALL 保持现有股票池行为不变。

#### Scenario: 默认关闭不改变现有股票池
- **WHEN** 运行配置未提供 `universe.filters.exclude_star_market`
- **THEN** resolver SHALL 不额外排除任何科创板标的
- **THEN** 结果股票池口径 SHALL 与改动前保持一致

#### Scenario: 显式开启后排除科创板
- **WHEN** `universe.filters.exclude_star_market=true`
- **THEN** resolver SHALL 排除标准化后属于 `688xxx.SH` 或 `689xxx.SH` 的 A 股标的
- **THEN** 非科创板 A 股标的 SHALL 保留

### Requirement: 科创板过滤结果 MUST 写入现有 universe 元数据
当科创板过滤启用时，系统 MUST 将过滤配置与排除计数写入现有 universe 元数据，确保验证接口、bundle 构建与真实执行可以审计该过滤是否生效。

#### Scenario: 记录过滤配置与排除数量
- **WHEN** `exclude_star_market=true` 且股票池中存在科创板标的
- **THEN** universe 元数据 SHALL 在 `filters_config` 中记录 `exclude_star_market=true`
- **THEN** universe 元数据 SHALL 在 `excluded_counts` 中记录 `EXCLUDE_STAR_MARKET` 的排除数量

### Requirement: Dynamic universe 路径 MUST 复用同一科创板过滤语义
系统 MUST 让 dynamic universe 解析路径与静态候选过滤路径复用同一套科创板识别和排除语义，避免验证结果、bundle 构建和运行期消费出现口径分叉。

#### Scenario: Dynamic ALL_A 路径启用科创板过滤
- **WHEN** `membership_mode` 为 dynamic 路径且 `exclude_star_market=true`
- **THEN** 下游消费的 symbol 列表 SHALL 在进入可交易集合前排除科创板标的
- **THEN** 实际运行期股票池 SHALL 与验证接口返回的过滤结果一致
