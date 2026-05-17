## 1. Apply 前核对

- [x] 1.1 确认用户明确要求直接升格 D7 deep-only stock-only 结果。
- [x] 1.2 确认本次正式锚点绑定 `exp_20260512_063520440_82bb`。
- [x] 1.3 确认升格范围仅限 `baseline_V10_1`，不改 combo baseline。

## 2. Baseline 重挂

- [x] 2.1 备份 `baseline_V10_1` 现有 `baseline.json` 与 `config.json`。
- [x] 2.2 将 D7 全周期配置快照写入 `baseline_V10_1/config.json` 与 `baseline_config_snapshot.json`。
- [x] 2.3 将 `baseline_V10_1/baseline.json` 的 `linked_exp_id` 重挂到 `exp_20260512_063520440_82bb`，并写入 `execution_contract_ref`。
- [x] 2.4 从 D7 实验复制核心审计产物到 `outputs/baselines/baseline_V10_1/`。
- [x] 2.5 刷新 `outputs/baselines/index.json` 并确认 `baseline_V10_1` 可解析到本地实验。

## 3. 台账与验证

- [x] 3.1 向 `baseline_V10_1` 追加一条 official promotion ledger/report 记录，并刷新 `latest_champion.json`。
- [x] 3.2 写 promotion note，说明证据、范围、风险和回退。
- [x] 3.3 `openspec validate promote-d7-deep-only-stock-baseline-v10-1 --strict` 通过。
- [x] 3.4 读回 `baseline_V10_1` 并确认 `linked_exp_id`、`config_hash`、`cagr`、`max_drawdown` 已切换到 D7。
