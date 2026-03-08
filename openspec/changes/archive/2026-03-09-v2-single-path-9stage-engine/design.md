## Context

`v2-backend-refactor-foundation` 已经把后端主线收敛到：

`config_json -> compiler -> DataBundle -> compatibility shell -> legacy strict core -> stable artifacts`

这解决了配置真相、数据预加载边界、基线回归门禁和实验目录协议问题，但还没有解决“执行编排真相”。当前系统仍然存在以下结构性问题：

- 9-stage 只停留在语义层和 UI 层，后端并没有一个真实的 stage 总线。
- legacy strict engine 内部仍保留策略分叉和特例路由，难以判断某次运行到底走了哪条内部分支。
- 旧逻辑里信号、退出、风控、排序、下单规划交织在一起，不利于逐步淘汰废弃代码，也不利于证明未来函数安全。
- 后续如果直接删旧代码或直接重写向量核，会同时引入“编排变化”和“计算变化”，失去基线归因能力。

因此，这条 change 的目标不是重写策略数学，而是在现有基线安全壳之上再推进一步：建立单路径 9-stage 日循环执行壳，把公开运行真相固定为一个可审计、可插拔、可逐步替换 legacy 逻辑的总线。

## Goals / Non-Goals

**Goals:**
- 建立唯一的日循环执行壳，明确单次回测只有一条公开执行路径。
- 把 9-stage 从“命名约定”提升为“真实运行契约”，固定 stage 顺序、输入边界和输出边界。
- 保持 `t` 日收盘决策、`t+1` 日开盘成交不变，且继续复用现有 fill / 记账 / NAV 计算核。
- 为每个 stage 增加最小观测面，使前端和治理脚本能看到 stage 是否启用、是否参与、输出了什么摘要。
- 在不改变 `exp_20260308_021045840_cde0` 核心结果的前提下，为后续删除 legacy 编排层建立过渡层。

**Non-Goals:**
- 本 change 不重写向量化价格矩阵、成交撮合、NAV 会计核。
- 本 change 不调整任何策略公式、交易成本、股票池定义或绩效指标口径。
- 本 change 不直接删除所有 legacy 代码，只冻结并收缩其职责。
- 本 change 不要求第一步就输出高体量逐日 stage trace；先交付稳定摘要，再决定是否需要细粒度追踪。

## Decisions

### D1: 新增 `stage_pipeline` 命名空间，而不是继续扩展 compatibility shell

新执行层将单独建在类似 `backend/core/stage_pipeline/` 的命名空间下，至少包含：

- `context.py`: `DayContext`、`PortfolioState`、`DataBundleView`
- `contracts.py`: stage 输入/输出 dataclass 与 neutral output 规范
- `shell.py`: 单一日循环总线
- `adapters/`: 对 legacy 信号/退出/风控/组合构建逻辑的薄包装
- `collector.py`: stage 摘要与审计计数收集

原因：
- `foundation_shell` 的职责是“兼容壳”，不是长期架构中心。
- 如果继续往兼容壳里塞 stage 概念，会让过渡层变成新的历史包袱。
- 独立命名空间可以明确区分“旧计算核”与“新编排壳”。

备选方案：
- 在 `foundation_shell.py` 上继续扩展。拒绝，因为会混淆兼容层和目标架构。
- 直接在 `portfolio_simulator_strict.py` 内改成 stage 模式。拒绝，因为会把编排改动和计算核改动耦合在一起。

### D2: 单路径 stage 壳采用“一层日循环 + 两条子流 + 一个合流点”

外层始终只有一个 `for day in trading_days` 控制循环。  
在每个交易日内，编排固定为：

1. 执行前一交易日挂单，按当日开盘价成交
2. 计算当日收盘后的持仓/NAV 快照
3. 候选流：`S1 -> S2 -> S3 -> S4 -> S5 -> S6`
4. 持仓流：`S9 -> S8`
5. 合流到 `S7`，统一做组合构建与次日挂单规划

说明：
- stage 编号对外保持 9-stage 语义不变。
- 运行顺序允许 `S9/S8` 在 `S7` 之前执行，因为交易上必须先知道卖什么、还剩多少风险预算，才能决定买什么。

原因：
- 这样既满足用户定义的 9-stage 总线，也符合真实交易时钟。
- 候选流和持仓流分开，可以避免“已有持仓逻辑污染新候选逻辑”。
- `S7` 成为唯一订单规划点，便于后续替换 legacy order planner。

备选方案：
- 按编号机械执行 `S1..S9`。拒绝，因为 `S7` 在交易时序上必须晚于退出与风险预算约束。
- 为不同策略保留不同 stage 顺序。拒绝，因为这会再次制造多执行路径。

### D3: 每个 stage 都必须只读输入、显式输出，禁用时返回 neutral output

每个 stage 统一接受：

- `DayContext`: 当前交易日、前一交易日、是否最后一日、执行时钟信息
- `DataBundleView`: 仅暴露截至当日可见的数据切片
- `PortfolioState`: 现金、持仓、待执行订单、上一日快照
- `StageInputs`: 来自前置 stage 的明确中间结果
- `ResolvedConfig/CompiledPlan`: 只读配置

每个 stage 统一返回：

- `StageOutputs`: 候选/持仓/约束/信号/退出/计数/告警等显式字段
- `reason_counts`
- `summary_fragment`

禁用某个 stage 时，不允许切换到另一条执行路径，只能返回 neutral output，例如：

- S2 未启用时返回“不过滤市场环境”
- S3 未启用时返回“不过滤行业”
- S8 未启用时返回“不给额外风险约束”

原因：
- “禁用模块不影响整条流水线”只能通过 neutral output 实现，不能靠 `if/else` 跳到另一种引擎。
- 这也是后续逐步删除 legacy 特例的前提。

备选方案：
- 允许 stage 自行修改全局状态。拒绝，因为无法审计和复用。
- 允许禁用 stage 时切换另一条旧逻辑。拒绝，因为会重新引入多路径真相。

### D4: Stage shell 先替换“决策编排”，继续复用 legacy 会计执行核

本 change 不重写 fill、成本、现金、持仓、NAV 和记账规则，而是把 legacy strict core 拆成两层责任：

- `Decision Shell`: stage pipeline 生成退出、候选和次日订单计划
- `Execution Kernel`: 执行挂单、更新现金/持仓、计算 NAV、写交易记录

第一阶段优先复用当前已经基线验证过的执行核，只替换决策编排方式。  
只有在 stage 壳稳定并长期通过基线门禁后，才允许进一步替换内部计算核。

原因：
- 这能最大限度降低“改编排时误改会计核”的风险。
- 也是满足“不改变基线结果”的唯一现实路径。

备选方案：
- 直接重写整个 engine。拒绝，因为风险过高且无法归因。

### D5: `DataBundleView` 是 stage 壳的唯一数据边界

`DataBundleBuilder` 已经把查库边界收在日循环之前。  
本 change 进一步要求：

- stage 不直接接触 provider、数据库连接或原始 bundle 对象
- stage 只能拿到 `DataBundleView.at(day_index)` 生成的时点切片
- 信号相关字段只能看到截至 `t` 日收盘的可见值
- `t+1` 开盘价只允许在次日 fill 阶段被执行核读取

原因：
- 这是防未来函数和时间错位的硬约束，不应靠实现细节自觉遵守。
- 有了时点视图，后续 stage 单测也更容易构造。

备选方案：
- stage 直接传全量矩阵并靠约定只读到当前日。拒绝，因为难以审计。

### D6: 观测面先交付稳定摘要，默认新增 `stage_summary.json`

为兼顾前端可读性和基线安全，本 change 默认新增一个稳定摘要文件：

- `stage_summary.json`

它至少包含：

- `schema_version`
- `execution_shell`
- `stage_order`
- `enabled_stages`
- `daily_loop_mode`
- `buy_pipeline_counts`
- `sell_pipeline_counts`
- `warnings`

同时：

- `manifest.json` 必须把它纳入 `artifacts`
- `run_meta.json` 必须包含 `stage_pipeline` 的精简摘要
- `audit.json` 必须包含 stage 顺序和关键异常汇总

原因：
- 前端和治理脚本需要一个稳定、轻量、机器可读的 stage 面。
- 直接上逐日 stage trace 体量太大，也更容易引入噪声和口径漂移。

备选方案：
- 只写到 `run_meta.json`。拒绝，因为不利于前端单独读取和版本演进。
- 一开始就输出全量逐日 trace。暂不采用，因为会扩大实现面和回归面。

### D7: 基线验证继续采用“小步替换、逐步放行”

本 change 的每个实现阶段都必须遵守：

1. 只替换一个编排层职责
2. 重新跑 `exp_20260308_021045840_cde0`
3. `portfolio_daily.csv`、`portfolio_trades.csv`、`portfolio_candidates.csv`、`perf.json`、`config_truth` 必须保持 `PASS`
4. 若出现 `WARN`，只能来自当前已允许的诊断性漂移

原因：
- stage 壳本质是大编排变更，如果不分步验证，后续 legacy 删除无法归因。

## Risks / Trade-offs

- [风险] Stage 语义与现有策略分支并不一一对应  
  -> Mitigation：第一阶段用 adapter 包裹 legacy 逻辑，只在编排层统一，不强行重写策略公式。

- [风险] 为了保持基线不变，stage 壳初期会保留一部分“看起来不优雅”的兼容逻辑  
  -> Mitigation：在 tasks 中明确哪些属于临时 adapter，后续只有在基线稳定后才可继续内化。

- [风险] 新增 `stage_summary.json` 会扩大产物协议面  
  -> Mitigation：字段先保持最小闭集，并通过 manifest 显式暴露，不改变现有核心文件名。

- [风险] `DataBundleView` 若实现不严，可能形成“名义只读、实际可越界”的假安全  
  -> Mitigation：接口层不向 stage 暴露 provider/full bundle，并补时点视图单测。

- [风险] stage 编号与执行顺序不完全一致可能引发理解成本  
  -> Mitigation：在 `stage_summary.json` 和审计摘要里同时记录“逻辑编号”和“实际执行顺序”。

## Migration Plan

1. 先创建 `stage_pipeline` 契约、`DayContext`、`DataBundleView` 和 `stage_summary.json` schema，不切公开入口。
2. 再把当前 compatibility shell 包进新的 stage shell，由 stage shell 驱动 legacy adapter 运行。
3. 完成后切 `experiment_runner` 到 stage shell，并保持 execution kernel 不变。
4. 为 stage 摘要、审计和 manifest 增加最小字段，并重新跑锁定基线。
5. 只有在 stage shell 稳定通过基线门禁后，才允许继续拆 legacy strict engine 内部编排代码。

回滚策略：

- 任一步骤只要出现阻塞性基线漂移，立即回退到上一阶段的 shell 入口。
- 在 stage shell 完全稳定前，保留 foundation compatibility shell 作为回退点，但不再增加新功能。

## Open Questions

- 后续是否需要在稳定摘要之外，再增加可选的逐日 `stage_trace` 调试产物；若需要，应当由显式 debug 开关控制，而不是默认输出。
