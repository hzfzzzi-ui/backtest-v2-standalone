## 1. 触发合同

- [x] 1.1 在 formal ETF stabilizer 中识别 `TRANS_UP` 状态切换沿，并形成单次 redeploy 触发条件。DoD：只有从更防守状态切入 `TRANS_UP` 时才允许触发；验证：provider 单测覆盖进入、持续和退出三种状态段；风险：不能把每个 `TRANS_UP` 日都变成补仓日。
- [x] 1.2 将 redeploy 限定为 `core_accumulator` floor 补齐，不触发 satellite rotation。DoD：非月末 redeploy 只会生成 core-only 买单；验证：订单 meta 与 reason_code 单测；风险：不能悄悄把 non-monthly 日升级成 full rebalance。

## 2. 产物与可观测性

- [x] 2.1 为 redeploy 增加最小审计字段和 reason_code。DoD：`orders.csv` / `portfolio_daily.csv` 能区分 monthly rebalance 与 `TRANS_UP` redeploy；验证：daily/accounting 单测；风险：字段命名不能和现有 monthly reason_code 混淆。
- [x] 2.2 为“未触发 redeploy”的关键分支补拒绝原因。DoD：至少能区分 hard block、floor 已满足、非状态切换沿三类拒绝；验证：provider reason_code 单测；风险：不能让拒绝原因再次变成黑箱。

## 3. 回归与结果验证

- [x] 3.1 完成 ETF stabilizer 相关回归。DoD：受影响单测通过；验证：`pytest tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_bridge_adapter_accounting.py tests/unit/test_etf_beta_contract.py`；风险：不引入 timing 或 accounting 回归。
- [x] 3.2 重跑正式 ETF 子实验并比较 `TRANS_UP` 部署结果。DoD：给出新旧 `CAGR / Sharpe / MaxDD`，以及 `TRANS_UP` 的实际平均仓位变化；验证：保存新实验 id 和对比结论；风险：必须明确这是单一主改动的结果。
