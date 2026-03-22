## Context

`pams_ohlcv_daily_v2` 已完成 `2007-01-04` 到 `2026-03-16` 的全历史重建，并具备 raw staging、canonical 主表、moneyflow 侧表、审计表与 exception 表。当前主要问题不再是“表建不出来”，而是：

- canonical 主表虽然实现了硬字段空值 `0`，但存在大量 `eligible_no_source`、`turnover_rate_imputed_zero`、`pre_close_imputed_zero`。
- `BJ` 异常既包含 `2021-11-15` 之后的真实数据源覆盖问题，也包含 `2021-11-15` 之前的历史映射污染。
- `V10.1` 直接消费 `v2` 时回测显著偏离 `v1`，说明 canonical 真值底座与 legacy runtime 口径之间仍缺少兼容层。

当前约束：
- `V2` 必须继续覆盖 `SH + SZ + BJ`，不能通过排除 `BJ` 来获得“伪通过”。
- 任何治理动作都必须区分“数据库真值目标”和“策略消费兼容目标”。
- `baseline_V10.1` 仍是当前正式主线，任何切换都必须具备明确回退路径。

## Goals / Non-Goals

**Goals:**
- 建立 `V2` 的正式数据源治理框架，明确字段级主源、补源、审计源和交易所阶段边界。
- 重构 canonical 行状态与字段来源表达，使 unresolved、synthetic fill、confirmed suspend 可被可靠区分。
- 将 `BJ` 拆分为 `2021-11-15` 前后的两类治理问题，避免把历史映射污染误判为正式北交所缺数。
- 建立 canonical gate 与 runtime gate 两层升格门禁。
- 产出 `v2` runtime compatibility 层，为 `V10.1` 及后续 baseline 提供稳定消费接口。

**Non-Goals:**
- 本 change 不直接改写 `V10.1` 的主逻辑、执行时点或排序主因子。
- 本 change 不承诺一次性消灭所有 unresolved 行，而是先把 unresolved 分类、来源和消费边界治理清楚。
- 本 change 不把 `moneyflow` 升格为主表硬字段。
- 本 change 不通过删除 `BJ` 来降低审计异常。

## Decisions

### 1. 将 `V2` 明确拆成 canonical 与 runtime 两个角色

决策：
- `pams_ohlcv_daily_v2` 保持 canonical 真值底座角色。
- 新增 `v2` runtime compatibility 层，供 `V10.1` 等策略消费。

原因：
- canonical 的目标是最大化来源表达与审计能力。
- runtime 的目标是最小化策略行为漂移与低可信记录污染。
- 二者目标天然冲突，不能继续混在一张表里。

备选方案：
- 直接继续让策略吃 canonical：拒绝。事实已经证明会明显改写 `V10.1`。
- 把 canonical 做回 `v1`：拒绝。会重新丢失 `v2` 的审计价值。

### 2. 对行状态进行四元治理，而非继续使用隐式二元状态

决策：
- canonical 行状态至少区分：
  - `traded`
  - `suspended_confirmed`
  - `synthetic_gap_fill`
  - `source_unresolved`

原因：
- 当前最大质量问题不是没有行，而是“低证据补行被伪装成正常停牌行”。
- 四元状态能把“真实停牌”和“缺源补位”分开，从根上降低误用风险。

备选方案：
- 继续使用 `is_suspended + source flags` 组合表达：拒绝。表达能力不够，容易让 runtime 误消费。

### 3. 为关键字段引入 `source` / `confidence` 双标记

决策：
- 对 `pre_close`、`adj_factor`、`turnover_rate` 以及 `daily_basic` 关键衍生字段引入：
  - `*_source`
  - `*_confidence`

原因：
- 仅靠“非空”无法表达字段质量。
- 当前 `turnover_rate_imputed_zero` 已证明“填平空值”不等于“高质量字段”。

备选方案：
- 继续只保留最终值，不保留来源：拒绝。后续无法解释字段质量，也无法做 runtime gate。

### 4. 将 `BJ` 正式拆成两个治理阶段

决策：
- `BJ pre-2021-11-15` 按历史映射治理处理。
- `BJ post-2021-11-15` 按正式北交所数据源覆盖治理处理。

原因：
- 现有审计已证明 `bj%` 异常的大头发生在北交所正式开市之前。
- 不拆阶段，就会把历史映射污染误判成正式北交所数据源失败。

备选方案：
- 整体按 `BJ` 一类处理：拒绝。会混淆问题性质。
- 从正式范围排除 `BJ`：拒绝。违背数据库目标边界。

### 5. 门禁拆成 canonical gate 与 runtime gate

决策：
- canonical gate 关注“数据库底座是否可信、是否可审计”。
- runtime gate 关注“当前 baseline 是否可以安全消费”。

原因：
- `V2` 可能先成为正式 canonical engine，再晚于此成为 `V10.1` 的正式 runtime source。
- 把这两件事混成一个 gate，会让治理顺序失真。

备选方案：
- 继续只保留一个总门禁：拒绝。无法支持分阶段升格。

## Risks / Trade-offs

- [Canonical 字段和状态增加，表结构更复杂] → 通过 schema contract、source matrix 和 runbook 固化字段职责，避免语义漂移。
- [Runtime compat 层增加维护成本] → 通过显式配置选择数据角色，避免把兼容逻辑散落到策略代码中。
- [BJ 历史映射治理需要额外数据源核查] → 优先建立 source matrix 与 lineage 规则，再决定是否引入新的 fallback。
- [短期内 `V10.1` 仍需继续依赖 `v1`] → 保持回退路径，先完成 `v2` 正式 canonical 升格，再推进 runtime 切换。
- [source/confidence 治理会增加回填成本] → 先覆盖最关键字段，再按优先级扩展。

## Migration Plan

1. 固化 `v2` source matrix 与字段级主源/补源/审计源。
2. 扩展 canonical schema：新增行状态、字段来源、字段可信度、BJ 阶段标记。
3. 调整 raw -> canonical build 逻辑，使 unresolved 不再伪装成 confirmed suspend。
4. 重跑全历史 canonical build 与 audit，输出新的 canonical gate 总结。
5. 新建 runtime compatibility 层，定义 `V10.1` 可消费集合和 compat 规则。
6. 跑 `V10.1` 三窗口回归，对比 `v1`、canonical `v2`、runtime `v2`。
7. 若 runtime gate 通过，再讨论切换默认数据源。

回退策略：
- 保留 `v1` 与现有 `baseline_V10.1` 默认配置不变。
- `v2` 的 canonical/runtime 通过新表或新视图上线，不覆盖旧表。
- 任意阶段失败时，runtime 继续指向 `v1`。

## Open Questions

- `BJ pre-2021-11-15` 的 symbol lineage 是否需要单独落表，还是以字段标记即可满足治理目标？
- `turnover_rate_f`、`volume_ratio`、`free_share` 这类软字段在 runtime gate 中应否纳入硬过滤，还是只作为置信度标签？
- `V10.1` runtime compat 是否应以视图实现，还是以物化表/托管脚本实现？
