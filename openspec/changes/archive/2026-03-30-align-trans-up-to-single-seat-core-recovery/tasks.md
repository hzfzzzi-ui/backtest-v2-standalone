## 1. 合同收敛

- [x] 1.1 收敛 `etf_beta_contract` 中 `TRANS_UP` 的 live 目标语义，只保留 `core_accumulator` 的单 seat recovery。
DoD: `TRANS_UP` 不再产出需要第二个 seat 的独立 `tactical_satellite` live target。
验证: `tests/unit/test_etf_beta_contract.py` 覆盖 `TRANS_UP` 的 target/floor/overlay 合同。
风险: 不能误伤 `BULL`、`TRANS_DOWN`、`RISK_OFF` 的既有语义。

- [x] 1.2 对齐 provider 的 `TRANS_UP` monthly path 与 state-change redeploy path，使两条路径都遵守单 seat core recovery。
DoD: `TRANS_UP` 的 BUY signal 与 selection meta 不再暗含 second-seat overlay。
验证: `tests/unit/test_cn_etf_beta_signal_provider.py` 覆盖月末与 redeploy 两条路径。
风险: 不能破坏已落地的 `TRANS_UP` floor redeploy 行为。

## 2. 审计与产物

- [x] 2.1 更新 `portfolio_daily.csv` / `orders.csv` / ETF 相关日级字段，让 `TRANS_UP` 显式暴露 `single-seat core recovery` 合同。
DoD: 日级产物能区分 `TRANS_UP` 是单 seat core recovery，而不是“core + overlay 未部署”。
验证: `tests/unit/test_bridge_adapter_accounting.py` 与 `tests/unit/test_experiment_runner_daily_schema.py`。
风险: 字段命名不能与现有 target/deployment 字段冲突。

- [x] 2.2 更新 `research_audit` 对 `TRANS_UP` 的解释，去掉 “second-seat overlay 漏部署” 的旧口径。
DoD: 审计把 `TRANS_UP` 缺失 satellite 解释为合同真相，而非执行失败。
验证: `tests/unit/test_research_audit_contract.py`。
风险: 不能把真实执行漏损误洗成合同解释。

## 3. 回归与实验验证

- [x] 3.1 完成受影响链路回归测试。
DoD: contract/provider/accounting/audit/schema 相关单测全部通过。
验证: `pytest tests/unit/test_etf_beta_contract.py tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_research_audit_contract.py tests/unit/test_experiment_runner_daily_schema.py -q`
风险: 不能引入 timing、accounting 或 reason-code 回归。

- [x] 3.2 重跑正式 ETF 子实验并核对 `TRANS_UP` 行为差异。
DoD: 给出新旧实验的 `cagr / sharpe / max_drawdown`、`TRANS_UP` 平均目标/实际暴露与订单分布。
验证: 新实验 `exp_20260329_071754120_c37c` 与旧实验 `exp_20260329_044252761_be36` 的对比。
风险: 必须明确这是合同收敛结果，不把收益变化误解为 pace 优化。
