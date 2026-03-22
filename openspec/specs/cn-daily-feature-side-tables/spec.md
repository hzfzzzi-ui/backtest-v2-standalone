# cn-daily-feature-side-tables Specification

## Purpose
TBD - created by archiving change add-cn-daily-basic-and-moneyflow-side-tables. Update Purpose after archive.
## Requirements
### Requirement: CN_A 日频换手率侧表入库
系统 MUST 为 `market='CN_A'` 的个股日频 `daily_basic` 数据提供独立侧表，按 `symbol + trade_date` 存储显式换手率字段。首版侧表 MUST 至少包含 `turnover_rate`、`turnover_rate_f`、`source`、`created_at`、`updated_at`。

#### Scenario: 显式换手率按交易日入库
- **WHEN** 同步脚本获取到某只 `CN_A` 股票在某个 `trade_date` 的 `daily_basic` 记录
- **THEN** 系统 SHALL 将 `turnover_rate` 和 `turnover_rate_f` 按 `symbol + trade_date` 写入侧表

#### Scenario: 同一主键重复同步时幂等更新
- **WHEN** 同步脚本重复处理同一 `symbol + trade_date`
- **THEN** 系统 SHALL 以 upsert 方式更新该行，而不是插入重复记录

### Requirement: CN_A 日频 moneyflow 分档侧表入库
系统 MUST 为 `market='CN_A'` 的个股日频资金流提供独立侧表，且首版 MUST 采用 Tushare `moneyflow` 口径。侧表 MUST 按 `symbol + trade_date` 存储小单、中单、大单、特大单的买卖量额，以及 `net_mf_vol`、`net_mf_amount`。

#### Scenario: 主动买卖单分档字段完整写入
- **WHEN** 同步脚本获取到某只 `CN_A` 股票在某个 `trade_date` 的 `moneyflow` 记录
- **THEN** 系统 SHALL 将四档买卖量额字段和净流入字段按 `symbol + trade_date` 写入侧表

#### Scenario: 不混入其他资金流口径
- **WHEN** 系统执行 moneyflow 侧表同步
- **THEN** 系统 SHALL NOT 使用 `moneyflow_ths` 或 `moneyflow_dc` 替代或混合写入该侧表

### Requirement: 侧表回填边界与增量同步可审计
系统 MUST 支持从 `2007-01-04` 到当前最新可得交易日的历史回填，并支持按交易日窗口执行后续增量同步。系统 MUST 为每次运行输出可审计摘要，至少包含开始日期、结束日期、写入行数、缺失交易日或失败批次信息。

#### Scenario: 默认历史回填以当前最新可得交易日收口
- **WHEN** 用户未显式指定 `--end`
- **THEN** 系统 SHALL 使用当前最新可得交易日作为回填上界，而不是写入未来日期

#### Scenario: 运行产物记录写入情况
- **WHEN** 同步脚本完成一次历史回填或增量更新
- **THEN** 系统 SHALL 输出摘要文件和样本文件，以展示时间范围、写入结果与缺口信息

### Requirement: 侧表覆盖率必须可独立审计
系统 MUST 提供独立覆盖率审计能力，按 `trade_date` 将 `pit_stock_daily_basic` 与 `pit_stock_moneyflow` 的实际落库行数对照 `pams_ohlcv_daily` 中 `market='CN_A'` 的参考行数，并输出覆盖率、覆盖最差交易日和缺口样本。

#### Scenario: 回填完成后输出逐交易日覆盖率
- **WHEN** 用户在任意日期窗口执行覆盖率审计
- **THEN** 系统 SHALL 输出每个 `trade_date` 的参考行数、`daily_basic` 行数、`moneyflow` 行数，以及对应覆盖率

#### Scenario: 审计结果暴露最差覆盖交易日
- **WHEN** 某些交易日的 `daily_basic` 或 `moneyflow` 相对参考表存在缺口
- **THEN** 系统 SHALL 输出缺口最严重交易日列表和缺口样本 symbol 文件，而不是只给总量汇总

### Requirement: 新侧表不得改变现有主行情合同
系统 MUST 保持 `pams_ohlcv_daily` 的既有语义和 baseline 默认消费路径不变。本次改动 SHALL 通过新增侧表补充数据，而不是要求主行情表新增必需字段或改变现有 provider 默认读取合同。

#### Scenario: 未启用新侧表时 baseline 保持不变
- **WHEN** 用户继续运行当前 baseline 和既有日频主链路
- **THEN** 系统 SHALL 不因新增侧表而改变现有主表依赖、默认查询路径或回测结果口径

#### Scenario: 侧表创建失败不污染主表
- **WHEN** 新侧表同步在建表或写入阶段失败
- **THEN** 系统 SHALL NOT 对 `pams_ohlcv_daily` 已有数据执行回退性改写或语义替换

