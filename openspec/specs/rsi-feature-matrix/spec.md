# rsi-feature-matrix Specification

## Purpose

定义向量化 RSI 特征矩阵的计算与接口要求，为均值回归信号和 benchmark/行业序列提供统一的底层 RSI 指标。

## Requirements

### Requirement: RSI 矩阵计算

系统 SHALL 在 `FeatureMatrices` 中新增 `rsi` 字段，并按 Wilder smoothed RSI 公式输出形状为 `(T, N)` 的 RSI 矩阵。

#### Scenario: 单列 RSI 结果可用
- **WHEN** 调用方传入一段单股票价格序列并请求 RSI 矩阵
- **THEN** 系统 SHALL 输出与 Wilder RSI 公式一致的 RSI 序列

### Requirement: `compute_feature_matrices` 支持 `rsi_period`

系统 MUST 为 `compute_feature_matrices` 新增可选参数 `rsi_period: int = 6`；当 `rsi_period > 0` 时计算 RSI，未显式传入时 SHALL 保持默认 RSI(6) 兼容行为。

#### Scenario: 默认参数向后兼容
- **WHEN** 现有调用方不传 `rsi_period`
- **THEN** 系统 SHALL 继续计算默认 RSI(6)

### Requirement: RSI 计算保持轻依赖与列式实现

系统 SHALL 使用与 ATR 相同级别的列式实现完成 RSI 计算，并且 SHALL NOT 引入除 numpy 与 pandas 外的额外依赖。

#### Scenario: 依赖集合不扩张
- **WHEN** 维护者检查 RSI 特征实现
- **THEN** 代码 SHALL 仅依赖 numpy 和 pandas
