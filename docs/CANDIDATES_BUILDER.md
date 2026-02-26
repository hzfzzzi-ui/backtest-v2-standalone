# Candidate Builder

根据实验产物自动筛选候选并输出执行清单骨架。

## 运行方式

```bash
python scripts/build_candidates.py --results_dir <results_dir>
```

或：

```bash
python scripts/build_candidates.py --exp_id <exp_id>
```

## 输入

- `manifest.json`
- `groups/*/perf.json`
- `groups/*/run_meta.json`
- `groups/*/reason_code_counts.csv`（用于 why 摘要）

## 筛选规则（当前硬编码）

- `Tier >= T2`
- `Scorecard >= B`（无显式 scorecard 时尝试用 `CAGR/MDD/Sharpe` 近似）
- `RedFlags = 0`（若无 red_flags 信息则给 warning，跳过该条过滤）
- `max_drawdown >= -0.20`

## 输出

- `outputs/candidates.json`
- `outputs/execution_list.json`

