## Context

当前 A 股系统已经把 `market_regime_engine` 作为 Governor 的正式上游输入，但实现仍分散在多个层面：

- `weekly_five_state_engine` 仍保留一套历史五状态技术骨架。
- `regime_engine_evaluator` 已经引入 `trend / risk / breadth / participation` 四类 block 与 persistence/fallback 机制，但对外状态语义仍是内部 evaluator 视角。
- `regime_audit`、`research_audit`、`artifacts_finalize` 已经开始消费 `base_state_5 / effective_state_5 / reason_codes / subscores / manual_override` 这些字段，但其中部分仍靠后处理补齐，而不是由 regime 模块正式输出。
- `cn_a_governed_mainline` 已经把 canonical 五状态和 coarse 三状态写入 Governor contract，但引擎层和审计层还没有彻底收敛到同一套正式状态语言。

现在的真实问题不是“没有 regime engine”，而是“已有 scoring/state machine 与正式 contract 之间还存在语义缝隙”。如果不先补齐这个缝隙，后续继续推进 Governor 执行化、ETF beta、保险层和人工判断，只会放大解释链不一致的问题。

## Goals / Non-Goals

**Goals:**

- 将 `market_regime_engine` 正式收口为一个可归因、可审计、可被 Governor 稳定消费的模块 contract。
- 统一对外正式状态语言为 canonical 五状态，并保留 coarse 三状态派生视图。
- 将“五状态是真相源、三状态只是派生视图”定为后续实现与演进的硬约束。
- 明确 `base_state_* / effective_state_*` 双轨 contract，支持人工判断但不污染模型原始输出。
- 统一 block 级与 domain 级归因输出，要求 regime 输出既能回答“状态是什么”，也能回答“为什么是这个状态”。
- 明确 Governor、研究审计和结果快照只消费正式 regime payload，而不再各自猜测状态语义。

**Non-Goals:**

- 不在本 change 中引入新的黑箱分类器或重写现有趋势/风控计算核心。
- 不在本 change 中把 `market_regime_engine` 强制重构成独立服务/进程。
- 不在本 change 中直接实现宏观和情绪全量数据链，只定义它们在 Phase 1 的解释增强和弱约束位置。
- 不在本 change 中扩展 `value_bluechip_satellite`、`insurance_overlay` 或新的 ETF 资产范围。
- 不在本 change 中修改 A 股股票 `V2 canonical` 数据口径。

## Decisions

### 决策 1：正式状态 contract 统一到 canonical 五状态，内部 evaluator 可继续存在过渡语义

正式对外状态统一为：

- `BULL`
- `TRANS_UP`
- `LIGHT`
- `TRANS_DOWN`
- `RISK_OFF`

同时输出派生 coarse 状态：

- `RISK_ON`
- `NEUTRAL`
- `RISK_OFF`

保留内部 evaluator 和 legacy engine 的现有状态名，但这些状态名不得直接暴露给 Governor、research audit 或 snapshot。所有外部消费端只认 canonical 五状态。

补充硬约束：

- canonical 五状态是唯一正式状态真相源
- coarse 三状态永远只从五状态派生
- 三状态不得反向成为上游状态输入或 override 真相源

原因：

- 当前代码里同时存在 `BULL_MAIN / TURN_STRONG / LIGHT_TREND / TURN_WEAK / DEFENSIVE`、`BULL / TRANS_UP / TRANS_DOWN / BEAR` 和 canonical 五状态三套语义。
- 与其重写全部 evaluator，不如先引入统一 canonicalizer，把对外 contract 固定下来。

备选方案：

- 直接把三状态当主状态，把五状态下沉成内部细节
  - 放弃。因为 `5 -> 3` 可接受，但 `3 -> 5` 不可逆，会丢失过渡态信息并伤害 Governor、保险层和人工判断的表达力。
- 直接把内部 evaluator 全改成 canonical 五状态
  - 放弃。风险太高，会把这轮从 contract 收敛变成底层重写。
- 继续允许不同模块暴露私有状态名
  - 放弃。Governor 和前端长期会持续错位。

### 决策 2：采用“Feature Bundle -> Block Scoring -> Canonical State -> Override Merge -> Audit Payload”五层结构

`market_regime_engine` 的正式结构定义为：

1. `feature bundle`
2. `block scoring`
3. `canonical state machine`
4. `override merge`
5. `audit payload builder`

其中：

- `feature bundle` 继续由现有 `regime_engine_inputs` 负责
- `block scoring` 继续沿用 `trend / risk / breadth / participation`
- `canonical state machine` 负责 persistence / cooldown / confidence floor / canonical state 映射
- `override merge` 负责 `base -> effective`
- `audit payload builder` 负责 reason code、subscores、stability、feature availability 的正式输出

原因：

- 这五层正好对应当前代码中已经存在但未正式统一的职责。
- 先分层，再做模块抽象，能最大程度避免在实现阶段混写逻辑和审计字段。

备选方案：

- 直接在 `regime_engine_evaluator` 里持续堆字段
  - 放弃。会把 evaluator 继续变成逻辑和产物耦合点。

### 决策 3：保留四类 block 作为底层评分单元，再映射到三类解释域

底层评分单元继续使用：

- `trend_block`
- `risk_block`
- `breadth_block`
- `participation_block`

对外解释域输出：

- `technical`
- `sentiment`
- `macro_global`

映射原则：

- `technical` 是主导解释域，主要由 `trend / risk / breadth` 聚合而成
- `sentiment` 在 Phase 1 主要映射 `participation`，允许后续接入拥挤度和情绪扩散
- `macro_global` 在 Phase 1 可以为空或弱信号，但 contract 必须预留正式位置

原因：

- 当前底层 block 在代码里已经存在并可 trailing-safe 计算。
- 你未来要的“技术 / 情绪 / 宏观”更适合作为对外解释域，而不是直接替代底层 block。

备选方案：

- 直接把底层评分也改成 `technical / sentiment / macro_global`
  - 放弃。现有代码和数据准备层都不是这样组织的。

### 决策 4：manual override 采用双轨且必须留痕，优先支持“状态覆盖、预算覆盖、保险触发”三类动作

Phase 1 的 `manual_override` contract 必须至少包含：

- `active`
- `scope`
- `reason`
- `actor`
- `effective_window`

并明确支持：

- `state_override`
- `budget_override`
- `hedge_overlay`

无论哪种 override，都不得覆盖 `base_state_*`，只能影响 `effective_state_*` 或 Governor 消费的最终预算解释。

原因：

- 你的系统明确允许必要时人工判断。
- 如果不从第一天就规定双轨制，后面所有 override 都会变成不可审计黑箱。

备选方案：

- 只在 `run_meta` 里记一条注释
  - 放弃。这不构成正式 contract，也无法支持日级回放。

### 决策 5：Governor、research audit 和 snapshot 只消费正式 regime payload，不再自行拼语义

本 change 之后：

- `cn-a-portfolio-governor` 只认正式 regime payload
- `backtest-research-audit` 只审正式 regime payload 的一致性和证据链
- `results-workbench-snapshot-boundary` 只消费 formal regime 摘要

这三层不得再各自根据 `market_state`、`trade_mode` 或私有字段猜测 coarse state、state reason 或 override 语义。

原因：

- 当前这三层已经开始各自补 regime 含义，长远一定会漂。
- regime 模块必须成为唯一真相源。

备选方案：

- 继续允许 audit/snapshot 自行组装解释字段
  - 放弃。会导致 contract 表面统一、解释链实际分叉。

## Risks / Trade-offs

- **[风险] 短期内模块边界更清楚，但实现文件数会增加** → 通过新增 facade/adapter，而不是重写底层 evaluator，控制迁移成本。
- **[风险] canonical 五状态与内部四状态/历史五状态共存，会增加学习成本** → 通过明确“内部可过渡、对外只认 canonical”降低混乱。
- **[风险] `macro_global` Phase 1 信号可能为空，容易被误解成未实现** → 在 contract 中明确它是预留解释域，Phase 1 可为空但不可缺位。
- **[风险] manual override 双轨输出会增加产物复杂度** → 这是后续 Governor 和保险层可信化的必要成本，通过 snapshot 摘要控制前端展示复杂度。
- **[风险] 若下游继续偷偷消费旧字段，contract 收敛会失效** → 在 Governor、research audit、snapshot 三处同步改 spec，并在实现时增加一致性断言。

## Migration Plan

1. 先在 specs 中固化 `market-regime-framework` 的正式 contract，包括 canonical 五状态、block/domain 归因、override 双轨。
2. 同步修改 `cn-a-portfolio-governor`、`cn-a-attribution-audit`、`backtest-research-audit`、`results-workbench-snapshot-boundary` 的输入输出边界，明确它们只消费正式 regime payload。
3. 实现阶段先新增 `market_regime_engine` facade 或等价组合层，把现有 evaluator、weekly engine 和 audit payload builder 串起来，不先改底层 scoring 公式。
4. 再逐步把后处理补字段逻辑从 audit/snapshot 移回 regime 模块输出。
5. 回归验证要求：
   - A 股主线回测行为无未解释漂移
   - regime audit 的状态、切换原因、置信度、override 字段在产物中完整可追踪
   - Governor 与 research audit 不再依赖私有状态名

回退路径：

- 若新 regime contract 影响下游产物兼容，优先回退 snapshot/research audit 的新消费方式；
- 若 facade 集成导致状态行为漂移，再回退 facade 入口，保留旧 evaluator 直连链路；
- 不回滚 `V2 canonical` 数据和 `cn_etf` 数据链。

## Open Questions

- `manual_override` 的写入入口在 Phase 1 是不是仅允许内部 debug/config 注入，还是需要同时规划桌面端入口。
- `macro_global` 的第一批最小信号是否只允许商品和美元代理，还是要同时预留海外权益风险代理。
- `results-workbench` 在 Phase 1 是否需要独立 Regime 卡片，还是先只在 snapshot/summary 层暴露字段即可。
