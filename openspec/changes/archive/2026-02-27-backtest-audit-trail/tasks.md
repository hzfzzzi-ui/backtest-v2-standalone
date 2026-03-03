## 1. AuditCollector 核心类

- [x] 1.1 新建 `backend/core/engine_vector/audit_collector.py`，实现 `AuditCollector` 类，包含：构造函数（接收 initial_cash、max_positions、cost_config）、内部状态（day_audits 列表、汇总计数器、flags 列表）。DoD：文件存在，类可实例化。
- [x] 1.2 实现 `record_data_quality(open_idx, close_idx, trading_days, symbols)` 方法（CP1）：统计 NaN 率、日期缺口数、标的覆盖率。DoD：调用后 `self.data_quality` 包含 close_nan_rate、open_nan_rate、trading_days_count、date_gaps、symbols_count、symbols_with_full_coverage。
- [x] 1.3 实现 `begin_day(date, cash, positions)` 方法：记录当天 fill 前的现金和持仓快照。DoD：调用后内部 `_current_day` 包含 cash_before 和 positions_before。
- [x] 1.4 实现 `record_fills(trade_rows_today, cash_after, positions_after)` 方法（CP2）：计算现金守恒检查（cash_after == cash_before + Σsell_net - Σbuy_net）、持仓守恒检查（positions_after == positions_before + new - exit）、每笔成交的 slip_bps 验证。DoD：_current_day 包含 cash_check、pos_check、fills 明细。
- [x] 1.5 实现 `record_nav(nav, cash, market_value)` 方法（CP3）：验证 nav == cash + market_value（容差 0.01）、nav 非 NaN 非负。DoD：_current_day 包含 nav_check。
- [x] 1.6 实现 `record_signals(signals_count, orders_count, fills_from_yesterday_count)` 方法（CP4）：记录信号/订单/成交数量，T+1 检查。DoD：_current_day 包含 t1_check。
- [x] 1.7 实现 `end_day(turnover_pct)` 方法：将 _current_day 汇总到计数器；检测当日可疑模式（现金负值、持仓超限、NAV 异常、单日全换手、孤立成交、涨跌停成交）；如有异常则加入 flagged_days。DoD：day_audits 递增，flags 按条件追加。
- [x] 1.8 实现 `finalize(exp_id, total_signals)` 方法（CP5）：计算策略僵死检测（连续 20 天无信号）、汇总价格跳空分布（P50/P95/Max）、汇总成本（total_commission/stamp_tax/slippage/cost_as_pct_of_initial）、组装完整 audit dict（version/exp_id/generated_at/summary/data_quality/flagged_days/flags）。截断 flags 至 50 条上限。DoD：返回完整 audit dict，符合 spec 定义的 schema。

## 2. 引擎集成——SMA 路径

- [x] 2.1 在 `run_vector_portfolio_backtest_strict()` 中实例化 `AuditCollector`，在循环前调用 `record_data_quality()`。DoD：CP1 数据在循环开始前已记录。
- [x] 2.2 在 SMA 路径的逐日循环中插入 `begin_day()` → fill 执行后 `record_fills()` → NAV 快照后 `record_nav()` → 信号/订单后 `record_signals()` → `end_day()`。DoD：每个交易日均触发 5 个检查点方法调用。
- [x] 2.3 在 SMA 路径循环结束后调用 `finalize()`，将 audit dict 写入 `metrics["audit"]`。DoD：`PortfolioBacktestResult.metrics["audit"]` 包含完整审计数据。

## 3. 引擎集成——Generic 路径

- [x] 3.1 在 `_run_vector_portfolio_backtest_generic_signals()` 中实例化 `AuditCollector`，在循环前调用 `record_data_quality()`。DoD：CP1 数据在循环开始前已记录。
- [x] 3.2 在 Generic 路径的逐日循环中插入相同的 5 个检查点方法调用。DoD：与 SMA 路径一致的审计覆盖。
- [x] 3.3 在 Generic 路径循环结束后调用 `finalize()`，将 audit dict 写入 `metrics["audit"]`。DoD：`PortfolioBacktestResult.metrics["audit"]` 包含完整审计数据。

## 4. 产物层集成

- [x] 4.1 在 `ensure_standard_artifacts()` 中新增 audit.json 写入：从 `result.get("metrics", {}).get("audit")` 提取审计数据，写入 `results_dir/audit.json`；更新 artifacts dict 增加 `"audit": "audit.json"` 或 null。DoD：回测后实验目录出现 audit.json。

## 5. 构建与验证

- [x] 5.1 Docker 重建并运行一次回测，验证：(1) audit.json 存在于实验目录 (2) summary 中 cash/pos/nav/t1_check_fail 均为 0 (3) data_quality 字段完整 (4) cost_config 与配置一致 (5) flags 为空数组或仅含 WARNING 级别。
