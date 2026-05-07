## Why

当前 `cn_stock_etf_v1` unified combo 的 stock/ETF 两条腿并没有消费正式锚点，而是从同一个 research template 深拷贝后各自裁剪，导致组合结果既不代表正式 `baseline_V10.1`，也不代表正式 ETF stabilizer。这个漂移已经直接造成 stock+ETF 结果误读，必须先收敛组件来源，再讨论组合本身是否值得推进。

## What Changes

- 将 unified combo 的 stock sleeve 改为从正式 `baseline_V10_1` baseline 记录物化，而不是从 unified template 深拷贝。
- 将 unified combo 的 ETF sleeve 改为从正式 `etf/cn_etf_first_wave_core` study 的主窗口与 `CORE` variant 物化，而不是从 unified template 深拷贝。
- 保持 unified combo 当前 `research_combo_only`、固定 `50/50`、按重叠 NAV 拼接的研究语义不变，不把本次改动扩展成正式多 sleeve Governor 运行。
- 在 compiled plan、run_meta 和 combo context 中补齐组件来源元数据，明确写出 stock baseline id、ETF study id、window key、variant name 和 source mode。
- 增加 unified combo 编译与运行回归测试，防止未来再次退回 research template 组件漂移。

## Capabilities

### New Capabilities
- `cn-stock-etf-unified-runtime-entry`: 定义 unified combo 作为 research-only 入口时，必须消费正式 stock/ETF sleeve anchors，并输出可审计的组件来源元数据。

### Modified Capabilities
- `api-runtime-config-compilation`: `cn_stock_etf_v1` 的 runtime compile 必须物化正式 stock baseline 与正式 ETF study anchor，而不能继续从 unified template 深拷贝两个 sleeve。

## Impact

- 受影响代码：
  - `backend/api/backtest_v2/runner_config_bundle.py`
  - `backend/core/services/cn_stock_etf_unified_runtime_service.py`
  - `tests/unit/test_experiment_runner_multi_alpha_compile.py`
  - `tests/unit/test_cn_stock_etf_unified_runtime_service.py`
- 受影响产物：
  - unified combo 的 `compiled_plan.json`
  - unified combo 的 `run_meta.json`
- 外部依赖：
  - 复用现有 `baseline_access`
  - 复用现有 `study_loader` / `study_runner.build_request_payload`
