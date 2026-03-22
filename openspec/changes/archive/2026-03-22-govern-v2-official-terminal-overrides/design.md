## Context

上一轮 `delist_tail_confirmed` 已经解决了“正式终止边界已知，且缺口位于最后原始源日期之后”的尾段问题。但 `sh600680` 与 `sh601268` 仍然残留在 `source_unresolved`，原因不是缺正式边界，而是当前规则把 `adj_factor/stk_limit` 这类辅助原始源也当成 veto 条件，导致显式官方边界证据被单一启发式挡住。

这两只的形态不同于 `sh600286`、`sz000583`、`sz000699`：

- `sh600680`：只剩摘牌日 `2019-05-24` 一行 unresolved，且上交所已正式披露终止上市与摘牌时间。
- `sh601268`：`2014-05-26 ~ 2014-09-01` 为 unresolved，但上交所官方资料已确认 `2014-05-26` 暂停上市；其后 `2014-09-02 ~ 2015-05-21` 已经不是 unresolved。

因此这次更合理的做法不是继续放宽启发式，而是引入一份显式、范围极窄的官方 override。

## Goals / Non-Goals

**Goals**

- 用最小改动收掉 `sh600680` 与 `sh601268` 中已被官方证据覆盖的 unresolved 行。
- 保持规则可审计：override 必须显式列出 symbol、日期窗口和证据来源标签。
- 保持 runtime 默认过滤口径不变。
- 不影响 `sh600286`、`sz000583`、`sz000699` 这类仍缺完整证据链的 unresolved symbol。

**Non-Goals**

- 不新增宽泛的“只要有 delist_date 就都收口”的通用启发式。
- 不把辅助原始源整体从 terminal governance 判定中删除。
- 不修改 baseline、runtime 或交易逻辑。
- 不在本次改动中处理剩余三只真无源 symbol。

## Decisions

### 1. 使用显式官方 override，而不是继续放宽通用 heuristic

新增一份 symbol 级 override 元数据，字段至少包括：

- `symbol`
- `start_date`
- `end_date`
- `evidence_source`
- `evidence_kind`

首批只允许：

- `sh600680`: `2019-05-24 ~ 2019-05-24`
- `sh601268`: `2014-05-26 ~ 2014-09-01`

原因：

- 这两只已有明确的官方边界证据。
- 其 unresolved 窗口很小且可枚举。
- 显式 registry 比进一步放宽通用规则更稳。

### 2. 复用 `delist_tail_confirmed`，不再新增 row_status

虽然 `sh601268` 更像“官方暂停后到已覆盖 terminal 段前的连续空窗”，但这类记录本质上仍属于“正式 terminal boundary 已知且不应视为真无源”的集合。

继续复用 `delist_tail_confirmed` 的原因：

- runtime 已经明确排除此状态，无需再改一层 gate。
- audit 与 schema 合同已支持该状态，复用能把改动压到最小。
- 不会引入新的状态分叉和额外报表解释成本。

### 3. override 只对原本的 `source_unresolved` 生效

分类顺序保持：

1. `traded`
2. `suspended_confirmed`
3. `synthetic_gap_fill`
4. `source_unresolved`
5. 若命中显式官方 override，则把第 4 步结果改记为 `delist_tail_confirmed`

这样可以保证：

- 不会把正常 `traded/suspended_confirmed` 行误覆盖。
- 不会把已有 `synthetic_gap_fill` 行强行重分类。
- `sh601268` 只会清掉 `2014-05-26 ~ 2014-09-01` 这段 unresolved，不碰后面的 `synthetic_gap_fill`。

### 4. override 必须保留证据标签并在 exception 中显式暴露

命中 override 时，exception 仍记录为 `delist_tail_confirmed`，但 `issue_detail` 和 `source_table` 要能看出这是官方 override，而不是普通 `delist_date` 尾段。

建议：

- `cause_class = official_terminal_override`
- `source_table = evidence_source`
- `issue_detail` 写入 `start_date/end_date/evidence_kind`

### 5. runtime 不变，audit 只改统计归属

- runtime 继续排除 `delist_tail_confirmed`
- `eligible_no_source_rows` 只统计真正保留为 `source_unresolved` 的行
- full-window audit 预期只减少：
  - `sh600680`: 1 行
  - `sh601268`: 70 行

## Implementation Plan

1. 在 `pams_ohlcv_daily_v2_common.py` 增加官方 terminal override registry。
2. 在 `update_pams_ohlcv_daily_v2.py` 增加读取和判定 helper，只对 `source_unresolved` 命中 override 时改记 `delist_tail_confirmed`。
3. 补单测，覆盖：
   - `sh600680` 摘牌日 override
   - `sh601268` 官方暂停窗口 override
   - 非 registry symbol 不得命中
   - 已是 `synthetic_gap_fill` 的行不得被 override 覆盖
4. 如有必要，更新 audit 的细节输出文案，但不改 runtime exclusion 规则。
5. 定向重建 `sh600680, sh601268`，再跑 full-window audit。

## Risks / Trade-offs

- 最大风险是 override registry 被滥用，逐步演变成“手工洗数表”。
- 另一风险是 `sh601268` 的窗口定义如果写错，会把本应 unresolved 的日期洗成 `delist_tail_confirmed`。
- 这次不尝试泛化为自动规则，换来的是需要显式维护 symbol 列表，但这是有意的约束。

## Migration Plan

1. 先发布代码和测试，不改现有 runtime view 合同。
2. 仅对 `sh600680, sh601268` 做 symbol slice rebuild。
3. 重跑 full-window audit，核对 `eligible_no_source_rows` 与 symbol-top-samples。
4. 如果结果符合预期，再考虑是否需要把主 spec 同步回主干。

## Rollback

- 删除 override registry 中的两条配置。
- 回退 `update_pams_ohlcv_daily_v2.py` 中的 override 分类分支。
- 对 `sh600680, sh601268` 重新做 slice rebuild。
- 重跑 full-window audit，确认两只恢复为 `source_unresolved`。
