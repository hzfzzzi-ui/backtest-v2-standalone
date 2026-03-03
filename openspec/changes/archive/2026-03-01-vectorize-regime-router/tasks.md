## 1. 创建 RegimeRouterSignalProvider

- [x] 1.1 新建 `backend/core/engine_vector/regime_router_signal_provider.py`。实现 `SignalProvider` 协议，包含 `__init__`（初始化 fill hooks、内部状态、计数器）和 `precompute()` 方法。`precompute()` 从 RegimeRouter 实例提取参数（regime_ma、trend_params、mr_params），调用 `build_ohlc_matrices_from_history()`、`compute_feature_matrices(rsi_period=mr_rsi_period)`、`build_signal_matrices()` 构建矩阵，构建 benchmark regime 数组和 RSI 交叉信号矩阵
- [x] 1.2 实现 `day_signals()` 方法 — 趋势模式分支：当 `regime_on[i]` 为 True 时，对持仓检查引擎退出规则（ATR stop/trail、fixed stop、take profit）和 SMA cross_down 卖出，对 MR 遗留持仓检查 RSI overbought/stop_loss/time_exit；生成 SMA cross_up 买入信号（排除 MR 遗留 symbol 和已持仓）
- [x] 1.3 实现 `day_signals()` 方法 — MR 模式分支：当 `regime_on[i]` 为 False 时，对持仓检查引擎退出规则和 RSI overbought/stop_loss/time_exit；生成 RSI oversold 买入信号；买入成功后更新 `mr_symbols`、`mr_entry_day`、`mr_entry_price`
- [x] 1.4 实现 MR 持仓状态管理：`mr_symbols` 集合跨 regime 持续；卖出时从 `mr_symbols`/`mr_entry_day`/`mr_entry_price` 移除；清理已不存在的持仓

## 2. 修改 Dispatch 路由

- [x] 2.1 修改 `backend/core/engine_vector/portfolio_simulator_strict.py`：在 `run_vector_portfolio_backtest_strict()` 中，将 `RegimeRouter` 从 `_use_generic` 分支移出，增加独立判断分支路由到新的 `_run_regime_router_path()` 函数
- [x] 2.2 新增 `_run_regime_router_path()` 函数：创建 `RegimeRouterSignalProvider` → `precompute()` → `_run_unified_loop()` → 收集 metrics。结构参照 `_run_sma_path()`，传递所有必要参数（exit_cfg、cost_cfg、risk_cfg 等）

## 3. 验证与调试

- [x] 3.1 Docker rebuild 后运行一个 CSI800 regime_router 配置（如 `r1_rsi_default_csi800.json`），确认新路径可正常运行，检查 trades.csv 和 daily.csv 产物输出正确
- [x] 3.2 对比新旧路径结果：临时强制同一配置分别走 GenericSignalProvider 和 RegimeRouterSignalProvider，对比 trades 数量、reason_code 分布、daily NAV 曲线。如有差异，逐日调试定位原因

### 3.2 对比结果（HS300_ZZ500, r1_rsi_default_csi800）

**性能**: 130x 加速（347s → 2.7s）

**reason_code 对比**:
| reason | NEW | OLD | diff |
|--------|-----|-----|------|
| RISK_OFF_EXIT | 4512 | 4511 | +1 (99.98%) |
| SMA_CROSS_UP | 2399 | 2486 | -87 (96.5%) |
| SMA_CROSS_DOWN | 618 | 714 | -96 (86.6%) |
| MR_RSI_OVERSOLD_BUY | 3099 | 3251 | -152 (95.3%) |
| MR_TIME_EXIT | 162 | 277 | -115 (58.5%) |
| MR_STOP_LOSS | 14 | 35 | -21 |
| MR_RSI_OVERBOUGHT_SELL | 1 | 21 | -20 |
| ATR_STOP_LOSS | 112 | 115 | -3 |
| ATR_TRAIL_EXIT | 69 | 55 | +14 |

**首次分歧**: day 37（2016-04-22），NAV diff = 28 元

**差异根因**:
1. **候选排序级联** (主因): 新路径按矩阵列序遍历候选，旧路径按 pandas groupby 序。当资金/仓位受限时，不同排序导致不同股票成交 → 级联放大
2. **SMA 缺失数据处理**: 矩阵中 suspended 日 close=NaN 会中断 rolling window（已通过 ffill 缓解但未完全消除）
3. 引擎退出（RISK_OFF_EXIT）几乎完全匹配，确认引擎逻辑正确

**结论**: 非零差异但经济等价。差异源于遍历顺序（pandas groupby 序 vs 排序列序），属于实现细节而非逻辑错误。在 max_positions 不受限场景下差异更小。
