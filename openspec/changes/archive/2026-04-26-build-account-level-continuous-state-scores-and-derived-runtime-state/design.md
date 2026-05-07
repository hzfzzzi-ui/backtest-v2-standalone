## Context

当前平台已经启动 stock alpha 因子目录和日频快照的第一条 change，但账户层状态仍主要由离散状态机和局部规则驱动。这样会带来三个问题：一是状态研究必须依附完整策略回放，二是状态解释和运行合同难以分层，三是后续多资产扩展时很难复用统一的分数面。第二条 change 需要先把账户层状态研究面正式化：连续状态分数是研究真相，离散状态只是解释产物。

## Goals / Non-Goals

**Goals:**
- 定义账户层连续状态分数目录，首版收敛为 `risk_on_score`、`recovery_score`、`defense_score`。
- 定义账户层日频状态分数快照、离散解释状态快照和最小来源链路字段。
- 提供单分数与组合分数研究入口，使状态研究可以脱离完整 runtime 原生运行。
- 明确连续分数到离散解释状态的映射合同，解释状态首版固定为 `BULL / TRANS_UP / TRANS_DOWN / RISK_OFF`。
- 保持研究层与执行层分离，不让本次 change 直接改变正式主线行为。

**Non-Goals:**
- 不修改当前正式 runtime 默认消费逻辑。
- 不修改账户预算映射、交易执行路径和 ETF/stock 预算分配。
- 不在本次 change 中引入更多状态或多层级状态体系。
- 不解决第二阶段的 runtime 接线问题。

## Decisions

### 1. 先做 account-level score，不同时做 stock-level / etf-level score
原因：当前目标是先把账户层状态研究面稳定下来，避免同时维护多套分数口径。后续如果需要组件级分数，应建立在账户层合同稳定之后。

备选方案：同步做组件级状态分数。
不选原因：会显著扩大字段、快照、研究入口和解释合同的范围，当前不利于归因。

### 2. 连续分数是主真相，离散状态是解释产物
原因：你已经明确希望“连续分数为主，离散状态为解释层产物”。因此首版设计里，`effective_state` 只能由状态分数映射而来，而不是反过来由离散状态机生成连续分数。

备选方案：保持离散状态机为主、连续分数仅作 diagnostics。
不选原因：会继续保留当前规则耦合问题，达不到平台因子化目标。

### 3. 状态研究入口独立于完整策略回放
原因：状态研究应支持单分数和多分数组合研究，最小输入只依赖状态分数快照，不要求先构造完整策略行为。这样可以把研究速度、可解释性和可审计性拉高。

备选方案：只在 unified runtime 中顺带输出状态分数。
不选原因：仍会把研究口径绑定到执行口径，不利于隔离验证。

### 4. 首版分数快照字段保持最小集合
首版快照至少包含：
- `date`
- `score_id`
- `scope`
- `raw_value`
- `normalized_value`
- `availability_flag`
- `asof_timestamp`
- `source_trace`
- `derived_state`

原因：先保证可审计和可解释，再扩展更复杂的贡献拆解字段。

备选方案：一开始就加入完整 factor lineage / component contribution matrix。
不选原因：范围过大，会拖慢第二条 change 落地。

## Risks / Trade-offs

- [风险] 连续分数定义过早收死，后续 runtime 接线时需要回改 → [缓解] 首版只固定 3 个 score，并在 spec 中明确这是研究层首版合同。
- [风险] 研究入口和未来 runtime score 合同脱节 → [缓解] 统一使用 `catalog + snapshot + study surface` 三层结构，为第三条 change 预留直接消费接口。
- [风险] 状态解释映射被误当成正式主线状态机切换 → [缓解] 在 spec 和说明中明确“derived runtime state”仅代表研究层派生产物，不默认替换正式 runtime。
- [风险] 快照字段过少影响后续归因 → [缓解] 保留 `source_trace` 和 `asof_timestamp` 两个最低必要审计字段，后续增量扩展而不是首版一次做满。

## Migration Plan

1. 先落地 score catalog、score snapshot、study surface 三个新能力。
2. 使用 focused tests 和最小研究样例验证产物闭环。
3. 本次 change 不修改主 runtime 默认逻辑，因此不需要主线迁移。
4. 若后续验证失败，直接回退新增研究模块、示例 study 和测试即可，不影响当前正式回测口径。

## Open Questions

- `source_trace` 首版是否只记录组件来源与输入窗口，还是需要记录更细的公式版本号。
- 连续分数的标准化方式是否统一为 `[0, 1]`，还是允许保留某些原始区间分数。
- 第三条 change 接 runtime 时，是否允许离散解释状态直接进入 artifacts 主输出，还是仍以 score 为主、状态为辅。
