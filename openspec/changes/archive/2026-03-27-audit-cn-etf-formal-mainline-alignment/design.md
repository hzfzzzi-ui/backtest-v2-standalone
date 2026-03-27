## Context

根目录正式策略文档 [A股ETF子系统策略思路md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股ETF子系统策略思路md) 已经明确定义了 `cn_etf_beta` 的 Phase 1 正式口径：

- 它是 Governor 约束下的 A 股 ETF beta 配置主线。
- 合法链路必须是 `market_regime_engine -> global_portfolio_governor -> cn_etf_beta -> attribution_audit`。
- 正式 core beta universe 固定为：
  - `510300.SH`
  - `510500.SH`
  - `510050.SH`
  - `512100.SH`
- limited defense candidate 固定为：
  - `512890.SH`
- `518880.SH`、`511010.SH`、`588000.SH`、`159915.SZ` 明确不属于当前正式主线核心。

但当前 ETF 研究和实现里，已有多条实验线依赖 `159915`、`588000`、`511010` 等资产，且部分 runtime/profile 仍沿用“筛票器”或研究分支语义。这会导致：

- 正式主线与研究分支混淆；
- “较优研究结果”被误读为正式策略改进；
- 后续收益优化失去正式基线。

因此本次 change 只做“正式口径对齐审计”和正式/研究边界收口，不做收益优化。

## Goals / Non-Goals

**Goals:**

- 以根目录正式策略文档为唯一正式口径来源，建立 ETF 正式口径对齐审计。
- 对当前 ETF profile、study、runtime 和产物做正式分类：
  - `formal_mainline`
  - `research_only`
  - `do_not_promote`
- 明确 ETF 正式主线在资产池、limited defense candidate、信号/输出语义上的合法范围。
- 要求 `run_meta` 和 `research_audit` 对 ETF 正式对齐状态和偏离原因给出可审计证据。

**Non-Goals:**

- 不优化 ETF 收益，不追求本轮提升 CAGR。
- 不新增行业 ETF 研究。
- 不修改个股 alpha 主线。
- 不实现 unified runtime 新能力。
- 不删除既有研究 study，只做正式降级和显式标注。

## Decisions

### 1. 以根目录正式策略文档作为 ETF Phase 1 唯一正式口径

选择：
- 把 [A股ETF子系统策略思路md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股ETF子系统策略思路md) 作为 ETF Phase 1 正式主线的唯一口径来源。

原因：
- 当前代码和研究线已经发生分叉，必须先有唯一真相源。
- 继续以“当前最优实验”倒推正式定义，会让正式边界不断漂移。

备选方案：
- 以当前较优研究结果反推正式定义。

不采用原因：
- 会把研究分支直接洗成正式主线，破坏研究纪律。

### 2. 用显式分类而不是隐式命名来区分正式主线与研究分支

选择：
- 为 ETF runtime profile、study metadata 和审计结果增加显式分类：
  - `formal_mainline`
  - `research_only`
  - `do_not_promote`

原因：
- 当前很多研究线名称看起来像主线，但实质已越过正式口径。
- 显式分类比继续靠文件名、preset 名或口头约定更稳。

备选方案：
- 只在文档里说明哪些不算正式主线。

不采用原因：
- 无法进入运行时产物和审计链，前端和后续分析仍会混淆。

### 3. 正式主线与研究分支共享 Governor 上游，但不共享“正式背书”

选择：
- Governor 仍是 ETF 的唯一合法上游预算/状态来源。
- 但只有符合正式文档的 ETF profile/study，才能被标记为 `formal_mainline`。

原因：
- 文档明确要求 ETF 不得绕开 Governor。
- 同时也不能因为都受 Governor 约束，就把所有 ETF 研究线都当成正式主线。

备选方案：
- 只要受 Governor 约束，就视作正式主线。

不采用原因：
- 会继续放大当前“研究分支冒充正式主线”的问题。

### 4. 正式对齐审计只判“边界合规性”，不判“收益优劣”

选择：
- 本轮审计仅回答：
  - 是否使用了正式资产池；
  - 是否使用了允许的 limited defense candidate；
  - 是否沿用了正式输出语义；
  - 是否越界使用研究资产或研究型信号语义。

原因：
- 这是 L3 边界清理任务，不是策略优劣评估任务。

备选方案：
- 一并把收益门槛写入正式对齐审计。

不采用原因：
- 会把“正式边界”与“性能评价”绑死，难以客观定位当前实现偏差。

## Risks / Trade-offs

- **[风险] 当前较优 ETF 研究线可能全部被降级为 `research_only`** → **缓解**：保留 study 和结果，只取消正式背书，不删除研究分支。
- **[风险] 正式可用 ETF 主线短期内变弱或更少** → **缓解**：这是预期结果；先稳住正式边界，再决定后续如何重构主线。
- **[风险] 运行时/前端需要适配新增分类字段** → **缓解**：分类字段先保持附加式输出，不破坏现有消费链。
- **[风险] 文档与现有 main specs 仍有历史口径差异** → **缓解**：本轮通过 delta specs 显式收口，以文档为准，不做双口径并存。

## Migration Plan

1. 新增 ETF 正式口径对齐 capability 与 delta specs。
2. 盘点当前 ETF profiles/studies，对非正式范围资产和语义显式标注为 `research_only` 或 `do_not_promote`。
3. 在 `run_meta` 和 `research_audit` 中增加正式对齐状态与偏离原因字段。
4. 用最小 smoke 验证：
   - 一条符合正式文档的 ETF 主线能被标为 `formal_mainline`
   - 一条含 `159915` / `588000` / `511010` 的研究线会被标为 `research_only`

回退策略：
- 回退新增的 formal alignment 字段与审计逻辑；
- 移除 study/profile 分类；
- 恢复原先不区分正式与研究的 ETF 输出。

## Open Questions

- 当前是否存在任何一条 ETF study/profile 在不重构逻辑的前提下即可直接视为 `formal_mainline`，还是全部都应先降级为 `research_only`。
- 前端是否需要在本轮就显式展示 `formal_mainline / research_only / do_not_promote`，还是先只在产物层落字段。
