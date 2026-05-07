# dynamic-max-positions Specification

## Purpose

Map breadth score to a per-day max_positions value, replacing the fixed constant with market-state-adaptive position management.

## Requirements

### Requirement: Step 模式映射

系统 SHALL 在 `mapping_mode=step` 时按 breadth score 阈值将每日 `max_positions` 映射为 `max_pos`、baseline 值或 `min_pos`。

#### Scenario: step 模式三档映射
- **WHEN** `score >= step_high`、`step_mid <= score < step_high` 或 `score < step_mid`
- **THEN** 系统 SHALL 分别输出 `max_pos`、baseline `max_positions` 或 `min_pos`

### Requirement: Smooth 模式映射

系统 SHALL 在 `mapping_mode=smooth` 时按 `clip((score - smooth_lo) / smooth_range, 0, 1)` 连续映射每日 `max_positions`。

#### Scenario: smooth 模式线性缩放
- **WHEN** breadth score 落在 `smooth_lo` 与 `smooth_lo + smooth_range` 之间
- **THEN** 系统 SHALL 线性插值计算每日 `max_positions`

### Requirement: 引擎按日应用动态持仓上限

系统 MUST 在 `_run_unified_loop` 中使用按日数组 `maxpos_arr[i]` 替代固定整数 `max_positions`；当 breadth 未启用时 SHALL 完全回退旧行为。

#### Scenario: breadth 未启用时保持原行为
- **WHEN** breadth 配置 `enabled=false`
- **THEN** `maxpos_arr` SHALL 全部等于原固定 `max_positions`

### Requirement: 超配时执行 forced sell

系统 MUST 在 `len(positions) > day_max` 时触发 forced sell，并按强度从弱到强排序卖出，同时遵守 `min_hold_days` 保护约束。

#### Scenario: 超配仓位被强制降档
- **WHEN** 当日动态 `day_max` 小于当前持仓数
- **THEN** 系统 SHALL 以 `BREADTH_FORCED_SELL` reason_code 生成正常卖出记录

### Requirement: BreadthConfig 定义完整参数

系统 SHALL 提供 `BreadthConfig`，至少包含 `enabled`、`score_type`、`mapping_mode`、`min_positions`、`max_positions`、`step_high`、`step_mid`、`smooth_lo`、`smooth_range`、`ema_fast` 与 `ema_slow`。

#### Scenario: 读取完整 breadth 配置
- **WHEN** 运行时加载 breadth 配置
- **THEN** 上述字段 SHALL 可被编译到 runtime config

### Requirement: API 与前端透传 breadth 配置

系统 MUST 将 `workbench_config.breadth` 透传为 runtime `BreadthConfig`，并在前端 Position & Risk 面板提供对应控件。

#### Scenario: 前端启用 breadth
- **WHEN** 用户在前端启用 breadth 并保存配置
- **THEN** 运行时 SHALL 接收到等价 `BreadthConfig`

### Requirement: 动态持仓上限必须可观测

系统 MUST 在 `daily_rows`、`perf.json` 和 `loop_state` 中输出 `breadth_score`、`dynamic_maxpos`、`forced_sell_count` 及其聚合统计。

#### Scenario: 回测后检查诊断字段
- **WHEN** 回测完成
- **THEN** 维护者 SHALL 能在诊断产物中读取动态持仓上限和 forced sell 统计
