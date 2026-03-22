## 1. 持仓快照真相

- [x] 1.1 新增模拟盘持仓快照 schema、标准化与落盘服务
  DoD: 能写入 `outputs/ops/sim_account/<account_id>/holdings/latest.json` 和 `history/<snapshot_id>.json`，非法 payload 不覆盖 latest。
- [x] 1.2 新增持仓同步状态与 drift 摘要服务
  DoD: 返回 `unsynced/fresh/stale`、最新 `snapshot_id`、同步时间和 drift 摘要。

## 2. 持仓感知重算

- [x] 2.1 新增 position-aware reconcile service，复用 semantic compile 与 planner 链路
  DoD: 基于最新 snapshot 生成 `reconcile_id`、`config_hash` 和 action sheet。
- [x] 2.2 补齐 action sheet 的参考价、建议股数和诊断字段
  DoD: 每条动作包含 `reference_price`、`reference_price_basis`、`suggested_qty`、`current_qty`、`target_weight`、`delta_qty` 和 `reason_tags`。

## 3. 手机端聚合与展示

- [x] 3.1 扩展 `/api/mobile/dashboard` 聚合 contract，优先接入 reconcile surface
- [x] 3.2 更新手机端卡片与状态区块，展示股票、价位、股数、同步时间和 stale/blocked 状态

## 4. 确认边界与失效控制

- [x] 4.1 在 approval prepare / commit 中加入 `snapshot_id`、`reconcile_id` 和 `as_of_date` 并发校验
- [x] 4.2 绑定 `approval ticket` 到 reconcile surface，并保证“确认不改当前持仓”

## 5. 验证与运行说明

- [x] 5.1 增加端到端测试，覆盖 unsynced、stale、drift、approved_pending、refresh 后失效等关键路径
- [ ] 5.2 补运行说明与回退文档，明确“同步持仓 -> 重算 -> 手机确认 -> 再同步持仓”的日常顺序
