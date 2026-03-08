# Stage Adapter Route-Control Freeze Map (2026-03-08)

## 结论

截至 `v2-legacy-route-control-shrink`，公开单次回测主链仍然固定为：

`config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`

本轮 change 的目标不是改变公开路径，而是继续压薄 `legacy_adapter.py` 的 route-specific 编排责任。现在 stage applicability、day controls 和 provider signal postprocess 已经迁出到专用模块，`legacy_adapter.py` 不得再重新承载这些细节实现。

## 新的内部责任归属

### 1. Stage applicability

- `backend/core/stage_pipeline/adapters/stage_applicability.py`
  - 负责：
    - disabled stage 归一化判断
    - `stage_is_applicable(...)` route-specific 适用性判定
  - 规则：
    - stage 可用性语义先收敛到这里，不再回填到 `legacy_adapter.py`

### 2. Route day controls

- `backend/core/stage_pipeline/adapters/day_controls.py`
  - 负责：
    - `effective_max_positions`
    - `dd_state`
    - `market_state`
    - `trade_mode`
    - `benchmark_regime_on`
    - `risk_on_today`
    - route/day-control 相关计数更新
  - 规则：
    - 任何 route/day-control 诊断口径调整必须先落在这里，再走基线门禁

### 3. Provider signal postprocess

- `backend/core/stage_pipeline/adapters/signal_postprocess.py`
  - 负责：
    - benchmark regime gate
    - market-filter state gate
    - provider day signal 的 route-specific 后处理
  - 规则：
    - buy signal 过滤顺序和条件优先级由这里控制，禁止在别处复制一套

## `legacy_adapter.py` 剩余允许持有的责任

- runtime 初始化与共享状态持有
- `_provider_precompute(...)`
- `ensure_day(...)` 主时序组织
- route/day-control/helper 的薄调用
- `_provider_base_order_value(...)`
- stage handler 组装与公开 adapter 入口

换句话说，`legacy_adapter.py` 现在允许“持有状态和编排”，不允许重新承载：

- stage applicability 细节
- route day-control 细节
- provider signal postprocess 细节

## 明确冻结的边界

以下逻辑现在视为已冻结迁出，不得重新塞回 `legacy_adapter.py`：

- `disabled_stages` 的具体判定实现
- `stage_is_applicable(...)` 的 route-specific 分支
- `_compute_day_controls(...)` 的实现体
- provider day signal 的 route-specific gate/postprocess

## 后续允许继续推进的方向

- 继续缩小 `_provider_precompute(...)` 与 adapter 的耦合
- 继续把 `ensure_day(...)` 中残余的 orchestration 向更清晰的 runtime shell 收敛
- 在不破坏基线的前提下，评估是否可以进一步收口 legacy route 初始化边界

## 明确禁止

- 在 `legacy_adapter.py` 新增新的 route-specific applicability 逻辑
- 在 `legacy_adapter.py` 新增新的 day-control 计算逻辑
- 在 `legacy_adapter.py` 新增新的 signal postprocess 逻辑
- 绕过锁定基线直接调整 route-control helper 实现

## 回归门禁

后续所有 related change 仍必须通过：

- `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`
- 锁定基线：`exp_20260308_021045840_cde0`
- 当前接受的唯一非阻塞漂移：`report.html` 的诊断性 hash 漂移
