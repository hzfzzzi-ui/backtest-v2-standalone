## Context

EMA(8,55) 交叉策略在震荡市中频繁产生金叉信号，导致反复开仓后被止损。现有引擎的 `enable_trend_slope_filter` 作用于 MA120/MA200（长期 regime 层），与信号级别的 slow_ma（如 EMA55）无关。

需要在信号矩阵层新增**信号级入场过滤**，使用信号自身的 `slow_ma`（而非 regime MA120）进行趋势确认，减少逆势入场。

当前数据流：
```
features.py (compute_feature_matrices) → fast_ma, slow_ma, trend_fast_ma, trend_slow_ma, atr14
    ↓
signal_matrix.py (build_signal_matrices) → cross_up, cross_down, trend_ok, slope_pass, buy_base ...
    ↓
portfolio_simulator_strict.py → raw_buy_mask = cross_up & buffer_ok & trend_ok & risk_on & ma_is_valid
    ↓
buy_candidate_mask = raw_buy_mask & tradable → 排名 → 下单
```

新增过滤插入点位于 `raw_buy_mask` 组装阶段（tradable 之后、排名之前）。

## Goals / Non-Goals

**Goals:**
- 在 `build_signal_matrices()` 中新增 `entry_above_slow_ma` 和 `entry_slow_ma_slope_pos` 两个布尔矩阵
- 在引擎买入候选过滤中将两个矩阵作为 AND mask 应用
- 每个过滤条件可独立开关，默认关闭（向后兼容）
- 提供诊断计数器，可观测过滤效果
- 前端 Signal Generation 面板增加控件
- 新建实验配置文件运行对比回测

**Non-Goals:**
- 不修改卖出逻辑（入场过滤仅影响买入）
- 不改变现有 `enable_trend_slope_filter`（MA120 regime）的行为
- 不引入新的均线计算（复用 `feats.slow_ma`）
- 不修改通用信号路径（仅修改 SMA/EMA 路径）

## Decisions

### D1: 矩阵计算位置 — signal_matrix.py vs portfolio_simulator_strict.py

**选择**: 在 `build_signal_matrices()` 中计算新矩阵

**理由**:
- `close` 和 `slow_ma` 已作为参数传入，无需额外数据
- 与现有 `slope_pass`（MA120 斜率）的模式一致
- 矩阵预计算一次，在每日循环中直接索引，性能最优
- 替代方案（在循环内逐日计算）会增加热路径开销

### D2: 过滤应用位置 — raw_buy_mask 组装 vs day_cands 循环内

**选择**: 在 `raw_buy_mask` 组装时应用（line 566-572）

**理由**:
- 与 `trend_ok`、`buffer_ok` 等现有过滤处于同一层级
- 被过滤的信号不会进入 `day_cands`，减少后续循环迭代
- 替代方案（在 `for c in day_cands` 循环内过滤）会增加候选列表大小，且诊断统计位置不一致

**具体实现**:
```python
raw_buy_mask = (
    sig_m["cross_up"][i, :]
    & sig_m["buffer_ok"][i, :]
    & sig_m["trend_ok"][i, :]
    & sig_m["risk_on_matrix"][i, :]
    & sig_m["ma_is_valid"][i, :]
)
# 新增入场过滤（仅在启用时应用）
if enable_entry_above_slow_ma:
    raw_buy_mask &= sig_m["entry_above_slow_ma"][i, :]
if enable_entry_slow_ma_slope:
    raw_buy_mask &= sig_m["entry_slow_ma_slope_pos"][i, :]
```

### D3: 参数传递路径

**选择**: 从策略 dataclass → registry → simulator → signal_matrix

**理由**: 与 `enable_trend_slope_filter` 完全一致的路径，最小改动

**参数流**:
```
EMACrossStrategy.enable_entry_above_slow_ma → registry.py →
  portfolio_simulator_strict.py (getattr) → build_signal_matrices()
```

新增 3 个参数: `enable_entry_above_slow_ma: bool = False`, `enable_entry_slow_ma_slope: bool = False`, `entry_slope_lookback: int = 5`

### D4: 斜率计算方式 — 差分 vs 回归

**选择**: 简单差分 `slow_ma[t] - slow_ma[t - lookback] > 0`

**理由**:
- 与现有 `slope_pass` 计算方式一致（`trend_fast_ma[lb:] - trend_fast_ma[:-lb]`）
- 简单、高效、可解释
- 线性回归增加复杂度但对布尔判定无显著优势

### D5: 诊断计数统计方式

**选择**: 在 `raw_buy_mask` 组装后，通过矩阵运算统计

```python
# 统计：在原始信号通过的前提下，被入场过滤阻断的数量
if enable_entry_above_slow_ma:
    entry_above_block = int(np.sum(base_mask & ~sig_m["entry_above_slow_ma"][i, :]))
if enable_entry_slow_ma_slope:
    entry_slope_block = int(np.sum(base_mask & ~sig_m["entry_slow_ma_slope_pos"][i, :]))
```

累计到 `entry_above_slow_ma_block_count` 和 `entry_slope_block_count`，写入 metrics。

### D6: 前端控件位置

**选择**: Signal Generation 区域，MA 参数下方新增"入场过滤"子区域

**理由**:
- 入场过滤依赖信号 slow_ma，逻辑上属于信号生成配置
- 与 Universe 和 Risk & Exit 无关
- 与 MA 参数（fast/slow）紧邻，用户认知连贯

## Risks / Trade-offs

**[性能]** 新增两个 (t, n) 矩阵增加内存占用 → 对于 800 只股票 × 2 年的矩阵，每个约 1.2MB，总增量 < 3MB，可忽略

**[向后兼容]** 默认 `enable_*=false`，不影响现有回测结果 → 零风险

**[参数过多]** 策略 dataclass 字段增多，前端面板更拥挤 → 使用折叠子区域缓解；入场过滤仅 3 个参数，可接受

**[信号级 vs Regime 级混淆]** 用户可能混淆"入场过滤"（信号 slow_ma）和"趋势斜率过滤"（MA120 regime） → 前端使用明确标签区分："入场趋势过滤 (基于信号 MA)" vs "大盘趋势过滤 (基于 MA120)"
