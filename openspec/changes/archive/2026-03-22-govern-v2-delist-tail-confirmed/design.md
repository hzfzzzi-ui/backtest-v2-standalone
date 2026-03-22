## Context

前一轮治理已经把大部分“有侧证据但缺主证据”的 `SH/SZ/BJ post` 行从 `source_unresolved` 收敛到 `synthetic_gap_fill`。剩余 `eligible_no_source` 的主体已经变成两类：

- `list_status='D'` 且存在 `delist_date` 的正式退市尾段
- 少量证券代码变更后的旧代码退役尾段，例如 `300114 -> 302132`

这两类都不是普通“源失败”。如果继续把它们当成 `missing_in_all_sources`，canonical gate 会持续被错误阻塞；但如果直接记成 `suspended_confirmed`，又会把正式终止边界伪装成停牌。

## Goals / Non-Goals

**Goals**

- 为退市尾段和代码变更退役尾段引入正式、可审计的终止边界治理。
- 让 canonical 明确表达 `delist_tail_confirmed`，并与 `source_unresolved`、`synthetic_gap_fill` 区分。
- 保持 runtime 默认消费口径不放宽，终止边界尾段继续被 runtime 排除。
- 用最小改动清掉剩余真无源里的“终止边界误判”部分。

**Non-Goals**

- 不把 `delist_tail_confirmed` 直接并入 runtime 可消费集合。
- 不把所有旧代码问题泛化成自动启发式映射。
- 不在本次变更里重做 `pit_security_master` 的全量刷新逻辑。
- 不修改 `baseline_V10.1 / V10.2` 的策略行为或执行口径。

## Decisions

### 1. 新增 `delist_tail_confirmed` 行状态，而不是复用 `suspended_confirmed`

决策：

- canonical 新增 `delist_tail_confirmed`
- 仅用于“正式终止边界已知，但对应交易日没有 `daily/suspend_d` 原始源”的尾段记录

原因：

- 它不是正常停牌
- 也不该继续算作普通 `source_unresolved`
- 单独状态可以保留审计可解释性，同时不污染 runtime

### 2. 终止边界必须来自显式证据，不能靠宽松启发式推断

终止边界只允许来自以下来源之一：

- `pit_security_master.delist_date`
- `pit_security_symbol_lineage` 中显式维护的代码变更退役边界，例如 `phase_type='cn_code_transition'`

额外约束：

- 该行必须原本会被分类为 `source_unresolved`
- `trade_date` 必须位于“最后一个原始源日期之后，到正式终止边界当日之前/当日”
- 不能存在同代码更晚的原始 `daily/suspend_d/daily_basic/adj_factor/stk_limit/moneyflow` 证据

### 3. `300114 -> 302132` 按“代码变更退役尾段”处理，不并入 delist 启发式

决策：

- `300114` 的旧代码尾段不走退市启发式
- 用显式代码变更边界治理：
  - 旧代码 `300114` 终止于 `2025-02-14`
  - 新代码 `302132` 自 `2025-02-17` 起启用

原因：

- 这是正式证券代码变更，不是普通退市
- 已有官方公告能提供明确边界
- 如果混进退市尾段规则，会把“主体延续但代码变化”的情形和“主体退市”混淆

### 4. Audit 与 runtime 必须把 `delist_tail_confirmed` 单列

决策：

- `eligible_no_source_rows` 只统计真 `source_unresolved`
- `delist_tail_confirmed` 单列统计与异常
- runtime exclusion breakdown 新增 `row_status_delist_tail_confirmed`

原因：

- canonical gate 要反映真无源缺口
- runtime gate 要保持排除，但不能把它错记成 `runtime_eligible`

## Implementation Plan

1. 扩展 canonical 分类逻辑，预先加载：
   - 每个 symbol 的最后原始证据日期
   - 显式代码变更退役边界
2. 在 `_classify_row_status` 前后新增终止边界判断：
   - 原本会落为 `source_unresolved`
   - 且满足终止边界条件
   - 则改记为 `delist_tail_confirmed`
3. 为 `delist_tail_confirmed` 记录独立 exception，而不是 `eligible_no_source`
4. 更新 audit 汇总和 runtime exclusion breakdown
5. 更新 SQL 合同、文档和单测
6. 重跑受影响 symbol slice 与 full-window audit

## Risks / Trade-offs

- 如果 `delist_date` 或代码变更终止边界本身错了，会把真实缺源误洗成终止尾段。
- 引入新状态后，所有依赖 `row_status` 的汇总和 runtime 过滤都必须同步更新，否则会出现“主表已变、审计没跟上”的假通过。
- 这次仍然不会把终止尾段放进 runtime，可审计性优先于表面覆盖率。

## Migration Plan

1. 先保留现有 runtime 过滤口径不变。
2. 扩展主表 `row_status` 合同，允许 `delist_tail_confirmed`。
3. 对受影响 symbol 做定向 rebuild：
   - `sz000805, sz000787, sh600286, sz000583, sh601268, sz000699`
   - 以及 audit 样本中的单日尾巴
4. 重跑 full-window audit，确认：
   - `eligible_no_source_rows` 下降
   - `delist_tail_confirmed_rows` 单列出现
   - runtime 默认行集不扩大

## Rollback

- 撤回 `delist_tail_confirmed` 分类逻辑和 SQL 合同扩展。
- 按受影响 symbol 重新跑 canonical slice rebuild。
- 重跑 audit，验证 `delist_tail_confirmed` 回到 `source_unresolved`。
