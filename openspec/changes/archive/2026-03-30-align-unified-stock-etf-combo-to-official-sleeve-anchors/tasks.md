## 1. 规格落地

- [x] 1.1 在 unified combo compile 层接入正式 stock baseline 物化路径。DoD：`cn_stock_etf_v1` 编译后的 stock sleeve semantic config 来自 `baseline_V10_1`；验证：单测断言 `start=2012-01-04` 与 residual ranking 字段存在；风险：baseline 记录缺失时必须快速失败。
- [x] 1.2 在 unified combo compile 层接入正式 ETF study 物化路径。DoD：ETF sleeve semantic config 来自 `etf/cn_etf_first_wave_core` 主窗口 `1626` 的 `CORE` variant；验证：单测断言 `phase1_scope_mode=core_beta_plus_limited_defense` 与 `start=2016-11-04`；风险：study 定义改名时会导致 compile 失败。

## 2. 元数据与运行产物

- [x] 2.1 在 compiled plan 的 `combo_context` 中写入官方组件来源元数据。DoD：包含 `component_source_mode`、stock baseline id、ETF study id、window key、variant name；验证：compile 单测断言字段存在；风险：字段命名漂移会破坏前后端契约。
- [x] 2.2 在 unified combo `run_meta.json` 中透传组件来源元数据，并继续标记 `research_combo_only`。DoD：运行服务产物同时包含 `research_combo_only=true` 与官方组件来源信息；验证：service 单测读取 `run_meta.json` 断言；风险：不能误导成正式多 sleeve runtime。

## 3. 回归与结果验证

- [x] 3.1 更新 unified combo 编译与运行回归测试。DoD：相关单测全部通过；验证：`pytest tests/unit/test_experiment_runner_multi_alpha_compile.py tests/unit/test_cn_stock_etf_unified_runtime_service.py`；风险：测试不得绑定过多非关键字段。
- [x] 3.2 重跑正式组件对齐版 combo 并核对新旧差异。DoD：产出新的 combo 实验并给出与旧 combo 的 CAGR / MaxDD / Sharpe 对比；验证：保存新实验 id 与结论；风险：必须明确这是 research-only 组合器结果。
