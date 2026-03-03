# breadth-score-engine

## 概述
横截面 breadth/dispersion score 计算引擎，基于 universe 内可交易股票的日收益统计量，输出每日 score ∈ [0, 1]。

## 需求

### R1: 三类指标计算
- **A (breadth_up)**: 当日上涨股票占可交易股票的比例，SMA5 平滑
- **B (breadth_momo)**: 当日 EMA(fast) > EMA(slow) 的股票占比，SMA5 平滑
- **C (dispersion)**: 当日横截面收益标准差的 20 日 rolling zscore，映射到 [0, 1]（低离散=高分）
- **combo**: 0.5×B + 0.5×C

### R2: 数据源与复权
- 收益 r_1d 使用后复权 (hfq) close 计算，避免除权跳变
- 分母为当日 tradable=True 的股票数（已排除停牌、ST、上市天数不足）
- NaN 值不参与统计（使用 nanmean/nanstd）

### R3: 无未来函数
- 所有 rolling/EMA 计算仅使用历史数据（t 及之前）
- 当日 score 基于当日及之前数据，不引用未来

### R4: 向量化实现
- 使用 numpy (T×N) 矩阵操作，避免 symbols×days 双重 Python 循环
- T 维度循环（~2400 步）可接受，N 维度（~700 股）必须向量化

### R5: 输出接口
- 返回 `BreadthScoreResult` 包含 scores_A/B/C/combo 四个 (T,) 数组
- 每个值 ∈ [0, 1]，NaN 表示当日无有效数据
- warmup 期间（EMA/rolling 窗口未满）输出 NaN

### R6: 可观测性
- score 值写入 daily_rows 诊断输出（字段名 `breadth_score`）
- 日志记录：warmup 天数、有效天数占比、score 均值/std
