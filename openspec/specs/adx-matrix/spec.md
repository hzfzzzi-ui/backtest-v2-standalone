# adx-matrix

## Purpose

Provide vectorized ADX (Average Directional Index) computation over T x N price matrices, enabling parallel ADX calculation for all stocks in a single pass using Wilder smoothing.

## Requirements

### Requirement: 向量化 ADX 矩阵计算

系统 SHALL 提供 `adx_matrix(high, low, close, period)` 函数，输入 T × N 的 high/low/close 矩阵，输出 T × N 的 ADX 矩阵。

计算逻辑与现有标量版 `compute_adx()` 一致（Wilder 平滑），但以矩阵形式并行处理所有列。

#### Scenario: 单列结果一致性
- **WHEN** 对单只股票的 high/low/close 序列分别用 `adx_matrix` 和现有 `compute_adx` 计算
- **THEN** 两者结果在浮点精度内一致（误差 < 1e-10）

#### Scenario: 矩阵维度
- **WHEN** 输入 high/low/close 形状为 (T, N)
- **THEN** 输出 ADX 矩阵形状为 (T, N)

---

### Requirement: ADX 矩阵 NaN 处理

ADX 计算需要 2×period 个有效数据点作暖机期（period 天 ATR + period 天 DX 平滑）。

- 前 2×period 行 MUST 填充 NaN
- 某列中间有 NaN（如停牌），该列的 ADX 在 NaN 之后 MUST 重新暖机或向前传播最近有效值

#### Scenario: 暖机期 NaN
- **WHEN** period=14 且某列数据从第 0 行开始
- **THEN** 该列 ADX[0:27] 为 NaN（至少 28 天暖机），ADX[28] 起有有效值

#### Scenario: 中间停牌处理
- **WHEN** 某列第 50~55 行为 NaN（停牌 6 天）
- **THEN** ADX 在 NaN 区间输出 NaN，复牌后延续 Wilder 平滑

---

### Requirement: Wilder 平滑实现

ADX 矩阵 MUST 使用 Wilder 平滑（等效 EMA alpha=1/period）：

1. True Range: TR = max(H-L, |H-prevC|, |L-prevC|)
2. +DM = max(H-prevH, 0) when H-prevH > prevL-L, else 0
3. -DM = max(prevL-L, 0) when prevL-L > H-prevH, else 0
4. Smoothed TR/+DM/-DM: 初始 = sum(first period), 后续 = prev - prev/period + current
5. +DI = smoothed_+DM / smoothed_TR × 100
6. -DI = smoothed_-DM / smoothed_TR × 100
7. DX = |+DI - -DI| / (+DI + -DI) × 100
8. ADX: 初始 = mean(first period DX), 后续 = (prev_ADX × (period-1) + DX) / period

#### Scenario: Wilder 平滑正确性
- **WHEN** 输入已知的 14 日 OHLC 序列
- **THEN** ADX 输出与标准 Wilder ADX(14) 公式计算结果一致

---

### Requirement: 支持 1D 和 2D 输入

`adx_matrix` MUST 同时支持：
- 2D 输入 (T, N)：标准矩阵模式，输出 (T, N)
- 1D 输入 (T,)：单序列模式（用于 benchmark、行业指数），自动升维为 (T, 1) 处理后 squeeze 回 (T,)

#### Scenario: 1D 输入自动处理
- **WHEN** 传入 shape=(3000,) 的 high/low/close
- **THEN** 输出 shape=(3000,) 的 ADX 序列

#### Scenario: 2D 输入矩阵计算
- **WHEN** 传入 shape=(3000, 800) 的 high/low/close
- **THEN** 输出 shape=(3000, 800) 的 ADX 矩阵
