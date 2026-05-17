## Why

`HS300_ZZ500_CSI1000 + PIT_DYNAMIC` 宽股票池主窗口在 Docker 内 OOM/exit 137。静态审计显示 A1 `1626` 约 3318 个 union symbols、704 万 OHLCV rows；当前运行路径仍倾向于按 `T * N_union * F` 构造 dense 计算图，导致宽 PIT 股票池无法稳定完成。

本变更目标是从算法复杂度层面降低运行成本，而不是改变股票池、排序因子、信号时点、成交时点、退出规则或资金预算。

## What Changes

- 为宽 PIT 股票池新增等价优化开关，按顺序推进：
  1. PIT interval pushdown：只让有效 membership 区间及 warmup 参与后续计算。
  2. top-k / argpartition：用 partial selection 替代全量排序。
  3. candidate-first expensive scoring：先做便宜 gate，再对必要集合计算昂贵评分。
  4. streaming rolling state：为 rolling 特征提供增量/流式执行路径或受控原型。
- 增加 profiling 与 parity 验证，要求 B0 与优化前结果一致或差异可解释。
- A1 `1626` 只在优化和 dry-run/parity 通过后重跑。

## Capabilities

### New Capabilities

- `wide-pit-stock-runtime-optimization`: 对宽 PIT 股票池运行时提供复杂度优化，同时保持研究口径可审计、可回滚、可做 parity check。

## Impact

- 影响范围：
  - `backend/core/tools/data_bundle_builder.py`
  - `backend/core/engine_vector/*`
  - `backend/core/stage_pipeline/*`
  - `research/studies/v10/*`
  - `tests/unit/*`
- 不影响范围：
  - baseline 主逻辑
  - 股票池 PIT 定义
  - Alpha、排序语义、入场/退出、成交、成本、仓位预算
  - ETF 腿和组合层
