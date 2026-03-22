# Implementation Notes

## 1. 实施范围

本轮实现只处理两类问题：

- V10.1 runtime 没把阶段漏斗计数稳定写出来，导致多个 stage 被压平
- workbench / 旧桥接层把 `null` 或 `available=false` 误渲染成 `0`

没有修改：

- baseline_V10.1 的执行时点
- 成交规则、仓位规则、风险预算
- benchmark / universe / signal 主逻辑
- NAV、收益、交易笔数的计算口径

## 2. 代码落点

- `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - 漏斗字段优先读取 provider diagnostics 与 `debug_plan`
  - 缺失阶段保留 `None`，不再回退到后置阶段数量
- `backend/core/portfolio/portfolio_runtime.py`
  - planner/debug_plan 正式写出 `selected_count`、`after_slot_filter_count`、`after_cash_lot_count`
- `backend/core/engine_vector/generic_signal_provider.py`
- `backend/core/engine_vector/multi_alpha_signal_provider.py`
- `backend/core/engine_vector/regime_router_signal_provider.py`
- `backend/core/engine_vector/breakout_provider_day_signals.py`
  - provider 补齐稳定 diagnostics 键名
- `backend/api/backtest_v2/artifacts_diagnostics.py`
  - `stage_funnel` 聚合保留 `available` / `null` 语义
  - 真 `0` 与 unavailable 不再混写
- `frontend/app/results-workbench/helpers/stageFunnelFormatting.js`
- `frontend/assets/js/artifacts.js`
  - 前端不再把 `null` / unavailable 吞成 `0`
  - workbench 与旧桥接层对 zero/unavailable 的判断对齐

## 3. 回归锚点与验收样例

### 3.1 主回归锚点

- 源实验：`exp_20260315_001145197_2aa2`
- 同请求复跑实验：`exp_20260315_165038145_5f9a`
- 复跑方式：在容器 `backtest-v2-standalone` 内，从源实验目录构造同请求再调用 runtime 同步执行

可复跑示意：

```powershell
@'
from pathlib import Path
from backend.cli.managed.baseline_regression_check import _build_baseline_request
from backend.core.tools import experiment_runtime_access

exp_dir = Path("outputs/experiments/exp_20260315_001145197_2aa2")
request = _build_baseline_request(exp_dir)
result = experiment_runtime_access.run_experiment_sync(request)
print(result["exp_id"])
'@ | docker exec -i -w /app backtest-v2-standalone python -
```

### 3.2 unavailable 样例

来自源实验与复跑实验的 `run_meta.counters.buy_stage_funnel`：

- `s2`：`available=false`，`input/output/filtered=null`
- `s3`：`available=false`，`input/output/filtered=null`
- `s9`：`available=false`，`input/output/filtered=null`

这组样例用于验证“未单独计数”不会再被前端渲染成 `0`。

### 3.3 真 `0` 样例

真 `0` 样例由单测固定：

- `tests/unit/test_backtest_v2_artifacts.py::test_build_buy_stage_funnel_keeps_true_zero_counts_measured`
  - `s6` / `s7` / `s8` 在 `available=true` 时保留 `output_count=0`
- `tests/unit/test_backtest_v2_artifacts.py::test_build_buy_stage_funnel_preserves_unavailable_stage_counts`
  - unavailable 阶段保持 `input/output=null`
- `tests/unit/test_bridge_adapter_accounting.py::test_apply_daily_decision_diagnostics_preserves_unavailable_stage_counts`
  - `daily_row` 不再把缺失阶段压平成 `0`

## 4. 验证命令

本轮实际执行过的验证：

```powershell
python -m pytest tests/unit/test_backtest_v2_artifacts.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_experiment_query_service.py tests/unit/test_experiment_runner_daily_schema.py -q
python -m pytest tests/integration/test_schema_and_artifacts.py tests/integration/test_backtest_v2_experiment_artifacts.py -q
python -m pytest tests/unit/test_bridge_adapter_route_control.py tests/unit/test_bridge_adapter_setup.py tests/unit/test_foundation_shell.py -q
npm run build:results-workbench
```

另外执行了一次真实容器内复跑，对比源实验 `exp_20260315_001145197_2aa2` 与复跑实验 `exp_20260315_165038145_5f9a`。

## 5. 实际观察结果

### 5.1 交易结果面

事实：

- `perf.json` 核心字段完全一致：
  - `total_return=4.425630011081876`
  - `max_drawdown=-0.29025259513173496`
  - `cagr=0.2032763161631579`
  - `sharpe=0.8891097010317657`
  - `calmar=0.7003428033809594`
  - `trades=467`
  - `turnover=0.02077596030035478`
- `nav.csv` 行数与文件哈希一致：
  - `rows=2303`
  - `file_hash=a597bdd16471ba31c890bb1018cebb6dd98d56614369c368812db27c43b50bae`
- `buy_orders_count=237`、`sell_orders_count=230` 保持一致
- `portfolio_trades.csv` 主字段逐行一致；文件哈希不同是因为 `meta_json` 附带诊断字段集合不完全相同，不是成交价格/数量漂移

推断：

- 这轮修复没有改变交易结果主口径
- `portfolio_daily.csv` 与 `buy_stage_funnel` 变化属于预期诊断变化，不应当按旧的精确哈希基线判失败

### 5.2 漏斗变化面

源实验旧漏斗存在压平：

- `s5: 34440 -> 23788`
- `s6: 23788 -> 23788`
- `s7: 23788 -> 23788`
- `s8: 23788 -> 241`

复跑后阶段被重新拉开：

- `s5: 34440 -> 34440`
- `s6: 34440 -> 33674`
- `s7: 33674 -> 15070`
- `s8: 15070 -> 241`

这说明：

- held filter、slot filter、cash/lot filter 已恢复为独立阶段计数
- unavailable 阶段仍保留 unavailable，而不是被补成 `0`

## 6. 回退条件

出现以下任一情况，整轮回退：

- 同请求复跑后 `perf.json` 核心字段不一致
- `nav.csv` 行数或哈希变化
- `buy_orders_count` / `sell_orders_count` 漂移
- `portfolio_trades.csv` 的主字段出现逐行差异
- workbench 或旧桥接层再次把 `available=false` / `null` 显示成 `0`
- `stage_funnel` 与 `run_meta.counters.buy_stage_funnel` 对同一阶段给出矛盾的 zero/unavailable 结论

## 7. 已知边界

事实：

- 当前工作树本身还有其他并行改动，本轮复跑是在“当前工作树整体状态”下完成的
- 这次验证已经证明当前工作树下，交易结果面保持稳定、漏斗诊断面按预期变化

推断：

- 若后续还有 runtime / artifact 相关改动，仍应继续复用这组锚点实验做回归
