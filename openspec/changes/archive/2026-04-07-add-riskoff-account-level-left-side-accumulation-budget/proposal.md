## Why

当前账户层已经成为 runtime 主真相，但 `RISK_OFF` 下的预算语义仍偏防守空仓化，不符合“弱势环境下用债为主、少量核心宽基持续捡便宜筹码”的研究目标。现在需要把这件事上收到账户层预算，而不是继续在 ETF 单腿执行路径里堆局部补丁。

## What Changes

- 在账户层新增 `RISK_OFF` 左侧累积预算合同，明确 `defense + core_beta` 的目标配比与约束。
- 将 `RISK_OFF` 的账户层预算语义从“纯防守缩仓”调整为“防守优先、少量核心宽基累积”。
- 保持 `TRANS_DOWN`、`stock alpha`、`50/50 reference` 和既有执行约束不变。
- 为 explain / audit 增加账户层左侧累积预算的可观测字段。

## Capabilities

### New Capabilities
- `riskoff-account-level-left-side-accumulation-budget`: 定义 `RISK_OFF` 下账户层左侧累积预算的正式合同与验收口径。

### Modified Capabilities
- `account-allocation-runtime-cutover`: 将 `RISK_OFF` 的 runtime 主预算解释从纯防守收缩更新为“债为主 + 少量核心宽基累积”的账户层语义。

## Impact

- Affected code:
  - `backend/core/services/account_allocator_shadow.py`
  - `backend/api/backtest_v2/runner_config_bundle.py`
  - `backend/core/services/cn_stock_etf_unified_runtime_service.py`
  - `backend/core/audit/research_audit.py`
  - `frontend/app/results-workbench/helpers/resultsFormatting.js`
- Affected artifacts:
  - `run_config.json`
  - `run_meta.json`
  - `audit.json`
  - 前端 governor / account allocator explain
- Dependencies:
  - 依赖当前 `account_allocator_runtime` 已成为主真相
  - 不依赖重做 ETF 局部 execution constraint
