# regime-filter-engine Specification

## Purpose

Provide a three-layer hierarchical regime filter (Market -> Sector -> Stock) that produces per-stock continuous trend signals in [0, 1], enabling fine-grained regime-aware trading decisions.

## Requirements

### Requirement: RegimeFilter 三层层级趋势过滤器

系统 SHALL 提供独立的 `RegimeFilter` 类，实现三层层级趋势评估（Market -> Sector -> Stock），输出每只股票每天的连续趋势信号 RegimeSignal_i ∈ [0, 1]。

RegimeFilter 不涉及持仓管理、下单逻辑或退出规则，是一个纯粹的信号计算模块。

#### Scenario: RegimeFilter 输出范围
- **WHEN** 调用 `regime_filter.get_signal(day_idx, symbol)` 或查表 `regime_signals[day_idx, col_idx]`
- **THEN** 返回值 ∈ [0.0, 1.0]，0 表示强烈非趋势，1 表示强烈趋势

#### Scenario: 无持仓/交易依赖
- **WHEN** RegimeFilter 计算信号
- **THEN** 计算过程不读取任何持仓、现金、订单状态，仅依赖价格数据和行业映射

---

### Requirement: 每层三因子趋势评分

每层（Market / Sector / Stock）MUST 使用相同的三因子公式计算原始趋势得分：

```
trend_score = w1 * slope + w2 * spread + w3 * adx_norm
```

其中：
- **slope**: EMA(50) 的 10 日变化率 = (EMA50[t] - EMA50[t-10]) / EMA50[t-10]
- **spread**: |EMA(20) - EMA(60)| / EMA(60)，衡量短长期均线的离散程度
- **adx_norm**: ADX(14) / 100，归一化到 [0, 1]
- 默认权重：w1=0.4, w2=0.3, w3=0.3（可配置）

#### Scenario: Market 层因子计算
- **WHEN** 计算 Market 层趋势得分
- **THEN** 使用 benchmark（如 000300.SH）的 close 序列计算 slope、spread、adx_norm，输出标量时间序列 trend_score_m[t]

#### Scenario: Sector 层因子计算
- **WHEN** 计算 Sector 层趋势得分
- **THEN** 对每个申万 L1 行业指数（801xxx.SI）分别计算 slope、spread、adx_norm，输出 T × S 矩阵（S = 行业数）

#### Scenario: Stock 层因子计算
- **WHEN** 计算 Stock 层趋势得分
- **THEN** 使用个股 close 矩阵（T × N）计算 slope、spread、adx_norm，输出 T × N 矩阵

#### Scenario: 因子数据不足时默认值
- **WHEN** EMA 或 ADX 在前期暖机阶段数据不足（NaN）
- **THEN** 该因子对应 trend_score 填入 NaN，后续 z-score 和门控视为中性值（sigmoid 输入 0 -> 门控 = 0.5）

---

### Requirement: Rolling Z-Score 标准化

每层的 trend_score MUST 经 rolling z-score 标准化：

```
z_score[t] = (trend_score[t] - mean(trend_score[t-W:t])) / std(trend_score[t-W:t])
```

- W = z-score 回看窗口（默认 120 个交易日）
- 标准化在每层独立进行（Market 自身标准化、每个 Sector 自身标准化、每只 Stock 自身标准化）
- std 为 0 时 z_score 设为 0

#### Scenario: Z-Score 独立标准化
- **WHEN** 计算 Sector 层 z-score
- **THEN** 每个行业指数的 trend_score 各自做 rolling z-score，不跨行业混合

#### Scenario: 冷启动期
- **WHEN** 回测前 W 个交易日数据不足
- **THEN** z_score 输出 NaN，门控默认 0.5

---

### Requirement: EMA 平滑

Z-Score 序列 MUST 经 EMA 平滑以减少噪声：

```
T_smooth[t] = EMA(z_score, span=S)[t]
```

- S = 平滑跨度（默认 10 个交易日）
- 平滑在每层独立进行

#### Scenario: 平滑抑制震荡
- **WHEN** z_score 在 +-0.5 附近频繁翻转
- **THEN** EMA 平滑后 T_smooth 的翻转频率显著降低

---

### Requirement: Sigmoid 门控

每层的平滑后趋势得分 T_smooth MUST 通过 Sigmoid 函数转化为门控值 G ∈ (0, 1)：

```
G = 1 / (1 + exp(-alpha * T_smooth))
```

- alpha 为陡度参数，每层独立配置：
  - Market 层：alpha_m（默认 2.0）
  - Sector 层：alpha_sec（默认 2.0）
  - Stock 层：alpha_i（默认 2.0）
- alpha 越大，门控越接近 0/1 二值开关；alpha 越小，过渡越平滑

#### Scenario: 强趋势区间
- **WHEN** T_smooth > 2.0 且 alpha = 2.0
- **THEN** G > 0.98，接近全通

#### Scenario: 弱趋势 / 中性区间
- **WHEN** T_smooth 约等于 0
- **THEN** G 约等于 0.5

#### Scenario: 强反趋势区间
- **WHEN** T_smooth < -2.0 且 alpha = 2.0
- **THEN** G < 0.02，接近全阻断

---

### Requirement: 三层乘法复合

最终 RegimeSignal MUST 为三层门控值的乘积：

```
RegimeSignal_i[t] = G_m[t] * G_sec(i)[t] * G_stock_i[t]
```

其中 `sec(i)` 为股票 i 在交易日 t 所属的申万 L1 行业。

#### Scenario: 全层看多
- **WHEN** G_m = 0.9, G_sec = 0.85, G_stock = 0.8
- **THEN** RegimeSignal = 0.9 * 0.85 * 0.8 = 0.612

#### Scenario: 行业层阻断
- **WHEN** G_m = 0.9, G_sec = 0.1, G_stock = 0.8
- **THEN** RegimeSignal = 0.9 * 0.1 * 0.8 = 0.072（接近阻断）

#### Scenario: 行业数据缺失时降级为两层
- **WHEN** 某股票所属行业的行业指数在该日期无数据（如 801960.SI 在 2021 年前不存在）
- **THEN** G_sec 默认为 1.0（不做行业层过滤），RegimeSignal = G_m * 1.0 * G_stock

---

### Requirement: 向量化预计算

RegimeFilter MUST 提供 `precompute()` 方法，在回测日循环之前一次性完成所有矩阵计算。日循环中通过索引查表获取信号值，时间复杂度 O(1)。

预计算步骤：
1. Market 层：从 benchmark close 计算 EMA50、EMA20、EMA60、ADX(14)，再到 trend_score -> z_score -> EMA 平滑 -> sigmoid -> G_m[T]
2. Sector 层：从行业指数 OHLCV 计算每个行业的因子和门控 -> G_sec[T × S]
3. Stock 层：从个股 close/high/low 矩阵计算因子和门控 -> G_stock[T × N]
4. 组装 RegimeSignal[T × N] = G_m * G_sec(映射) * G_stock

总时间复杂度：O(T * max(N, S))，其中 T = 交易日数，N = 股票数，S = 行业数 (31)

#### Scenario: precompute 完成后矩阵可用
- **WHEN** 调用 `regime_filter.precompute(benchmark, sector_data, stock_matrices, industry_mapping)`
- **THEN** `regime_filter.regime_signals` 为形状 (T, N) 的 float64 数组，值域 [0, 1]

#### Scenario: 日循环查表 O(1)
- **WHEN** 日循环中调用 `regime_filter.regime_signals[day_idx, :]`
- **THEN** 返回长度 N 的数组，不触发任何额外计算

---

### Requirement: 无未来函数

RegimeFilter 的所有计算 MUST 仅使用 t 及之前的数据。

- EMA、Rolling Mean、Rolling Std 的 min_periods 参数 MUST 等于其 span/window
- ADX 使用 Wilder 平滑（单边回溯）
- Z-Score 的回看窗口 [t-W+1, t] 不包含 t 之后的数据

#### Scenario: 无前瞻验证
- **WHEN** 修改某日 close 价格
- **THEN** 仅该日及之后的 RegimeSignal 值变化，之前的值不变

---

### Requirement: 配置参数

RegimeFilter MUST 接受以下可配置参数（均有默认值）：

| 参数 | 默认值 | 说明 |
|------|-------|------|
| ema_slope_span | 50 | 斜率用 EMA 跨度 |
| slope_lookback | 10 | 斜率回看天数 |
| ema_short_span | 20 | spread 用短期 EMA 跨度 |
| ema_long_span | 60 | spread 用长期 EMA 跨度 |
| adx_period | 14 | ADX 周期 |
| w_slope | 0.4 | 斜率权重 |
| w_spread | 0.3 | spread 权重 |
| w_adx | 0.3 | ADX 权重 |
| zscore_window | 120 | z-score 回看窗口 |
| ema_smooth_span | 10 | z-score EMA 平滑跨度 |
| alpha_m | 2.0 | Market 层 sigmoid 陡度 |
| alpha_sec | 2.0 | Sector 层 sigmoid 陡度 |
| alpha_i | 2.0 | Stock 层 sigmoid 陡度 |
| regime_threshold | 0.3 | RegimeSignal 阈值（>= 则视为趋势环境） |

#### Scenario: 使用默认参数
- **WHEN** 未传入任何参数创建 RegimeFilter
- **THEN** 使用上表所有默认值

#### Scenario: 自定义 alpha 调节灵敏度
- **WHEN** 传入 alpha_m=5.0
- **THEN** Market 层的门控更接近 0/1 二值开关

---

### Requirement: 可观测性诊断输出

RegimeFilter MUST 在 precompute 完成后提供以下诊断数据：

- `gate_m_mean`: G_m 全时段均值
- `gate_sec_coverage`: 有数据的行业比例（0~1）
- `regime_signal_mean`: RegimeSignal 全矩阵均值（非 NaN）
- `regime_signal_above_threshold_pct`: RegimeSignal >= threshold 的比例
- `precompute_seconds`: 预计算耗时

这些数据通过 `regime_filter.diagnostics` 属性获取，合并到 run_meta 或 metrics 产物中。

#### Scenario: 诊断数据可获取
- **WHEN** precompute 完成后访问 `regime_filter.diagnostics`
- **THEN** 返回包含上述字段的 dict，所有值为有效数值（非 NaN）
