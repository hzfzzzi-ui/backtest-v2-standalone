## 1. Apply 前核对

- [x] 1.1 确认用户明确要求直接提升为组合基线 V3。
- [x] 1.2 确认 V3 绑定全周期 `1226` 实验 `exp_20260510_034302669_7790`。
- [x] 1.3 确认旧 active 同周期 baseline 需要降级，避免重复 active。

## 2. Baseline 注册

- [x] 2.1 复制候选实验核心产物到 `outputs/baselines/CN_STOCK_ETF_COMBO_BASELINE_V3/`。
- [x] 2.2 写出 V3 `baseline.json`、`baseline_config_snapshot.json`、`config.json`。
- [x] 2.3 将 `CN_STOCK_ETF_FORMAL_V1` 和 `CN_STOCK_ETF_COMBO_BASELINE_V2` 标记为 `superseded`。
- [x] 2.4 刷新 `outputs/baselines/index.json` 并确认同周期 active 唯一。

## 3. 默认入口

- [x] 3.1 将前端默认 bootstrap baseline 改为 `CN_STOCK_ETF_COMBO_BASELINE_V3`。
- [x] 3.2 将 baseline regression current anchor 改为 V3。
- [x] 3.3 更新对应单元测试断言。

## 4. 验证

- [x] 4.1 `openspec validate promote-domestic-pool-combo-baseline-v3 --strict` 通过。
- [x] 4.2 baseline access 能读取 V3，且 `linked_exp_id` 可解析。
- [x] 4.3 前端默认 baseline 文案指向 V3。
- [x] 4.4 相关单元测试通过。
- [x] 4.5 Docker 内执行 baseline regression `--rerun --write-to-candidate` 通过；candidate `exp_20260510_043240625_52f9` 对 V3 锚点 `exp_20260510_034302669_7790` 为 `PASS`，blocking/warning/total mismatches 均为 0。
