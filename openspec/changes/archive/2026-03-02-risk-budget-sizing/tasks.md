## 1. Config 层改动

- [x] 1.1 在 `models.py` 新增 `RiskBudgetConfig` dataclass（enabled, base_portfolio_risk, trend_multiplier, dd_scale_10, dd_scale_15, dd_fixed_20, dd_stop_pct, min_active_ratio, atr_stop_k）
- [x] 1.2 在 `BacktestConfig` 中新增 `risk_budget: RiskBudgetConfig` 字段（默认值）
- [x] 1.3 从 `SizingConfig` 删除 `enable_volatility_sizing` 和 `vol_target_risk_pct`
- [x] 1.4 从 `RiskConfig` 删除 `enable_drawdown_breaker`、`drawdown_breaker_pct`、`drawdown_breaker_recover_pct`
- [x] 1.5 从 `ExitConfig` 删除 `atr_stop_k`（移入 RiskBudgetConfig）
- [x] 1.6 在 `loader.py` 中添加 `RiskBudgetConfig` 加载逻辑，旧字段静默忽略

## 2. 仿真循环改动

- [x] 2.1 在 `portfolio_simulator_strict.py` 的 `_run_unified_loop()` 中删除 drawdown breaker 逻辑（_breaker_active 状态机、trigger/recover 计数器）
- [x] 2.2 新增 risk budget 计算逻辑：在 NAV/drawdown 计算后，根据 dd_ratio 计算 portfolio_risk、dd_scale、per_trade_risk、risk_amount
- [x] 2.3 当 dd_ratio >= dd_stop_pct 时，拦截所有买入信号并累加 `dd_stop_block_count`
- [x] 2.4 将 `risk_amount` 作为参数传入 `build_rebalance_orders()`
- [x] 2.5 在 daily_row 中写入 `portfolio_risk`、`per_trade_risk`、`dd_scale`、`trend_mult` 四个字段
- [x] 2.6 新增分档计数器（dd_scale_08_count, dd_scale_06_count, dd_fixed_03_count, dd_stop_count, dd_stop_block_count），写入最终 metrics

## 3. 订单构建改动

- [x] 3.1 在 `portfolio_builder.py` 的 `build_rebalance_orders()` 中新增 `risk_amount` 和 `atr_stop_k` 参数
- [x] 3.2 当 `risk_amount > 0` 时，替换等权/vol sizing 逻辑为 ATR 定仓：`shares = risk_amount / (atr_stop_k × atr)`
- [x] 3.3 ATR 不可用时降级为等权（`nav / max_positions / price`）
- [x] 3.4 添加 single_stock_cap 安全上限截断
- [x] 3.5 删除旧 vol sizing 代码块（lines 315-321 附近）

## 4. 退出规则 atr_stop_k 统一

- [x] 4.1 在 signal provider 初始化时从 `RiskBudgetConfig.atr_stop_k` 读取 k 值（替代 `ExitConfig.atr_stop_k`）
- [x] 4.2 更新 `sma_signal_provider.py` 中 atr_stop_k 的读取来源
- [x] 4.3 更新 `generic_signal_provider.py` 中 atr_stop_k 的读取来源
- [x] 4.4 更新 `regime_router_signal_provider.py` 中 atr_stop_k 的读取来源

## 5. API / 实验透传

- [x] 5.1 在 `backtest_v2.py` API 端点中解析前端传入的 risk_budget 参数，构建 `RiskBudgetConfig`
- [x] 5.2 在 `experiment_runner.py` 中透传 `RiskBudgetConfig` 到引擎调用
- [x] 5.3 确保 `run_meta.json` 配置快照包含 risk_budget 配置

## 6. 前端 UI

- [x] 6.1 在 `index.html` "仓位风控"区块中添加"风险预算"控件组（开关 + 参数输入）
- [x] 6.2 在 `backtest_v2.js` 中收集 risk_budget 参数并发送到后端 API
- [x] 6.3 移除前端旧"波动率调仓"和"回撤熔断"的 UI 控件
- [x] 6.4 在 `backtest_v2.js` 中删除旧 vol sizing 和 drawdown breaker 参数收集代码

## 7. 验证

- [ ] 7.1 Docker rebuild + 运行回测，确认 risk_budget.enabled=false 时行为与改动前一致
- [ ] 7.2 启用 risk_budget，确认 daily_row 包含 portfolio_risk/per_trade_risk/dd_scale/trend_mult 字段
- [x] 7.3 确认前端"仓位风控"区块显示新控件，旧控件已移除

## 8. DD_STOP 恢复机制

- [x] 8.1 在 `RiskBudgetConfig` 添加 `dd_stop_cooldown_days: int = 120` 和 `dd_stop_protect_days: int = 60`
- [x] 8.2 在 `_run_unified_loop()` 实现恢复状态机：STOP(idle≥120天)→FIXED_PROTECTED(60天)→重新评估
- [x] 8.3 新增计数器 `dd_stop_reset_count`，daily_row 新增 `dd_stop_state` 字段
- [x] 8.4 API/前端透传新参数（loader + _experiment_runner_api + ui-controls + index.html + artifacts.js）
- [x] 8.5 Docker rebuild + 跑 2015-2026 回测验证恢复机制（peak_nav reset 生效，5次重置，max_dd从70%降到37%）
