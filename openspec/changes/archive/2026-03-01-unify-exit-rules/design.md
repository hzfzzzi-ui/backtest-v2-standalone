## Context

Phase 2（extract-engine-primitives）已提取 `_build_price_indices` 和 `_process_pending_fills`。现在统一两路径的退出规则判断逻辑。

经分析，两路径退出规则的差异如下：

| 退出规则 | SMA 路径 | Generic 路径 |
|---------|---------|-------------|
| RISK_OFF_EXIT | 有（`risk_on[i]` 向量） | **缺失** |
| ATR_STOP_LOSS | 有 | 有 |
| FIXED_STOP_LOSS | 有 | 有 |
| TREND_BREAK_EXIT | 有（需 signal matrix） | N/A（策略层） |
| TAKE_PROFIT | 有 | 有 |
| ATR_TRAIL_EXIT | 有 | 有 |
| TIME_EXIT | 有 | **代码缺失**（_max_hold_days2 从未使用） |
| CROSS_DOWN | 有（需 signal matrix） | N/A（策略层） |
| min_hold 约束 | 有 | 无 |

**提取范围**：RISK_OFF、ATR_STOP、FIXED_STOP、TAKE_PROFIT、ATR_TRAIL、TIME_EXIT — 共 6 条引擎级规则。

**不提取**：TREND_BREAK_EXIT 和 CROSS_DOWN 需要 signal matrix，属于策略层信号，Phase 4 处理。min_hold 约束由 SMA 路径调用方在收到退出信号后再过滤。

## Goals / Non-Goals

**Goals:**
- 提取 `_evaluate_engine_exits()` 统一 6 条引擎级退出规则
- 补齐 Generic 路径的 RISK_OFF_EXIT（需要 benchmark regime）和 TIME_EXIT
- Generic 路径的 ATR 计算从 per-symbol dict lookup 迁移到与 SMA 相同的 close_idx 方式
- SMA 路径回测结果完全一致
- Generic 路径在不启用新规则时回测结果完全一致

**Non-Goals:**
- 不提取 TREND_BREAK_EXIT / CROSS_DOWN（Phase 4）
- 不提取 min_hold 约束（调用方逻辑）
- 不统一 benchmark regime 的计算方式（SMA 用向量，Generic 需要新增标量查询）
- 不改变退出规则的优先级顺序

## Decisions

### D1: `_evaluate_engine_exits` 签名设计

```python
def _evaluate_engine_exits(
    *,
    positions: dict[str, int],
    day: date,
    close_idx: dict[tuple[date, str], float],
    position_avg_cost: dict[str, float],
    peak_state: dict[str, float],
    entry_day: dict[str, date],
    exit_cfg: ExitConfig,
    get_atr: Callable[[str, date], float | None],
    risk_on: bool = True,
    max_hold_days: int = 0,
) -> tuple[list[Signal], dict[str, float], ExitCounts]:
    """返回 (exit_signals, updated_peak_state_snapshot, exit_counts)"""
```

**关键设计点：**
- `peak_state`：原地修改（与 `_process_pending_fills` 一致的 mutable dict 模式）
- `get_atr: Callable[[str, date], float | None]`：ATR 获取用回调函数统一两路径差异。SMA 路径传入从 NumPy matrix 读取的 lambda，Generic 路径传入从 dict lookup 读取的 lambda
- `risk_on: bool`：单个布尔值，由调用方从各自的数据源解析（SMA: `risk_on[i]`，Generic: benchmark dict 查询）
- `exit_cfg: ExitConfig`：统一参数来源，SMA 路径需将 strategy 属性映射到 ExitConfig
- 返回 `ExitCounts` 命名元组记录各规则触发次数，调用方累加

### D2: ExitCounts 数据结构

```python
@dataclass(slots=True)
class ExitCounts:
    atr_stop: int = 0
    atr_trail: int = 0
    take_profit: int = 0
    fixed_stop_loss: int = 0
```

轻量 dataclass，不包含 RISK_OFF 和 TIME_EXIT 的计数（这两个目前不在 metrics 中被跟踪，添加会改变 API 输出）。

### D3: SMA 路径 ATR 来源适配

SMA 路径的 ATR 来自 `feats.atr14[i, c]`（后复权价格 scale），需要缩放到不复权 scale：
```python
_raw_atr = atr_v * (_raw_close_v / cclose)
```

这个缩放逻辑放在 `get_atr` 回调中。SMA 调用方构造 lambda 时在内部完成缩放，使 `_evaluate_engine_exits` 接收到的 ATR 值已经是不复权 scale。

### D4: Generic 路径补齐 RISK_OFF_EXIT

Generic 路径目前没有 benchmark regime 数据。有两个选择：

**选择 A**（采用）：Generic 路径增加 risk_on 标量计算（从已有的 benchmark DataFrame 派生），传入 `risk_on=bool` 参数。
- 优点：与函数签名统一，改动最小
- 缺点：Generic 路径需要新增 benchmark 数据预处理

**选择 B**（放弃）：在 `_evaluate_engine_exits` 内部计算 risk_on。
- 缺点：函数需要访问 benchmark 数据，增加参数和职责

### D5: SMA 路径调用后保留 TREND_BREAK + CROSS_DOWN

SMA 路径调用 `_evaluate_engine_exits` 获取引擎级退出信号后，在调用方继续追加策略级退出（TREND_BREAK_EXIT、CROSS_DOWN），但需要避免对已有引擎退出信号的标的重复生成。使用与 Generic 路径相同的 `exit_rule_syms: set[str]` 模式。

### D6: SMA 路径不替换，保持内联

分析后决定 SMA 路径保持内联退出逻辑，不调用 `_evaluate_engine_exits()`。原因：

1. **优先级交错**：TREND_BREAK_EXIT 位于 FIXED_STOP 和 TAKE_PROFIT 之间，调用共享函数会改变优先级（TAKE_PROFIT 提前于 TREND_BREAK），虽然当前测试配置下无影响（TAKE_PROFIT 默认关闭），但不保证所有配置下一致
2. **富 meta**：SMA 退出信号携带 14+ 字段的 meta（adjusted close、break_streak、trend tier 等），共享函数返回最小 meta，需要调用方二次遍历补充，不减少代码
3. **双峰值状态**：SMA 维护 `peak_close_state`（后复权，用于 meta）和 `_raw_peak_state`（不复权，用于退出判断），共享函数只处理一个
4. **break_streak 持久化**：break_streak 写入 trade_rows 的 `break_streak` 列（数值列），改变会导致 CSV 比对失败

SMA 路径的退出逻辑将在 Phase 4（统一引擎循环）中随整个 per-symbol 循环一起消除。

## Risks / Trade-offs

- **[风险] Generic 路径新增 RISK_OFF_EXIT 可能改变回测结果** → 缓解：在验证步骤中，如果 benchmark 未配置或始终 risk_on=True，则无影响；如果配置了，则行为变化是符合预期的修复
- **[风险] get_atr 回调引入间接调用开销** → 缓解：Python function call 开销在每日循环内可忽略（~ns 级别 vs 循环体 ~ms 级别）
- **[权衡] peak_state 仍用 mutable dict** → 延续 Phase 2 的模式，Phase 4 统一审视
- **[权衡] SMA 路径保持内联** → 代码暂不统一，但确保 Phase 3 零回归风险；Phase 4 的统一引擎循环将完全消除 SMA 路径的 per-symbol 逻辑
