## Context

当前正式系统里，Governor 是 `global_portfolio_governor`，且被定义为预算真相来源；ETF 只能消费 Governor 下发的 budget、exposure cap、defense bias 与 execution flags。这个边界在现有文档与代码里已经成立。

但当前 formal ETF Phase 1 仍是 `phase1_allocation_engine` 口径：它按五态三桶做预算内分配，弱市默认走 reduced allocation，不负责长期底仓积累。与此同时，仓库里存在 `CN_STOCK_ETF_50_50` 的 research combo 服务，它用固定 `0.5/0.5` 权重拼接个股和 ETF NAV，但这条路径本质上是研究装配器，不是正式 Governor 合同。

如果产品目标转成“ETF 长期 beta 稳定器”，当前设计会出现三个结构性偏差：

- Governor 只发布单层目标仓位，无法同时表达长期底仓、战术 overlay 和部署节奏。
- ETF sleeve 没有正式的 `core_accumulator / tactical_satellite / limited_defense` 角色划分，弱市只会减配，不会做受控的长期承接。
- 审计无法区分“生产级预算真相”和“research combo 假设”，容易把 50/50 装配结果误读成正式组合逻辑。

## Goals / Non-Goals

**Goals:**

- 把 Governor 正式定义为组合级风险与预算宪法，而不是单一 target 的下发器。
- 为正式 Governor 合同补齐分层预算输出：战略底仓、战术 overlay、部署节奏、硬阻断与防守偏置。
- 把 formal `cn_etf_beta` 的正式角色升级为长期 beta 稳定器，并定义弱市下的底仓保留、overlay 收缩与 paced accumulation 边界。
- 让 audit 与正式产物能够区分生产级 Governor 真相、ETF 本地决策与 research combo 假设。

**Non-Goals:**

- 不在本 change 中直接修改 current formal ETF 的 denominator 或 `hard_max_positions` 公式。
- 不在本 change 中扩大 ETF 正式资产池，不引入 bond/gold/insurance 等完整多资产防守层。
- 不在本 change 中实现最终收益优化，不承诺新定义会立即提升 CAGR。
- 不在本 change 中重写 `CN_STOCK_ETF_50_50` research combo 的 NAV 合成逻辑，只要求明确它的 research-only 身份。

## Decisions

### 决策 1：Governor 统一发布“战略底仓 + 战术 overlay + 部署节奏 + 硬阻断”四层合同

选择：

- Governor SHALL 对每个正式 sleeve 输出至少以下字段：
  - `strategic_floor_cap`
  - `tactical_overlay_cap`
  - `deployment_pace`
  - `hard_block_flags`
  - `defense_bias`
- 现有 `target_exposure` 可以保留，但只能作为聚合视图，不能替代上述分层预算真相。

原因：

- 长期 beta 稳定器关心的不只是“今天最多上多少仓”，还关心“长期必须持有多少”和“今天允许多快往上靠”。
- 如果 Governor 只发一个 target，ETF sleeve 会被迫自己发明长期/短期语义，重新变成第二套风险系统。

备选但不采用：

- 继续保留单层 `target_exposure`，把长期底仓逻辑全部塞进 ETF 本地策略。
  - 否决原因：这会让 Governor 失去组合级预算宪法的地位，且 audit 很难区分“上游允许”和“下游擅自承接”。

### 决策 2：formal ETF 改为 strategic beta stabilizer，而不是继续扩写 tactical allocation engine

选择：

- formal `cn_etf_beta` SHALL 具备三个正式角色层：
  - `core_accumulator`
  - `tactical_satellite`
  - `limited_defense`
- 建议的默认角色是：
  - `510300.SH`、`510050.SH` 作为 `core_accumulator`
  - `510500.SH`、`512100.SH` 作为 `tactical_satellite`
  - `512890.SH` 作为 `limited_defense`

原因：

- 长期 beta 稳定器的关键不是“选几只 ETF”，而是把“必须长期持有的宽基底仓”和“可收可放的进攻卫星”拆开。
- 不做角色拆分，弱市语义就只能继续在所有 ETF 之间平均减配，无法表达“先砍卫星，后动底仓”。

备选但不采用：

- 维持当前所有 ETF 平权的单层模板，只调整权重数值。
  - 否决原因：这属于调参，不是定义升级，无法稳定回答长期定投与弱市承接的产品问题。

### 决策 3：弱市语义必须先收缩 overlay，再决定是否允许 paced accumulation

选择：

- `LIGHT`：保留 `strategic_floor_cap`，收缩部分 `tactical_overlay_cap`，允许低速部署。
- `TRANS_DOWN`：继续保留 floor，overlay 进一步收缩，允许在 Governor 未硬阻断时做 paced accumulation，但仅限 `core_accumulator`。
- `RISK_OFF`：默认保留最低 floor 或 `floor + limited_defense` 过渡；不允许新增 satellite 风险。
- 只有 `allow_new_risk=false`、`force_deleveraging=true` 或等价 Governor 硬阻断信号出现时，ETF 才允许停止新增或优先去风险。

原因：

- 这既符合“长期 beta 稳定器”的直觉，也保留了 Governor 对组合级风控的最终裁决权。
- 这样定义后，“定投”不再是无限制抄底，而是受 Governor 配额与节奏控制的长期部署。

备选但不采用：

- 弱市一律继续高强度加仓。
  - 否决原因：这会让 ETF sleeve 越权变成逆势主策略，不再是组合级风险体系下的 beta 稳定器。
- 弱市一律清零。
  - 否决原因：这会让“长期底仓”概念失效，也不符合你希望的长期定投型目标。

### 决策 4：固定 50/50 只能是 research combo 假设，不得升级为正式预算真相

选择：

- 任何 `CN_STOCK_ETF_50_50` 或等权 stock/ETF 组合模式 SHALL 被标记为 `research_combo_only`。
- 正式 Governor 合同 SHALL NOT 从固定 50/50 假设派生生产级 sleeve budget。

原因：

- 当前 50/50 组合器本质上是研究装配器，用来快速比较两个组件，并非正式资产配置中枢。
- 如果把它直接升格为主线，会把研究假设误读成系统正式定义。

备选但不采用：

- 直接把当前 50/50 combo 当成双 sleeve 正式主线起点。
  - 否决原因：这没有经过 Governor 合同设计，也没有解释为什么是 50/50 而不是 70/30 或动态分配。

### 决策 5：审计必须按 floor / overlay / hard block / combo 假设分层归因

选择：

- `research_audit` 与 ETF 相关正式产物 MUST 能回答：
  - 当天的 `strategic_floor_target` 是多少
  - 当天的 `tactical_overlay_target` 是多少
  - 当天的 `deployment_pace` 是多少
  - 当前是否处于 `hard_block`
  - 实际暴露中，`core_accumulator`、`tactical_satellite`、`limited_defense` 各占多少
  - 当前结果是否来自 `research_combo_only`

原因：

- 如果不把这些层次拆开，用户仍然无法判断“低仓位是因为 Governor 在压，还是因为 stabilizer 自己没在买”。
- 这符合项目的“可信、可审计、可解释”原则。

备选但不采用：

- 仅保留当前 `target_exposure / actual_exposure` 两个汇总数。
  - 否决原因：它们不足以回答长期底仓系统里的关键产品问题。

## Risks / Trade-offs

- [风险] Governor 合同字段扩张会影响多个消费者。  
  缓解：保留旧字段作为聚合视图，同时为新字段增加显式版本化与审计断言。

- [风险] ETF 角色重定义会显著改变历史回测行为。  
  缓解：把这条 change 明确为新正式口径，不与当前 formal Phase 1 收益直接混比，必须重跑对照实验。

- [风险] `research_combo_only` 的界线不清，会导致前端或报表继续误读 50/50。  
  缓解：要求 `run_meta`、`audit` 和组合 summary 同时暴露 research-only 标签。

- [风险] paced accumulation 如果定义过宽，会演变成逆势抄底系统。  
  缓解：要求 accumulation 只能消费 Governor 下发的 `deployment_pace` 和 `strategic_floor_cap`，不能自扩预算。

## Migration Plan

1. 先在 OpenSpec 中修改 Governor、ETF sleeve 和 research audit 的正式要求。
2. 实现阶段先扩展 Governor 输出合同与 audit 字段，不先动具体资产池。
3. 再实现 ETF stabilizer 模式的 role map、weak-state semantics 和 paced accumulation 边界。
4. 最后处理 research combo 的标记与产物说明，避免继续把 50/50 当成正式真相。
5. 每一步都要求可回退，并重跑 ETF-only 与 research combo 两类实验做差异核对。

## Open Questions

- `strategic_floor_cap` 的正式量纲应该是绝对 notional，还是相对于 sleeve cap 的比例。
- `deployment_pace` 应该做成离散档位，还是连续数值。
- `RISK_OFF` 是否允许最小 floor 永远大于 0，还是允许 Governor 把 floor 本身压到 0。
- `core_accumulator` 的正式默认资产是否就是 `510300 + 510050`，还是还需要留出配置化角色映射。
