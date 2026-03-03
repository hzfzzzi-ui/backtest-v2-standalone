# Tasks

## Phase 1: 配置与数据模型

- [x] T1: 在 `backend/core/config/models.py` 新增 `BreadthConfig` dataclass（enabled, score_type, mapping_mode, min/max_positions, 阈值参数, ema_fast/slow）
- [x] T2: 在 `backend/core/config/loader.py` 加载 `breadth` section 到 BacktestConfig
- [x] T3: 在 `backend/api/endpoints/_experiment_runner_api.py` 新增 breadth config API 透传

## Phase 2: Breadth Score 计算模块

- [x] T4: 新建 `backend/core/engine_vector/breadth.py`，实现 `BreadthScoreResult` dataclass 和 `compute_breadth_scores()` 函数——包含指标 A (breadth_up)、B (breadth_momo)、C (dispersion)、combo 的向量化计算
- [x] T5: 在 `breadth.py` 中实现 `compute_dynamic_maxpos()` 函数——阶梯版和平滑版两种映射模式

## Phase 3: 引擎集成

- [x] T6: 修改 `_run_unified_loop` 参数：新增 `breadth_cfg` 参数，precompute 阶段从 provider._mx 获取数据并计算 breadth scores + maxpos_arr
- [x] T7: 修改 `_run_unified_loop` 日循环：max_positions 使用 per-day 动态值，`calc_buy_slots` 使用 `day_max`
- [x] T8: 实现 forced sell 逻辑：当 `len(positions) > day_max` 时按 strength 升序卖出最弱持仓，受 min_hold 约束
- [x] T9: 新增 daily_rows 诊断字段（breadth_score, dynamic_maxpos, forced_sell_count）和 loop_state 累计计数器
- [x] T10: 透传 breadth_cfg：`run_portfolio_backtest` → `run_vector_portfolio_backtest_strict` → `_run_sma_path` / `_run_generic_path` / `_run_regime_router_path` → `_run_unified_loop`

## Phase 4: 实验脚本与运行

- [x] T11: Docker rebuild + 冒烟测试（breadth.enabled=false 行为不变；breadth.enabled=true + score_type=B + mapping_mode=smooth 能正常跑完）
- [x] T12: 编写并运行实验脚本：7 组（baseline + A 阶梯/平滑 + B 阶梯/平滑 + C 阶梯/平滑）× 10 年全区间，收集 CAGR/MaxDD/Sharpe/Calmar/trades/avg_positions
- [x] T13: 对表现最好 2 组 + baseline 跑 10 个 1 年 walk-forward 窗口
- [x] T14: 对表现最好 2 组跑 5/15/30/50bp 成本敏感性
- [ ] T15: 可选：combo score (0.5×B + 0.5×C) 阶梯/平滑各一组（跳过——A/B/C 全部跑输 baseline，combo 无意义）

## Phase 5: 报告

- [x] T16: 生成汇总报告（markdown）：summary_table + delta_table + walk-forward 对比 + 结论
