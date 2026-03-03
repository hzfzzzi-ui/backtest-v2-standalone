# rsi-feature-matrix

向量化 RSI 特征矩阵计算，为均值回归信号提供底层指标。

## Requirements

### REQ-1: RSI 矩阵计算

- 在 `FeatureMatrices` 中新增 `rsi` 字段：`np.ndarray`，shape = (T, N)
- RSI 计算方式：Wilder's smoothed RSI（与 A 股常用 RSI 一致）
  - `avg_gain = ewm(gain, span=period)`, `avg_loss = ewm(abs(loss), span=period)`
  - `RS = avg_gain / avg_loss`
  - `RSI = 100 - 100 / (1 + RS)`
- 默认周期: 由调用方传入（策略层默认 6）
- NaN 处理: 数据不足 period+1 天时为 NaN

### REQ-2: compute_feature_matrices 签名扩展

- 新增可选参数 `rsi_period: int = 6`
- 当 `rsi_period > 0` 时计算 RSI 矩阵
- 向后兼容：现有调用不需要传 rsi_period，默认计算 RSI(6)

### REQ-3: 性能要求

- RSI 计算使用列式循环（per-column），与现有 ATR 计算模式一致
- 不引入额外依赖（只用 numpy + pandas）
