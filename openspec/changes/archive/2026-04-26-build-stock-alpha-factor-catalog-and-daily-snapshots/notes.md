# 实现说明

## 改动边界

这条 change 只实现三件事：

1. `stock alpha factor catalog`
2. `daily factor snapshot / factor score snapshot`
3. `single-factor / factor-combo` 研究入口

这条 change 不改：

1. 主 runtime 默认消费逻辑
2. 账户层连续状态分数
3. 正式组合预算与执行行为

## 本次实现文件

新增：

1. `backend/research/stock_alpha_factor_catalog.py`
2. `backend/research/stock_alpha_factor_snapshots.py`
3. `backend/research/stock_alpha_factor_study.py`
4. `research/studies/factors/stock_alpha_factor_surface_demo.study.yaml`
5. `tests/unit/test_stock_alpha_factor_catalog.py`
6. `tests/unit/test_stock_alpha_factor_study.py`

修改：

1. `backend/research/study_runner.py`

## 验证

已通过 focused tests：

```bash
pytest tests/unit/test_stock_alpha_factor_catalog.py tests/unit/test_stock_alpha_factor_study.py tests/unit/test_study_runner.py tests/unit/test_a_share_moneyflow_divergence.py -q
```

结果：

- `28 passed`

## 风险

1. 目前 `factor snapshot` 仍是研究层产物，还没有接入正式 runtime
2. `human summary` 只提供最小研究摘要，不是最终研究报告模板
3. 因子定义仍是第一版目录，后续扩展必须继续遵守单轮最小改动

## 回退

最小回退集：

1. `backend/research/stock_alpha_factor_catalog.py`
2. `backend/research/stock_alpha_factor_snapshots.py`
3. `backend/research/stock_alpha_factor_study.py`
4. `backend/research/study_runner.py`
5. `research/studies/factors/stock_alpha_factor_surface_demo.study.yaml`
6. `tests/unit/test_stock_alpha_factor_catalog.py`
7. `tests/unit/test_stock_alpha_factor_study.py`

回退后，研究平台会恢复到“无 stock alpha factor catalog / snapshot / study surface”的状态。
