## Context

`regime_router` 策略已实现：benchmark close vs MA(regime_ma) 判断市场状态，趋势市用 SMA 金叉/死叉，震荡市用 RSI 超卖反转，引擎层 ATR 止损/跟踪止损覆盖两种模式。交易成本（佣金万三、印花税千一、滑点 2bps）已在引擎 `_process_pending_fills` 中生效。Parquet 缓存使 OHLCV 加载 <1s。

现需批量运行 16 组实验，分层扫描 RSI 和 ATR 参数，在 CSI 800 和全 A（限 4000 只）两个 universe 下对比关键指标。

## Goals / Non-Goals

**Goals:**
- 生成 16 个可复现的 JSON 配置文件，覆盖 2 轮 × 4 参数组 × 2 universe
- 提供批量运行脚本，一键执行全部实验（含错误恢复）
- 提供结果汇总脚本，从各实验 `perf.json` 提取指标生成对比 CSV

**Non-Goals:**
- 不做自动参数优化（贝叶斯优化、网格搜索框架等）
- 不修改引擎或策略代码
- 不做前端 UI 展示（终端输出即可）
- 不优化内存占用（已有 universe_limit 控制）

## Decisions

### Decision 1: 配置文件命名与组织

**选择**: `backend/configs/sweep/` 目录下，命名格式 `{round}_{id}_{universe}.json`

示例：
```
sweep/
  r1_rsi_default_csi800.json
  r1_rsi_default_alla.json
  r1_rsi_fast_csi800.json
  r1_rsi_fast_alla.json
  r1_rsi_classic_csi800.json
  r1_rsi_classic_alla.json
  r1_rsi_patient_csi800.json
  r1_rsi_patient_alla.json
  r2_atr_tight_csi800.json
  r2_atr_tight_alla.json
  r2_atr_standard_csi800.json
  r2_atr_standard_alla.json
  r2_atr_wide_csi800.json
  r2_atr_wide_alla.json
  r2_atr_trailonly_csi800.json
  r2_atr_trailonly_alla.json
```

**理由**: 文件名直接表达实验维度，方便排序和对比。

### Decision 2: 参数矩阵

**固定参数（所有 16 组共享）：**
```json
{
  "strategy.name": "regime_router",
  "strategy.regime_ma": 60,
  "strategy.trend_strategy": "sma_cross",
  "strategy.trend_params.fast": 5,
  "strategy.trend_params.slow": 20,
  "universe.start": "2016-03-01",
  "universe.end": "2026-02-13",
  "universe.benchmark": "000300.SH",
  "portfolio.initial_cash": 1000000,
  "portfolio.max_positions": 10
}
```

**第一轮 RSI 扫描（ATR 固定 stop=2.0, trail=3.0）：**

| ID | rsi_period | buy | sell | max_hold | stop_loss |
|----|-----------|-----|------|----------|-----------|
| rsi_default | 6 | 20 | 80 | 5 | 0.03 |
| rsi_fast | 6 | 20 | 80 | 3 | 0.03 |
| rsi_classic | 14 | 30 | 70 | 5 | 0.05 |
| rsi_patient | 14 | 25 | 75 | 10 | 0.05 |

**第二轮 ATR 扫描（RSI 锁定第一轮最优）：**

| ID | atr_stop | atr_trail | 备注 |
|----|----------|-----------|------|
| atr_tight | 1.5 | 2.5 | 紧止损 |
| atr_standard | 2.0 | 3.0 | 系统默认 |
| atr_wide | 2.5 | 4.0 | 宽松 |
| atr_trailonly | off | 3.0 | 仅跟踪 |

### Decision 3: 批量运行方式

**选择**: Python 脚本 `batch_runner.py`，遍历 `configs/sweep/*.json`，对每个调用 `run_experiment()`，捕获异常后继续下一个。

**替代方案**:
- Shell 脚本循环调 API — 需要 Docker 容器运行，多一层间接
- 直接在 notebook 中跑 — 不可复现

**理由**: 复用 `experiment_runner.run_experiment()` 函数，与现有产物协议一致，输出到 `runs/<run_id>/artifacts/`。

### Decision 4: 结果汇总

**选择**: `sweep_report.py` 脚本，扫描所有实验目录的 `perf.json`，提取关键指标，输出对比 CSV + 终端表格。

**提取指标**:
- `total_return` — 总收益率
- `annual_return` — 年化收益
- `max_drawdown` — 最大回撤
- `sharpe_ratio` — 夏普比率
- `win_rate` — 胜率
- `total_trades` — 总交易次数
- `turnover` — 换手率

**对比表输出**: CSV 文件 + 终端 `print` 对齐表格，按 `sharpe_ratio` 降序排列。

### Decision 5: 全 A universe_limit

**选择**: 全 A 配置使用 `universe_limit: 4000`

**理由**: 全 A × 10yr (~5300 sym × 2500 天) 预估 RSS ~17 GB，超过系统 15.3 GB 内存。限制 4000 只可控制在 ~12 GB，同时覆盖 >75% 活跃标的。

## Risks / Trade-offs

- **第二轮依赖第一轮结果**: ATR 扫描需要先确定最优 RSI 参数，需手动更新第二轮配置中的 RSI 参数。`batch_runner.py` 分两批运行，第一轮结束后更新第二轮配置再跑。
- **universe_limit 截断偏差**: 按 symbol 排序截断到 4000 只，可能偏向 SH 开头（上交所）股票。但对参数相对排序影响不大。
- **单次运行无随机性**: 策略本身是确定性的，同参数只需跑一次。
