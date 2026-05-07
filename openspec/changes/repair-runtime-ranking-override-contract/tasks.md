## 1. 合同收口

- [x] 1.1 在 `build_foundation_runtime_plan()` 增加 legacy 排序字段规范化，把 `runtime_config.strategy.params` 中的 residual/multifactor 排序意图一次性写入 `RuntimePlan.execution_overrides`；DoD：`execution_overrides` 成为唯一排序执行真相；验证：新增/更新 foundation shell 单测；风险：显式 override 优先级不能被覆盖。
- [x] 1.2 保持 compile path 与 direct runtime-config path 的排序字段语义等价，只规范化 compile path 已承认的少量字段；DoD：不会引入新的排序模式或额外 runtime 分支；验证：定向单测覆盖 `ranking_mode`、`enable_residual_ranking`、显式关闭三类输入；风险：扩大派生范围会引入额外行为漂移。

## 2. 验证与复跑

- [x] 2.1 更新定向单元测试，证明 direct runtime-config path 在未给显式 override 时会生成 `enable_multifactor_rank=true`，且显式 `false` 仍优先；DoD：相关测试稳定通过；验证：`pytest tests/unit/test_foundation_shell.py -q`；风险：测试只验证字段透传，不应假装覆盖完整回测行为。
- [x] 2.2 只重跑 `v10/live_baseline_ablation_s1` 的 `B0` 与 `A1_NO_RESIDUAL_RANK`；DoD：`B0` 不再出现 `final_score_rank_applied_days=0 && mf_rank_applied_days=0` 的死路径特征，且 `B0/A1` 结果产生可解释差异；验证：`python -m backend.cli study_run v10/live_baseline_ablation_s1 --window 1226 --variant ...`；风险：这是 L3 行为修复，结果变化必须限定在最小复跑范围解释。
