## Context

当前主线的市场状态判断由基准指数价格相对长期均线的位置，以及一个固定窗口的 EMA 斜率决定，再映射到 `BULL / TRANS_DOWN / TRANS_UP / BEAR` 和 `TREND_MAIN / TREND_LIGHT / NO_TRADE`。这套逻辑实现成本低、可复现，但它的定位更像“执行过滤器”，而不是成熟的市场状态框架。

当前问题主要有四个：
- 状态输入过于单一，无法区分横盘、缩量震荡、风险抬升和假启动。
- 状态切换缺少 persistence / hysteresis，图上容易出现碎片化阶段。
- 前端颜色蒙版展示的是 runtime 状态名，但后端状态机并没有足够强的语义承载能力。
- 审计输出不完整，当前很难回答“为什么今天是 `TRANS_UP` 而不是 `BULL`”。

这次 change 的目标不是直接替换主线实现，而是固化一套可以逐步替换当前 MA200 状态机的成熟 regime 框架合同，使后续实现有清晰边界、可审计输出和回退路径。

## Goals / Non-Goals

**Goals:**
- 定义一个正式的 trailing regime framework，输入至少覆盖趋势、风险、广度、参与度四类因子。
- 保留现有对外兼容状态名与交易模式名，但重新定义其生成规则和切换条件。
- 引入状态置信度、持续天数、切换原因和最小诊断输出，使 regime 可解释、可验证。
- 为后续实现保留 fallback 路径：新框架未启用时，系统仍可退回 MA200 简化模式。
- 让前端结果页和配置工作台显示的市场状态语义，与后端真实状态机保持一致。

**Non-Goals:**
- 本次 change 不直接修改 `baseline_V10.1` 或 `baseline_V10.2` 的正式交易逻辑。
- 不在本次 change 中引入外部付费宏观数据源。
- 不在前端重算 regime，不把展示层变成研究真相源。
- 不在本次 change 中最终决定具体参数值，只定义参数族、持久化规则和审计协议。

## Decisions

### 决策 1：正式市场状态框架只使用 trailing/rolling 数据

选择：
- 新框架只允许使用“当日及之前”可观测数据。
- 所有特征一律通过固定 lookback 或 rolling window 计算，不允许 future-looking 修正。

原因：
- 这是研究纪律底线，必须避免前视偏差。
- 也与当前系统“配置唯一真相 + 可复现”原则一致。

备选方案：
- 用 centered window 或 ex-post 标注做更平滑的状态线。
- 否决原因：展示会更漂亮，但会直接污染研究口径。

### 决策 2：状态判断采用“趋势主轴 + 风险/广度/参与度确认”的多因子结构

选择：
- `trend_block`：价格相对长均线、长均线斜率、突破/失守确认。
- `risk_block`：滚动波动率、ATR 带宽、下行波动或 drawdown 压力。
- `breadth_block`：成分股站上 MA50/MA200 比例、新高新低、涨跌家数类广度指标。
- `participation_block`：指数成交额、换手率、广度成交额等参与度确认项。

原因：
- 成熟 regime 方法不会只用一个价格窗口，也不会把量能单独当状态真相。
- 对 A 股来说，广度比单纯指数成交额更能解释“牛/熊/过渡”的结构差异。

备选方案：
- 只在现有 MA200 框架上叠加量能过滤。
- 否决原因：这仍然是“单轴状态机 + 辅助条件”，很难从根上提升分段质量。

### 决策 3：状态判断与交易模式分层

选择：
- `market_state` 负责描述市场结构：`BULL / TRANS_UP / TRANS_DOWN / BEAR`。
- `trade_mode` 负责描述执行权限：`TREND_MAIN / TREND_LIGHT / NO_TRADE`。
- `trade_mode` 不是 `market_state` 的简单一对一映射，而是 `market_state + confidence + persistence + execution confirmation` 的结果。

原因：
- 当前系统已经暴露出“状态名”和“实际执行模式”语义不一致的问题。
- 分层后才能表达“市场结构仍在 TRANS_UP，但执行仍然 NO_TRADE”等更真实的过渡期。

备选方案：
- 保持状态名和执行模式完全绑定。
- 否决原因：会继续混淆研究真相与交易妥协。

### 决策 4：引入 persistence / hysteresis，避免高频抖动

选择：
- 新框架必须定义：
  - `entry_confirm_bars`
  - `exit_confirm_bars`
  - `min_state_duration`
  - `confidence_floor`
  - `transition_cooldown`

原因：
- 成熟 regime 模型通常都需要状态持续性约束，否则图上会出现大量碎片化切换。
- 当前前端看到的“分段很不准”，一部分就是因为没有 persistence。

备选方案：
- 仅通过拉长均线周期解决抖动。
- 否决原因：这会降低响应速度，但不真正解决切换不稳的问题。

### 决策 5：正式输出最小 regime 诊断协议

选择：
- 每次运行输出：
  - `market_state`
  - `trade_mode`
  - `regime_confidence`
  - `regime_duration_bars`
  - `regime_transition_reason`
  - `regime_feature_snapshot`
- 聚合层输出：
  - 各状态天数
  - 各模式天数
  - 状态切换次数
  - 切换原因分布
  - 低置信度状态占比

原因：
- 不把审计合同一起升级，新的 regime 框架仍然会变成“看起来更复杂，但解释不了”。

备选方案：
- 只保留状态名和计数器。
- 否决原因：不足以支持回测差异归因和前端解释。

### 决策 6：前端只展示后端 regime 真相，不在前端自行推导

选择：
- 前端 overlay 与图例只消费 artifacts 内的正式 regime 输出。
- 前端可以做周期聚合，但不重算趋势、广度、量能或状态切换。

原因：
- 防止展示层和研究层口径漂移。

备选方案：
- 在前端用 benchmark K 线实时重算状态。
- 否决原因：会制造第二套真相源。

## Risks / Trade-offs

- [风险] 新框架引入的特征太多，导致实现复杂度明显上升  
  → Mitigation：先把 capability contract 固化，后续实现按最小增量逐层启用。

- [风险] 广度与参与度数据在历史窗口上覆盖不齐，导致 regime 本身不可用  
  → Mitigation：在 contract 中要求明确 fallback 层级和 `feature_availability` 输出，不允许静默跳过。

- [风险] persistence 过强会降低状态响应速度  
  → Mitigation：把确认条和最短持续期都配置化，并要求输出切换延迟诊断。

- [风险] 新框架与现有 `baseline_V10.1` 路由逻辑耦合过深，回归面太大  
  → Mitigation：保留 `ma200-market-state` fallback，先允许新旧双模式并存。

- [风险] 用户把图上的 regime 颜色误解成“涨跌颜色”  
  → Mitigation：要求前端显示 legend 和状态说明，不允许只给颜色不给语义。

## Migration Plan

1. 先新增 `market-regime-framework` 能力，并把旧 `ma200-market-state` 降级为 fallback contract。
2. 再让 `regime-router` 消费新的 regime 输出字段，但保留旧模式兼容开关。
3. 再升级前端 overlay 与配置 UI，使其能展示新框架语义与配置层。
4. 最后才进入实现与对照验证，严格走三窗口研究纪律。

回退策略：
- 配置层保留 `regime_engine = ma200_legacy`。
- 前端 overlay 继续能消费旧 `market_state/trade_mode`。
- 所有新字段均为可选扩展，旧 artifacts 不因新框架而失效。

## Open Questions

- 广度特征是否以 `CSI800` 成分股为正式基准，还是允许跟随当前 universe 动态切换？
- 参与度特征是否应优先使用指数成交额，还是使用成分股聚合换手率更符合 A 股特性？
- `TRANS_UP` 与 `TRANS_DOWN` 的边界是否需要对称，还是允许“上行确认更严、下行切换更快”？
- 新框架第一期是规则式评分引擎，还是直接允许无监督状态聚类模型作为可选实现？
