## Context

当前 `pre_profit_failure_context_risk` 已经在研究面证明自己更像持仓早期失败风险，而不是买入前候选风险。上一轮把它接到 candidate-layer veto 后，overlay 虽然启用，但候选层零匹配、零作用面，说明问题不在因子本身，而在插入层级。继续沿用候选层钩子只会重复得到无效 A/B。

当前系统里现成最好插的 research hook 偏向 candidate plan，但这类 hook 天然只作用于买入前候选。生命周期 fragility 因子需要的却是另一类插入点：它必须能够看到“已持仓”“entry 已发生”“利润是否建立”“当前持有是否进入脆弱期”这些状态。也就是说，这轮要解决的不是新因子定义，而是 research-only 插入层必须从 candidate layer 挪到 holding/exit layer。

## Goals / Non-Goals

**Goals:**
- 为 stock-only 研究运行时新增 holding/exit layer 的 fragility hook，不改变正式主线默认行为。
- 允许 research-only A/B 在已持仓股票上消费 `pre_profit_failure_context_risk` 一类生命周期风险因子。
- 明确记录 hook 的作用范围、命中持仓、触发后的持仓状态与退出结果，保证 A/B 可审计。
- 为后续最小 A/B 提供唯一正确的插入层，避免继续把 lifecycle 因子误接到 candidate plan。

**Non-Goals:**
- 不新增或修改正式主线默认退出规则。
- 不把 lifecycle fragility 因子接成 candidate veto、candidate tiebreak 或主排序权重。
- 不同时处理 ETF / defense。
- 不在本轮把研究因子直接升级为主线策略能力。

## Decisions

### 1. research-only hook 只允许作用于“已持仓股票”
决策：
- holding/exit fragility hook 只能在持仓层运行，输入对象必须是当前已有持仓，而不是当天新候选。

原因：
- `pre_profit_failure_context_risk` 的语义依赖 entry 之后的生命周期状态；如果对象不是已持仓，就没有可解释含义。
- 这样可以从系统层面阻止再次把 lifecycle 因子接回 candidate layer。

备选方案：
- 继续复用 candidate overlay，并试图通过日期对齐补出作用面。
- 放弃原因：这只能修补数据匹配，不会改变角色错位。

### 2. hook 的第一版只提供“研究态动作建议”，不直接改正式退出
决策：
- hook 第一版只产出 research-only action flags，例如 `fragility_watch`、`fragility_trim_candidate`、`fragility_exit_candidate`，由 A/B 配置决定是否映射成实验动作。

原因：
- 先把 research layer 的作用面与可审计性打通，再决定哪种动作值得进入最小 A/B。
- 避免一步到位把研究因子写死成某个退出规则。

备选方案：
- 直接把高风险桶映射到强制平仓。
- 放弃原因：过于激进，会把“研究作用面验证”和“策略动作选择”绑在一起。

### 3. 诊断产物必须同时覆盖日级和持仓级
决策：
- 日级产物记录 hook 是否启用、覆盖持仓数、命中高风险持仓数、建议动作计数。
- 持仓级产物记录符号、entry 日期、当前持仓天数、风险分位、命中动作、真实后续退出类型。

原因：
- 这类因子如果只看 perf，很容易再次出现“开了但其实零作用面”的假实验。
- 持仓级审计是解释生命周期因子的必要条件。

备选方案：
- 只扩 portfolio_daily。
- 放弃原因：缺少持仓级轨迹，无法解释为什么命中、命中后发生了什么。

### 4. 第一轮 A/B 只允许 stock-only、单因子、单动作
决策：
- 第一轮运行面限定为当前认可的 stock-only 基线，只允许一个 lifecycle 因子和一个动作映射，不和 moneyflow、quality、state score 组合。

原因：
- 生命周期因子本来就贴近持有管理，和其他 context 因子叠加会立刻丧失归因能力。

备选方案：
- 直接做组合级实验或多因子联动。
- 放弃原因：违背“单轮只做一个主改动”的研究纪律。

## Risks / Trade-offs

- [风险] holding/exit hook 需要更多持仓级状态，研究产物体积会变大。
  → 缓解：第一版只记录最小必要字段，不复刻完整持仓账本。
- [风险] research-only action flags 最后可能证明没有任何动作值得推进。
  → 缓解：先接受这是研究结论，不提前承诺策略收益。
- [风险] 如果 hook 读不到稳定的 entry/holding 状态，结果仍可能失真。
  → 缓解：spec 强制要求作用对象是已持仓，且产物必须带 entry 相关审计字段。
- [风险] 环境与 DB 口径仍可能像上一轮那样导致假阻塞。
  → 缓解：A/B surface 要求显式记录 baseline 锚点、factor source 和运行时 DB 口径。

## Migration Plan

1. 新增 holding/exit fragility research hook 合同与审计合同。
2. 在 research-only runtime 中接入 hook，不改正式主线默认配置。
3. 先跑单因子 stock-only A/B，确认 hook 是否有非零作用面。
4. 若研究失败，直接回退 research-only hook，不影响正式主线。

## Open Questions

1. 第一轮动作映射是先做 `watch`、`trim` 还是 `exit_candidate`。
2. 当前持仓级产物是否已有足够 entry 字段可复用，还是需要额外落盘。
3. `pre_profit_failure_context_risk` 之外，`early_fade_risk` 是否要作为后续辅助信号进入同一 hook。
