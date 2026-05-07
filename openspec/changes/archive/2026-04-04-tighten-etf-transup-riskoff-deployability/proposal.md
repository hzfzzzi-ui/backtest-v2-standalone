## Why

当前 ETF research mainline `exp_20260331_064758953_0fa5` 的部署合同与执行路径明显失配：`BULL` 平均目标暴露为 `1.0`，平均实际暴露只有 `0.49`；`TRANS_UP` 平均目标暴露为 `0.9`，平均实际暴露只有 `0.013`；`RISK_OFF` 明明给了正目标暴露，运行时仍被压成 `deployment_pace=0.0`。如果继续维持“非 rebalance 日只等不补”的实现，本轮用户要求的 `BULL/TRANS_UP` 目标与实际暴露偏差不超过 `10%` 无法达成。

## What Changes

- 修改 ETF 单腿在 `governed_broad_based_standalone_mainline` 路径下的部署合同，使 `RISK_OFF` 的正目标暴露在无 Governor hard block 时不再被静默压成零部署。
- 修改 ETF 单腿在 `governed_broad_based_standalone_mainline` 路径下的 `TRANS_UP` 恢复逻辑，使其不再只依赖一次性状态切换补仓，而是允许持续补齐强状态目标缺口。
- 为 `BULL/TRANS_UP` 新增强状态 gap-fill 执行路径，用统一的 target/deployment/gap 诊断链路约束实际补仓，避免继续长期停留在 `hold_until_rebalance`。
- 保留 ETF 资产池、排序链、调仓频率、前端、combo 与 formal ETF stabilizer 主边界不变。
- 增补测试与回测核验，直接以 `2012-01-01` 到 `2026-03-24` 的 research mainline 结果验证 `BULL/TRANS_UP` 偏差是否压到 `10%` 内。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `cn-etf-beta-sleeve`: 扩展 ETF 单腿在 research-only standalone mainline 路径下的 `RISK_OFF / TRANS_UP` 部署合同，并增加 `BULL/TRANS_UP` 强状态 gap-fill 执行语义与可审计证据。

## Impact

- 受影响代码：
  - `backend/core/config/etf_beta/common.py`
  - `backend/core/config/etf_beta/exposure_semantics.py`
  - `backend/core/engine_vector/etf_beta/selection.py`
  - `backend/core/engine_vector/etf_beta/execution_paths.py`
  - `backend/core/stage_pipeline/adapters/etf_beta_accounting.py`
  - `backend/core/audit/research_audit.py`
  - `tests/unit/test_etf_beta_contract.py`
  - `tests/unit/test_cn_etf_beta_signal_provider.py`
  - `tests/unit/test_bridge_adapter_accounting.py`
- 受影响产物：
  - `run_meta.json`
  - `audit.json`
  - `portfolio_daily.csv`
  - `orders.csv`
- 不在本次范围：
  - ETF 资产池与 research study 配置
  - Governor 预算合同
  - front-end / combo / unified runtime
