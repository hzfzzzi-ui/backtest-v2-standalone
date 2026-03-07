# 市场状态细分实验（基于 3月6日冠军配置）

## 目标
- 基线配置：`cfg_da4a2be7f3b7`（3月6日冠军配置）
- 回测区间：`2016-03-01 ~ 2026-03-01`
- 限制：不改 entry，不改 stop，只调整“市场状态 -> 仓位系数”。

## 本次细分能力接入
- 新增可选参数：
  - `trans_down_multiplier`
  - `trans_up_multiplier`
  - `bear_multiplier`
- 兼容旧逻辑：
  - 不配置时，仍使用旧逻辑：`TRANS_DOWN/TRANS_UP = light_multiplier`，`BEAR = 0`

## 实验矩阵
- `baseline_off`：关闭 market_filter
- `legacy_2state`：`bull=1.2, light=0.6`
- `segmented_v1`：`bull=1.2, td=0.4, tu=0.8, bear=0.2`
- `segmented_v2`：`bull=1.1, td=0.3, tu=0.7, bear=0.3`
- `segmented_v3`：`bull=1.3, td=0.5, tu=0.9, bear=0.1`

## 结果

| Variant | exp_id | CAGR | Sharpe | MDD | Trades | Avg Positions |
|---|---|---:|---:|---:|---:|---:|
| baseline_off | exp_20260306_153724 | 8.02% | 0.40 | -43.81% | 88 | 5.49 |
| legacy_2state | exp_20260306_153814 | 3.85% | 0.27 | -43.96% | 100 | 6.48 |
| segmented_v1 | exp_20260306_153859 | 3.85% | 0.27 | -43.96% | 100 | 6.48 |
| segmented_v2 | exp_20260306_153943 | 6.35% | 0.35 | -41.19% | 92 | 6.52 |
| segmented_v3 | exp_20260306_154027 | 6.03% | 0.34 | -49.08% | 110 | 6.86 |

## 结论
- 在“启用市场过滤”的细分组里，`segmented_v2` 最优：
  - 相比 `legacy_2state`，CAGR 和 Sharpe 明显提升，MDD 也改善。
- 但与 `baseline_off` 比较，细分市场状态仍未超越原冠军（收益与 Sharpe 仍低）。
- `segmented_v3` 的 bull/transition 更激进，导致回撤显著变差，不建议继续沿该方向加杠杆。

## 产物
- 汇总：`outputs/experiments/market_state_segmentation_20260306_154110.json`
- 运行脚本：`backend/scripts/run_market_state_segmentation_experiments.py`

