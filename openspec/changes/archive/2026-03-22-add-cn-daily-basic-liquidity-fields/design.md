## Context

当前系统的 CN A 日线主表已经包含 `open/high/low/close/volume/turnover`，其中 `turnover` 实际表示成交额。运行时 canonical 协议把它映射为 `amount`，股票池流动性过滤 `min_avg_turnover_20d` 也实际基于成交额均值工作。系统缺少按 `trade_date + symbol` 对齐的日频换手率字段，因此无法在不混淆语义的前提下研究 `turnover_rate` / `turnover_rate_f`。

本次 change 的约束很明确：

- baseline 行为不能变
- 不能把现有 `turnover` 改名或改义
- 不能通过未来填充或最新股本反推历史换手率
- 配置与审计必须能区分“成交额过滤”和“换手率过滤”

## Goals / Non-Goals

**Goals:**

- 为 CN A 日线主表补齐可审计的 daily_basic 流动性字段
- 在不改变现有 canonical 必需列的前提下，让运行时 history frame 可选读取这些字段
- 提供默认关闭的换手率过滤配置，保证 baseline 与现有 amount-based 过滤不变
- 在 validate/audit 链路中增加字段存在性、语义与时间对齐保护

**Non-Goals:**

- 不在本 change 中引入基于换手率的新策略收益优化
- 不在本 change 中重构整套市场数据模型
- 不默认启用新的换手率过滤
- 不把指数 `index_dailybasic` 一并纳入首批实施范围

## Decisions

### D1: 新增字段直接落在 `pams_ohlcv_daily`

首版实现将 daily_basic 流动性字段直接追加到 `pams_ohlcv_daily`，而不是新建独立 `pit_stock_daily_basic`。

原因：

- 当前运行时数据路径、provider、universe filter 都围绕单表 `load_ohlcv_daily()` 组织
- 追加 nullable 列的改动面更小，避免新增 join 与第二套主键约束
- 现有表已经承载 `adj_factor`、`limit_up`、`is_suspended` 这类非纯 OHLCV 字段，继续追加流动性扩展列符合当前工程风格

备选方案：

- 新建 `pit_stock_daily_basic`：语义更干净，但会扩大 provider、bundle builder、validation 和测试改动面，当前不优先

### D2: 保持 `turnover=成交额` 语义不变

新增字段使用明确名称：`turnover_rate`、`turnover_rate_f`、`volume_ratio`，现有 `turnover` 继续只表示成交额。

原因：

- 现有 config 已把 `turnover -> amount`
- 现有 liquidity filter、matrix 构建、execution realism 审计都已把 `turnover` 当成交额使用
- 复用旧字段名会直接破坏 baseline 可比性与历史产物口径

### D3: 运行时采用“可选扩展列透传”，不改 canonical 必需列集合

`load_ohlcv_daily()` 的必需列仍保持 `date/symbol/open/high/low/close/volume/amount`，新增流动性字段作为 optional extras 透传到 history frame。

原因：

- baseline 与现有调用方不需要改
- 新字段可被 universe filter、factor 逻辑按需消费
- 设计上与 `limit_up`、`adj_factor` 的扩展列模式一致

### D4: 换手率过滤使用新配置键，默认关闭

不复用现有 `min_avg_turnover_20d`。新增独立配置键：

- `min_avg_turnover_rate_20d`
- `turnover_rate_field`，允许 `turnover_rate_f` 或 `turnover_rate`

原因：

- 复用旧键会让“成交额阈值”和“换手率阈值”共用同一语义名，增加口径漂移风险
- 新键默认 `0.0/disabled`，可严格保证 baseline 不变
- 现有 `universe.filters` 已以原始 dict 方式传递，可低成本加新键

### D5: 时间对齐按“t 日观测，t+1 执行”处理，禁止未来填充

daily_basic 字段与当日 `trade_date` 对齐写入，但任何基于该字段的过滤或信号都遵守收盘后观测、下一交易日执行的合同。字段缺失时保留 `NaN`，不得 `bfill`，也不得用未来数据补齐。

原因：

- 换手率属于日终口径，不满足盘中可知
- `bfill` 或跨日回填会把未来可见信息带回过去

### D6: 校验与审计只在启用时升级约束

当 `min_avg_turnover_rate_20d > 0` 时，校验链路必须检查所选字段是否存在、是否为非负值、是否按 `trade_date + symbol` 对齐；字段不可用时应明确报错或告警。默认未启用时，这些检查不影响 baseline 运行。

原因：

- 兼顾 baseline 向后兼容与新功能的安全防护
- 避免“字段不存在却静默回退成成交额过滤”

### D7: 以“股票先行、支持字段可选、缺口保守处理”为默认收口

为保证本 change 可以直接进入实现，首版默认采用以下边界：

- 首版仅覆盖 `market='CN_A'` 的股票 daily_basic，不包含指数 `index_dailybasic`
- `float_share/free_share/circ_mv` 在上游可得时一并写入，但不作为首版换手率过滤的必需前置条件
- 当过滤启用且字段在 schema/mapping 层缺失时，校验直接 FAIL
- 当字段列存在但个别交易日有缺口时，校验给出覆盖率告警，运行时将对应股票对应日期视为该过滤不可用，不做未来填充

原因：

- 这组边界不会阻塞首版实现
- 它同时满足 baseline 不变、审计保守、后续可扩展三个目标

## Risks / Trade-offs

- [Risk] 上游源字段单位与现有库表单位不一致 → Mitigation：实现时必须用样本校验 `turnover` 与 `close*volume` 量级，并为新字段写入前增加单位归一化测试
- [Risk] 历史 daily_basic 存在缺口，启用新过滤后样本规模骤降 → Mitigation：默认关闭；启用时先在 validate_data 中做字段覆盖率检查
- [Risk] 继续把 `min_avg_turnover_20d` 误解成换手率阈值 → Mitigation：新增独立键，不复用旧键，并在 proposal/spec/tasks 中显式声明
- [Risk] 未来如果还要加入更多 daily_basic 字段，单表会继续变宽 → Mitigation：首版先以最小改动交付，后续若 daily_basic 消费面扩大，再考虑拆表

## Migration Plan

1. 为 `pams_ohlcv_daily` 增加 nullable 流动性字段
2. 编写/接入 daily_basic 回填脚本，对历史区间执行幂等更新
3. 扩展 provider 与 mapping，将新字段作为 optional extras 透传
4. 在 universe filter 中新增默认关闭的换手率过滤键
5. 为 validate_data / audit 增加启用态检查
6. 通过测试和样本校验后，再由研究配置显式启用新过滤

回滚策略：

- 配置层保持默认关闭即可回到 baseline 行为
- 即使新列已存在，只要不启用新过滤，运行时路径应与当前一致
- 不在首版回滚中要求删除新增列或清理历史值

## Open Questions

- 是否需要在后续 change 中补上指数 `index_dailybasic`，用于 benchmark/regime 级别的流动性研究
- supporting fields 是否值得在第二阶段提升为强制覆盖要求，以便为更多横截面因子做审计交叉校验
