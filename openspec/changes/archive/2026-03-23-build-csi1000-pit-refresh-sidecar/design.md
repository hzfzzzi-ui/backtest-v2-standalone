## Context

当前 `CSI1000` 链路由三段组成：

- `fetch_csi1000_pit_by_calendar.py` 按调样日历抓 `Tushare index_weight` 或静态 fallback，生成 snapshots 与 changes CSV。
- `build_csi1000_pit_from_manual_snapshots.py` 在人工快照路径上做同样的“快照 -> 区间变更”重建。
- `import_csi1000_pit.py` 只导入 `changes.csv`，对 `pit_index_constituents(index_code='000852.SH')` 做全量替换。

这条链有两个结构性问题：

- 数据库只保留区间真值，不保留 refresh 级证据，导致零差异 refresh 和非 PIT refresh 日期会在导入后丢失。
- `Tushare index_weight(000852.SH)` 当前最早可验证日期是 `2015-07-31`，而不是 `2012-01-01`；如果继续只看区间表，很容易把 `2012-2015` 的无覆盖空窗误读成“正式历史已补齐”。

## Goals / Non-Goals

**Goals:**

- 为 `CSI1000` 新增 refresh 级侧表，记录每个 refresh 日期下的 constituent snapshot 以及它映射到哪条主 PIT 区间行。
- 保留 scheduled、ad_hoc 和零差异 refresh 事件，不让它们在导入后消失。
- 在导入摘要和 membership audit 中显式暴露 `Tushare` 覆盖下限，禁止把 `2012-2015` 误标为 formal PIT。
- 保持 `pit_index_constituents` 继续作为 resolver 的区间真值表，避免一次任务同时改主消费路径。

**Non-Goals:**

- 本 change 不新增 `2012-2015` 的外部正式源，也不伪造该时间段 PIT 数据。
- 本 change 不改 `CSI1000` resolver 的核心过滤逻辑；resolver 仍从 `pit_index_constituents` 读取历史区间。
- 本 change 不把 `CSI1000` 直接升格为 baseline 正式主线，只补齐 refresh 证据和审计真相。

## Decisions

### 1. 新增 refresh 侧表，但不把区间真值拆出主表

采用一张新的侧表 `pit_index_constituent_refresh_membership`（命名可在实现时微调，但语义不变），每行代表：

- `index_code`
- `refresh_date`
- `symbol`
- `constituent_start_date`（指向主表区间起点的自然键）
- `source`
- `event_type`
- `snapshot_trade_date`
- `rebalance_calendar_version/source/generated_at`
- `created_at`

理由：

- 用户要求的是“每个 PIT 刷新日期时存一份当前日期下股票代码索引到主表即可”，这天然是 sidecar，不应反向污染主区间表。
- 主表 `pit_index_constituents` 继续承担 resolver 真值，不需要因为 refresh 侧证据而改消费合同。
- 零差异 refresh 在主表中不会产生新 `start_date`，但在侧表中仍可保留成分清单和事件证据。

备选方案：

- 方案 A：直接把每个 refresh 展平成主表新行。放弃，因为会破坏当前区间语义，导致 resolver 和 audit 全面重写。
- 方案 B：只把 refresh summary 写 JSON，不落库。放弃，因为用户明确要求“建立侧表”，且 JSON 不便查询和审计。

### 2. 侧表用自然键映射主表，不引入新的 surrogate key 依赖

导入时通过 `(index_code, symbol, constituent_start_date)` 把 refresh 侧表映射到 `pit_index_constituents` 的区间行；不要求当前任务先给主表补 surrogate PK。

理由：

- 当前 `pit_index_constituents` 还没有正式主键合同，强行加 surrogate key 会把任务面扩得过大。
- 对 `CSI1000` 单指数分区，`(index_code, symbol, start_date)` 已足够表达“该 symbol 进入当前区间的那条真值行”。

备选方案：

- 方案 A：先为 `pit_index_constituents` 引入 `id BIGSERIAL` 再外键引用。放弃，因为这是更大的 DB governance 任务。

### 3. 明确把 `snapshot_trade_date` 从 `source_note` 提升为结构化字段

当前 Tushare 路径只把实际命中的 `trade_date` 塞进 `source_note`。本 change 改为在 snapshots CSV 和 refresh 侧表中显式保存 `snapshot_trade_date`。

理由：

- `source_note` 只适合人读，不适合审计或 SQL 查询。
- refresh 侧表的一个关键价值就是复原“这个 refresh 事件到底命中了哪一天的 Tushare 快照”。

### 4. 对 `2012-2015` 只做 uncovered truth，不做伪补齐

只要上游仍是 `Tushare index_weight(000852.SH)`，系统就必须把最早覆盖日视为 `2015-07-31` 左右的 provider floor；任何早于该日期的 `required_start` 都只能落为 uncovered/approximate，而不能伪装成 formal。

理由：

- 用户要求的是“从 Tushare 同步 2012-2026”，但实测 `2012` 为 `0` 行，最早有效日期是 `2015-07-31`。继续做“逻辑补齐”会违反项目的可信和可审计原则。

备选方案：

- 方案 A：把 `2012-2015` 直接前向填充成第一批成分。放弃，因为这是造数据。
- 方案 B：自动回退到静态成分补历史。放弃，因为会把 static fallback 伪装成 Tushare formal。

### 5. 导入时同时重建主表与侧表，并对零差异 refresh 继续落库

`import_csi1000_pit.py` 扩展为同时消费 `changes.csv` 和 `snapshots.csv`。导入步骤：

1. 全量替换 `pit_index_constituents(index_code='000852.SH')`
2. 基于已导入主表，对每个 snapshot row 解析所处区间
3. 全量替换 `pit_index_constituent_refresh_membership(index_code='000852.SH')`
4. 输出主表 + 侧表摘要

理由：

- snapshots 与 changes 是同一批 refresh 构造出来的，必须事务性一致。
- 零差异 refresh 只在 snapshot 路径里存在，不能等主表导完后再丢掉。

## Risks / Trade-offs

- [风险] `Tushare` 覆盖下限早于用户目标窗口，最终不能给出“2012-2026 全正式 PIT”。  
  → 缓解：在 proposal/design/spec/audit 中显式写死 uncovered truth，等待用户决定是否补别的正式源。

- [风险] 主表没有正式 PK，侧表只能依赖自然键映射。  
  → 缓解：使用 `(index_code, symbol, constituent_start_date)` 唯一表达当前任务的映射关系，并补校验测试。

- [风险] 零差异 refresh 会显著增加 sidecar 行数。  
  → 缓解：侧表只保存 refresh 日期，不扩展成每日成员表；并为 `(index_code, refresh_date)` 建索引。

- [风险] 旧 import 脚本和 summary 产物默认只认识 `changes.csv`。  
  → 缓解：保持 `changes.csv` 路径兼容，新增 `snapshots.csv` 为显式可选参数；若缺失则跳过 sidecar 导入并给结构化告警。

## Migration Plan

1. 新增 refresh 侧表 schema 和必要索引。
2. 扩展 snapshots CSV 结构，加入 `snapshot_trade_date` 等字段。
3. 扩展 import/refresh summary，在同一事务中重建主表与 refresh 侧表。
4. 扩展 membership audit，暴露 refresh event 统计与 coverage floor。
5. 对现有 `2015-2026` `CSI1000` Tushare 数据做一次 sidecar backfill。

回退：

- 删除新侧表与相关 import path，主表 `pit_index_constituents` 不受影响。
- 恢复 `fetch/import/refresh` 脚本旧参数和旧 summary 字段。

## Resolved Scope

- 用户已确认本次实现口径收敛为 `2015-2026`。
- `2015-07-31` 之前的窗口继续显式保留为 uncovered/approximate，不做前向填充或 static 伪补齐。
