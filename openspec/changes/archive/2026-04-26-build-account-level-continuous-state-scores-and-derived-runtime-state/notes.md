# 实现说明

## 改动边界

这条 change 只实现三件事：

1. `account-level continuous state score catalog`
2. `daily score snapshot / combo snapshot`
3. `single-score / combo-score` 研究入口

这条 change 不改：

1. 主 runtime 默认消费逻辑
2. 账户预算映射与执行行为
3. 正式 artifacts 主输出结构

## 本次实现文件

新增：

1. `backend/research/account_state_score_catalog.py`
2. `backend/research/account_state_score_snapshots.py`
3. `backend/research/account_state_score_study.py`
4. `research/studies/state_scores/account_state_score_surface_demo.study.yaml`
5. `tests/unit/test_account_state_score_catalog.py`
6. `tests/unit/test_account_state_score_study.py`

修改：

1. `backend/research/study_runner.py`

## 验证

计划验证：

```bash
pytest tests/unit/test_account_state_score_catalog.py tests/unit/test_account_state_score_study.py tests/unit/test_study_runner.py -q
```

## 风险

1. 首版连续分数公式仍是研究层近似定义，不应误当正式 runtime 状态真相
2. `derived_state` 当前只是研究层解释产物，不应直接接入正式主线 budget/execution
3. 如果后续第三条 change 接 runtime，必须继续保持 score 为主、离散状态为辅

## 回退

最小回退集：

1. `backend/research/account_state_score_catalog.py`
2. `backend/research/account_state_score_snapshots.py`
3. `backend/research/account_state_score_study.py`
4. `backend/research/study_runner.py`
5. `research/studies/state_scores/account_state_score_surface_demo.study.yaml`
6. `tests/unit/test_account_state_score_catalog.py`
7. `tests/unit/test_account_state_score_study.py`
