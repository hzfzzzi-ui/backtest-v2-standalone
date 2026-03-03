## 1. 配置文件生成

- [x] 1.1 创建 `backend/configs/sweep/` 目录，生成第一轮 RSI 扫描的 8 个 JSON 配置（4 参数组 × 2 universe）。每个配置完整包含 strategy（regime_router + trend_params + mr_params）、exit（ATR stop=2.0, trail=3.0）、universe（CSI800 或 ALL_A limit=4000）、portfolio 等所有必要字段
- [x] 1.2 生成第二轮 ATR 扫描的 8 个 JSON 配置模板（4 参数组 × 2 universe）。RSI 参数暂用默认值，第一轮结果出来后更新

## 2. 批量运行脚本

- [x] 2.1 创建 `backend/core/tools/batch_runner.py`：接收配置目录路径和可选 pattern 过滤，遍历匹配的 JSON 文件，依次调用 `run_experiment()` 执行。每个实验用 try/except 包裹，失败记录日志后继续。终端显示进度 `[N/M] config_name ... done (Xs)` 或 `FAILED (reason)`
- [x] 2.2 在 `run_experiment()` 调用时注入 `source_config` 到 run_meta，确保结果可追溯

## 3. 结果汇总脚本

- [x] 3.1 创建 `backend/core/tools/sweep_report.py`：扫描指定实验目录列表的 `perf.json`，提取 total_return/annual_return/max_drawdown/sharpe_ratio/win_rate/total_trades/turnover，输出对比 CSV（按 sharpe 降序）+ 终端对齐表格。失败实验标记 FAILED

## 4. 执行第一轮 RSI 扫描

- [x] 4.1 Docker rebuild 确保环境就绪，运行第一轮 8 个实验（`pattern="r1_*"`），记录耗时和结果
- [x] 4.2 生成第一轮对比报告，确定最优 RSI 参数组

## 5. 执行第二轮 ATR 扫描

- [x] 5.1 将第一轮最优 RSI 参数更新到第二轮 8 个配置文件中
- [x] 5.2 运行第二轮 8 个实验（`pattern="r2_*"`），记录耗时和结果
- [x] 5.3 生成第二轮对比报告，确定最优 ATR 参数组
- [x] 5.4 输出最终推荐参数组合及其在两个 universe 下的表现

## 实验结果

### Round 1: RSI 参数扫描（固定 ATR stop=2.0, trail=3.0）

| 参数组 | RSI Period | Buy/Sell | MaxHold | StopLoss | CSI800 Sharpe | CSI800 Return | ALL_A Sharpe | ALL_A Return |
|--------|-----------|----------|---------|----------|--------------|---------------|-------------|-------------|
| **patient** | 14 | 25/75 | 10 | 5% | **0.189** | **+17.98%** | -0.175 | -60.95% |
| classic | 14 | 30/70 | 5 | 5% | 0.103 | -1.74% | -0.468 | -80.60% |
| default | 6 | 20/80 | 5 | 3% | 0.020 | -18.37% | -0.533 | -83.50% |
| fast | 6 | 20/80 | 3 | 3% | 0.005 | -21.25% | -0.547 | -84.64% |

**Round 1 最优**: `patient` (rsi_period=14, buy=25, sell=75, max_hold=10, stop_loss=5%)

### Round 2: ATR 退出参数扫描（固定 patient RSI 参数）

| ATR 参数组 | ATR Stop K | ATR Trail K | CSI800 Sharpe | CSI800 Return | CSI800 MaxDD | ALL_A Sharpe | ALL_A Return |
|-----------|-----------|------------|--------------|---------------|-------------|-------------|-------------|
| **trailonly** | OFF | 3.0 | **0.215** | **+24.93%** | -56.89% | -0.211 | -64.58% |
| wide | 2.5 | 4.0 | 0.191 | +18.72% | -57.71% | -0.224 | -66.91% |
| standard | 2.0 | 3.0 | 0.189 | +17.98% | -57.51% | -0.175 | -60.95% |
| tight | 1.5 | 2.5 | 0.165 | +12.54% | -56.96% | -0.155 | -58.88% |

**Round 2 最优**: `trailonly` (enable_atr_stop=false, atr_trail_k=3.0)

### 最终推荐参数

```json
{
  "strategy": {
    "name": "regime_router",
    "regime_ma": 60,
    "trend_params": { "fast": 5, "slow": 20, "order_size": 1000 },
    "mr_params": {
      "rsi_period": 14,
      "rsi_buy_threshold": 25.0,
      "rsi_sell_threshold": 75.0,
      "mr_max_hold_days": 10,
      "mr_stop_loss_pct": 0.05,
      "order_size": 1000
    }
  },
  "exit": {
    "enable_atr_stop": false,
    "enable_atr_trail": true,
    "atr_trail_k": 3.0
  }
}
```

**CSI800 表现**: Sharpe 0.215, Return +24.93%, MaxDD -56.89%
**ALL_A 表现**: Sharpe -0.211, Return -64.58%, MaxDD -75.71%

**关键发现**:
1. 较长 RSI 周期 (14) + 宽松阈值 (25/75) + 长持有期 (10天) 显著优于短期激进参数
2. 关闭 ATR 固定止损、仅保留跟踪止损，在 CSI800 上提升 ~7% 绝对收益
3. 所有配置在 ALL_A (4000 标的) 上均为负收益，说明策略更适合大盘蓝筹股池
4. 向量化引擎使 16 次实验总耗时从预估 ~90 分钟降至 ~7 分钟
