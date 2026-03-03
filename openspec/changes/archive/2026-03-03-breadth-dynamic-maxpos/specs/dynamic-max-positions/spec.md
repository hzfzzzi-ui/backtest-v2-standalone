# dynamic-max-positions

## 概述
将 breadth score 映射为当日 max_positions，替代固定常量，实现市场状态自适应的仓位管理。

## 需求

### R1: 阶梯映射 (step)
- score ≥ step_high (默认 0.60) → max_positions = max_pos (默认 15)
- step_mid ≤ score < step_high (默认 0.45) → max_positions = 基线值 (默认 10)
- score < step_mid → max_positions = min_pos (默认 3)

### R2: 平滑映射 (smooth)
- `scale = clip((score - smooth_lo) / smooth_range, 0, 1)`
- `max_positions = round(min_pos + scale * (max_pos - min_pos))`
- 默认: smooth_lo=0.40, smooth_range=0.20, min_pos=3, max_pos=15

### R3: 引擎集成
- `_run_unified_loop` 中 max_positions 从固定 int 变为 per-day 数组
- 每日使用 `maxpos_arr[i]` 替代固定值
- `calc_buy_slots(day_max, positions_after_sell)` 使用动态值
- breadth 未启用时，maxpos_arr 全部填充为原始固定 max_positions（行为不变）

### R4: Forced Sell（持仓超限缩减）
- 当 `len(positions) > day_max` 时触发 forced sell
- 排序规则：按 strength（close/MA120-1）升序，最弱优先卖出
- 约束：min_hold_days 未满的持仓不参与 forced sell（跳过）
- 如全部受 min_hold 保护，当日 maxpos 临时上调至实际持仓数（soft enforcement）
- Forced sell 产生正常交易记录，reason_code = "BREADTH_FORCED_SELL"
- 交易成本与正常卖出相同

### R5: 配置
- `BreadthConfig` dataclass，enabled 默认 false
- score_type: A / B / C / combo
- mapping_mode: step / smooth
- min_positions / max_positions / step_high / step_mid / smooth_lo / smooth_range
- ema_fast / ema_slow（用于 breadth_momo 计算）

### R6: API 透传
- workbench_config.breadth section → 运行时 BreadthConfig
- 前端 Position & Risk 面板新增控件（checkbox + select + input）

### R7: 诊断产物
- daily_rows 新增：`breadth_score`、`dynamic_maxpos`、`forced_sell_count`
- perf.json 新增：`avg_dynamic_maxpos`、`breadth_score_mean`、`forced_sell_total`
- loop_state 新增：`breadth_forced_sell_count`、`breadth_avg_maxpos`
