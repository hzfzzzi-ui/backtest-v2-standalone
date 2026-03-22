## ADDED Requirements

### Requirement: `pams_ohlcv_daily_v2` MUST 以应有证券交易日网格构建零行缺口主表
系统 MUST 以 `pit_security_master` 中处于有效上市区间的 `CN_A` 证券和开市日 `trade_cal` 生成应有证券交易日网格，并将该网格作为 `pams_ohlcv_daily_v2` 的正式行集边界。系统 MUST 对网格中的每个 `symbol + trade_date` 生成且仅生成一行正式主表记录，除非该行被异常门禁拒绝。

#### Scenario: 交易日有原始行情时生成 traded 行
- **WHEN** 某个 `symbol + trade_date` 位于应有网格内，且存在 `raw daily` 记录
- **THEN** 系统 MUST 在 `pams_ohlcv_daily_v2` 中生成一行 `row_status='traded'` 的主表记录

#### Scenario: 交易日无原始行情但存在停牌记录时生成 suspended 行
- **WHEN** 某个 `symbol + trade_date` 位于应有网格内，不存在 `raw daily`，但存在 `raw suspend_d` 命中
- **THEN** 系统 MUST 在 `pams_ohlcv_daily_v2` 中生成一行 `row_status='suspended'` 的主表记录

#### Scenario: 应有网格行无法解释时阻断正式构建
- **WHEN** 某个 `symbol + trade_date` 位于应有网格内，既不存在 `raw daily`，也不存在 `raw suspend_d`
- **THEN** 系统 SHALL NOT 将该行静默跳过
- **THEN** 系统 MUST 记录 `eligible_no_source` 异常并使该批次构建不满足正式升格条件

### Requirement: `pams_ohlcv_daily_v2` MUST 强制执行硬字段零空值合同
系统 MUST 为 `pams_ohlcv_daily_v2` 提供硬字段、软字段和审计字段三层合同。硬字段在正式主表中 MUST 满足零空值规则；软字段允许保留源空值，但 MUST 被显式审计；审计字段 MUST 始终可用以追溯来源和构建批次。

#### Scenario: 硬字段完整写入 traded 行
- **WHEN** 系统生成 `row_status='traded'` 的主表记录
- **THEN** `symbol, ts_code, market, trade_date, row_status, is_suspended, pre_close, open, high, low, close, volume, turnover, adj_factor, limit_up, limit_down, turnover_rate` MUST 全部非空

#### Scenario: 硬字段完整写入 suspended 行
- **WHEN** 系统生成 `row_status='suspended'` 的主表记录
- **THEN** `open, high, low, close` MUST 全部等于 `pre_close`
- **THEN** `volume` 与 `turnover` MUST 等于 `0`
- **THEN** 其余硬字段 MUST 仍保持非空

#### Scenario: 软字段允许源空值但不得伪造
- **WHEN** `turnover_rate_f, volume_ratio, float_share, free_share, circ_mv` 的原始来源缺失
- **THEN** 系统 MAY 将字段保留为空
- **THEN** 系统 MUST 在审计结果中记录对应软字段缺失

### Requirement: `daily_basic` 字段 MUST 按主表分层规则补齐
系统 MUST 将 `daily_basic` 补齐逻辑限制在本合同定义的字段边界内，其中 `turnover_rate` 是唯一允许升格为主表硬字段的 `daily_basic` 字段；其余 `daily_basic` 字段 MUST 按软字段处理，除非后续 change 明确升格。

#### Scenario: `turnover_rate` 先用 Tushare 再用 AkShare 补齐
- **WHEN** 某个主表行缺失 `Tushare daily_basic.turnover_rate`
- **THEN** 系统 MUST 先尝试使用 `AkShare stock_zh_a_hist` 的同日 `换手率` 进行补齐
- **THEN** 若补齐成功，正式主表中的 `turnover_rate` MUST 非空

#### Scenario: `turnover_rate` 允许按确定性规则补算
- **WHEN** `turnover_rate` 在主表行中仍为空，且 `volume` 与 `float_share` 均可用
- **THEN** 系统 MAY 按 `turnover_rate = volume / float_share` 进行补算
- **THEN** 系统 MUST 为该值打上规则补算来源标记

#### Scenario: 软字段缺失不阻止主表行落库
- **WHEN** 主表硬字段已完整，但 `turnover_rate_f` 或 `free_share` 或 `volume_ratio` 缺失
- **THEN** 系统 MUST 允许主表行落库
- **THEN** 系统 MUST 将该缺失纳入软字段审计而非主表失败
