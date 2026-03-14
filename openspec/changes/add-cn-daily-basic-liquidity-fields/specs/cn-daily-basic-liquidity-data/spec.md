## ADDED Requirements

### Requirement: CN_A 日频流动性字段入库
系统 SHALL 为 `pams_ohlcv_daily` 中 `market='CN_A'` 的日线记录存储与 `trade_date + symbol` 对齐的日频流动性字段，至少包括 `turnover_rate`、`turnover_rate_f`、`volume_ratio`。系统 MAY 一并存储 `float_share`、`free_share`、`circ_mv` 作为审计与扩展辅助字段。系统 MUST 保持现有 `volume` 和 `turnover` 字段语义不变，其中 `turnover` 继续表示成交额，不得改作换手率。

#### Scenario: daily_basic 字段成功写入主表
- **WHEN** 导入链路处理某个 `CN_A` 股票在某个 `trade_date` 的 daily_basic 记录
- **THEN** 系统 SHALL 将 `turnover_rate`、`turnover_rate_f`、`volume_ratio` 写入与该 `symbol + trade_date` 对应的 `pams_ohlcv_daily` 行

#### Scenario: 现有成交额字段语义保持不变
- **WHEN** 系统完成流动性字段回填
- **THEN** 现有 `turnover` 字段 SHALL 继续表示成交额
- **THEN** 系统 SHALL NOT 用 `turnover_rate` 或 `turnover_rate_f` 覆盖或重命名 `turnover`

### Requirement: 运行时历史帧透传可选流动性字段
系统 SHALL 在 `load_ohlcv_daily()` 返回的 history frame 中按同一 `date + symbol` 透传已存在的流动性字段，但 MUST 保持当前必需 canonical 列集合不变。若流动性字段在表中不存在或映射未配置，baseline 运行 MUST 继续成功，不得因新增字段缺失而改变现有默认行为。

#### Scenario: 表中存在流动性字段时透传到 history frame
- **WHEN** `pams_ohlcv_daily` 包含 `turnover_rate_f` 且 schema mapping 已配置
- **THEN** `load_ohlcv_daily()` 返回的 history frame SHALL 包含 `turnover_rate_f`

#### Scenario: 基线配置未启用新字段时保持兼容
- **WHEN** 运行使用当前 baseline 配置且未配置任何新流动性字段映射
- **THEN** `load_ohlcv_daily()` SHALL 继续返回现有必需列
- **THEN** 回测结果 SHALL NOT 因新增字段缺失而失败

### Requirement: 换手率过滤使用独立配置且默认关闭
系统 SHALL 提供独立于现有成交额过滤的换手率过滤配置。默认情况下换手率过滤关闭，现有 `min_avg_turnover_20d` 成交额过滤和 baseline 结果 MUST 保持不变。启用后，系统 SHALL 仅使用截至当日的历史 `turnover_rate` 或 `turnover_rate_f` 计算 rolling 20 日均值，并据此过滤候选股票。

#### Scenario: 默认配置不改变现有 amount-based 过滤
- **WHEN** 用户未设置 `min_avg_turnover_rate_20d` 或其值为 `0`
- **THEN** 系统 SHALL 不启用换手率过滤
- **THEN** 现有 `min_avg_turnover_20d` 成交额过滤行为 SHALL 保持不变

#### Scenario: 启用自由流通换手率过滤时仅使用历史窗口
- **WHEN** 用户设置 `min_avg_turnover_rate_20d > 0` 且 `turnover_rate_field='turnover_rate_f'`
- **THEN** 系统 SHALL 基于截至当日的 `turnover_rate_f` 历史窗口计算 20 日均值
- **THEN** 系统 SHALL NOT 使用未来交易日的换手率值参与当日过滤判断

### Requirement: 流动性字段校验与审计
当换手率过滤启用时，系统 MUST 在运行前检查所选流动性字段是否存在、是否为非负数值、是否按 `trade_date + symbol` 同日对齐。系统 MUST NOT 通过 `bfill` 或跨日 future fill 回填缺失换手率值。字段不可用时，系统 SHALL 返回明确的校验失败或审计告警，而不是静默回退成成交额过滤。

#### Scenario: 启用换手率过滤但字段缺失
- **WHEN** 用户启用 `min_avg_turnover_rate_20d`，但所选 `turnover_rate_field` 在表中不存在或映射缺失
- **THEN** 数据校验 SHALL 返回失败或明确告警
- **THEN** 系统 SHALL NOT 静默改用 `turnover` 成交额字段继续运行

#### Scenario: 日频流动性字段存在缺口
- **WHEN** 某股票某日缺少 `turnover_rate` 或 `turnover_rate_f`
- **THEN** 系统 SHALL 保留该值为缺失态或将该日标记为不可用于对应过滤
- **THEN** 系统 SHALL NOT 使用未来日期的值回填该缺口
