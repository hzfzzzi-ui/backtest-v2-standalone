# Stage Adapter Accounting Freeze Map (2026-03-08)

## 结论

截至 `v2-legacy-accounting-boundary-shrink`，公开单次回测主链仍然固定为：

`config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`

本轮 change 的目的不是改变公开路径，而是继续压薄 `legacy_adapter.py` 的内部责任。现在开盘成交、日度快照和结果桥接已经迁出到专用模块，`legacy_adapter.py` 不得再重新长回这些细节实现。

## 新的内部责任归属

### 1. 开盘成交与成交会计

- `backend/core/stage_pipeline/adapters/fill_accounting.py`
  - 负责：
    - 挂单 payload 规范化
    - 开盘成交价与滑点/手续费/印花税处理
    - 现金、仓位、持仓均价更新
    - trade row 组装
    - provider 的卖出清理和买入 side-effect 更新
  - 规则：
    - 后续任何成交口径调整必须先落在这里，再走基线门禁

### 2. 日度 NAV 快照与 daily row

- `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - 负责：
    - 收盘 NAV snapshot
    - drawdown、turnover、gross exposure 计算
    - top holdings 组装
    - daily row 组装
    - daily decision diagnostics 回填
  - 规则：
    - `prev_nav`、`peak_nav`、`_traded_value_today` 的更新时间点由这里控制，禁止在别处复制一套

### 3. 结果桥接

- `backend/core/stage_pipeline/adapters/result_bridge.py`
  - 负责：
    - `daily_rows / trade_rows / candidate_rows` 转 DataFrame
    - `_compute_metrics(...)` 桥接
    - metrics augment
    - `PortfolioBacktestResult` 组装
  - 规则：
    - 结果字段和指标桥接逻辑优先收敛到这里，不再回填到 `legacy_adapter.py`

## `legacy_adapter.py` 剩余允许持有的责任

- runtime 初始化与共享状态持有
- `ensure_day(...)` 主时序组织
- route/day-control 判定
- provider day signal 获取与后处理
- stage handler 委托入口
- 对 accounting/daily/result helper 的薄调用

换句话说，`legacy_adapter.py` 现在允许“编排”，不允许重新承载：

- 开盘成交细节
- daily row 组装细节
- metrics augment 细节

## 明确冻结的边界

以下逻辑现在视为已冻结迁出，不得重新塞回 `legacy_adapter.py`：

- 开盘 BUY/SELL 成交实现
- 持仓均价更新实现
- trade row 字段组装
- NAV snapshot 与 daily row 字段组装
- `PortfolioBacktestResult` 和 metrics augment 组装

## 后续允许继续推进的方向

- 继续拆 `legacy_adapter.py` 中剩余的 route/day-control 责任
- 继续缩小 provider diagnostics 与 adapter 的耦合
- 在不破坏基线的前提下，让 result bridge 更贴近稳定 artifact 协议

## 明确禁止

- 在 `legacy_adapter.py` 新增成交会计逻辑
- 在 `legacy_adapter.py` 新增 daily row 字段组装逻辑
- 在 `legacy_adapter.py` 新增 metrics augment 逻辑
- 绕过锁定基线直接调整 accounting/helper 实现

## 回归门禁

后续所有 related change 仍必须通过：

- `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`
- 锁定基线：`exp_20260308_021045840_cde0`
- 当前接受的唯一非阻塞漂移：`report.html` 的诊断性 hash 漂移
