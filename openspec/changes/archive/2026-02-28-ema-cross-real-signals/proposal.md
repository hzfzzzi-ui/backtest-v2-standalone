## Why

VECTOR 引擎的 SMA 路径中，`compute_feature_matrices()` 只实现了 `_rolling_mean_matrix()`（SMA），无论配置写 `ema_cross` 还是 `sma_cross`，信号计算始终是 SMA。同时，单笔下单金额被硬编码为 `NAV / max_positions`，导致小单触发最低佣金（5元），实际佣金率远高于名义 0.03%。当前 `max_positions=10` + 小单 → gross_exposure 仅 0.41，大量资金闲置。正式实验前必须修复这三个参数失效问题，否则后续优化收益无意义。

## What Changes

- 在 `features.py` 中新增 `_ewm_mean_matrix()` 函数，`compute_feature_matrices()` 接受 `ma_type` 参数（`"SMA"` | `"EMA"`），根据类型选择计算方法
- VECTOR 引擎 SMA 路径读取 strategy 对象的 `ma_type` 属性，传入 feature 计算
- VECTOR 引擎 SMA 路径的订单 sizing 支持 `base_order_value` 模式：当配置指定 `base_order_value` 时，使用该值作为每仓目标金额（受可用现金约束），而非硬编码 `NAV / max_positions`
- 新增实验配置文件 `configs/plan_a_ema_cross.json`，包含方案 A 的全部参数

## Capabilities

### New Capabilities
- `ema-signal-engine`: VECTOR 引擎支持 EMA 类型的均线交叉信号计算，以及固定金额的订单 sizing 模式

### Modified Capabilities
（无——本次变更不修改已有 spec 的行为定义，仅新增引擎能力）

## Impact

- **引擎核心**：`features.py`（新增 EWM 矩阵计算）、`portfolio_simulator_strict.py`（读取 ma_type、支持 base_order_value sizing）
- **配置/模型**：`models.py` 可能需要新增 `ma_type` 字段到 `StrategyConfig`；新建实验配置 JSON
- **前端**：无变更
- **性能**：EWM 计算与 SMA 计算复杂度相当（pandas `ewm().mean()` 也是 O(T×N)），无性能退化
