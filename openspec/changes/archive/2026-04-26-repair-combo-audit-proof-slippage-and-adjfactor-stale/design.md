## Context

最近组合审计已经确认，当前代码实现本身没有直接暴露出明显未来函数或成交穿模，但组合层审计证明链不完整，且 `slippage_mode` 与 `adj_factor` stale 风险还没有被系统级合同覆盖。继续在这个状态下推进收益实验，会把“审计缺口”误当成“策略问题”。

## Goals / Non-Goals

**Goals**
- 让组合层 `timing_alignment` 与 `universe_lineage` 可以正式聚合 component 证据，不再无端停在 `UNKNOWN`。
- 让 `slippage_mode` 在 stage-pipeline fill 路径有真实运行时语义。
- 让 `adj_factor` stale 前向填充有明确统计与 audit gate。

**Non-Goals**
- 不改 `NEXT_OPEN` 成交时点。
- 不改 stock / ETF sleeve 的信号逻辑。
- 不改组合预算或仓位分配逻辑。
- 不扩展到更多成本模型选项。

## Decisions

### 决策 1：组合层审计聚合走 component run_meta，而不是重写一套组合专属 PIT 推理
- 选择：组合 audit 直接读取 `run_meta.sleeves.*` 对应 component 的 `run_meta.json`，递归复用现有 `evaluate_timing_alignment` / `evaluate_universe_lineage`。
- 原因：component 证据已经存在，重复推理只会继续漂移。
- 备选：在组合层单独解析 `config.json` 和 `compiled_plan.json` 再重推一遍 PIT / NEXT_OPEN。
- 放弃原因：重复逻辑多、风险高，而且无法继承 component 层已有审计结论。

### 决策 2：`slippage_mode` 先只修 stage-pipeline 主路径
- 选择：本次只修当前组合真实走的 stage-pipeline fill 路径。
- 原因：这是当前正式主路径，且用户本次审计对象就是当前组合。
- 备选：同时改旧 strict runtime。
- 放弃原因：会扩大改动面，违反最小改动原则。

### 决策 3：`cost_only` 保持价格不偏移，只把 slippage 作为独立现金成本记账
- 选择：
  - `price_adjustment_only`: 继续通过 `fill_price` 偏移体现 slippage。
  - `cost_only`: `fill_price == open`，slippage 作为独立现金成本进入 `net_amount`。
- 原因：这样两种语义清晰且可审计。
- 备选：`cost_only` 仍然改 `fill_price`，但额外再记一份成本。
- 放弃原因：会产生双重扣减和语义混乱。

### 决策 4：`adj_factor` stale 审计以“连续缺失导致前向填充跨度”为核心指标
- 选择：在 data bundle 里记录每个 symbol 的 `adj_factor` 连续缺失最大跨度，并在 audit 中按阈值输出 `PASS/WARN/FAIL`。
- 原因：真正需要防的是“长期 stale 复权因子被静默沿用”，不是单日缺失本身。
- 备选：只看 `null_count`。
- 放弃原因：`null_count` 无法区分一次性噪音和长时间 stale。

## Risks / Trade-offs

- [风险] 组合层递归读取 component run_meta 时路径缺失 -> 缓解：保留 `UNKNOWN`，同时把缺失路径写入 evidence。
- [风险] `slippage_mode=cost_only` 改变既有收益口径 -> 缓解：只在显式配置该模式时生效，默认 `price_adjustment_only` 不变。
- [风险] `adj_factor` stale 阈值过严 -> 缓解：第一版只给保守阈值，并把阈值写进 audit evidence。

## Migration Plan

1. 新增 change artifacts 与 specs。
2. 在 `research_audit.py` 增加 combo component 聚合 helper，并补组合 timing / lineage / adj-factor gate。
3. 在 stage-pipeline runtime bootstrap 与 fill accounting 中接入 `slippage_mode`。
4. 在 `data_bundle_builder.py` 计算 `adj_factor` stale 统计。
5. 补最小单测并回填 notes。

## Open Questions

- 后续是否要把相同的 `slippage_mode` 语义补到旧 strict runtime；本次不做。
