## Context

当前手机端半自动链路已经具备三块基础能力：

- `backend/core/services/mobile_dashboard_service.py` 会读取最新实验、`execution preview` 和 `mobile_ops`，拼装手机端看板。
- `backend/core/services/mobile_ops_service.py` 已经提供二次确认、`approval ticket`、撤回和基础风险锁。
- `frontend/mobile.html` 与 `frontend/assets/js/mobile-dashboard.js` 已经能展示买卖建议、当前持仓和待执行 ticket。

但现阶段“当前持仓”和“待确认动作”的口径仍然是实验视角，不是模拟盘视角：

- `positions` 来自实验 `portfolio_trades.csv` 重建，而不是真实模拟盘持仓。
- `guidance` 来自 `execution preview target_positions` 与实验持仓的差集，而不是“以当前真实持仓为输入”的正式策略重算。
- 手机端确认后只会生成 `approval ticket`，系统里没有“持仓同步 -> 重算 -> 动作失效 -> 再同步”的明确闭环。

如果下一步直接把这套链路接到模拟盘，手机端会看到“实验差集动作单”，而不是“真实模拟盘当前仓位下的动作单”。这会污染执行口径，也会让人工确认失去意义。

本次设计的约束如下：

- 维持 `baseline_V10.1` 的研究口径，不改信号时点，不改执行时点，不把手机端变成最终执行端。
- 当前阶段只做 A 股模拟盘闭环，且优先支持“每日/每次操作前同步一次持仓，再生成下一次动作单”。
- 不在前端重算核心研究逻辑；策略重算必须在后端完成，并输出可审计产物。
- `mobile_ops` 继续只承担移动端确认写模型；真实持仓和重算结果应归入更通用的 `ops` 运行产物。

## Goals / Non-Goals

**Goals:**

- 把模拟盘最新持仓变成手机端“当前持仓”的唯一真相，而不是继续从实验成交反推。
- 在不改 baseline 研究口径的前提下，以最新持仓快照为输入，重跑一次正式策略的日度规划逻辑，生成待确认 action sheet。
- 让手机端同时看到三类信息：最新同步持仓、当前待确认买卖动作、已确认待执行状态。
- 显式表达 freshness、漂移、失效和阻断状态，避免旧动作单继续被当成可执行建议。
- 保持“确认不等于持仓已更新”，当前持仓只能由下一次持仓同步或执行回写刷新。

**Non-Goals:**

- 本轮不做直连券商/模拟盘 SDK 的自动下单，也不把手机端变成最终执行端。
- 本轮不改 `baseline_V10.1` 的信号时点、撮合时点或组合构建口径。
- 本轮不做盘中实时信号刷新，默认仍是日度同步、日度重算、下一交易时点执行。
- 本轮不重做桌面研究平台，不把参数编辑和回测运行搬到手机端。
- 本轮不展开多资产和多账户权限体系，先以单 A 股模拟盘账户为主。

## Decisions

### 决策 1：真实持仓与重算产物进入 `outputs/ops/sim_account/`，不写回实验目录，也不混入 `mobile_ops`

- 选择：
  - 在 `outputs/ops/sim_account/<account_id>/` 下新增：
    - `holdings/latest.json`
    - `holdings/history/<snapshot_id>.json`
    - `reconcile/latest.json`
    - `reconcile/history/<reconcile_id>/...`
    - `audit_log.jsonl`
- 不选：
  - 把真实持仓写回实验目录。
  - 把真实持仓和重算结果继续混进 `outputs/mobile_ops/`。
- 原因：
  - 实验目录是研究产物真相，不能混入运行中账户状态。
  - `mobile_ops` 是手机端确认写模型，不应该兼做账户持仓真相。
  - `outputs/ops/` 已经承载运维/操作产物，最符合这次“每日同步 + 重算”的运行语义。

### 决策 2：首阶段只支持“标准化持仓快照推送/导入”，不直接耦合模拟盘连接器

- 选择：
  - 先定义统一持仓快照 schema，由手工导出脚本、桌面同步脚本或后续连接器写入同一入口。
  - 快照至少包含 `account_id`、`trade_date`、`synced_at`、`cash`、`positions[]`、`qty`、`sellable_qty`、`avg_cost`、`source_type`。
- 不选：
  - 首轮直接把某个模拟盘厂商 SDK、网页登录态或专有 API 硬编码进主链路。
- 原因：
  - 现在最缺的是“口径统一的账户真相”，不是“某一家连接器”。
  - 先把 snapshot 合同做稳，可以后续平滑切到自动同步，而不反向污染手机端和策略侧接口。
  - 这也符合“先固化研发秩序，再扩真实接入”的阶段优先级。

### 决策 3：重算链路采用“SignalProvider + build_rebalance_orders”的持仓感知 planner，而不是继续使用 `execution preview` 差集

- 选择：
  - 新增 position-aware reconcile service，复用现有：
    - semantic config 编译
    - `build_signal_provider()`
    - `precompute_signal_provider()`
    - `provider.day_signals()`
    - `build_rebalance_orders()`
  - 重算输入使用最新持仓快照中的 `positions`、`position_avg_cost`、`cash` 和可选 `holding_sources`。
- 不选：
  - 继续用 `execution preview target_positions - 当前实验持仓` 生成动作单。
  - 为了做模拟盘闭环再拉起一条完整历史回测日循环。
- 原因：
  - 当前 `execution preview` 不消费真实持仓，只适合作为轻量候选预览，不适合作为模拟盘动作单真相。
  - 完整历史回放成本更高，也会把“每日操作规划”错误地和“历史实验回放”绑死。
  - `SignalProvider` 协议本身已经支持 `positions` 和 `position_avg_cost`，适合作为单日规划的可信基础。

### 决策 4：动作单中的“价位”统一定义为计划参考价，首阶段默认取 `as_of_date` 收盘价，并显式暴露 `reference_price_basis`

- 选择：
  - action row 输出：
    - `reference_price`
    - `reference_price_basis`
    - `suggested_qty`
    - `target_weight`
    - `current_qty`
    - `delta_qty`
  - 默认 `reference_price_basis = latest_close`，A 股股数建议按 lot size 和可用现金规则计算。
- 不选：
  - 在没有实时行情和正式撮合上下文的情况下伪造“可直接成交价”。
  - 只给目标权重，不给手机端实际操作所需的参考价和股数。
- 原因：
  - 用户明确要在手机端看到股票、价位和股数。
  - 当前系统的正式交易时钟仍是“收盘后决策，下一交易时点执行”，因此首阶段只能给规划参考价，不能冒充实盘报价。
  - 把 `reference_price_basis` 暴露出来，可以避免后续把参考价误读成已成交价。

### 决策 5：状态机明确拆成 `holdings_snapshot -> reconcile_plan -> approval_ticket -> execution/fill writeback -> next holdings_snapshot`

- 选择：
  - `holdings_snapshot` 表示模拟盘真实持仓真相。
  - `reconcile_plan` 表示基于某个 snapshot 和某个 market date 生成的动作单。
  - `approval_ticket` 表示用户已确认但未完成执行/未完成回写的动作。
  - 新 snapshot 到来后，如与旧 `reconcile_plan` 的 `snapshot_id` 不一致，则旧 plan 进入 `stale` / `drifted`。
- 不选：
  - 手机端确认后立即把“当前持仓”改成预期持仓。
  - 把持仓状态、动作单状态和确认状态混成一个对象。
- 原因：
  - “已确认”不是“已成交”，也不是“当前真实持仓已更新”。
  - 如果确认后直接改持仓，会让手机端持仓失真，后续再同步模拟盘会反复打架。
  - 拆分状态机后，漂移、过期和重复确认都更容易审计。

### 决策 6：继续复用 `/api/mobile/dashboard` 作为聚合入口，但把数据主语从“实验差集”切到“reconcile surface”，并保留兼容降级

- 选择：
  - `/api/mobile/dashboard` 新增：
    - `holding_sync`
    - `reconcile`
    - `positions_source`
    - 卡片级 `snapshot_id` / `reconcile_id`
  - 现有 `guidance` / `approval_cards` 结构尽量保持兼容，由新 reconcile 结果填充。
  - 在 feature flag 关闭或无 snapshot 时，接口可降级回当前只读实验模式，但必须显式标记 `source_mode=experiment_fallback`。
- 不选：
  - 直接另起一套手机端页面和完全独立的 API。
- 原因：
  - 当前手机端前端已经具备基础展示和确认能力，保留入口可以把改动收敛到聚合服务和字段扩展。
  - 但同时必须显式标记当前到底是“真实持仓模式”还是“实验降级模式”，不能静默混用。

### 决策 7：approval prepare / commit 必须校验 `snapshot_id` 和 `reconcile_id`，防止用户确认旧动作单

- 选择：
  - prepare 和 commit 阶段都要求卡片携带 `snapshot_id`、`reconcile_id`、`as_of_date`。
  - 若最新 snapshot / reconcile 与卡片绑定版本不一致，则返回 `409` 并提示先刷新。
- 不选：
  - 只校验 `exp_id` / `signal_date`，继续沿用当前实验视角幂等判断。
- 原因：
  - 一旦真实持仓同步进来，动作单是否有效的关键不再只是实验 id，而是“这张单是否基于当前最新持仓”。
  - 否则用户在手机上看到的旧动作单会在实际账户已变动后继续通过确认。

## Risks / Trade-offs

- [手工或脚本同步的持仓快照可能存在字段缺失、代码映射错误] → 在快照标准化阶段强校验 `symbol/qty/avg_cost`，失败时拒绝覆盖 `latest.json`，并记录 `sync_failed` 审计事件。
- [持仓感知 planner 与现有完整回测路径存在实现分叉风险] → planner 只复用现有 `SignalProvider` 和 `build_rebalance_orders`，并要求输出编译 hash、配置引用和 reason_code 计数，避免出现第二套隐式规则。
- [参考价使用收盘价会与次日真实下单价格偏离] → 明确返回 `reference_price_basis=latest_close`，手机端允许改单股数，但不把该价位描述为可成交价。
- [用户确认后若迟迟未在模拟盘执行，手机端会看到“已确认待执行”但持仓不变] → 保持状态机分层，并在 dashboard 中显式展示 `approved_pending` 与最新持仓同步时间，必要时支持撤回或过期。
- [新持仓快照到来后旧动作单可能失效] → 通过 `snapshot_id/reconcile_id` 并发校验和 plan stale 标记阻断旧单确认。
- [同一手机端入口同时支持 experiment fallback 和 real holdings 模式，容易造成混淆] → 响应必须显式返回 `source_mode`，前端用明显文案标出“实验降级”或“真实持仓模式”。

## Migration Plan

1. 先新增 `sim_account` 持仓快照 schema、落盘服务和同步状态接口，但不改手机端确认行为。
2. 新增 position-aware reconcile service，输出 `reconcile/latest.json` 和历史 run 产物，先做只读验证。
3. 扩展 `/api/mobile/dashboard`，在 feature flag 打开时优先读 reconcile surface；无 snapshot 时仍可回落到 experiment fallback。
4. 在 mobile approval prepare / commit 中加入 `snapshot_id/reconcile_id` 校验，并把 ticket 与 reconcile surface 绑定。
5. 最后才把“无持仓同步时禁止确认”“新 snapshot 到来后旧动作单失效”设为默认硬阻断。
6. 若需回滚：
   - 关闭 `SIM_ACCOUNT_RECONCILE_ENABLED` 等价 feature flag。
   - `/api/mobile/dashboard` 回落到当前 experiment-based 逻辑。
   - 已有 `outputs/ops/sim_account/` 产物保留用于审计，但不再驱动手机端。

## Open Questions

- 首阶段模拟盘持仓是通过哪种方式同步进来最符合你的日常流程：手工导出 CSV/JSON、桌面脚本抓取，还是已有模拟盘 API？
- A 股模拟盘是否需要在第一阶段就严格区分 `qty` 和 `sellable_qty`，以防止 T+1 场景下生成不可卖出的动作单？
- 人工执行完成后，你更希望通过“再次同步持仓”刷新当前仓位，还是额外增加一个“成交回写/已执行确认”入口？
- 首阶段是否只支持单账户（例如 `paper_a_share_main`），还是需要在手机端切换多个模拟盘账户？
