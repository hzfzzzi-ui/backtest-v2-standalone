# Alpha 四实验回测记录（2016 对齐）

## 1) 回测范围与基线
- 对齐区间：`2016-03-01` ~ `2026-03-01`
- 基准：`000300.SH`
- 基线策略：`breakout_trend`
- 基线核心参数：
  - `universe_mode=HS300_ZZ500`
  - `benchmark_regime.enabled=false`
  - `ATR stop k=1.5`
  - `ATR trail k=3.0`
  - `risk_budget.enabled=true (dd_reduce_pct=0.10, dd_reduce_scale=0.5)`

## 2) 四个实验定义（仅改指定变量）
- 实验1 `EXP1_MARKET_REGIME`：
  - 在基线上仅开启 `benchmark_regime`
  - 参数：`enabled=true, fast_period=20, slow_period=120, slope_window=5`
- 实验2 `EXP2_UNIVERSE_ALL_A`：
  - 在基线上仅修改 Universe
  - 参数：`universe_mode=ALL_A`
  - 过滤：`min_avg_turnover_20d=1e8`（并保留 `min_list_days=120, price_min=5`）
- 实验3 `EXP3_ATR_TIGHT_1P2`：
  - 在基线上仅收紧 ATR stop
  - 参数：`atr_stop_k: 1.5 -> 1.2`
- 实验4 `EXP4_ALL_THREE`：
  - 同时启用实验1 + 实验2 + 实验3

## 3) 指标结果
| 组别 | CAGR | Sharpe | Max Drawdown | Trades | Total Return | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| BASE_REF | 4.05% | 0.311 | -44.28% | 69 | 46.49% | 0.091 |
| EXP1_MARKET_REGIME | 5.20% | 0.330 | -37.60% | 82 | 62.85% | 0.138 |
| EXP2_UNIVERSE_ALL_A | 4.19% | 0.299 | -45.19% | 65 | 48.47% | 0.093 |
| EXP3_ATR_TIGHT_1P2 | 5.86% | 0.370 | -33.63% | 81 | 72.97% | 0.174 |
| EXP4_ALL_THREE | 6.09% | 0.345 | -42.34% | 86 | 76.63% | 0.144 |

## 4) 相对 BASE 变化
| 组别 | ΔCAGR | ΔSharpe | MDD 改善(+) |
|---|---:|---:|---:|
| EXP1_MARKET_REGIME | +1.15% | +0.019 | +6.68% |
| EXP2_UNIVERSE_ALL_A | +0.15% | -0.011 | -0.91% |
| EXP3_ATR_TIGHT_1P2 | +1.81% | +0.059 | +10.64% |
| EXP4_ALL_THREE | +2.04% | +0.035 | +1.94% |

注：`MDD 改善(+) = |MDD_base| - |MDD_exp|`，正值代表回撤收敛。

## 5) Universe 过滤执行情况（实验2/4）
- `raw_count=2833`
- `tradable_symbols=1482`
- 排除原因统计：
  - `EXCLUDE_LOW_TURNOVER=1051`
  - `EXCLUDE_LIST_DAYS=204`
  - `EXCLUDE_LOW_PRICE=82`

说明：`min_avg_turnover_20d` 已实际生效，不再触发“全量过滤后回退”。

## 6) 产物路径
- 汇总 JSON：
  - `/app/outputs/experiments/exp_4runs_2016_1772781575.json`
- 各实验目录（容器内）：
  - `BASE_REF`: `/app/outputs/experiments/exp_20260306_071721`
  - `EXP1_MARKET_REGIME`: `/app/outputs/experiments/exp_20260306_071739`
  - `EXP2_UNIVERSE_ALL_A`: `/app/outputs/experiments/exp_20260306_071756`
  - `EXP3_ATR_TIGHT_1P2`: `/app/outputs/experiments/exp_20260306_071837`
  - `EXP4_ALL_THREE`: `/app/outputs/experiments/exp_20260306_071853`

