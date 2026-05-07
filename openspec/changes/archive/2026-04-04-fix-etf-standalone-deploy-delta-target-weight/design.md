## Context

ETF partial fallback fix 落地后，`BULL` 暴露明显下滑，暴露出更深的合同问题：standalone inter-rebalance deploy 在写 BUY signal 的 `target_weight` 时，仍然把 `target_exposure_by_symbol` 当作最终目标仓位直接下单，没有扣掉当前组合中已经存在的 ETF 暴露。对于已经持有 defense/fallback 仓位的日子，这会把 core 宽基 BUY signal 放大成接近 `1.0 NAV` 的整仓单，最终在执行核里被 `SKIP_NO_CASH` 挡掉。

## Goals / Non-Goals

**Goals:**

- 让 standalone inter-rebalance deploy 的 BUY signal 使用增量 deploy gap 语义。
- 确保 emitted BUY signals 的 `target_weight` 总和不超过当日 `standalone_deploy_gap`。
- 保持 monthly rebalance 与 formal `TRANS_UP redeploy` 的既有合同不变。

**Non-Goals:**

- 不改 ETF partial fallback fix。
- 不改 benchmark gate。
- 不改 candidate_plan / execution_orders 的通用执行核。
- 不改变 ETF 研究状态语义或池子定义。

## Decisions

### 决策 1：standalone inter-rebalance deploy 按 symbol delta gap 分配

- 做法：对 standalone inter-rebalance deploy 的活跃 symbols，先计算每个 symbol 的“最终目标 - 当前持仓暴露”得到 `raw_symbol_gap`；再按 `raw_symbol_gap` 比例，把总 `standalone_deploy_gap` 分配成 emitted BUY signals 的 `target_weight`。
- 原因：这能保证 emitted BUY signals 表达的是本次应补的增量 notional，而不是最终整仓目标。
- 备选方案：
  - 在 execution kernel 里扣减已持仓：会把 ETF 语义泄漏进通用执行核。
  - 直接用 `target_exposure_by_symbol`：就是当前导致整仓大单的旧问题。

### 决策 2：只改 standalone inter-rebalance deploy，不改其他路径

- 做法：monthly rebalance 与 formal `TRANS_UP redeploy` 继续保留原有合同。
- 原因：当前问题定位明确在 standalone inter-rebalance deploy，不能把 formal 路径一起带着改。

## Risks / Trade-offs

- [风险] 修复后 `BULL` 的真实可部署暴露可能低于当前结果。  
  → 缓解：这是把错误整仓目标拿掉后的真实行为，应通过回测重新定位下一层瓶颈。

- [风险] 若 delta 分配口径写错，可能让 emitted BUY signals 总和低于应补 gap。  
  → 缓解：增加专门断言，验证 emitted `target_weight` 总和不超过且尽量贴近 `standalone_deploy_gap`。

- [风险] held top-up 在 candidate plan 里仍有 `ALREADY_HELD` 约束。  
  → 缓解：本轮只修 emitted BUY signal 的金额语义，不扩到下一层 held top-up 合同。
