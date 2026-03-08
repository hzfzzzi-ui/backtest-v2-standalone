## 1. Wave1 退役证据固化

- [x] 1.1 复核并固化 `run_alpha_v1.py` 的零 live caller 证据、替代路径与删除前置条件；DoD: 形成可直接引用的 wave1 retirement ledger；验证: grep/文档审阅；风险: 漏掉隐藏调用者导致误删
- [x] 1.2 明确 wave1 的“不删除清单”，写清 `_experiment_runner_api`、`_config_governance`、`_candidate_presets`、`backtest_v2_artifacts`、`report_generator` 当前仍不可删的原因；DoD: 删除边界清晰，不会把 live shim 误纳入本 wave；验证: 文档审阅；风险: 范围描述模糊导致实现时越界

## 2. Active Tree Retirement

- [x] 2.1 删除 `backend/scripts/run_alpha_v1.py`，并清理 active tree 中依赖其 frozen 行为的测试或运行面引用；DoD: active 代码树中不再存在该脚本文件；验证: 文件缺失检查与 targeted harness；风险: 遗漏测试/工具引用
- [x] 2.2 更新 active spec 与当前 ops 文档，使其表达“该能力已退役”而不是“仍由 frozen stub 承接”；DoD: active spec 不再声明系统 SHALL 提供 `run_alpha_v1.py`；验证: spec/文档审阅；风险: code truth 与 spec truth 再次漂移

## 3. Retirement Guard

- [x] 3.1 补 targeted checks，覆盖：`run_alpha_v1.py` 已删除、active source 无 live caller、历史冻结文档与 retirement ledger 一致；DoD: 新检查能阻止该脚本被悄悄加回 active tree；验证: 定向 harness；风险: 只检查文件存在与否，未检查引用回流
- [x] 3.2 运行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`，确认锁定基线 `exp_20260308_021045840_cde0` 的核心产物继续 `PASS`，若有 `WARN` 仅允许 `report.html` 诊断漂移；DoD: delete wave 不改变结果真相；验证: baseline compare 报告；风险: 看似无关的删除动作误伤脚本或产物链路
