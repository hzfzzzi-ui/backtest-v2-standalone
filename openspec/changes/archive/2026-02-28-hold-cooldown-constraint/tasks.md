## 1. 策略参数声明

- [x] 1.1 在 `ema_cross.py` EMACrossStrategy 新增 `min_hold_days: int = 0`、`cooldown_days: int = 0`、`min_hold_exempt_reasons: list[str]` 三个字段，默认豁免列表为 `["ATR_STOP_LOSS", "ATR_TRAIL_EXIT", "RISK_OFF_EXIT", "TREND_BREAK_EXIT"]`
  - DoD：字段声明存在且有默认值
  - 验证：import 无报错

- [x] 1.2 在 `sma_cross.py` SMACrossStrategy 新增同样三个字段
  - DoD：SMA 策略与 EMA 策略参数对齐
  - 验证：import 无报错

- [x] 1.3 在 `registry.py` 的 ema_cross 和 sma_cross 分支中从 params 读取并传入构造
  - DoD：`build_strategy()` 正确传递 min_hold_days / cooldown_days / min_hold_exempt_reasons
  - 验证：构造 strategy 对象后 getattr 验证值正确

## 2. 引擎核心逻辑

- [x] 2.1 在 `portfolio_simulator_strict.py` SMA 路径模拟循环（line 298 附近）新增 `entry_day: dict[str, date]` 和 `last_sell_day: dict[str, date]` 状态 dict，以及 `min_hold_block_count` / `cooldown_block_count` 计数器
  - DoD：状态变量在循环外初始化
  - 验证：代码无语法错误

- [x] 2.2 BUY 成交阶段（pending 填充 BUY 分支，line 393 附近）：写入 `entry_day[sym] = day`
  - DoD：每次 BUY 成交记录入场日期
  - 验证：在 trade_rows 中验证 entry_day 存在

- [x] 2.3 SELL 成交阶段（pending 填充 SELL 分支，line 358-363 附近）：当 `positions[sym] <= 0` 时写入 `last_sell_day[sym] = day` 并 pop `entry_day[sym]`
  - DoD：清仓时记录卖出日并清理入场日
  - 验证：清仓后 last_sell_day 有值，entry_day 已清理

- [x] 2.4 SELL 信号生成循环（held-only SELL，line 490 附近）：在 reason 判定后、append sell_sigs 前，检查 min_hold_days 约束。若 `held_days < min_hold_days` 且 `reason not in exempt_set` 则 skip 并计数
  - DoD：cross_down 受约束，风控退出不受约束
  - 验证：min_hold_days=5 时持仓 3 天的 cross_down 被阻断，ATR_STOP 不受影响

- [x] 2.5 BUY 候选循环（for c in day_cands，line 596 附近）：在持仓检查后追加 cooldown 检查。若 `sym in last_sell_day` 且 `(day - last_sell_day[sym]).days < cooldown_days` 则 continue 并计数
  - DoD：冷却期内同一标的不被买入
  - 验证：cooldown_days=5 时刚清仓的标的 3 天后金叉不买入

- [x] 2.6 将 `min_hold_block_count` 和 `cooldown_block_count` 加入 metrics 返回 dict 和 `candidate_diag_reason_counts`
  - DoD：metrics 中有两个新计数器
  - 验证：回测结果 JSON 中可见 BLOCK_MIN_HOLD / BLOCK_COOLDOWN

## 3. 参数映射

- [x] 3.1 在 `backtest_v2.py _build_runtime_cfg_from_workbench()` 中从 `wb_cfg.exit_rules.hold_constraint` 读取 min_hold_days / cooldown_days，映射到 `strategy.params`
  - DoD：前端配置 → 后端运行时参数链路贯通
  - 验证：workbench_config 中设置 hold_constraint 后 strategy.params 有值

## 4. 前端 UI

- [x] 4.1 在 `index.html` 退出规则面板（退出优先级之前）新增"持仓约束"分组，含 wbMinHoldDays（number, 0~15, default 0）和 wbCooldownDays（number, 0~30, default 0）
  - DoD：UI 控件可见
  - 验证：页面刷新后控件存在且默认值为 0

- [x] 4.2 在 `backtest_v2.js` 中：buildConfigDraft() 输出 exit_rules.hold_constraint；诊断面板渲染 BLOCK_MIN_HOLD / BLOCK_COOLDOWN；加载配置时 hydration
  - DoD：配置生成 / 诊断展示 / 加载回填三路贯通
  - 验证：设置参数 → 运行 → 诊断面板显示计数 → 加载历史实验恢复参数

## 5. 端到端验证

- [x] 5.1 Docker 构建，使用 plan_a_ema_cross_entry_filter.json 配置（追加 min_hold_days=5, cooldown_days=10）运行对比回测，验证 BLOCK_MIN_HOLD / BLOCK_COOLDOWN 计数 > 0 且交易次数下降
  - DoD：诊断计数器非零，交易频次降低
  - 验证：对比 baseline（无约束）与 hold+cooldown 配置的 trades 数和 reason_code 统计
