## 1. 调用者盘点与冻结边界

- [x] 1.1 生成剩余脚本/工具调用者矩阵，覆盖 `public caller`、`internal helper caller`、`frozen legacy script` 三类；DoD: 至少覆盖 `run_alpha_v1`、`baseline_regression_check`、`run_clean_data_standard_reruns`、`report_consistency_check`；验证: 盘点文档审阅；风险: 漏统计算法导致删除候选误判
- [x] 1.2 形成 internal shim 冻结文档，明确 `_experiment_runner_api`、`_config_governance`、`_candidate_presets`、`backtest_v2_artifacts`、`report_generator` 的 live callers、替代入口与退役门槛；DoD: 每个 shim 都有 owner、replacement、delete gate；验证: 文档审阅与 change 内引用完整；风险: shim 边界描述不清导致后续继续长逻辑

## 2. Internal Helper 收口

- [x] 2.1 设计并落地 internal helper 边界，承接 internal rerun、manifest/artifact 读取、saved config provenance 与 optional report 访问；DoD: 内部脚本可不再直接 import endpoint 私有实现；验证: 新增 helper 定向测试；风险: helper 变成新的散乱兼容层
- [x] 2.2 将 `baseline_regression_check.py`、`run_clean_data_standard_reruns.py`、`report_consistency_check.py` 迁到 internal helper 或记录为显式冻结例外；DoD: 三者都不再直接散落依赖私有 endpoint 细节；验证: 定向 harness 与脚本 dry-run；风险: 误伤基线门禁或报告诊断流程

## 3. 旧脚本迁移与退役候选

- [x] 3.1 迁移 `run_alpha_v1.py` 到 internal helper，或将其正式列入冻结清单并写明不迁移原因；DoD: 它不再隐式依赖公开旧字段；验证: 脚本调用面审阅与最小 smoke；风险: 为兼容旧脚本而反向污染公开 `config_json`
- [x] 3.2 形成第一批可安全删除的 legacy 模块候选清单，并附上零 live caller 证据、替代入口与删除前置条件；DoD: 候选清单可直接作为后续 retirement change 输入；验证: 文档审阅；风险: 候选范围过大导致误删

## 4. 回归与退役门槛验证

- [x] 4.1 补充 internal helper 与脚本治理的 targeted tests，覆盖 caller 分类、manifest/helper 读取链路和冻结例外；DoD: 新增测试能卡住脚本再次回到旧公开字段；验证: 定向测试/harness；风险: 只验证 happy path
- [x] 4.2 执行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`，并对保留的内部诊断脚本做最小一致性验证；DoD: 锁定基线 `exp_20260308_021045840_cde0` 的核心产物继续 `PASS`，若有 `WARN` 仅允许 `report.html` 诊断漂移；验证: baseline compare 报告与内部脚本定向结果；风险: 脚本迁移意外改变配置真相或产物读写口径
