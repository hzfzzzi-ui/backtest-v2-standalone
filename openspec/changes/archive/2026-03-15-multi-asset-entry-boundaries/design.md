## Context

当前系统已经把旧 API、旧前端 fallback、旧研究脚本入口和多数 runtime compat 壳清掉，主路径已经稳定在 `study -> runtime compile -> foundation_shell -> stage_pipeline -> engine_vector/portfolio -> manifest/surface -> Vue workbench`。但这一整条链路仍然默认“资产= A 股”，并把以下语义隐式散落在不同层：

- universe_mode、industry、suspension、ST、lot size 等市场规则
- benchmark / regime 的 A 股默认
- signal provider 和 route registry 的 A 股前提
- 前端结果面和配置面里对 A 股字段的默认解释
- study / generated thin script 中未显式声明的资产范围

如果后续要正式接入美股 ETF、加密现货和防守层资产，继续沿用这种隐式 A 股前提，会导致：

- compile 层无法判断哪些字段是跨资产通用，哪些是市场专用
- provider 和 universe 会被局部条件分支污染
- manifest/surface 无法成为真正的资产无关真相
- 前端 snapshot 无法稳定消费多资产结果

本次设计只做“入口边界显式化”，不做新资产交易逻辑落地；一切行为继续锚定 `baseline_V10.1 -> exp_20260314_144548534_7db9`。

## Goals / Non-Goals

**Goals:**
- 定义 canonical `asset_scope`、`asset_profile`、`market_profile` 和 `execution_profile`。
- 让 runtime compile 先解析资产边界，再进入 universe/signal/risk 编译。
- 让 provider、route registry 和 universe resolver 显式消费 asset profile。
- 让 manifest、surface、runtime snapshot 和 ResultsWorkbenchSnapshot 携带薄资产上下文。
- 让 study 定义和 generated thin script 显式声明资产范围。
- 保持 `V10.1` 的收益、回撤、订单数、交易数和关键 diagnostics 口径不变。

**Non-Goals:**
- 不在本 change 中实现美股 ETF、加密现货或防守层资产的正式交易逻辑。
- 不在本 change 中优化任何收益指标。
- 不重写 `strict runtime` 或 `stage pipeline` 的执行时点。
- 不引入“为了泛化而泛化”的抽象层；只隔离真正的资产入口假设。

## Decisions

### 决策 1：引入统一的 Asset Entry Boundary

系统将正式引入以下薄对象：

- `asset_scope`
  - 由前端、study、CLI 显式声明
  - 表示“本次运行打算使用哪类资产/市场组合”
- `asset_profile`
  - 后端 canonical 解析结果
  - 表示“运行时应采用哪套资产语义和 adapter”
- `market_profile`
  - 市场规则与约束摘要
  - 包括交易日历、lot 规则、停牌语义、行业/成分可用性等
- `execution_profile`
  - 薄执行风格摘要
  - 用于暴露订单规划和执行规则族，但不改变当前时点

选择这个方案，而不是继续从 `universe_mode`、`benchmark`、`symbols_source` 等字段拼接推断，是因为拼接推断会持续把 A 股假设藏在 compile 和 UI 中。

### 决策 2：Runtime compile 先解析资产边界，再编译各配置域

`runner_config_helpers` façade 不再把资产边界当作 universe/signal/risk 的附属字段，而是先通过 asset boundary compile 解析 canonical profile，再把 profile 分发给：

- universe compile
- signal compile
- risk/exit compile
- semantic bundle

不采用“每个 compile 子模块自己猜资产类型”的方案，因为那会把同一资产真相复制到多个模块，未来必然漂移。

### 决策 3：Universe resolver 改成按 asset family 分发

当前 `universe-resolver` 规范是 A 股主导的。新设计中：

- resolver 入口先接收 canonical `asset_profile`
- 先按 `asset_family` 路由
- A 股 resolver 只是其中一个 adapter

不直接把“美股/加密逻辑”写进现有 A 股 resolver，是为了避免把 A 股专用字段继续定义成全局主语义。

### 决策 4：Provider façade 显式消费 asset_profile，但不在本轮改行为

`signal-provider-protocol` 将要求：

- provider `precompute/day_signals` 可消费 asset profile 或 market profile
- route registry 选择 route/provider 时显式携带 asset boundary
- 未声明支持的资产 family 必须显式失败，而不是默默回落到 A 股行为

不在本轮直接实现多资产 provider 行为，只把入口 contract 和失败语义收紧。

### 决策 5：Manifest / Surface / Snapshot 只暴露薄资产上下文

结果真相层会增加薄资产上下文，例如：

- `asset_scope`
- `asset_profile_id`
- `asset_family`
- `market_profile_id`

但不会把整套市场规则对象塞进 surface。详细市场规则仍留在 compile/runtime 层。这样可以让前端消费稳定摘要，而不反向依赖内部 adapter 结构。

### 决策 6：Study 与 generated thin script 必须成为多资产正式入口

`.study.yaml` 将被要求显式声明资产范围。generated thin script 只负责透传 study，不再承担“默认这是 A 股”的隐式责任。

不采用“先继续靠 baseline_id 猜资产范围”的方案，因为基线是实验锚点，不应该承担长期资产入口身份语义。

## Risks / Trade-offs

- [风险] 资产边界 compile 可能意外改变 `V10.1` 运行配置语义 → 通过 `baseline_V10.1` smoke、runtime config compare 和 manifest compare 锁死。
- [风险] 过早泛化可能引入抽象噪音 → 只抽 asset entry boundary，不提前实现新资产算法。
- [风险] 前端状态新增 assetContext 后，页面壳和 snapshot 可能出现双真相 → 明确规定 runtime/source truth 仍只有一套，assetContext 只是其薄摘要。
- [风险] universe resolver 的入口修改会影响部分测试和工具脚本 → 统一通过 study/CLI/runtime access 调整，不保留向前兼容壳。

## Migration Plan

1. 新增 canonical asset boundary 类型与 registry，并把 `CN_A` 固化为当前唯一正式 profile。
2. 调整 runtime config compile，使 asset boundary 成为第一阶段编译输入。
3. 调整 study definition、generated thin script 和 runtime access，使其显式透传 asset scope。
4. 调整 universe resolver、signal provider façade 和 route registry 的入口签名，使其消费 asset profile。
5. 调整 manifest、surface、runtime snapshot 和 ResultsWorkbenchSnapshot，暴露薄资产上下文。
6. 用 `baseline_V10.1` 对照 runtime config、manifest、surface 和关键 perf 指标，确认行为未漂移。

回退策略：

- 回退本 change 即可恢复“隐式 A 股”为主的旧边界。
- 不需要回退 baseline 或实验产物。
- 如 smoke 显示 `V10.1` 行为漂移，停止继续推进 provider/universe 入口收口。

## Open Questions

- canonical asset id 是否采用 `cn_a_equity` / `us_etf` / `crypto_spot` 这种稳定命名，还是引入更细的 market+instrument 组合 ID。
- 前端 assetContext 是否只显示 `asset_family/market_profile_id`，还是同时显示 benchmark family。
- `transactions` / mobile action schema 是否要在本轮一并带上 assetContext，还是留到正式多资产行动面再处理。
