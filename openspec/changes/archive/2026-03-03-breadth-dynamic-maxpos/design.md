## Architecture

### 数据流总览

```
precompute 阶段（引擎启动，一次性计算）
┌──────────────────────────────────────────────────────┐
│  provider._mx.close (T×N, hfq)                       │
│  provider._mx.tradable (T×N, bool)                    │
│          │                                            │
│          ▼                                            │
│  breadth.py: compute_breadth_scores()                 │
│    ├─ r_1d = close[t]/close[t-1] - 1  (hfq)         │
│    ├─ breadth_up = mean(r_1d > 0) → SMA5             │
│    ├─ breadth_momo = mean(EMA8 > EMA25) → SMA5       │
│    ├─ dispersion = std(r_1d) → zscore_20d → sigmoid  │
│    └─ 输出: scores dict {"A": (T,), "B": (T,), ...}  │
│          │                                            │
│          ▼                                            │
│  breadth.py: compute_dynamic_maxpos()                 │
│    ├─ 阶梯: ≥0.60→15, ≥0.45→10, <0.45→3             │
│    └─ 平滑: round(3 + clip((s-0.40)/0.20, 0, 1)*12) │
│    └─ 输出: maxpos_arr (T,) int array                 │
└──────────────────────────────────────────────────────┘

daily loop 阶段（每个交易日）
┌──────────────────────────────────────────────────────┐
│  day i:                                               │
│    day_max = maxpos_arr[i]  (从预计算数组读取)         │
│                                                       │
│    ① provider.day_signals() → buy_sigs, sell_sigs     │
│    ② dd_stop / benchmark_regime 阻断 (不变)           │
│    ③ ★ forced sell: if len(positions) > day_max       │
│    │    按 strength 排序，卖出最弱的 N 只              │
│    │    受 min_hold 约束（未满不卖）                    │
│    ④ calc_buy_slots(day_max, positions_after_sell)     │
│    ⑤ 正常下单流程 (不变)                               │
└──────────────────────────────────────────────────────┘
```

### 模块划分

```
backend/core/engine_vector/breadth.py  (新建)
├── BreadthScoreResult (dataclass)
│   ├── scores_A: np.ndarray (T,)  # breadth_up SMA5
│   ├── scores_B: np.ndarray (T,)  # breadth_momo SMA5
│   ├── scores_C: np.ndarray (T,)  # dispersion zscore→[0,1]
│   └── scores_combo: np.ndarray (T,)  # 0.5*B + 0.5*norm(C)
│
├── compute_breadth_scores(close, tradable, ema_fast_period, ema_slow_period)
│   → BreadthScoreResult
│
└── compute_dynamic_maxpos(scores, mapping_mode, min_pos, max_pos)
    → np.ndarray (T,) int
```

## Key Decisions

### 1. Score 计算细节

**指标 A (breadth_up)**：
- `r_1d[t, j] = close[t, j] / close[t-1, j] - 1`（hfq close，避免除权跳变）
- `raw_breadth_up[t] = nanmean(r_1d[t, tradable[t]] > 0)`
- 5 日 SMA 平滑：`scores_A = rolling_mean(raw_breadth_up, 5)`
- 输出范围：[0, 1]

**指标 B (breadth_momo)**：
- 对 close 矩阵做 EMA8 和 EMA25（与 G5 信号结构一致）
- `raw_breadth_momo[t] = nanmean(ema8[t, tradable[t]] > ema25[t, tradable[t]])`
- 5 日 SMA 平滑
- 输出范围：[0, 1]

**指标 C (dispersion)**：
- `raw_disp[t] = nanstd(r_1d[t, tradable[t]])`
- 20 日 rolling zscore：`z[t] = (raw_disp[t] - mean_20d) / std_20d`
- 映射到 [0, 1]：`scores_C = clip(1.0 - (z + 1.0) / 4.0, 0, 1)`
  - z = -3 → score ≈ 1.0（低离散 → 强势市）
  - z = 0 → score ≈ 0.75
  - z = +3 → score ≈ 0.0（高离散 → 弱势市）

**组合分数**：`scores_combo = 0.5 * scores_B + 0.5 * scores_C`

### 2. EMA 矩阵计算

复用 `features.py` 中的 `_ewm_mean_matrix()` 辅助函数，对 (T×N) close 矩阵做向量化 EMA：

```python
def _ewm_mean_matrix(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    result = np.full_like(arr, np.nan, dtype=float)
    result[0] = arr[0]
    for t in range(1, arr.shape[0]):
        prev = result[t - 1]
        curr = arr[t]
        valid = ~np.isnan(curr)
        result[t] = np.where(valid, alpha * curr + (1 - alpha) * np.where(np.isnan(prev), curr, prev), prev)
    return result
```

这个循环是 T 维度（~2400 天），每步操作 N 个股票的向量运算，性能可接受。

### 3. Forced Sell 规则

当 `len(positions) > day_max` 时：
1. 收集所有当前持仓的 strength 值：`strength[t, col] = close[t, col] / MA120[t, col] - 1`
2. 按 strength 升序排列（最弱在前）
3. 依次标记卖出，直到持仓数 ≤ day_max
4. **min_hold 约束**：持仓天数 < min_hold_days 的不参与 forced sell（跳过）
5. 如果全部受 min_hold 保护无法卖出，则当日 maxpos 临时上调（soft enforcement）
6. forced sell 的 reason_code = "BREADTH_FORCED_SELL"

### 4. daily_rows 诊断输出

每日记录新增字段：
- `breadth_score`: 当日使用的 score 值
- `dynamic_maxpos`: 当日计算的 max_positions
- `forced_sell_count`: 当日 forced sell 数量

### 5. 配置结构

```python
@dataclass(slots=True)
class BreadthConfig:
    enabled: bool = False
    score_type: str = "B"          # A / B / C / combo
    mapping_mode: str = "smooth"   # step / smooth
    min_positions: int = 3
    max_positions: int = 15
    # 阶梯版阈值
    step_high: float = 0.60
    step_mid: float = 0.45
    # 平滑版参数
    smooth_lo: float = 0.40
    smooth_range: float = 0.20
    # EMA 周期（用于 breadth_momo）
    ema_fast: int = 8
    ema_slow: int = 25
```

## Alternatives Considered

### A. 在 signal provider 内部计算 breadth

**否决**：breadth 是 universe 级别统计量，不属于任何单个 signal provider。放在引擎的 precompute 阶段更合理。

### B. Forced sell 按 PnL 排序

**否决**：PnL 排序引入路径依赖（同一信号不同入场价 → 不同排序），且与现有 strength 排序体系不一致。按 strength（close/MA120-1）排序与引擎现有逻辑一致。

### C. 直接过滤买入信号而非动态仓位

**否决**：这就是 benchmark regime filter 失败的原因——砍掉了牛市启动时的好信号。动态仓位的优势是：信号照常生成，只是持仓上限变化，牛市时 maxpos=15 允许更多持仓，不会错过趋势。

## Risks

1. **Forced sell 频率**：如果 score 波动大导致 maxpos 频繁变化，forced sell 可能增加不必要的交易成本。SMA5 平滑应缓解此问题。
2. **min_hold 与 forced sell 冲突**：极端情况下所有持仓都在 min_hold 内，无法执行 forced sell。设计为 soft enforcement（临时上调 maxpos）处理。
3. **过拟合风险**：阈值参数（step_high=0.60, smooth_lo=0.40 等）可能过拟合。实验矩阵覆盖阶梯+平滑两种映射以减轻。
