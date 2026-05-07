## Context

当前 formal ETF Phase 1 已经在 contract 层具备三桶配置语义：`equity_core_bucket`、`defense_tilt_bucket`、`cash_buffer_bucket`，并且原始文档明确要求 `RISK_OFF` 采用“缩减权益 + limited defense + cash buffer”的过渡语义。但现行 provider 仍保留基于五状态硬编码 `slot_cap` 的边界表，并在 `slot_cap <= 0` 时直接短路为 `NO_TRADE`。这使 formal mainline 同时存在两套边界定义：文档/contract 的配置边界，以及 provider 的状态退出边界。

这不是单点 bug，而是正式语义和执行边界错位：一旦继续在实现层直接放开 `TRANS_DOWN` 或 `RISK_OFF` 的槽位，容易把本轮从“formal 对齐”滑向“新承接策略研究”。因此需要先用一条 L3 设计把 formal Phase 1 的 boundary source of truth、执行阻断条件和审计输出边界讲清楚。

## Goals / Non-Goals

**Goals:**
- 让 formal ETF Phase 1 的本地 deployability 明确服从原始文档的三桶配置语义，而不是服从遗留 `_STATE_SLOT_CAPS` 硬编码。
- 明确 `RISK_OFF` 在 formal Phase 1 中默认仍是“可缩减配置状态”，而不是默认 `NO_TRADE`。
- 明确只有 Governor 的显式执行阻断信号，例如 `allow_new_risk=false` 或 `force_deleveraging=true`，才能把 formal Phase 1 压成零买入或零配置。
- 让 research audit 和 formal ETF 产物能清楚区分“Governor 上游边界”和“ETF 本地 boundary 决策”。

**Non-Goals:**
- 不改变 ETF 正式资产池与 limited defense 范围。
- 不引入新的 `controlled_accumulation_mode`、`light_accumulate` 或 `TRANS_DOWN` 承接研究口径。
- 不修改上游 `market_regime_engine`、Governor 主预算公式或 canonical 五状态定义。
- 不做收益优化，不在本轮研究行业 ETF、fallback 资产扩展或 unified runtime 配比。

## Decisions

### 决策 1：formal Phase 1 的本地 boundary 真相以 Governor budget + execution flags + 三桶语义为准

选择：
- formal Phase 1 的本地 deployability 以 Governor 下发的 `requested_budget`、执行 flags 与三桶配置结果为主真相。
- `_STATE_SLOT_CAPS` 不再作为 formal Phase 1 是否 `NO_TRADE` 的唯一或最高优先级判据。

原因：
- 原始文档明确定义 ETF 只消费统一状态与统一预算，再在本地做三桶配置。
- 当前 contract 已经表达 `TRANS_DOWN / RISK_OFF` 的三桶模板；继续由 `_STATE_SLOT_CAPS` 直接归零，会让 contract 语义失效。

备选但不采用：
- 继续保留 `_STATE_SLOT_CAPS` 作为 formal Phase 1 主边界。
  - 否决原因：会维持两套互相冲突的正式真相。

### 决策 2：`RISK_OFF` 在 formal Phase 1 中是缩减配置状态，不是默认零配置状态

选择：
- 当 Governor 仍下发正预算且未显式禁止新风险时，`RISK_OFF` 允许 formal Phase 1 生成 reduced `targets`，其中权益低配、防守和现金占比提高。
- 当 Governor 显式要求去风险时，formal Phase 1 才允许表现为零买入、减仓优先或纯现金缓冲。

原因：
- 这与原始文档中 `RISK_OFF` 的正式建议语义一致。
- 这样可以把“状态偏弱”和“执行被硬阻断”区分开，避免再把所有零交易都错误归咎于上游。

备选但不采用：
- 直接把 `RISK_OFF` 固定成 `slot_cap=0`。
  - 否决原因：与正式文档冲突，且让 limited defense candidate 失去存在意义。

### 决策 3：`TRANS_DOWN` 的受控承接不纳入本 change

选择：
- formal Phase 1 在本 change 中只修正文档对齐，不引入新的 `controlled_accumulation_mode`。
- `TRANS_DOWN` 是否允许受控承接、允许到什么暴露带，留给后续独立研究 change。

原因：
- 当前 formal alignment 仍将非 `none` 的 `controlled_accumulation_mode` 视为超出 formal Phase 1 语义。
- 如果本轮同时放开 `TRANS_DOWN` 承接，就无法区分“formal 对齐修复”和“新策略研究”。

备选但不采用：
- 本轮同时把 `TRANS_DOWN` 改成 `slot_cap=1` 或直接开放轻仓承接。
  - 否决原因：会把 L3 修复和新研究变量绑在一起。

### 决策 4：审计层必须显式拆分上游边界与下游本地 boundary

选择：
- formal ETF 产物与 `research_audit` 必须同时输出：
  - Governor 下发的预算/执行边界证据
  - ETF 本地 boundary 决策证据
- 当出现零部署或严重部署不足时，审计必须能判断这是“Governor 压制”还是“ETF 本地 boundary/contract 选择”。

原因：
- 如果不拆这两层，后续仍会把本地状态短路误标成 Governor 真相。
- 这与项目的“可审计、可解释、可复现”原则一致。

备选但不采用：
- 只保留统一的 budget reason codes。
  - 否决原因：不足以定位 formal contract 与执行边界之间的偏差。

## Risks / Trade-offs

- [风险] formal Phase 1 对齐后，`RISK_OFF` 交易数和仓位利用率可能上升，导致回撤行为发生变化。 → 缓解：本轮只要求语义对齐与证据可解释，必须通过单测和 formal study 对照说明行为差异。
- [风险] 实现时容易顺手把 `TRANS_DOWN` 承接一起放开。 → 缓解：spec 显式把 controlled accumulation 排除在本 change 之外，并在测试中锁定 formal profile 的 `controlled_accumulation_mode=none`。
- [风险] 旧研究分支可能仍依赖 `_STATE_SLOT_CAPS` 语义。 → 缓解：本 change 仅约束 formal Phase 1 profile，不要求研究 profile 同步对齐。
- [风险] 审计字段增加后，产物消费者可能误把新字段当成新的上游真相。 → 缓解：字段命名必须明确区分 `governor_boundary` 与 `local_boundary_decision`。

## Migration Plan

1. 先在 OpenSpec 中为 `cn-etf-beta-sleeve` 和 `backtest-research-audit` 补齐 formal boundary 对齐要求。
2. 实现阶段只修改 formal Phase 1 contract/provider 的 boundary 选择顺序与审计字段，不改资产池和上游 Governor 预算公式。
3. 增加单测，覆盖 `RISK_OFF` 正预算、显式风险阻断、`TRANS_DOWN` 仍不开放 controlled accumulation 等场景。
4. 重跑 formal ETF study，对比旧实验与新实验的 `total_exposure_cap`、`requested_budget`、`targets`、交易数和 audit 解释差异。
5. 若结果不可接受，可回退 formal Phase 1 boundary 分支与新增审计字段，不影响 ETF 资产池和 Governor 主逻辑。

## Open Questions

- formal Phase 1 的“显式风险阻断”最小集合是否只包括 `allow_new_risk=false` 与 `force_deleveraging=true`，还是还需要纳入其他 Governor execution flags。
- `RISK_OFF` 对齐后，formal Phase 1 是否允许 limited defense candidate 在非 rebalance 日仅做持仓维持，而不是生成新买入。
