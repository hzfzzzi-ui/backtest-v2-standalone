# suspension-chart-overlay Specification

## Purpose

定义个股图表在停牌区间的折线与 K 线渲染要求，使停牌期在前端可被清晰识别而不污染大盘蒙版语义。

## Requirements

### Requirement: 停牌区间灰色折线标注
前端图表 SHALL 在停牌区间将折线渲染为灰色，使用户能直观区分停牌期与正常交易期。背景蒙版保留给大盘走势（MarketStateOverlay），不用于停牌标注。

#### Scenario: 个股模式下存在停牌区间
- **WHEN** 个股序列数据中包含连续的 `suspended: true` 数据点
- **THEN** 停牌区间的折线颜色 SHALL 切换为灰色（`#999` 或近似灰色）
- **THEN** 非停牌区间的折线 SHALL 保持原有橙色（`#f59e0b`）
- **THEN** 背景蒙版 SHALL 继续由 MarketStateOverlay 按大盘走势渲染，不受停牌影响

#### Scenario: 无停牌区间
- **WHEN** 个股序列数据中所有数据点的 `suspended` 均为 `false`
- **THEN** 折线 SHALL 全部为橙色，无灰色段

#### Scenario: 多段不连续停牌
- **WHEN** 个股在查询区间内有多次停牌（如停牌→复牌→再停牌）
- **THEN** 图表 SHALL 分别将每段停牌区间的折线渲染为灰色

### Requirement: 停牌期间折线为平线
停牌期间的归一化 NAV 值 SHALL 保持不变，折线自然呈现为水平线。

#### Scenario: 停牌前后折线连续
- **WHEN** 股票从停牌前 close=13.37 进入停牌，停牌期间所有点 close=13.37
- **THEN** 折线 SHALL 在停牌期间呈现为水平线
- **THEN** 复牌后折线 SHALL 从停牌价水平线位置继续按实际价格走势渲染

### Requirement: 停牌期间 K 线为横线
停牌日的 OHLC 值全部相同（被后端 fill 为同一价格），K 线 SHALL 呈现为无实体、无影线的横线。

#### Scenario: 停牌日 K 线渲染
- **WHEN** 某交易日 `open == high == low == close` 且 `suspended == true`
- **THEN** K 线 SHALL 渲染为一条水平线（十字星形态，实体高度为 0）
