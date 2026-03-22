## Context

当前仓库已经有 A 股日频主行情链路：
- `pams_ohlcv_daily` 负责 `CN_A` / `CN_INDEX` 的主表
- `update_pams_ohlcv_daily.py` 负责 Tushare 日线、复权和部分 `daily_basic` 字段同步
- `data_refresh` 提供托管更新入口

但本次用户要的不是继续扩宽 `pams_ohlcv_daily`，而是把两类研究输入拆成独立侧表：
- `daily_basic` 的显式换手率
- `moneyflow` 的主动买卖单分档资金流

同时，用户明确要求在真实历史回填后补上覆盖率审计，而不是只看单日 smoke。

## Goals / Non-Goals

**Goals**
- 新增 `pit_stock_daily_basic` 与 `pit_stock_moneyflow`
- 提供 `2007-01-04` 到当前最新可得交易日的历史回填与后续增量更新
- 提供独立覆盖率审计，按交易日对比参考表与两张侧表的实际覆盖情况
- 输出可审计产物，包括摘要、覆盖率 CSV、缺口最严重交易日和缺口样本

**Non-Goals**
- 不在本次把侧表字段接入 baseline 排序、过滤、组合构建或 regime 逻辑
- 不混用 `moneyflow`、`moneyflow_ths`、`moneyflow_dc`
- 不改 API 主输出结构或前端展示
- 不对缺口做未来值填充

## Decisions

### D1: 使用两张侧表，而不是继续扩宽 `pams_ohlcv_daily`

新增：
- `pit_stock_daily_basic`
- `pit_stock_moneyflow`

原因：
- 用户要求是“数据表新增”，不是主行情表扩列
- 两类数据都适合按 `symbol + trade_date` 独立生命周期管理
- 侧表可以独立回填、独立同步、独立审计，避免主表语义继续膨胀

### D2: `pit_stock_daily_basic` 首版只保留显式换手率字段

字段：
- `symbol`
- `trade_date`
- `turnover_rate`
- `turnover_rate_f`
- `source`
- `created_at`
- `updated_at`

原因：
- 用户当前明确需要的是日频个股换手率
- `turnover_rate` / `turnover_rate_f` 是 Tushare 显式字段，不需要成交额换算
- 首版收敛到最小必要字段，降低回填与审计复杂度

### D3: `pit_stock_moneyflow` 完整保留 Tushare `moneyflow` 分档字段

字段：
- 键：`symbol`、`trade_date`
- 四档买卖量字段
- 四档买卖额字段
- `net_mf_vol`
- `net_mf_amount`
- `source`
- `created_at`
- `updated_at`

原因：
- 用户要求是“按主动买卖单 + 明确单笔金额分档”
- 完整保留分档字段比只存净额更可审计
- 首版明确只用 Tushare `moneyflow` 口径，不混 THS/DC

### D4: 回填与增量同步继续采用托管脚本模式

每张表都提供 `backend/cli/managed` 脚本，负责：
- 自动建表
- 按交易日窗口抓取
- `symbol + trade_date` 幂等 upsert
- 输出 `summary.json` 和样本 CSV

原因：
- 与现有托管脚本模式一致
- 便于后续补跑、审计和运维固化

### D5: 历史回填上界按“当前最新可得交易日”动态收口

回填下界固定 `2007-01-04`，上界优先取：
- 用户显式传入的 `--end`
- 否则取当前最新可得交易日

原因：
- 避免把未来日期写进任务定义
- 与真实可得数据口径一致

### D6: 覆盖率审计独立于回填脚本执行

新增独立审计脚本，对以下三张表按 `trade_date` 做对比：
- `pams_ohlcv_daily` 作为 `market='CN_A'` 参考基线
- `pit_stock_daily_basic`
- `pit_stock_moneyflow`

审计产物至少包含：
- 每个交易日的参考行数、daily_basic 行数、moneyflow 行数
- 两张侧表相对参考表的覆盖率
- 覆盖最差交易日列表
- 缺口 symbol 样本

原因：
- 覆盖率是运行后结论，不应和单次抓取摘要混在一起
- `moneyflow` 覆盖天然可能窄于主行情，必须独立审视

### D7: 不修改 baseline 默认消费路径

本次只新增表、同步链路与审计，不默认修改：
- `pams_ohlcv_daily`
- provider 默认查询
- baseline 配置

原因：
- 用户当前要的是“开启数据表新增”，不是把新数据直接接入主线策略
- 把落库与研究接入拆开，能保留清晰归因和回退空间

## Risks / Trade-offs

- [Risk] `daily_basic` 早期年份可能存在缺口
  Mitigation：输出逐交易日覆盖率和缺口样本，不做静默补齐。
- [Risk] `moneyflow` 长区间回填可能受接口限流影响
  Mitigation：按日期分段回填，失败可补跑。
- [Risk] 覆盖率只看总量，会掩盖局部严重缺口
  Mitigation：审计产物强制输出最差覆盖交易日和缺口样本。
- [Risk] 后续研究直接把侧表字段并入策略而不另开 change
  Mitigation：本次明确只做落库和审计，策略接入必须另开变更。

## Migration Plan

1. 在 `docs/db` 维护 apply / rollback SQL。
2. 在 `backend/cli/managed` 提供两条回填脚本和一条覆盖率审计脚本。
3. 在 `data_refresh` 注册三条托管入口。
4. 补充单元测试，覆盖规范化、参数解析、摘要计算和目标注册。
5. 先做小窗口 smoke，再做全历史分段回填。
6. 回填完成后立即执行覆盖率审计。

回退策略：
- 运行层回退：停止调用新脚本和审计脚本，不影响 baseline
- 结构层回退：执行 rollback SQL 删除侧表
- 数据层回退：保留产物，允许按批次重跑，不对主表做回退性改写
