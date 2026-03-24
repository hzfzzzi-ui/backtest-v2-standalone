## Context

当前 A 股主线已经同时具备三类现实基础：

- `baseline_V10.1` 已经是成熟的个股 alpha 主干，且其市场状态、风险预算和回撤约束已经真实影响运行行为。
- `cn_etf` 已经具备独立数据链、资产范围与最小研究入口，但仍停留在 research entry 阶段，尚未纳入统一的总控语义。
- regime、budget、audit、snapshot 相关逻辑已经分散在 `engine_vector`、`order_planning`、`portfolio_runtime`、`research_audit` 与前端 snapshot 桥接中，但没有统一的 Phase 1 contract。

本 change 的目标不是立即把这些能力抽成全新服务，而是先把 A 股子系统在 Phase 1 中的正式边界固定下来。核心约束来自三份架构文档：`A股子系统架构设计.md`、`A股子系统接口模块定义.md`、`A股子系统系统架构思路.md`。这些文档已经明确：

- `baseline_V10.1` 必须重定位为 `cn_stock_trend_alpha_core`
- `cn_etf_beta` 必须作为 Governor 约束下的低频 beta sleeve，而不是复制股票 breakout 壳
- `market_regime_engine` 必须强化可归因能力，但不应在本阶段被伪装成已独立服务
- `global_portfolio_governor` 必须成为唯一合法总控，但本阶段仍允许其逻辑分散实现
- `attribution_audit` 必须从散点字段升级为正式横切模块

## Goals / Non-Goals

**Goals:**

- 固化 A 股 Phase 1 的正式模块边界：`market_regime_engine`、`global_portfolio_governor`、`cn_stock_trend_alpha_core`、`cn_etf_beta`、`attribution_audit`
- 让 `baseline_V10.1` 在 contract 层正式降级为股票 alpha sleeve，而不是继续承担整个系统的语义
- 让 regime 输出从“局部技术状态”升级为可被 Governor、audit、snapshot 一致消费的状态 contract
- 让总风险预算、sleeve 预算、drawdown ladder、recovery/cooldown 统一归口到 Governor contract
- 让 `cn_etf` 研究入口有正式的主线定位，服务于 A 股 beta sleeve，而不是孤立的 ETF 实验入口
- 让结果产物和工作台能够解释“今天的预算和仓位为什么这样”，而不只给出收益和净值结果

**Non-Goals:**

- 不在本 change 中正式实现 `value_bluechip_satellite`
- 不在本 change 中正式实现 `insurance_overlay`
- 不在本 change 中把 `market_regime_engine` 或 `global_portfolio_governor` 强制抽成独立服务/进程
- 不在本 change 中推翻现有五状态技术骨架并换成全新三状态或黑箱分类器
- 不在本 change 中把黄金、债券、高弹性成长 ETF 一次性全部纳入正式 `cn_etf_beta`
- 不在本 change 中重写 `baseline_V10.1` 的核心 alpha 信号壳

## Decisions

### 决策 1：Phase 1 保留五状态技术骨架，三状态只作为派生视图

保留的正式主状态为：

- `BULL`
- `TRANS_UP`
- `LIGHT`
- `TRANS_DOWN`
- `RISK_OFF`

三状态只作为 Governor 和展示层的派生视图：

- `RISK_ON = BULL + TRANS_UP`
- `NEUTRAL = LIGHT`
- `RISK_OFF = TRANS_DOWN + RISK_OFF`

`CRISIS` 在 Phase 1 不作为主状态，而是 `stress_flag / crisis_overlay`。

原因：

- 当前主线下游已经围绕细粒度技术状态运行，直接改主状态会与现有风险预算和行为计数器冲突。
- 五状态更适合保留过渡态信息，避免 Governor 只能看到粗粒度 `on/off`。

备选方案：

- 直接切成 `RISK_ON / NEUTRAL / RISK_OFF`
  - 放弃，因为会抹平现有 `TRANS_UP / TRANS_DOWN` 的中间态信息。
- 直接引入 `CRISIS` 作为第六主状态
  - 放弃，因为数据与人工 override 语义尚未稳定，先作为 overlay 更稳。

### 决策 2：`market_regime_engine` 在 Phase 1 先合同化，不强行服务化

Phase 1 将 `market_regime_engine` 定义为逻辑上独立、实现上仍内嵌于现有 runtime/provider 链路的状态解释层。

原因：

- 当前 regime 逻辑已经分散在 `breakout_signal_provider` 及其相关引擎文件中，直接重构成独立服务会引入不必要的迁移风险。
- 当前更缺的是统一输出 contract 与归因字段，而不是新的部署边界。

备选方案：

- 直接新建独立 Governor/Regime 服务
  - 放弃，因为会把 L3 范围扩成架构迁移和服务拆分工程。

### 决策 3：`manual_override` 采用 `base_state / effective_state` 双轨制

任何人工判断或策略外部干预都不得覆盖 `base_state`。系统必须同时保留：

- `base_state_*`
- `effective_state_*`
- `override_reason`
- `override_actor`
- `override_scope`

原因：

- 你的需求明确强调“状态来源可归因”和“必要时人工判断”，这两者只有在双轨制下才能同时成立。
- 若人工直接覆盖原始状态，后续无法审计 Governor 为什么降仓、是模型错还是人改的。

备选方案：

- 只记录最终状态，不记录 base payload
  - 放弃，因为无法支持可信回放和责任分离。

### 决策 4：Governor 先定义 contract，再决定是否抽象为独立模块

`global_portfolio_governor` 在 Phase 1 中被定义为唯一合法的总风险预算层，但其实现允许继续分散在：

- `breakout_signal_provider`
- `order_planning`
- `portfolio_runtime`
- `multi_alpha_strategy`

原因：

- 当前系统已存在这些逻辑雏形，先统一 contract 才能在后续实现中安全收敛。
- 若先抽模块、后想 contract，容易做成“名字统一、语义仍散”。

备选方案：

- 立即强制所有预算逻辑迁移到新文件/新服务
  - 放弃，因为这会把本轮从“实现计划”变成高风险重构。

### 决策 5：`baseline_V10.1` 正式重定位为 `cn_stock_trend_alpha_core`

Phase 1 中，`baseline_V10.1` 不再代表整个 A 股系统，而是股票 alpha sleeve 的当前正式主干。

原因：

- 当前 A 股系统已经不再只服务个股 alpha；ETF beta、defense、insurance 的未来位置已被明确。
- 如果文义上继续让 `V10.1` 代表整个系统，后续所有预算和状态 contract 都会和历史基线语义冲突。

备选方案：

- 保持 `V10.1` 为系统主名，仅在内部增加 sleeve
  - 放弃，因为会持续混淆“股票 alpha 主干”和“系统总控”。

### 决策 6：`cn_etf_beta` Phase 1 范围收窄为 core beta + limited defense candidate

Phase 1 正式纳入 `cn_etf_beta` 的范围仅限：

- core beta：`510300.SH`、`510500.SH`、`510050.SH`、`512100.SH`
- limited defense candidate：`512890.SH`

暂不纳入正式 core beta sleeve 的资产：

- `518880.SH`
- `511010.SH`
- `588000.SH`
- `159915.SZ`

原因：

- 当前 change 的重点是把 ETF 正式接入统一总控，而不是一次性完成完整 ETF 配置层。
- 黄金/债券属于未来 defense layer；科创/创业板高弹性 ETF 会稀释 Phase 1 的边界。

备选方案：

- 直接把现有 9 只 ETF 全量纳入正式 beta sleeve
  - 放弃，因为会把 beta、defense、growth 三种角色混在一起。

### 决策 7：`attribution_audit` 必须是正式模块，不再只做结果散点字段

Phase 1 里，`attribution_audit` 需要具备统一的日志与引用层，最少包含：

- `state_logs`
- `budget_logs`
- `sleeve_logs`
- `manual_override_logs`
- `reason_code_summary`

并被 `run_meta.json`、`audit.json`、snapshot 摘要统一引用。

原因：

- 未来若没有这层，系统无法稳定回答“为什么今天降仓/停仓/只保留 ETF/触发人工判断”。
- 你的系统目标不是黑箱收益最大化，而是可信、可审计、可解释。

备选方案：

- 继续把这些字段分散在 `run_meta` 与各类 debug 中
  - 放弃，因为无法形成统一 contract，也无法被工作台稳定消费。

## Risks / Trade-offs

- **[风险] 五状态继续保留会让 contract 看起来比三状态更复杂** → 通过派生视图向 Governor/UI 提供三状态，同时保留五状态细粒度证据。
- **[风险] Governor 先合同化、后模块化，短期内实现仍分散** → 通过 specs 和 attribution_audit 先把语义统一，避免“换个文件名但逻辑依旧发散”。
- **[风险] `baseline_V10.1` 重定位可能影响现有用户对基线的理解** → 在 proposal/specs 中明确它仍是股票 alpha 正式主干，只是不再承担整个 A 股系统语义。
- **[风险] `cn_etf_beta` 范围收窄后，有人会认为 ETF 设计不完整** → 明确标注这是 Phase 1 核心 beta sleeve，而不是完整 defense/growth ETF 平台。
- **[风险] manual override 双轨会增加产物字段与 UI 负担** → 这是审计可用性的必要成本，Phase 1 可先从 run_meta/audit/snapshot 摘要开始，不要求一次到位的复杂 UI。

## Migration Plan

1. 先通过 specs 固化五状态 regime、Governor、stock alpha sleeve、ETF beta sleeve、attribution_audit 的正式边界。
2. 在实现阶段先从输出 contract 下手：
   - regime 输出 `base/effective state`
   - Governor 输出 total/sleeve budget
   - audit 输出 attribution refs
3. 再逐步收敛当前分散逻辑到统一 reason code 与 snapshot/产物字段。
4. 对 `baseline_V10.1` 和 `cn_etf` 入口做语义重定位，但不先推翻已有信号逻辑。
5. 在回归中确保：
   - 现有 A 股股票主线行为不因 contract 收敛而发生未解释漂移
   - ETF 入口仍保持独立真值表，不污染股票 `V2 canonical`

回退策略：

- contract 回退时，以删除/回退本 change 的新增 spec 与实现为主，不回滚现有 `cn_etf` 数据链和股票 `V2 canonical` 数据口径。
- 若实现阶段发现 Governor/Regime contract 引发产物不兼容，可先保留实现、回退 snapshot/attribution 暴露面。

## Open Questions

- Phase 1 中 `results-workbench-snapshot-boundary` 是不是只要求最小摘要可见，还是要求桌面工作台提供独立 Governor/Attribution 视图。
- `manual_override` 的 actor/source 是否需要在第一版就区分“人工按钮”“策略配置”“外部事件注入”。
- `cn_etf_beta` 的 first execution shell 是否沿用现有 `cn_etf` preset 默认调仓频率，还是在实现阶段单独固化 Governor-compatible 的周频/双周频节奏。
