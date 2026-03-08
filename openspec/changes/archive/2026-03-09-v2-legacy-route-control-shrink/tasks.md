## 1. Stage applicability split

- [x] 1.1 抽出 `stage_applicability.py`，承接 `disabled_stages` 和 `stage_is_applicable(...)` 判定；DoD：`legacy_adapter.py` 不再直接内嵌 stage 可用性逻辑；验证：聚焦单测覆盖 disabled stage 与 route-specific applicability；风险：neutral output 触发条件漂移。
- [x] 1.2 为 stage applicability 增加聚焦测试；DoD：覆盖 `S2/S3/S8` 和 disabled stage 组合；验证：定向 harness 或单测通过；风险：测试未覆盖 route-specific 条件分支。

## 2. Route day-control and signal postprocess split

- [x] 2.1 抽出 `day_controls.py`，承接 `_compute_day_controls(...)` 和相关计数更新；DoD：`legacy_adapter.py` 只保留 helper 调用；验证：聚焦单测比较 `effective_max_positions/risk_on_today/market_state/trade_mode`；风险：计数器更新顺序漂移。
- [x] 2.2 抽出 `signal_postprocess.py`，承接 provider day signal 的 route-specific 后处理；DoD：benchmark regime gate 与 market-filter gate 过滤顺序保持不变；验证：定向测试比较 buy signal 过滤结果；风险：buy signal 过滤优先级变化。
- [x] 2.3 更新 `legacy_adapter.py` 冻结边界；DoD：adapter 仅保留 runtime 容器、少量时序组织和 helper 委托；验证：代码审阅和冻结文档一致；风险：route-specific 新逻辑继续长回单体 adapter。

## 3. Verification and freeze

- [x] 3.1 运行 route/day-control 相关聚焦测试与 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`；DoD：锁定基线 `exp_20260308_021045840_cde0` 的核心产物继续 `PASS`；验证：baseline compare 输出；风险：run_meta/perf 诊断计数出现隐蔽漂移。
- [x] 3.2 补充 route-control 冻结文档，明确 applicability、day controls、signal postprocess 的新归属和 `legacy_adapter.py` 剩余责任；DoD：文档可直接作为下一条 change 的边界输入；验证：文档落盘并与实现一致；风险：冻结范围定义不清，后续又往 adapter 回填 route-specific 逻辑。
