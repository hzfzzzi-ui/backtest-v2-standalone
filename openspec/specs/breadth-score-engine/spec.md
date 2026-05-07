# breadth-score-engine Specification

## Purpose

Cross-sectional breadth/dispersion score calculation engine. Computes daily scores in [0, 1] based on statistical measures of returns across a tradable universe of stocks.

## Requirements

### Requirement: 三类基础广度指标与组合分数

系统 SHALL 计算三类基础广度指标 `breadth_up`、`breadth_momo`、`dispersion`，并进一步输出组合分数 `combo = 0.5 * breadth_momo + 0.5 * dispersion`。

#### Scenario: 输出四类分数序列
- **WHEN** 引擎对一段可交易股票矩阵执行 breadth score 计算
- **THEN** 结果 SHALL 包含 `scores_A`、`scores_B`、`scores_C` 与 `scores_combo`

### Requirement: 数据口径与分母定义

系统 MUST 使用 hfq 收盘价计算日收益，并以当日 `tradable=True` 的股票数量作为横截面统计分母；NaN 值 SHALL 从统计中排除。

#### Scenario: 停牌和 ST 不计入分母
- **WHEN** 某日部分股票停牌、ST 或不满足上市天数约束
- **THEN** 这些股票 SHALL NOT 计入 breadth 分母

### Requirement: 计算过程不得前视

系统 MUST 保证所有 rolling、EMA 和 z-score 计算仅使用 t 日及以前的数据，不得引用未来样本。

#### Scenario: 当日分数仅基于历史
- **WHEN** 计算某交易日 t 的 breadth 分数
- **THEN** 系统 SHALL 只使用 t 日及以前的输入矩阵

### Requirement: 宽度维度必须向量化

系统 MUST 采用 T×N 矩阵级 numpy 或等价向量化实现，避免 symbols×days 的双重 Python 嵌套循环。

#### Scenario: 横截面计算向量化
- **WHEN** 股票数量达到数百只级别
- **THEN** N 维计算 SHALL 使用向量化矩阵操作

### Requirement: 输出值域和暖机行为

系统 SHALL 返回 `BreadthScoreResult`，其中各分数字段值域位于 `[0, 1]`，暖机期或无有效输入的日期输出 `NaN`。

#### Scenario: 暖机期输出 NaN
- **WHEN** EMA 或 rolling 窗口尚未满足长度要求
- **THEN** 对应日期的 breadth 分数 SHALL 为 `NaN`

### Requirement: 结果可观测

系统 MUST 将 breadth score 写入 `daily_rows` 诊断字段 `breadth_score`，并记录暖机天数、有效天数占比和分数均值/标准差日志。

#### Scenario: 诊断字段可读取
- **WHEN** 回测完成并输出 daily diagnostics
- **THEN** 维护者 SHALL 能读取 `breadth_score` 和相关统计日志
