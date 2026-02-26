## Context

Risk & Exit Drawer 模块当前状态：
- `index.html` 374-397 行：两个 `<details class="wb-acc">` 区块（Exit / Position & Risk），纯配置输入
- `backtest_v2.js`：`buildConfigDraft()` 序列化 exit_rules + position_risk → JSON；`loadGroupArtifacts()` 从 results 加载 counter 但只显示在 Explain dock
- 后端 `diag_reason_counts` 字典已有 `SKIP_LOT_TOO_SMALL`、`SKIP_CASH_INSUFFICIENT`、`BLOCK_NO_SLOTS` 等；`atr_stop_exit_count`、`atr_trail_exit_count`、`atr_trail_update_count`、`avg_positions` 已在 results 响应中
- 缺失：`reversal_exit_count`、`time_exit_count`、`cap_hit_single`、`cap_hit_industry`、`slots_left`

## Goals / Non-Goals

**Goals:**
- 在 Drawer Risk 模块中展示运行后统计（Exit 触发 + 约束触发）
- 添加 ATR 口径只读提示
- 实现控件联动（checkbox ↔ input disabled）
- 后端补全缺失 counter 字段
- 为 Risk Gate / Exit Priority / Min-trade 提供前端占位 + config JSON 规范
- 所有新 counter 统一在现有 results 响应中返回（方案 B）

**Non-Goals:**
- 不实现 Risk Gate 引擎逻辑（portfolio_simulator_strict.py 不改）
- 不实现 Exit Priority 引擎逻辑
- 不修改回测核心调度流程
- 不新增独立 API 端点

## Decisions

### Decision 1: 统计数据在 Drawer 中展示

**选择**：每个 `<details>` 区块的 `.wb-acc-body` 底部添加统计行，运行后由 JS 填充
**备选**：只在 Dock Explain tab 展示 → 配置和结果分离，不直观
**理由**：用户在调参时需要同时看到配置和上次运行的效果，放一起更高效

### Decision 2: API 规范 — 补全现有 results 响应

**选择**：在 `_extract_counters()` 和 `_stabilise_row()` 中补全缺失字段
**备选**：新建 `/risk_stats` 端点 → 增加 API 复杂度
**理由**：数据来源相同（同一次运行产物），补全字段最简洁

补全字段清单：

| 字段 | 来源 | 说明 |
|------|------|------|
| `reversal_exit_count` | orders/signals 中 reason_code 含 `SIGNAL_REVERSE` 或 `SMA_CROSS_DOWN` 的 sell 计数 | 新增 |
| `time_exit_count` | orders 中 reason_code 含 `TIME_EXIT` 的 sell 计数 | 新增 |
| `cap_hit_single` | diag_reason_counts 中 `BLOCK_SINGLE_CAP` 或类似 key | 新增（如后端无此 key 则默认 0 占位） |
| `cap_hit_industry` | diag_reason_counts 中 `BLOCK_INDUSTRY_CAP` 或类似 key | 新增（同上） |
| `slots_left` | `max_positions - avg_positions` 计算 | 新增 |
| `cash_skip_count` | `diag_reason_counts["SKIP_CASH_INSUFFICIENT"]` 重命名输出 | 别名 |
| `lot_skip_count` | `diag_reason_counts["SKIP_LOT_TOO_SMALL"]` 重命名输出 | 别名 |

### Decision 3: 控件联动方式

**选择**：JS 监听 checkbox change 事件，toggle 对应 input 的 `disabled` 属性 + CSS `.formInput:disabled` 样式
**理由**：原生 HTML disabled 语义正确，屏幕阅读器友好，CSS 自动灰显

### Decision 4: ATR 口径说明

**选择**：Exit 区块内添加一个只读 `<div class="wb-atr-note">` 展示当前配置推导出的 ATR 信息
**内容**：ATR 窗口（固定 14 日）、价格口径（从 Universe 模块的 `wbPriceAdj` 读取）、触发价口径（从 `wbMatchPrice` 读取）
**理由**：避免口径混乱，让用户清楚 ATR 的计算依据

### Decision 5: Risk Gate / Exit Priority / Min-trade — 前端占位策略

三个"强烈建议"功能均采用相同策略：
1. **HTML**：添加 UI 区块，配置控件可交互
2. **JS**：`buildConfigDraft()` 中序列化到 config JSON（`risk_gate` / `exit_priority` / `min_trade_hint` 字段）
3. **后端**：本次不消费这些字段，引擎忽略未知 key
4. **前端标注**：占位区块加 `(即将支持)` 标签

config JSON 规范：

```json
{
  "risk_gate": {
    "enabled": false,
    "drawdown_threshold": -0.10,
    "action": "reduce",
    "cooldown_days": 5
  },
  "exit_priority": ["stop_loss", "reversal", "time", "trail"],
  "min_trade_hint": {
    "enabled": true
  }
}
```

### Decision 6: CSS 新增量

在 `workbench.css` 中添加：
- `.wb-stat-row`：统计行容器（flex，灰色背景条）
- `.wb-stat-item`：单个统计项（label + value）
- `.wb-atr-note`：ATR 口径说明框样式
- `.wb-badge-soon`：「即将支持」标签
- `.formInput:disabled`：灰显样式
- `.wb-priority-list`：退出优先级列表样式

## Risks / Trade-offs

- **[风险] 后端缺少 reversal/time exit 的独立 reason_code** → 需确认引擎中 sell order 的 reason_code 值，可能需要在 `_extract_counters` 中做模式匹配（如 `SMA_CROSS_DOWN` 归入 reversal）
- **[风险] cap_hit 相关的 diag_reason_counts key 可能不存在** → 后端补全时先检查 key 是否存在，不存在则返回 0 占位
- **[权衡] 占位功能不可运行** → 用 `(即将支持)` 标签明确告知用户；checkbox 默认 unchecked
- **[权衡] Drawer 宽度 340px 内塞更多内容** → 统计行用紧凑布局（2-3列 grid），避免超出
