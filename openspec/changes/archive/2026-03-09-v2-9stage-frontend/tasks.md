## 1. Rail 按钮与面板路由

- [x] 1.1 在 `frontend/index.html` 中将 Rail 区域从 5 个按钮扩展到 11 个（S1-S9 + JSON + History），使用 `data-panel="s1"` ~ `data-panel="s9"` 属性，S1-S9 使用数字 badge + 单字标签
- [x] 1.2 在 `frontend/assets/css/workbench.css` 中缩小 Rail 按钮间距以容纳 11 个按钮，添加 S1-S9 按钮的 badge 样式和分隔线样式
- [x] 1.3 在 `frontend/assets/js/ui-controls.js` 中更新面板切换逻辑：`data-panel` 值从 `universe/sigcomp/risk/json/history` 变为 `s1~s9/json/history`，Drawer 标题根据当前面板显示对应阶段名称

## 2. HTML 面板拆分重组

- [x] 2.1 在 `frontend/index.html` 中将 `data-module="universe"` 改为 `data-module="s1"`，HTML 内容不变
- [x] 2.2 新建 `data-module="s2"` 面板：从 sigcomp 中提取市况判断面板（wbRegimePanel 及其子元素）作为独立的 S2 大盘环境面板
- [x] 2.3 新建 `data-module="s3"` 面板：行业门控参数（enable 开关, rank_window=60, top_pct=30%）
- [x] 2.4 新建 `data-module="s4"` 面板：从 sigcomp 中提取入场趋势过滤块（wbEntryFilterBlock 及其子元素），改为独立的 S4 个股趋势面板
- [x] 2.5 新建 `data-module="s5"` 面板：个股排序参数（momentum_top_pct 启用开关 + 百分比输入）
- [x] 2.6 重组 `data-module="s6"` 面板：保留策略选择器 + 趋势模式参数 + 震荡模式参数，删除 Composition Pipeline 区块
- [x] 2.7 新建 `data-module="s7"` 面板：从 risk 中提取持仓部分（max_positions, lot, single_stock_cap, sizing 相关控件）
- [x] 2.8 新建 `data-module="s8"` 面板：从 risk 中提取风控部分（DD 熔断参数, MA200 市场过滤, ATR 止损倍数）
- [x] 2.9 重组 `data-module="s9"` 面板：原 Exit 面板改为独立面板，新增 MA20 退出和 LOW10 退出开关

## 3. S6 策略选择器与参数面板

- [x] 3.1 在 S6 面板的策略选择器 `<select id="wbTrendStrategy">` 中新增 `BREAKOUT_TREND`（突破趋势）和 `RSI_REVERSAL`（RSI 均值回归）选项
- [x] 3.2 新增 Breakout 参数面板 HTML（`wbBreakoutParams`：breakout_window 输入框，默认 20）
- [x] 3.3 新增 RSI 参数面板 HTML（`wbMrParamsRSI`：rsi_period=6, rsi_buy=20, rsi_sell=80, hold=10, stop=5%）
- [x] 3.4 在 `ui-controls.js` 中为策略选择器添加 change 事件处理：根据选择动态显示/隐藏对应参数面板（SMA→sma面板, BREAKOUT→breakout面板, RSI→rsi面板）

## 4. buildConfigDraft / applyConfigToUI 重构

- [x] 4.1 在 `buildConfigDraft()` 中添加 BREAKOUT_TREND 分支：生成 `signal_generation.breakout = { breakout_window }` 块
- [x] 4.2 在 `buildConfigDraft()` 中添加 RSI_REVERSAL 分支：生成 `signal_generation.mr = { rsi_period, rsi_buy_threshold, rsi_sell_threshold, mr_hold_days, mr_stop_loss_pct }` 块
- [x] 4.3 在 `buildConfigDraft()` 中添加 S3/S5/S9 新字段：`sector_gate`、`signal_generation.ranking`、`stock_trend_filter`、`exit_rules.ma20_exit`、`exit_rules.low10_exit`、`universe_filter.min_price`
- [x] 4.4 在 `applyConfigToUI()` 中添加 BREAKOUT_TREND 反向映射：选中选择器 → 显示 breakout 面板 → 填写 breakout_window
- [x] 4.5 在 `applyConfigToUI()` 中添加 RSI_REVERSAL 反向映射：选中选择器 → 显示 RSI 面板 → 填写所有 RSI 参数
- [x] 4.6 在 `applyConfigToUI()` 中添加 S3/S4/S5/S8/S9 新字段的反向映射（sector_gate, stock_trend_filter, ranking, risk_budget, ma20_exit, low10_exit）

## 5. 冠军配置预置

- [x] 5.1 在 `_config_store.py` 中新增 `_breakout_champion_config_json()` 函数，返回 P3-D 冠军配置的 workbench JSON（breakout_window=20, TP=20%, trail=3, stop=1.5, DD=10%/0.5, CSI800, 2016-2026）
- [x] 5.2 在 `_config_store.py` 中新增 `_ema_champion_config_json()` 函数，返回 EMA(8,25) 冠军配置的 workbench JSON（TP=30%, trail=6, min5/cool5, CSI800, 2016-2026）
- [x] 5.3 在 `_ensure_builtin_flow_script_config()` 同级新增 `_ensure_builtin_champion_configs()` 函数，在配置列表 API 被调用时自动创建两个冠军配置文件
- [x] 5.4 在 `list_backtest_v2_configs()` 和 `get_backtest_v2_config()` 中调用 `_ensure_builtin_champion_configs()`

## 6. 端到端验证

- [x] 6.1 从前端加载 Breakout 冠军配置 → 检查 UI 控件回填正确 → 发起回测 → 验证结果与 3.4 号脚本一致（CAGR +5.46%, MDD -24.32%）
- [x] 6.2 从前端加载 EMA 冠军配置 → 检查 UI 控件回填正确 → 确认 fast_ma=8, slow_ma=25, TP=30%, trail=6 均正确显示
