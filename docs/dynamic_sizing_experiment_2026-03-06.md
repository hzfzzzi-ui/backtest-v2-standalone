# 仓位动态化实验（基于 3月6日冠军配置）

## 实验目标
- 基线：`cfg_da4a2be7f3b7`（3月6日冠军配置）
- 区间：`2016-03-01 ~ 2026-03-01`
- 约束：不改 entry / 不改 stop，只改仓位层

## 实验设计
- `baseline`：`weight_mode=equal`，`market_filter.enabled=false`
- `inverse_vol`：`weight_mode=inverse_vol`，`market_filter.enabled=false`
- `market_filter`：`weight_mode=equal`，启用市场状态动态仓位
  - `bull_multiplier=1.2`
  - `light_multiplier=0.6`
  - `slope_ma_period=50`
  - `slope_window=10`
- `combo`：`inverse_vol + market_filter`

## 回测结果

| Variant | exp_id | CAGR | Sharpe | MDD | Trades | Avg Positions |
|---|---|---:|---:|---:|---:|---:|
| baseline | exp_20260306_152420 | 8.02% | 0.40 | -43.81% | 88 | 5.49 |
| inverse_vol | exp_20260306_152509 | 0.20% | 0.11 | -39.01% | 117 | 6.61 |
| market_filter | exp_20260306_152557 | 3.85% | 0.27 | -43.96% | 100 | 6.48 |
| combo | exp_20260306_152641 | 1.39% | 0.17 | -35.72% | 120 | 7.87 |

## 结论
- 以当前参数看，`baseline` 仍然最优（收益与夏普显著领先）。
- `inverse_vol` 与 `combo` 明显“降收益换回撤”，其中 `combo` 回撤降到 -35.72%，但收益明显被压缩。
- `market_filter` 在当前阈值下也未优于基线，且没有改善最大回撤。

## 产物
- 汇总 JSON：`outputs/experiments/dynamic_sizing_matrix_20260306_152728.json`
- 四组实验目录：
  - `outputs/experiments/exp_20260306_152420`
  - `outputs/experiments/exp_20260306_152509`
  - `outputs/experiments/exp_20260306_152557`
  - `outputs/experiments/exp_20260306_152641`

