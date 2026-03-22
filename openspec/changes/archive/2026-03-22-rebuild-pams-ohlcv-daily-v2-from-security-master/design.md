## Context

当前仓库中：
- `V10.1` 的股票日频数据源仍是 `pams_ohlcv_daily`
- 现有同步脚本 `update_pams_ohlcv_daily.py` 把 Tushare 原始抓取、`daily_basic` 字段融合、停牌补行、涨跌停计算和主表写入放在一个过程里
- `pit_security_master` 已存在，可作为证券边界
- `pit_trade_cal` 已存在，但历史覆盖只有 `2010-01-04` 到 `2026-02-13`，不足以支撑 `2007-2026` 重建
- `pit_stock_daily_basic` 与 `pit_stock_moneyflow` 已经落库，并证明相对旧主表存在系统性缺口和超出

因此，`pams_ohlcv_daily_v2` 不能继续沿用“直接抓源 -> 直接写最终表”的方式，而应拆成：
1. raw staging
2. canonical builder
3. audit
4. shadow switch

## Goals / Non-Goals

**Goals:**
- 建立 A 股日频原始 staging 层，保存 `daily`、`adj_factor`、`daily_basic`、`moneyflow`、`trade_cal` 原始口径
- 基于 `pit_security_master` 和 raw `daily` 重建 `pams_ohlcv_daily_v2`
- 在 `v2` 上对齐 `daily_basic` 字段，并单独维护 `pit_stock_moneyflow_v2`
- 输出原始覆盖率、主表构建覆盖率、异常样本和 `v1/v2` 差异审计
- 通过 shadow 配置让 V10.1 可以平行验证 `v2`

**Non-Goals:**
- 本轮不直接替换现有 `pams_ohlcv_daily`
- 本轮不把 `moneyflow` 并入主表 schema
- 本轮不在没有显式停牌原始源的前提下大规模合成停牌行
- 本轮不修改 baseline 默认运行时合同和默认配置

## Decisions

### D1: 采用 raw staging -> canonical build，而不是直接重写最终表

选择：
- 新增 raw 表，先固化 Tushare 原始返回
- 再从 raw 表构建 `pams_ohlcv_daily_v2`

原因：
- 满足“可信、可审计、可复现”
- 避免再次把抓取异常、限流、字段缺失直接固化到最终主表
- 允许后续重放某一批次、比较源漂移和重建差异

备选：
- 继续写一条 direct-to-final 脚本。未选，因为这会复制 `v1` 的结构性问题。

### D2: `pams_ohlcv_daily_v2` 以 raw `daily` 观测行为主，不以 `security master x trade_cal` 全展开补行

选择：
- 主表行来源只接受 raw `daily` 观测到的交易行
- `security master` 用于过滤合法证券、识别异常和统计应有覆盖，不直接强制生成每个日期的落库行

原因：
- 目前仓库没有可靠的停牌原始层
- 只凭“某日没有 daily”就补停牌行，会混淆源缺失和真实停牌
- 运行时已能按交易日历对缺行做停牌视图补齐

备选：
- 直接按在册证券全集补停牌行。未选，除非后续补齐 `suspend_d` 或等价停牌原始源。

### D3: `daily_basic` 继续并入主表，`moneyflow` 保持 v2 侧表

选择：
- `turnover_rate* / volume_ratio / share / circ_mv` 继续作为主表字段
- `moneyflow` 独立为 `pit_stock_moneyflow_v2`

原因：
- 当前运行时 schema mapping 已直接消费 `turnover_rate*`
- `moneyflow` 覆盖和空值问题更重，不适合作为主表硬合同
- 主表保持“价格 + 流动性基础字段”，资金流走侧表更清晰

备选：
- 两者都放进主表。未选，原因是 schema 膨胀且会污染主消费合同。

### D4: `pams_ohlcv_daily_v2` 保持 v1 兼容列，并新增少量审计字段

选择：
- 保留 v1 的核心列名和语义
- 额外新增 `ts_code`、source presence 标记、`build_run_id`、`build_version`

原因：
- 便于后续 shadow 切换
- 便于从 `symbol` 追溯到原始 `ts_code`
- 额外元字段不会破坏现有 schema mapping

### D5: Phase 1 只覆盖 `CN_A`，不强行把 `CN_INDEX` 混进 v2 主表

选择：
- `pams_ohlcv_daily_v2` 的重建范围先限定在 `CN_A`
- `CN_INDEX` 继续由 `pit_index_daily` 承担

原因：
- 当前配置已经 `prefer_index_table=true`
- `allow_cn_index_in_stocks_table=false`
- 先把核心问题收敛在股票主表重建，避免一次改动跨两个市场口径

备选：
- 同时重建 `CN_INDEX`。未选，原因是扩大范围但不提升当前主问题的解决度。

### D6: v2 必须内建三层审计

三层分别是：
- raw 层覆盖审计：交易日、证券边界、抓取成功率
- canonical 层构建审计：主表落行数、过滤数、异常数
- `v1/v2` 差异审计：逐日行数、关键字段空值率、样本差异

原因：
- 没有审计，v2 只是另一张更大的表，不是更可信的表

## Risks / Trade-offs

- [Risk] `pit_trade_cal` 当前不完整，无法直接作为 2007-2026 日期骨架
  → Mitigation：把 trade_cal 原始落地纳入 v2 前置步骤，并将 `pit_trade_cal_v2` 或 raw trade_cal 视为构建依赖。
- [Risk] 没有停牌原始层时，缺行既可能是停牌也可能是源缺失
  → Mitigation：Phase 1 不合成停牌行，只记录 `eligible_missing_daily` 异常。
- [Risk] raw staging 显著增加存储和运维复杂度
  → Mitigation：按 `trade_date` 分区，优先保留必要字段和 source run metadata。
- [Risk] `v2` 与 `v1` 行数差异很大，容易被误判为 bug
  → Mitigation：强制输出 `v1/v2` 差异审计与样本，区分“覆盖修复”与“构建错误”。
- [Risk] 直接切换到 `v2` 会改变历史股票池和回测口径
  → Mitigation：先用 shadow 配置平行验证，默认配置不动。

## Migration Plan

1. 新增 raw staging 表和 `pams_ohlcv_daily_v2` / `pit_stock_moneyflow_v2` / 审计表 DDL。
2. 增加 `pit_trade_cal` 补齐或 `raw_tushare_trade_cal` 落地步骤，先解决 `2007-2026` 日期骨架。
3. 先回填 raw 历史数据，再跑 canonical builder 生成 `v2`。
4. 输出 `v1/v2` 差异产物，并在三窗口跑 shadow regression。
5. 只有在审计与回归都通过后，才允许新增 `pams_cn_pg_v2.json` 作为可选运行配置。

回退策略：
- 结构层回退：删除 `v2` 表与 raw staging，不影响 `v1`
- 运行层回退：不使用 shadow 配置即可
- 数据层回退：保留 raw staging 和 audit 产物，允许按批次重建 `v2`

## Open Questions

- 是否要在 Phase 1 就引入 `suspend_d` 原始层，还是先只记录 `eligible_missing_daily`？
- `pams_ohlcv_daily_v2` 是否需要物理分区，还是先普通表 + 索引，等 shadow 回归后再分区？
- `moneyflow_v2` 是只对齐到 `v2` 主表主键，还是同时保留 raw-only 异常明细表？
- `pams_cn_pg_v2.json` 是否单独维护，还是在现有配置编译链中支持 shadow override？
