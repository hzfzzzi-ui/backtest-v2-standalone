- [x] 1. 固化数据库合同与文档
  - [x] 1.1 将 [pams_ohlcv_daily_v2_schema_contract.md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/docs/db/pams_ohlcv_daily_v2_schema_contract.md) 与本 change 的 specs 对齐
  - [x] 1.2 明确 `pams_ohlcv_daily_v2`、`pit_stock_moneyflow_v2`、审计表的字段类型、主键、索引和非空规则

- [x] 2. 建立 `v2` raw source 层
  - [x] 2.1 为 `trade_cal, stock_basic, daily, adj_factor, daily_basic, suspend_d, stk_limit, moneyflow` 编写 raw 表 DDL
  - [x] 2.2 为各 raw 表增加批次号、写入时间和必要来源字段
  - [x] 2.3 新增回填和增量同步入口，禁止 direct-to-final

- [x] 3. 构建 `pams_ohlcv_daily_v2`
  - [x] 3.1 基于 `pit_security_master x trade_cal(open days)` 生成应有网格
  - [x] 3.2 按 `daily` 和 `suspend_d` 生成 `traded/suspended` 行
  - [x] 3.3 写入主表硬字段、软字段和审计字段
  - [x] 3.4 对 `turnover_rate` 接入 `Tushare -> AkShare -> 规则补算` 链路
  - [x] 3.5 对 `limit_up/down` 接入 `stk_limit` 主源与规则兜底

- [x] 4. 构建 `pit_stock_moneyflow_v2`
  - [x] 4.1 仅按 `v2` 主表主键对齐写入侧表
  - [x] 4.2 增加 `source_moneyflow_present` 和 `net_fields_present`
  - [x] 4.3 为覆盖率门槛和默认研究白名单输出可消费结果

- [x] 5. 建立 `v2` 审计与升格门禁
  - [x] 5.1 实现 `pams_ohlcv_daily_v2_audit_daily`
  - [x] 5.2 实现 `pams_ohlcv_daily_v2_exceptions`
  - [x] 5.3 实现 `v1/v2` 逐日差异审计
  - [x] 5.4 将 `eligible_no_source`、硬字段空值和关键异常纳入升格门禁

- [ ] 6. 完成全历史回填与验证
  - [ ] 6.1 回填 `2007-01-04` 到 `2026-03-16`
  - [ ] 6.2 输出 `2016-2026`、`2007-2017`、`2007-2026` 三窗口正式审计结果
  - [ ] 6.3 给出 `v2` 是否可作为正式 shadow 数据源的最终结论

当前附注：

- 已完成真实数据库 DDL。
- 已完成 `2026-03-16` 单日 smoke：`security_master -> raw -> v2 main -> moneyflow_v2 -> audit`。
- 全历史正式回填尚未启动，当前还不能给出 `shadow` 升格结论。
