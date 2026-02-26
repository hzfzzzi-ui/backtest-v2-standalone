## 1. CSS 新增样式

- [x] 1.1 在 `workbench.css` 中添加 `.wb-stat-row`（统计行容器：grid 2-3列、紧凑布局）
- [x] 1.2 添加 `.wb-stat-item`（单个统计项：label + value 上下排列）
- [x] 1.3 添加 `.wb-atr-note`（ATR 口径说明框：border-left 蓝条、小字灰底）
- [x] 1.4 添加 `.wb-badge-soon`（「即将支持」标签：小圆角、黄色边框）
- [x] 1.5 添加 `.formInput:disabled` 灰显样式
- [x] 1.6 添加 `.wb-priority-list`（退出优先级列表样式）
- [x] 1.7 添加 `.wb-hint-warn`（最小成交警告样式）

## 2. HTML — Exit 区块增强

- [x] 2.1 为 `trail_k` 和 `N days` 的 `<label>` 添加单位标注（×ATR / 天）
- [x] 2.2 在 Exit accordion body 底部添加 ATR 口径说明 `<div id="wbAtrNote" class="wb-atr-note">`
- [x] 2.3 在 Exit accordion body 底部添加触发统计行 `<div id="wbExitStats" class="wb-stat-row">`，包含 5 个 `wb-stat-item` 占位
- [x] 2.4 在 Exit accordion body 底部添加退出优先级区块 `<div id="wbExitPriority">` 带 `wb-badge-soon` 标签

## 3. HTML — Position & Risk 区块增强

- [x] 3.1 在 Position & Risk accordion body 底部添加约束统计行 `<div id="wbConstraintStats" class="wb-stat-row">`，包含 6 个 `wb-stat-item` 占位
- [x] 3.2 在 Position & Risk accordion body 底部添加最小成交提示 `<div id="wbMinTradeHint">` 带 `wb-badge-soon`

## 4. HTML — Risk Gate 新区块

- [x] 4.1 在 Position & Risk 下方添加新的 `<details class="wb-acc">` 区块 "Risk Gate (即将支持)"
- [x] 4.2 包含控件：enable checkbox、drawdown_threshold input（%）、action select（降档/停手）、cooldown_days input
- [x] 4.3 包含 trigger_count 统计占位

## 5. JS — 控件联动

- [x] 5.1 添加 `syncExitLinkage()` 函数：监听 wbExitTrail / wbExitTime checkbox 的 change 事件，toggle 对应 input 的 disabled 属性
- [x] 5.2 页面 init 时调用 `syncExitLinkage()` 设置初始状态
- [x] 5.3 `hydrateConfig()` 加载配置后也调用 `syncExitLinkage()`

## 6. JS — ATR 口径说明

- [x] 6.1 添加 `updateAtrNote()` 函数：从 wbPriceAdj 和 wbMatchPrice 读取当前配置，更新 `#wbAtrNote` 内容
- [x] 6.2 Universe 模块的价格口径 / 成交价假设控件 change 时调用 `updateAtrNote()`
- [x] 6.3 页面 init 和 config load 时调用 `updateAtrNote()`

## 7. JS — 统计数据填充

- [x] 7.1 添加 `populateExitStats(counters)` 函数：将 5 个退出计数填入 `#wbExitStats` 的各 stat-item
- [x] 7.2 添加 `populateConstraintStats(counters, config)` 函数：将 6 个约束计数填入 `#wbConstraintStats`，`slots_left` = `max_positions - avg_positions`
- [x] 7.3 在 `loadGroupArtifacts()` 的 counter 加载逻辑中调用上述两个函数

## 8. JS — Config 序列化 & 加载

- [x] 8.1 `buildConfigDraft()` 中添加 `risk_gate` 字段序列化
- [x] 8.2 `buildConfigDraft()` 中添加 `exit_priority` 字段序列化（默认 `["stop_loss", "reversal", "time", "trail"]`）
- [x] 8.3 `hydrateConfig()` 中添加 Risk Gate 控件加载
- [x] 8.4 `hydrateConfig()` 中添加 exit_priority 列表加载

## 9. 后端 — 补全 counter 字段

- [x] 9.1 在 `backtest_v2.py` 的 `_extract_counters()` 中添加 `reversal_exit_count`：从 orders/signals 中计数 reason_code 包含信号反转的 sell
- [x] 9.2 在 `_extract_counters()` 中添加 `time_exit_count`：从 orders 中计数 reason_code 包含 `TIME_EXIT` 的 sell
- [x] 9.3 在 `_extract_counters()` 中添加 `cash_skip_count` 和 `lot_skip_count`（从 diag_reason_counts 映射）
- [x] 9.4 在 `_extract_counters()` 中添加 `cap_hit_single` 和 `cap_hit_industry`（从 diag_reason_counts 映射，不存在则 0）
- [x] 9.5 在 `_extract_counters()` 中添加 `slots_left`（`max_positions - avg_positions`）
- [x] 9.6 在 `_stabilise_row()` 和 `backtest_v2_artifacts.py` 的 counter 白名单中注册新字段

## 10. 验证

- [x] 10.1 Docker 重建，验证页面 Risk 模块所有新 UI 元素正确显示
- [x] 10.2 验证控件联动：unchecked 状态下 input 置灰
- [x] 10.3 验证 ATR 口径说明跟随 Universe 配置更新
- [x] 10.4 验证运行回测后 Exit 统计和约束统计能被填充
