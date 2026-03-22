# `V2` Source Matrix

## 1. 目的

这份矩阵用于约束 `V2` 的主源、补源、审计源和适用阶段边界，避免在回填、审计、runtime compat 中再次出现“字段能拿到但来源不清”“零值补平但不可解释”的问题。

适用对象：
- `pams_ohlcv_daily_v2`
- `pit_stock_moneyflow_v2`
- `pams_ohlcv_daily_v2_audit_daily`
- `pams_ohlcv_daily_v2_exceptions`

## 2. 交易所与阶段划分

正式划分：
- `SH`：上交所
- `SZ`：深交所
- `BJ pre-2021-11-15`：`bj%` 历史映射阶段
- `BJ post-2021-11-15`：北交所正式开市阶段

约束：
- `BJ pre-2021-11-15` 不得直接按“北交所正式数据源缺失”解释
- `BJ post-2021-11-15` 才能按正式北交所覆盖问题治理

## 3. 数据源角色

定义：
- 主源：默认第一真值来源，优先写入 canonical
- 补源：主源缺失时可用的免费补源
- 审计源：不直接写 canonical 主值，但用于交叉验证、coverage 审计或异常回放

## 4. 字段矩阵

| 字段/能力 | 主源 | 补源 | 审计源 | 适用阶段 | 当前判断 |
|---|---|---|---|---|---|
| `trade_cal` | `Tushare trade_cal` | 无 | `SSE/SZSE/BSE` 官网日历/规则页 | 全阶段 | 主源足够 |
| `security master` | `pit_security_master` | `巨潮资讯`、交易所公告 | `SSE/SZSE/BSE`、`中证` 公告 | 全阶段 | 现有主数据可用，但 `BJ pre-2021-11-15` 需 lineage 治理 |
| `daily OHLCV` | `Tushare daily` | `AkShare stock_zh_a_hist` | 交易所官网历史资料 | `SH/SZ`、`BJ post-2021-11-15` 优先 | 主源可用；`BJ pre-2021-11-15` 不可直接视为正式北交所行情 |
| `adj_factor` | `Tushare adj_factor` | 无正式补源 | 与 `close` 链、分红送配事件交叉核 | 全阶段 | 主源可用，但须保留来源与低可信回填标记 |
| `daily_basic.turnover_rate` | `Tushare daily_basic` | `AkShare stock_zh_a_hist` | 无 | `SH/SZ`、`BJ post-2021-11-15` | 最值得补源的字段 |
| `daily_basic.turnover_rate_f` | `Tushare daily_basic` | 无稳定免费补源 | 无 | 全阶段 | 软字段，只保留审计 |
| `daily_basic.volume_ratio` | `Tushare daily_basic` | 无稳定免费补源 | 无 | 全阶段 | 软字段，只保留审计 |
| `daily_basic.float_share/free_share/circ_mv` | `Tushare daily_basic` | `巨潮资讯` 事件型股本数据、公式推导 | 无 | 全阶段 | 需要 source/confidence 表达 |
| `suspend_d` | `Tushare suspend_d` | 无 | 交易所停复牌公告 | 全阶段 | 有源时可确认为 `suspended_confirmed` |
| `stk_limit` | `Tushare stk_limit` | 规则推导 | 交易所制度规则 | 全阶段 | 主源可用，推导只做兜底 |
| `moneyflow` | `Tushare moneyflow` | 无全历史免费补源 | `东方财富`、`AkShare` 近端核验 | 全阶段 | 只做侧表，不进主表硬合同 |
| `公司沿革/股本变动` | `巨潮资讯` | 无 | 交易所公告 | 全阶段 | `BJ pre-2021-11-15` 治理重点 |
| `PIT 指数样本调整审计` | 无直接主源 | 无 | `中证指数` 官网/公告 | 全阶段 | 审计源，不进主表 |

## 5. 当前正式结论

### 5.1 可以作为 `V2` 主源的免费数据

- `Tushare`

### 5.2 应优先接入的免费补源

- `AkShare`
  - 重点字段：`turnover_rate`
  - 重点用途：`daily_basic` 补核、`BJ post-2021-11-15` 覆盖测试
- `巨潮资讯`
  - 重点字段：`float_share`、`free_share`、沿革/股本事件
  - 重点用途：`BJ pre-2021-11-15` 映射治理

### 5.3 应保留为审计源的免费数据

- `东方财富`
  - 重点用途：`moneyflow` 交叉核验
- `SSE/SZSE/BSE` 官网
  - 重点用途：规则、边界、制度与历史文件审计
- `中证指数`
  - 重点用途：PIT 样本调整审计

## 6. 使用纪律

- 不允许没有 source matrix 说明就把新字段接入 `V2`
- 不允许把补源值与主源值混写但不保留 `*_source`
- 不允许把 `BJ pre-2021-11-15` 直接按“正式北交所缺数”统计
- 不允许把 `东方财富` 直接当 canonical 主源

## 7. 后续更新规则

新增或替换数据源时，必须同步更新：
- 本矩阵
- `pams_ohlcv_daily_v2_schema_contract.md`
- 审计门禁文档
- 回填/审计 runbook
