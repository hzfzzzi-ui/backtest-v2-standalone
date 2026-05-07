# 实现说明

## 改动边界

这条 change 只实现三件事：

1. `snapshot-backed research runtime` 输入合同
2. `study runner` 对 snapshot-backed research 的接线
3. `snapshot lineage` 的最小 machine outputs

这条 change 不改：

1. 正式主线 runtime 默认消费逻辑
2. 账户预算、执行行为与交易路径
3. 正式主线 artifacts 主输出结构

## 本次实现文件

新增：

1. `backend/research/snapshot_backed_study.py`
2. `research/studies/snapshots/stock_alpha_snapshot_backed_demo.study.yaml`
3. `research/studies/snapshots/account_state_snapshot_backed_demo.study.yaml`
4. `tests/unit/test_snapshot_backed_study.py`

修改：

1. `backend/research/study_runner.py`

## 验证

计划验证：

```bash
pytest tests/unit/test_snapshot_backed_study.py tests/unit/test_study_runner.py tests/unit/test_stock_alpha_factor_study.py tests/unit/test_account_state_score_study.py -q
```

## 风险

1. 当前 snapshot-backed runtime 仍然是 research-only，不能误当正式主线入口
2. snapshot lineage 首版只覆盖最小字段，后续如需更细审计仍要增量扩展
3. 若未来允许 snapshot 缺失时 fallback 重算，会重新引入口径漂移

## 回退

最小回退集：

1. `backend/research/snapshot_backed_study.py`
2. `backend/research/study_runner.py`
3. `research/studies/snapshots/stock_alpha_snapshot_backed_demo.study.yaml`
4. `research/studies/snapshots/account_state_snapshot_backed_demo.study.yaml`
5. `tests/unit/test_snapshot_backed_study.py`
