# http-surface-boundary-split Specification

## MODIFIED Requirements

### Requirement: 桌面主 HTTP surface 必须暴露最近一周资金不足拦截明细
系统 MUST 在实验 surface 中暴露 `cash_blocked_buys_recent` section，使桌面端和诊断工具可以通过统一 `surface/{section}` 读取最近一周交易日的资金不足拦截买入明细。客户端 SHALL NOT 通过底层 artifact 路径自行推断该信息。

#### Scenario: 客户端请求资金不足拦截明细
- **WHEN** 客户端请求 `/api/backtest_v2/experiments/{id}/surface/cash_blocked_buys_recent`
- **THEN** 系统 MUST 返回最近一周交易日内的资金不足拦截明细列表
- **THEN** 每条记录 MUST 至少包含 `date`、`symbol`、`cash_available`、`estimated_qty`、`estimated_amount`

#### Scenario: 实验没有资金不足拦截记录
- **WHEN** 对应实验最近一周没有 `SKIP_NO_CASH` 明细
- **THEN** 系统 MUST 返回空列表
- **THEN** `surface` 的 lazy section 元数据 MUST 标记该 section 可用
