## 1. Study 定义

- [x] 1.1 新增 `research/studies/v10/moneyflow_monthly_soft_weight_s1.study.yaml`
- [x] 1.2 新增 `1217 / 1226` 两个 window base runtime config，并绑定现代 `factor_snapshot.csv` 路径
- [x] 1.3 只保留 `B0 / SCORE_WEIGHT_BASE / MF_SOFT_10 / MF_SOFT_20` 四个变体

## 2. 入口治理

- [x] 2.1 新增 generated thin script `backend/scripts/generated/run_v10_moneyflow_monthly_soft_weight_s1.py`
- [x] 2.2 确保新 study 继续使用 `runtime_config_path + runtime_config_json` 的唯一执行真相

## 3. 验证

- [x] 3.1 对新 study 执行 `study_run --dry-run`
- [x] 3.2 运行两窗口真实 study，并比较 `B0 / SCORE_WEIGHT_BASE / MF_SOFT_10 / MF_SOFT_20`
- [x] 3.3 运行定向测试，验证 study surface 与 generated script surface 未破坏
