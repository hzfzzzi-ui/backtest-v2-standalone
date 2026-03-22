## MODIFIED Requirements

### Requirement: 数据层加载 adj_factor

`pg_provider.load_ohlcv_daily()` 必须（SHALL）在返回的 DataFrame 中包含 `adj_factor` 列。当数据库中 `adj_factor` 为 NULL 时，先按股票前向填充（`groupby("symbol").ffill()`），兜底才填 1.0。

#### Scenario: 正常加载含 adj_factor 的行情数据
- **WHEN** 调用 `load_ohlcv_daily(symbols, start, end, source)` 加载一组股票
- **THEN** 返回的 DataFrame 包含 `adj_factor` 列，所有值为正浮点数

#### Scenario: 最新交易日 adj_factor 数据滞后
- **WHEN** 某股票最新交易日 `adj_factor` 为 NULL，但前一交易日 `adj_factor=24.839`
- **THEN** 该行 `adj_factor` 填充为 `24.839`，而非 `1.0`

#### Scenario: 原始 adj_factor 缺口需要正式修复入口
- **WHEN** `pams_ohlcv_daily` 在给定日期范围内存在 `market='CN_A' AND adj_factor IS NULL` 的记录
- **THEN** 系统 MUST 提供正式 repair 模式，只重抓该范围内存在缺口的交易日
- **THEN** 该模式 SHALL 复用正式的 `update_pams_ohlcv_daily` 抓取与 upsert 链路，而不是另造第二套写库逻辑

#### Scenario: repair 模式返回修复后完整性审计
- **WHEN** repair 模式执行完成
- **THEN** summary MUST 记录修复前命中的缺口交易日列表
- **THEN** summary MUST 记录修复后仍存在缺口的交易日列表与剩余缺口行数
- **THEN** summary MUST 提供布尔完整性结果，供同步服务与运维诊断消费

#### Scenario: 日常同步后的 adj_factor 缺口不得静默成功
- **WHEN** 正式日常同步已追到目标交易日，但本次覆盖的交易日仍存在 `adj_factor IS NULL` 的 `CN_A` 记录
- **THEN** 同步结果 SHALL 被判定为失败
- **THEN** 系统 SHALL NOT 仅因“最新交易日已追平”而把该次同步记为成功
