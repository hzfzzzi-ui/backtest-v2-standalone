## Why

当前执行链仍大量经过旧过渡壳：

- 子系统跨边界正式输入/输出仍混着 `candidate_plan`、旧 `target_book` 过渡语义
- `global_portfolio_governor`、子系统与 `execution_kernel` 的正式职责虽然已经在文档里收口，但实现层尚未对齐
- 旧执行壳如果继续扩张，会反向污染研究链、事务域和前端

根据当前正式文档，运行主链已经定为：

`market_regime_engine -> global_portfolio_governor -> 子系统 -> action_intent_v1 / risk_override_v1 -> execution_kernel -> target_book_v1 + execution_audit`

这意味着执行边界必须被单独收口。

## What Changes

- 将运行时执行边界正式收口到 `action_intent_v1 / risk_override_v1 -> execution_kernel -> target_book_v1 + execution_audit`。
- 明确 `candidate_boundary / candidate_plan / 过渡 target_book` 仍可作为子系统内部或迁移期结构存在，但不再被定义为跨共享执行边界主合同。
- 收紧 `SOURCE_ONLY`、`PREFER_HIGHER_SCORE`、卖出权限和 Governor 强平语义。
- 为执行层补齐 golden/contract 场景，确保迁移后有稳定回归面。

## Capabilities

### Modified Capabilities
- `runtime-boundary-contracts`: 正式跨边界合同收口到 `action_intent_v1`、`risk_override_v1`、`target_book_v1`、`execution_audit`。
- `candidate-plan-boundary-contracts`: `candidate_plan` 降级为子系统内部或迁移期结构，不再是执行层主输入。
- `cn-a-portfolio-governor`: Governor 正式输出预算与 `risk_override_v1`，并拥有跨来源强平权限。
- `source-aware-holdings`: 继续沿用 `SOURCE_ONLY`，并限制普通卖出只能卖自己来源仓位。
- `execution-contract-goldens`: 增补运行时合同与阻断/覆盖/截断的黄金样例。

## Impact

- 主要影响模块：
  - `backend/core/stage_pipeline`
  - `backend/core/portfolio`
  - `backend/core/services`
  - 执行审计与结果工作台消费层
- 主要风险：
  - 迁移过程中容易误改研究口径或执行时点
  - compat 壳与正式合同并存时容易出现双重语义
- 主要验证：
  - runtime contract goldens
  - baseline 行为等价回归
  - execution audit 回归
