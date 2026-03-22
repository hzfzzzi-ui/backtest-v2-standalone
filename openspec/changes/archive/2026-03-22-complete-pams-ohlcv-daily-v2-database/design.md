## Context

当前仓库已经存在一条面向 `v2` 总体重建的 change，但数据库补全本身还没有被单独约束成“可判定成功或失败”的合同。现实问题有三层：

- `pams_ohlcv_daily` 不是稳定基线，早年既有缺口也有超出，不能继续拿它当唯一真相。
- `daily_basic`、`suspend_d`、`stk_limit`、`moneyflow` 的覆盖性质不同，不能再混在一条脚本里按同一标准处理。
- 用户对 `v2` 的正式要求已经明确收敛为：零行缺口、核心字段零空值、审计完整，而不是“所有扩展字段都并入一张表”。

因此，这个 change 不再讨论泛化架构，而是只解决 `pams_ohlcv_daily_v2` 的数据库补全问题，并将该问题拆成主表、原始层、侧表和门禁四个独立能力。

## Goals / Non-Goals

**Goals:**
- 让 `pams_ohlcv_daily_v2` 以 `security master x trade_cal(open days)` 为边界实现零行缺口。
- 让主表硬字段实现零空值，软字段保留显式审计。
- 固化 `Tushare` 主源、`AkShare` 补源的边界，避免来源漂移。
- 把 `moneyflow` 保持为侧表，并补上缺失治理和研究门槛。
- 建立全历史回填、逐日审计、异常明细和 `v1/v2` 差异门禁。

**Non-Goals:**
- 本 change 不将 `moneyflow` 并入 `pams_ohlcv_daily_v2` 主表。
- 本 change 不要求 `turnover_rate_f/free_share/volume_ratio` 升格为硬字段。
- 本 change 不处理 `CN_INDEX`。
- 本 change 不直接切换 `V10.1` 默认运行时数据源。

## Decisions

### D1: 将“数据库补全”与“总体重建”拆成独立 change

选择：
- 新开 `complete-pams-ohlcv-daily-v2-database`

原因：
- 之前的 `rebuild-pams-ohlcv-daily-v2-from-security-master` 更偏总架构和 shadow 方向。
- 当前需要单独约束数据库成功条件，否则实现阶段仍然会反复回到“补哪些字段算修好”的争论。

备选：
- 直接继续改旧 change。未选，因为会把总体架构和数据库补全门禁混在一起，scope 过大。

### D2: 用应有网格而不是 raw observed rows 作为正式主表边界

选择：
- `pams_ohlcv_daily_v2` 以 `pit_security_master x trade_cal(open days)` 生成应有网格。
- 用 `daily` 决定 `traded`，用 `suspend_d` 决定 `suspended`。
- 无法解释的应有行记为 `eligible_no_source`，视为构建失败。

原因：
- 用户已经接受 `v2` 的目标是零行缺口，继续沿用“只按 observed rows 落主表”不可能满足这个目标。
- 只要 `suspend_d` 可用，就应把停牌和源缺失拆开。

备选：
- 继续只按 `raw daily` 落主表。未选，因为它无法达成零行缺口。

### D3: 硬字段只保留价格主字段和 `turnover_rate`

选择：
- 将 `turnover_rate` 升格为唯一 `daily_basic` 硬字段。
- `turnover_rate_f, volume_ratio, float_share, free_share, circ_mv` 暂时保留为软字段。

原因：
- `turnover_rate` 既有 `Tushare daily_basic`，又有 `AkShare stock_zh_a_hist` 可补，具备硬字段条件。
- 其余字段缺少等价历史补源，强行升格会让主表再次受制于源缺失。

备选：
- 把全部 `daily_basic` 字段都升格为硬字段。未选，因为当前源能力不支持。

### D4: `AkShare` 只作为有限补源和审计源

选择：
- `AkShare stock_zh_a_hist` 仅用于补 `turnover_rate`
- `AkShare stock_share_change_cninfo` 仅用于 `float_share` 事件审计或规则补算

原因：
- `AkShare` 没有等价于 `daily_basic` 的全历史日频全字段面板。
- `AkShare stock_individual_fund_flow` 只有近 120 个交易日，不可能承担全历史资金流主源。

备选：
- 用 `AkShare` 替代 `Tushare` 作为 `daily_basic` 或 `moneyflow` 主源。未选，因为事实不成立。

### D5: `moneyflow` 坚持侧表治理，不进入主表成功定义

选择：
- `moneyflow` 仅维护 `pit_stock_moneyflow_v2`
- 以 `v2` 主表主键对齐
- 通过覆盖率白名单管理研究使用

原因：
- `moneyflow` 历史缺口和空值是结构性的，不适合进入主表硬合同。
- 继续把它和主表修复绑在一起，会让数据库永远达不到“修好”状态。

备选：
- 直接把 `moneyflow` 并入主表。未选，因为会把结构性缺口引入主表。

### D6: 升格门禁必须数据库化

选择：
- 用逐日审计表、异常表和 `v1/v2` 差异审计表来决定是否允许升格为 shadow 数据源

原因：
- 如果不把门禁写成可查询、可回放的数据库对象，最终还是会回到口头判断。

备选：
- 只输出 CSV 报告。未选，因为不能形成数据库层的正式门禁。

## Risks / Trade-offs

- [Risk] 应有网格扩大后，`eligible_no_source` 可能比预期更多
  - Mitigation：先全历史跑审计，不直接切运行时；把异常分为停牌缺失、源缺失和证券边界异常

- [Risk] `AkShare` 属于网页抓取类补源，稳定性弱于 `Tushare`
  - Mitigation：只将其用于 `turnover_rate` 补源和股本事件审计，不承担主源责任

- [Risk] 软字段长期不升格，可能让部分研究继续面对空值
  - Mitigation：先把主表成功条件压缩到可证明实现的集合，再单独推进软字段升格 change

- [Risk] `v1/v2` 差异可能很大，容易被误判为构建错误
  - Mitigation：强制输出逐日差异和样本明细，区分覆盖修复与构建错误

## Migration Plan

1. 新增 `v2` 所需 raw 表、主表、侧表、审计表 DDL。
2. 回填 `trade_cal, stock_basic, daily, adj_factor, daily_basic, suspend_d, stk_limit, moneyflow` 到正式时间窗口。
3. 生成 `eligible_symbol_date_grid`，构建 `pams_ohlcv_daily_v2`。
4. 用 `Tushare` 主源和 `AkShare` 补源补齐 `turnover_rate`，并按规则补算允许的字段。
5. 构建 `pit_stock_moneyflow_v2`，生成逐日审计和异常明细。
6. 运行三窗口全历史审计，得到是否可升格的正式结论。
7. 通过门禁后，再由独立 change 或独立任务决定是否接入 shadow config。

回退策略：
- DDL 回退：删除 `v2` 新表与索引，不动 `v1`
- 数据回退：保留 raw 表，允许重新构建
- 运行时回退：不接入 shadow config 即可

## Open Questions

- `trade_cal` 是否直接使用现有 `pit_trade_cal` 扩容，还是单独建立 `raw_tushare_trade_cal` 与 `pit_trade_cal_v2`
- `limit_up/down` 的规则兜底是否需要把 `pit_st_history` 与板块规则固化成独立 helper 表
- `soft_field_null_after_build` 是否需要拆成逐字段 issue_type，还是先统一异常类型
