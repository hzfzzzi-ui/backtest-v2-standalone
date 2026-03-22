## 1. Raw Staging 与日期骨架

- [ ] 1.1 新增 raw staging DDL；DoD：落地 `daily`、`adj_factor`、`daily_basic`、`moneyflow`、`trade_cal` 原始表以及批次元数据表，主键和必要索引齐备；验证：SQL/迁移文件可读，空库执行后能查询到目标表结构；风险：raw 表主键、字段单位或批次元字段设计不一致，后续无法稳定重放。
- [ ] 1.2 实现 `pit_trade_cal` 补齐或 `trade_cal` raw 刷新脚本；DoD：能把日期骨架补到 `2007-01-04` 至当前最新可得交易日；验证：真实库检查最小/最大日期覆盖目标窗口；风险：继续依赖当前不完整日期骨架，导致 v2 构建窗口天然残缺。
- [ ] 1.3 实现 raw 抓取托管脚本；DoD：支持按日期窗口抓取并幂等写入原始 `daily`、`adj_factor`、`daily_basic`、`moneyflow`；验证：小窗口 smoke run 生成 `summary.json`、raw sample CSV 和失败批次摘要；风险：限流、空返回与真实失败未区分，审计口径失真。

## 2. Canonical v2 构建

- [ ] 2.1 新增 `pams_ohlcv_daily_v2` 与 `pit_stock_moneyflow_v2` DDL；DoD：`v2` 主表保留 v1 兼容列并新增 `ts_code`/source presence/build 元字段，`moneyflow_v2` 侧表具备主键与索引；验证：DDL 与 design/spec 对齐；风险：v2 schema 与当前运行时合同不兼容，shadow 无法验证。
- [ ] 2.2 实现 `pams_ohlcv_daily_v2` canonical builder；DoD：基于 raw `daily` 观测行 + `pit_security_master` 过滤构建主表，按同键融合 `adj_factor` 与 `daily_basic`，生成 limit_up/down 和 source presence 标记；验证：短窗口跑通并输出逐日行数、空值率与样本；风险：把无效证券写入主表，或把源缺失误当停牌硬补行。
- [ ] 2.3 实现 `pit_stock_moneyflow_v2` 对齐构建；DoD：只对齐到 `v2` 主表已存在的 `symbol + trade_date`，raw-only 资金流写异常输出；验证：短窗口对齐结果、覆盖率和异常样本可核对；风险：把 raw-only 资金流误当合法主表键，污染消费口径。

## 3. 审计与差异验证

- [ ] 3.1 实现 `v2` 原始层与构建层审计脚本；DoD：输出逐交易日 `eligible/raw/v2/daily_basic/moneyflow` 统计、异常样本和字段空值率；验证：审计产物与短窗口 SQL 抽样一致；风险：只有总量没有分日/样本，无法定位覆盖问题。
- [ ] 3.2 实现 `v1/v2` 差异审计；DoD：输出 `pams_ohlcv_daily` 与 `pams_ohlcv_daily_v2` 的逐日行数差异、样本差异和关键字段空值率对比；验证：已知缺口/超出日期能在 diff 产物中复现；风险：无法区分“覆盖修复”和“构建错误”。
- [ ] 3.3 补充测试；DoD：覆盖 raw 规范化、canonical build、moneyflow 对齐、runtime shadow compile 和审计摘要核心逻辑；验证：pytest 相关用例通过；风险：只测 happy path，漏掉 raw-only、未知证券和空字段场景。

## 4. Shadow 切换与回归

- [ ] 4.1 新增 `pams_cn_pg_v2.json` 或等价 shadow 配置；DoD：显式把 `stocks_table` 指向 `pams_ohlcv_daily_v2`，默认配置不变；验证：runtime compile 能区分默认与 shadow 两条链路；风险：隐式替换默认表，污染当前 baseline 结果。
- [ ] 4.2 执行最小窗口 shadow run；DoD：V10.1 能在不改默认配置的前提下读取 `v2`，并输出基础回测产物与诊断；验证：`perf/nav/orders/trades/run_meta` 及差异审计文件齐备；风险：v2 虽能建表，但运行时合同未真正打通。
- [ ] 4.3 执行三窗口回归与结论输出；DoD：在 `2016-2026`、`2007-2017`、`2007-2026` 上完成 `v1/v2` 平行验证，形成切换建议；验证：行数差异、空值率、收益/回撤/交易数和停牌行为都有结论；风险：只看收益不看数据口径，导致错误切换判断。
