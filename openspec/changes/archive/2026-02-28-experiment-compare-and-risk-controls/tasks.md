## 1. Phase 1 — 后端风控增强（引擎 + 配置）

- [x] 1.1 在 `models.py` 中新增 `ExitConfig`（止盈 + 固定止损字段）和 `RiskConfig`（回撤熔断字段），扩展 `SizingConfig`（波动率调仓字段）
- [x] 1.2 在 `portfolio_simulator_strict.py` 退出优先级链中新增止盈判断（固定百分比模式 + ATR 倍数模式），reason_code = `TAKE_PROFIT`
- [x] 1.3 在 `portfolio_simulator_strict.py` 退出优先级链中新增固定百分比止损判断，reason_code = `FIXED_STOP_LOSS`
- [x] 1.4 在 `portfolio_simulator_strict.py` 日循环中新增回撤熔断逻辑：跟踪 NAV 峰值和回撤比例，熔断时 buy_slots = 0
- [x] 1.5 在 `portfolio_builder.py` 的 `build_rebalance_orders()` 中新增波动率调仓：ATR 反比调整下单金额，设上下限
- [x] 1.6 将新增配置从 `experiment_runner.py` / `_experiment_runner_api.py` 透传到引擎调用链
- [x] 1.7 在引擎 metrics 输出中新增所有计数器：`take_profit_exit_count`, `fixed_stop_loss_exit_count`, `drawdown_breaker_block_count`, `drawdown_breaker_trigger_count`, `drawdown_breaker_recover_count`
- [x] 1.8 Docker rebuild + curl 冒烟测试：确认默认参数（全部关闭）下回测结果不变

## 2. Phase 2 — 前端风控 UI

- [x] 2.1 在 `index.html` 退出配置区域新增止盈控件：checkbox + 模式选择 + 参数输入（百分比/ATR倍数）
- [x] 2.2 在 `index.html` 退出配置区域新增固定止损控件：checkbox + 百分比输入
- [x] 2.3 在 `index.html` 仓位配置区域新增波动率调仓控件：checkbox + 目标风险比例输入
- [x] 2.4 在 `index.html` 风控配置区域新增回撤熔断控件：checkbox + 触发/恢复阈值输入
- [x] 2.5 在 `ui-controls.js` 的 `buildConfigDraft()` 和 `applyConfigToUI()` 中新增字段映射
- [x] 2.6 在 `_experiment_runner_api.py` 的 `_build_runtime_cfg_from_workbench()` 中新增字段编译
- [x] 2.7 在 `artifacts.js` 的 `renderExplainPanel()` 中新增计数器展示（止盈、固定止损、熔断拦截）
- [x] 2.8 Docker rebuild + 前端验证：启用止盈后运行回测，确认 reason_code 和计数器正确

## 3. Phase 3 — 多实验对比

- [x] 3.1 在 `_experiment_history.py` 中新增 `POST /api/backtest_v2/experiments/compare` 端点：批量读取 perf.json + nav.csv
- [x] 3.2 在 `backtest_v2.js` 历史面板中新增勾选模式：checkbox + "对比"按钮 + 已选计数
- [x] 3.3 新建 `compare.js`：对比视图 overlay 组件（KPI 对比表 + 最优值高亮 + 关闭/加载交互）
- [x] 3.4 在 `compare.js` 中实现 NAV 多曲线叠加渲染（复用 LightweightCharts，多 LineSeries）
- [x] 3.5 在 `index.html` 中添加 `compare.js` 的 `<script>` 标签和对比 overlay 的 HTML 容器
- [x] 3.6 Docker rebuild + 前端验证：勾选 2-3 个实验后打开对比视图，确认 KPI 表和 NAV 曲线正确

## 4. Phase 4 — 集成验证

- [x] 4.1 完整流程测试：启用全部风控参数运行回测 → 查看计数器 → 再运行一次不同参数 → 对比两次实验
- [x] 4.2 确认默认参数（风控全关）下回测结果与修改前一致
- [x] 4.3 确认前端配置保存/加载正确包含新增字段
