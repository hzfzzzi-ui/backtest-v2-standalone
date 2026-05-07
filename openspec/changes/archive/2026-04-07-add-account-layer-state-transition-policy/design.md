## Context

当前系统已经完成账户层 steady-state budget 上收，但 `docs/04_重构思路` 对照现实后，仍存在三个结构性断层：

1. 账户层只接管了稳态预算，没有接管状态切换时的库存重构与现金释放。
2. 组合 runtime 仍通过 `stock_weight / etf_weight` 的旧二腿混合器表达主结果，`combo/reference` 仍与账户层主叙事并列存在。
3. explain、audit、query 与前端结果页虽然已接入账户层字段，但仍在同一层并列展示旧 combo/governor 语义，持续制造双重语义。

这意味着当前系统虽然已切到账户层主真相，但状态切换与执行落地仍部分依赖旧 ETF 局部逻辑。若继续推进 `RISK_OFF-only` change，会进一步放大新旧语义并存的问题。

## Goals / Non-Goals

**Goals:**
- 建立覆盖全部状态切换类型的账户层统一合同，而不是继续按单状态 patch 推进。
- 明确账户层状态机是上游真相，sleeve 状态只能作为输入证据，不得反向定义账户状态。
- 统一定义状态切换输出：carry rules、de-risk rules、cash release rules、budget handoff rules。
- 收紧 `combo/reference` 边界，使其退为 benchmark/reference 区，不再与账户层主叙事并列承担 runtime 真相。
- 收紧 explain / audit / query / frontend，确保 `runtime_truth_source = account_allocator` 时只保留账户层主叙事。

**Non-Goals:**
- 本 change 不直接重写 stock alpha、主 regime 或总暴露曲线。
- 本 change 不要求一次性落地全部状态切换的执行实现；允许先完整定义合同，再按优先级逐类实现。
- 本 change 不要求立即把 ETF 代码拆成两个独立 runtime sleeve；本轮先统一语义与边界。
- 本 change 不把收益提升作为首要目标，首要目标是单真相、可归因和状态切换合同完整性。

## Decisions

### 1. 先统一定义全部状态切换合同，再按优先级实现
- 决策：合同层一次覆盖四类状态切换：`risk_on -> risk_on`、`risk_on -> defensive`、`defensive -> defensive`、`defensive -> recovery`。
- 原因：只定义 `RISK_OFF` 会天然保留双语义；统一合同是消除“单状态新语义 + 其余状态旧语义”的前提。
- 备选方案：继续按 `RISK_OFF-only` 推进。
- 放弃原因：会把实现优先级误当成合同范围，持续制造双真相。

### 2. 账户状态机必须成为上游真相
- 决策：账户层状态不得再由 stock/ETF sleeve 状态简单聚合反推；组件状态只能作为账户状态机的输入证据。
- 原因：`docs/04` 的核心就是“账户先定预算，再由 sleeve 执行”。
- 备选方案：继续使用 `_most_defensive_state(stock_state, etf_state)` 作为账户状态。
- 放弃原因：这会让账户层继续成为 sleeve 派生层，而不是上游真相。

### 3. 状态切换合同必须显式输出四类执行意图
- 决策：账户层在状态切换时必须显式输出：
  - carry rules
  - de-risk rules
  - cash release rules
  - budget handoff rules
- 原因：当前所有弱势问题都反复暴露在“库存和现金结构没有被正式定义”的断层上。
- 备选方案：继续把 cash release、cash drip、weak-state materialization 留在 ETF 局部执行链。
- 放弃原因：这会把执行层继续变成策略补丁层。

### 4. `combo/reference` 保留，但只能退为参考区
- 决策：保留历史 combo/reference 以支持 benchmark、回放参考和兼容读，但它们必须退到 reference 区，不再与账户层主叙事并列。
- 原因：现有主线仍需要历史比较锚点，但不能继续让 reference 与 runtime 主真相同层竞争解释权。
- 备选方案：彻底删除 combo/reference。
- 放弃原因：会损失回放与历史比较能力，且并非当前最紧迫问题。

### 5. explain / audit / frontend 统一到账户层优先
- 决策：当 `runtime_truth_source = account_allocator` 时，query 与前端只能输出一个主叙事；旧 combo/governor 只能作为 reference 附属说明。
- 原因：如果展示层继续平铺账户层与 combo 层，用户将持续看到双重语义。
- 备选方案：继续保留并列展示，由用户自行理解。
- 放弃原因：这与“账户层成为唯一真相”的架构目标直接冲突。

## Risks / Trade-offs

- [风险] 合同范围一次定义全状态切换，短期实现成本明显上升。 → [缓解] 将“合同定义”与“执行实现优先级”分开，允许先完整定义，再优先实现 `risk_on -> defensive`。
- [风险] 收紧 combo/reference 主叙事后，部分旧页面或脚本的字段期待会变化。 → [缓解] 保留 reference 区字段，但在主 surface 中降级呈现，不直接删除底层参考数据。
- [风险] 账户状态机上收后，现有由 sleeve 状态聚合的 explain 逻辑会出现迁移成本。 → [缓解] 先统一 runtime/audit/query 合同，再逐步替换前端和报表字段。
- [风险] 如果继续把执行 patch 混入本 change，会再次扩大归因面。 → [缓解] 本 change 只定义统一合同与边界收口，不在同一轮混入新的局部执行补丁。
