## Context

当前 V10.1 的交易漏斗问题横跨后端 runtime、artifact 聚合层和前端结果工作台，属于典型的跨模块合同漂移。

现状不是单点故障，而是三层同时失真：

```text
SignalProvider diagnostics
   │  有些路径产出真实前后阶段计数
   │  有些路径把多个阶段压成同一个数
   ▼
daily_accounting / daily_row
   │  继续用回退值补齐，进一步压平阶段
   ▼
artifact service / buy_stage_funnel
   │  聚合 daily_row 与 run_meta
   │  某些阶段明确 available=false, count=null
   ▼
results workbench
   │  把 unavailable/null 和真实 0 混在一起
   ▼
用户看到“大量 0 值”
```

当前仓库已经有三个相关正式约束：

- [daily-funnel-schema](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/openspec/specs/daily-funnel-schema/spec.md)：定义 daily_row 买卖漏斗字段
- [signal-provider-protocol](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/openspec/specs/signal-provider-protocol/spec.md)：定义 provider diagnostics 应透传到 daily_row 或审计产物
- [results-workbench-finalization](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/openspec/specs/results-workbench-finalization/spec.md)：定义结果工作台为唯一展示 owner

但这三条合同目前没有把“真实计数”和“未单独计数”的边界钉死，导致：

- `daily_accounting` 使用后置阶段值回填前置阶段
- provider diagnostics 键名虽然存在，但不同 provider 语义不一致
- 前端把 `null` 收敛成 `0`

这次设计的目标不是重做漏斗 UI，也不是重做 runtime 路径，而是把漏斗作为“可审计诊断面”重新收紧。

## Goals / Non-Goals

**Goals:**

- 明确 V10.1 交易漏斗的唯一语义：真实计数、汇总值、未单独计数三者必须可区分
- 明确各层 owner，避免 provider、stage pipeline、artifact service、前端互相补数
- 在不改变交易结果的前提下，让结果工作台正确表达漏斗完整度
- 为后续 runtime bridge 清理和热点模块拆分提供稳定的漏斗合同，而不是继续依赖启发式回填

**Non-Goals:**

- 不修改 baseline_V10.1 的执行时点、成交规则、仓位构建或风险预算
- 不强行要求所有 9 个阶段都在本轮产出完整数值
- 不新增新的 artifact 文件名、HTTP 接口名或前端 section 名
- 不借本轮顺手重构整个结果工作台或 signal provider 架构

## Decisions

### D1. 以 `daily_row` 为漏斗计数真相源，`stage_funnel` 仅做投影

**选择**

- 每日漏斗计数的 canonical source 是 `portfolio_daily.csv` 对应的 `daily_row` 字段
- `run_meta.counters.buy_stage_funnel` 与 `stage_funnel` lazy section 只负责聚合和表达，不重新发明计数

**原因**

- `daily_row` 是最接近运行时决策的审计切面，也是当前已有 spec 的正式落点
- 如果 `stage_funnel` 再去补推、猜测或二次纠错，就会形成第二真相源
- 前端本身更不应承担补数责任

**拒绝的替代方案**

- 直接把 `buy_stage_funnel` 视为唯一真相：拒绝。它已经是聚合视图，信息密度低于 `daily_row`
- 让前端从 `dailyRows + reasonRows + counters` 重新推完整漏斗：拒绝。这会把展示层变成研究口径 owner

### D2. 正式区分三种阶段语义：`counted` / `derived` / `unavailable`

**选择**

- `counted`：后端有明确来源的真实阶段计数，数值允许为 `0`
- `derived`：汇总或投影值，用于解释链路，但不宣称是独立阶段真实计数
- `unavailable`：当前没有独立计数来源，必须显式保留 `available=false`，并让相关计数保持 `null`

**映射原则**

- `S1` 属于 `derived`
- `S4-S7` 优先收敛为 `counted`
- `S2/S3/S9` 在没有稳定 runtime owner 前允许保持 `unavailable`
- `S8` 继续拆成执行/约束桶展示，而不是强行塞回买入主链单个数字

**原因**

- 这能把“真实为 0”和“现在没数”分开
- 也允许系统在不造假的前提下逐步提高漏斗完整度

**拒绝的替代方案**

- 要求 9 个阶段全部立即产出数值：拒绝。部分阶段当前没有可靠 source，硬补只会造假
- 继续用 `0` 代表 unavailable：拒绝。这正是当前误导用户的核心问题

### D3. 按层划分 owner，禁止跨层补数

**选择**

- `SignalProvider diagnostics` 负责它真正知道的前序信号计数
  - 例如 `raw_buy_signal_count`、`buy_candidate_count`、`after_held_filter_count`
- `build_rebalance_orders/debug_plan` 负责订单规划后的约束计数
  - 例如 `after_slot_filter_count`、`after_cash_lot_count`、`selected_count`
- `daily_accounting` 负责按优先级收口并写入 `daily_row`
- `artifact service` 负责聚合和保留 `available/null` 语义
- `results workbench` 只负责渲染，不新增、不推断、不改写阶段数值

**计数优先级**

```text
1. 显式 provider diagnostics / planner diagnostics
2. debug_plan 中明确命名的阶段计数
3. 已定义的 derived 规则
4. unavailable（而不是回退成 0 或后置阶段数量）
```

**原因**

- 当前最大问题就是 `daily_accounting` 在缺值时直接退回 `len(day_signals.buy_signals)`，把多个阶段压平
- 把 owner 明确后，任何阶段数值都可以问清楚“它从哪来”

**拒绝的替代方案**

- 继续保留宽松 fallback：拒绝。宽松 fallback 会静默掩盖诊断缺口
- 让 artifact service 用启发式填补缺失阶段：拒绝。那会让聚合层偷偷接管 runtime 合同

### D4. 前端必须原样保留 unavailable/null，不得数值化

**选择**

- 结果工作台 view model 只在 `Number.isFinite(value)` 成立时渲染数值
- 对 `available=false` 或 `null` 的阶段，展示状态、说明和完整度提示，但不显示伪造的 `0`
- summary card 可以继续显示汇总值，但必须与阶段 badge 区分

**原因**

- 漏斗 UI 的职责是“解释系统做了什么”，不是“把所有格子填满”
- 一旦前端把 `null` 数值化，用户就无法区分“策略真的没触发”还是“系统压根没单独记”

**拒绝的替代方案**

- 在 UI 上把 unavailable 显示为灰色的 `0`：拒绝。视觉上仍然会被理解为真实零值
- 只写 note，不改渲染逻辑：拒绝。用户首先看到的还是数字

### D5. 保持 surface 兼容，收紧语义而非扩协议

**选择**

- 继续保留现有 `stage_funnel` section 名和 `run_meta.counters.buy_stage_funnel` 路径
- 优先复用已有字段：
  - `available`
  - `input_count`
  - `output_count`
  - `filtered_count`
  - `note`
- 本轮不引入新的公开 API 名或新的 artifact 文件

**原因**

- 这个问题的本质是语义漂移，不是协议名字不够多
- 保持 surface 路径不变，可以把回归验证集中在“值与语义是否正确”

**拒绝的替代方案**

- 新增 `stage_funnel_v2` 或新 artifact：拒绝。会把简单合同修复升级成协议迁移

## Risks / Trade-offs

- [Risk] 某些 provider 目前拿不到稳定的阶段前后计数，只能继续 unavailable
  → Mitigation：允许 unavailable 合法存在，但禁止再伪装成 0；后续逐 provider 提升覆盖率

- [Risk] 旧实验目录缺少更细粒度 diagnostics，前端切换到新语义后会看到更多“未单独计数”
  → Mitigation：把这视为更诚实的展示；历史实验不强制回填，只保证不误报为 0

- [Risk] 修改 `daily_accounting` 收口逻辑时容易误触交易路径
  → Mitigation：明确本轮只允许修改 diagnostics 写入；若交易结果、NAV、交易笔数漂移，直接判失败

- [Risk] 工作台当前存在多套漏斗 helper，局部修复后仍可能产生双重语义
  → Mitigation：先在 result workbench 主路径落实语义；legacy helper 仅要求与新语义兼容，不在本轮扩大前端重构面

- [Trade-off] 不追求一次性把 S2/S3/S9 全部变成 counted
  → 好处是避免造假；代价是 UI 仍会保留“未单独计数”的阶段提示

## Migration Plan

1. 先修改 specs，补齐 `daily-funnel-schema` 与结果工作台的 unavailable/null 语义
2. 再调整前端结果工作台渲染，让 `null` 不再数值化
3. 再收紧 `daily_accounting` 的 fallback，改为“有正式来源就写值，没有就 unavailable”
4. 最后逐个 provider 补齐可稳定提供的 diagnostics

**验证门槛**

- 同一实验前后对比：
  - `portfolio_daily.csv`
  - `run_meta.json` 中的 `counters.buy_stage_funnel`
  - 结果工作台漏斗面板
- 必须确认：
  - unavailable 阶段不再显示为 0
  - counted 阶段不再被无意义压平
  - 收益、回撤、交易笔数、NAV 不漂移

**回退**

- 这是一条纯合同与诊断修复线，回退只需恢复旧的 spec 与渲染/diagnostics 写法
- 若出现任何交易结果变化，应整轮回退，而不是尝试保留局部“改进”

## Open Questions

- `S2/S3` 在 V10.1 是否应该长期保留为 unavailable，还是应在后续 change 中引入正式 runtime owner？
- `buy_candidate_count` 与 `after_held_filter_count` 是否需要在所有 provider 中强制等义拆分，还是允许部分策略只输出更粗粒度 diagnostics？
- 是否需要给 `stage_funnel` 增加 machine-readable 的 `status` 字段，还是继续只依赖 `available + null` 就足够？
