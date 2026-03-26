## Context

当前仓库主干仍可理解，但 ETF 和前端结果边界已经进入明显的架构债阶段。

现状主要有三类问题：

1. ETF contract 没有单一 owner  
当前 ETF 相关字段会同时出现在：
- API schema
- governed config 归一化
- ETF provider
- artifact finalize
- research audit

这导致同一批语义要在多处重复透传、重复归一化、重复投影。新增字段时很容易出现一处改了、另一处漏掉，或者不同层对同一字段做了不同解释。

2. 前端结果层仍在补算和拼装研究真相  
结果工作台虽然已经以 snapshot 为主，但旧桌面壳和结果 helper 仍在客户端：
- 从 `dailyRows`、`market_state`、`trade_mode` 推导 regime 语义
- 为 research combo 拼装组件级伪 snapshot

这和“后端输出唯一真相、前端只消费 canonical surface”的目标不一致。

3. 前端旧壳和 Vue workbench 仍然双 owner  
`index.html + backtest_v2.js + ui-controls.js + artifacts.js` 仍保留大量页面控制逻辑；Vue workbench 又承担结果可视化。当前并非完全重复，但边界不稳定，已经出现旧壳函数重复定义和过渡逻辑继续长胖的问题。

这条 change 的目标不是做新策略，也不是推进 unified runtime，而是先把这些边界收紧，避免继续叠加技术债。

## Goals / Non-Goals

**Goals:**

- 为 ETF beta contract 建立单一正式 owner，统一配置归一化、运行时摘要和下游投影。
- 让结果工作台和 research combo 继续下沉到后端 canonical truth surface，前端不再重算研究语义。
- 明确旧桌面壳与 Vue workbench 的 owner map，阻止旧壳继续吸收结果真相和活跃逻辑。
- 保持当前 A 股个股 alpha、ETF 研究规则和研究结果口径不变。

**Non-Goals:**

- 不调整 baseline 主逻辑。
- 不新增 ETF 规则族，不优化 ETF 收益。
- 不实现 unified runtime。
- 不重做整个前端，只做 owner boundary 收口。
- 不改动 `outputs/` 中的历史产物口径。

## Decisions

### 决策 1：新增 ETF contract owner 边界，而不是继续把 ETF 字段散落在各层

做法：
- 新增一个正式 ETF contract owner 能力，负责：
  - ETF beta 配置归一化
  - 运行时 contract projection
  - artifact / audit 消费所需的 canonical summary
- provider、artifact finalize、research audit 只消费该投影，而不再各自重新解释 ETF 配置。

原因：
- 当前 ETF 线演化太快，继续手工透传会放大字段漂移。
- contract owner 先收口，比继续做规则研究更有基础价值。

替代方案：
- 继续维持现有多点透传，只靠测试兜底。  
不选，因为这只能延缓问题，不能解决 owner 不清的问题。

### 决策 2：results workbench 只允许消费后端 canonical truth，不再在前端补算 regime / combo 语义

做法：
- 继续强化 `ResultsWorkbenchSnapshot` 和 experiment surface。
- research combo 必须有后端生成的 canonical truth model。
- 前端 helper 只做展示级格式化，不再把 `dailyRows`、`market_state`、`trade_mode` 当成真相源做反推。

原因：
- 当前前端补算 regime / combo，会让 UI 和后端产物存在双真相。
- 这与可审计、可复现目标冲突。

替代方案：
- 保留前端 fallback 补算，等 unified runtime 再收口。  
不选，因为当前 bug 和混乱已经主要来自这条过渡路径。

### 决策 3：旧桌面壳保留，但正式退化成 bootstrap / bridge / compatibility layer

做法：
- 旧壳文件只允许承担：
  - bootstrap
  - 页面 chrome
  - 事件接线
  - snapshot bridge
- 结果真相、面板模型和研究解释必须收回到后端或 Vue workbench。

原因：
- 一次性重写前端成本高、风险大。
- 但继续让旧壳吸收新逻辑会使边界进一步恶化。

替代方案：
- 全量前端迁移到 Vue。  
不选，因为本轮目标是边界收口，不是前端重构工程。

### 决策 4：本轮只做 boundary rationalization，不顺手做 unified runtime 或 ETF 策略升级

做法：
- 所有新增 contract 和界面边界都以“不改变研究口径”为硬约束。
- 若实现过程中发现需要统一组合真相，只解决 truth surface，不直接落 unified runtime。

原因：
- 本轮是 L3 边界治理。
- 同时绑定策略、runtime 和前端改造，会使结果不可归因。

## Risks / Trade-offs

- [风险] 只收边界，不做 unified runtime，可能让 research combo 仍有阶段性过渡结构  
  → 通过“后端 canonical truth surface”先统一解释层，避免前端继续补算。

- [风险] ETF contract owner 抽象过早，可能和后续 ETF 正式主线不完全一致  
  → 只收口当前已存在的字段和投影，不提前设计未来未知规则族。

- [风险] 旧壳瘦身后，某些隐式 fallback 可能消失，暴露老实验兼容问题  
  → 通过边界测试和显式 empty state 保留兼容，而不是继续默默补算。

- [风险] 同一工作区已有多条并行 change 和大量未归档改动，边界治理容易碰到脏代码  
  → 这条 change 只处理 contract owner、snapshot truth 和 owner map，不顺手整理其他线。

## Migration Plan

1. 先新增 ETF contract owner 边界与 canonical projection。
2. 再把 artifact finalize / research audit / surface builder 切到消费 canonical ETF projection。
3. 然后下沉 research combo truth，补足后端 canonical snapshot。
4. 最后收紧旧桌面壳边界，增加静态边界测试，确认不再补算 regime / combo 真相。

回退策略：
- 如果 ETF contract owner 抽象引入回归，先回退 owner 抽象与下游消费切换，保留旧透传路径。
- 如果前端 truth 下沉引发旧实验展示异常，先恢复 empty state 与兼容显示，不回到前端补算。

## Open Questions

- research combo 的 canonical truth 应该由现有 experiment surface 扩展，还是新增专用 combo surface。
- ETF contract owner 最终放在 `backend/core/config` 还是更偏 `backend/core/tools` 的 contract/projection 层。
- 当前桌面旧壳中哪些函数应立即删除，哪些保留为带 `legacy shim` 标记的过渡函数。
