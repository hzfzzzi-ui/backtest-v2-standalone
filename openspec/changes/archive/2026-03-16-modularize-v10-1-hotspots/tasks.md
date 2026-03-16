## 1. Runtime Config Compile 拆分

- [x] 1.1 将 `runner_config_helpers.py` 按 `base / universe / signal / risk-exit / bundle` 拆成独立模块，并保留 façade 入口。
- [x] 1.2 为 runtime config compile 补齐边界测试，验证 canonical config 与 semantic bundle 输出不变。
- [x] 1.3 以前后对照 `baseline_V10.1` 运行一次最小 compile + runtime smoke，确认不引入口径漂移。

## 2. Artifact Finalize Pipeline 拆分

- [x] 2.1 将 `artifacts_impl.py` 按 `io / manifest / stage-summary / diagnostics / finalize` 拆成独立模块，并保留 façade 入口。
- [x] 2.2 补齐 artifact stabilize、manifest、surface section 的边界测试，验证标准产物协议不变。
- [x] 2.3 对 `baseline_V10.1` 对应实验目录执行 stabilize/manifest 对照，确认 canonical outputs 不漂移。

## 3. Provider Hotspot 拆分

- [x] 3.1 为 `regime_router_signal_provider.py` 建立集中 state/config owner，并把 `precompute/day routes` 外提到专用模块。
- [x] 3.2 为 `breakout_signal_provider.py` 建立集中 state/config owner，并继续把 route/precompute 重块迁出 façade。
- [x] 3.3 补 provider 协议测试和 route 级 golden 对照，确认 provider façade 行为不变。

## 4. Default Route Hotspot 拆分

- [x] 4.1 将 `strict_runtime_default.py` 按 `input / benchmark / signal / daily-loop / result` 五个阶段外提到专用模块。
- [x] 4.2 保持 `strict_runtime_default.py` 只做 façade 编排，不再承载具体阶段实现。
- [x] 4.3 对默认 route 跑 `baseline_V10.1` 前后对照，确认收益、回撤、订单数和交易数完全一致。

## 5. 回归与收口

- [x] 5.1 统一更新相关 import、注释和模块说明，明确 façade 与专用模块的职责边界。
- [x] 5.2 跑 `node/python/pytest/compileall` 的相关验证集，确保拆分后没有静态错误。
- [x] 5.3 回写 OpenSpec 任务状态，并记录 `baseline_V10.1 -> exp_20260314_144548534_7db9` 的最终对照结果。

## Verification Notes

- `runner_config` smoke：`outputs/ops/modularize_v10_1_runner_config_smoke.json`，候选实验 `exp_20260315_163134664_2c20`，状态 `PASS`。
- `artifact finalize` 对照：`outputs/ops/modularize_v10_1_artifact_compare/artifact_compare.json`，`all_pass = true`。
- `default route` smoke：`outputs/ops/modularize_v10_1_runtime_smoke.json`，候选实验 `exp_20260315_170848599_e501`，状态 `PASS`。
- 锚定基线：`baseline_V10.1 -> exp_20260314_144548534_7db9`
  - `total_return = 4.425630011081876`
  - `max_drawdown = -0.29025259513173496`
  - `cagr = 0.2032763161631579`
  - `sharpe = 0.8891097010317657`
  - `calmar = 0.7003428033809594`
  - `orders = 467`
  - `closed_trades = 230`
