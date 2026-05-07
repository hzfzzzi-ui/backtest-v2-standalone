## MODIFIED Requirements

### Requirement: Runtime config compile MUST 编译 canonical market source contract
系统 MUST 以 `canonical_market` 为正式市场数据消费目标编译 runtime config，而不是继续把 `v1`、`v2 runtime` 或 `data_role` 暴露为正式上层数据角色。编译结果 MAY 保留 canonical source reference 作为审计元信息，但 SHALL NOT 再要求上层通过 `data_role` 或具体 `stocks_table` 决定正式市场数据入口。

#### Scenario: 编译 baseline 使用正式默认市场数据入口
- **WHEN** 用户继续使用当前正式默认运行配置
- **THEN** runtime config compile MUST 产出指向 `canonical_market` 的正式市场数据入口
- **THEN** compile 结果 SHALL NOT 继续把 `pams_ohlcv_daily` 作为默认正式股票数据表

#### Scenario: 编译 canonical shadow 对照实验
- **WHEN** 用户或研究配置指定 canonical shadow source 做对照实验
- **THEN** compile 结果 MUST 明确记录 canonical source reference
- **THEN** 运行产物 MUST 能区分该实验是 canonical 对照，而非正式默认入口被隐式切换

### Requirement: Runtime config compile 必须支持显式的 canonical shadow source 切换
系统 MUST 允许 runtime config compile 在不改变正式默认行为的前提下，显式编译出替代性的 canonical market source 引用。该切换 MUST 来自明确的 shadow 配置或 override，而不是由 compile 流程隐式替换默认市场数据入口。

#### Scenario: Shadow 配置编译为 canonical shadow source
- **WHEN** 用户提供 `pams_cn_pg_v2.json` 或等价 shadow override
- **THEN** runtime config compile MUST 产出指向 canonical shadow source 的 source reference 和相应 schema mapping
- **THEN** 其他运行时字段语义 SHALL 与默认配置保持一致

#### Scenario: 默认配置不被隐式切换
- **WHEN** 用户继续使用当前默认运行配置
- **THEN** runtime config compile SHALL 继续产出指向正式默认 `canonical_market` 入口的结果
- **THEN** compile 流程 SHALL NOT 因存在 `v2` 或 compat 表而自动发出 `pams_ohlcv_daily` 或 `pams_ohlcv_daily_v2_runtime` 作为正式默认入口
