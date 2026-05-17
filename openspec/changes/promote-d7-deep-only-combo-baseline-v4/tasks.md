## 1. Apply 前核对

- [x] 1.1 确认用户明确要求将组合主线升级到 V4。
- [x] 1.2 确认 V4 绑定 `exp_20260511_073506050_3d22`。
- [x] 1.3 记录这是 user-approved override，而不是 combo headline 自然胜出。

## 2. Baseline 注册

- [x] 2.1 备份 `CN_STOCK_ETF_COMBO_BASELINE_V3` 现有 `baseline.json`、`config.json` 与 `index.json`。
- [x] 2.2 将 `CN_STOCK_ETF_COMBO_BASELINE_V3` 标记为 `superseded`，`superseded_by = CN_STOCK_ETF_COMBO_BASELINE_V4`。
- [x] 2.3 创建 `CN_STOCK_ETF_COMBO_BASELINE_V4`，写出 `baseline.json`、`baseline_config_snapshot.json`、`config.json`。
- [x] 2.4 复制 V4 候选实验核心产物到 `outputs/baselines/CN_STOCK_ETF_COMBO_BASELINE_V4/`。
- [x] 2.5 刷新 `outputs/baselines/index.json` 并确认同周期 active 唯一。

## 3. 默认入口

- [x] 3.1 将桌面端默认 bootstrap baseline 改为 `CN_STOCK_ETF_COMBO_BASELINE_V4`。
- [x] 3.2 将 foundation baseline regression current anchor 改为 V4。
- [x] 3.3 更新对应最小测试与说明文档。

## 4. 验证

- [x] 4.1 `openspec validate promote-d7-deep-only-combo-baseline-v4 --strict` 通过。
- [x] 4.2 读回 V4 baseline，确认 `linked_exp_id`、`config_hash`、`cagr`、`max_drawdown` 正确。
- [x] 4.3 跑最小回归：`pytest -q tests/unit/test_baseline_regression_check.py tests/unit/test_frontend_runtime_boundaries.py`。
