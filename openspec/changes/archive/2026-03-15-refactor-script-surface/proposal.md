## Why

当前 `backend/scripts` 已经演化成第二套事实上的应用边界，AI 和人工实验都在不断复制新的大脚本，导致总线约束、产物协议和 baseline 归档不断失控。现在必须把脚本面收编成正式命令面、study 定义面和薄脚本入口，否则后续任何实验治理都会重新长回散脚本模式。

## What Changes

- 建立统一 CLI 命令面，并以 `study_run` 作为所有实验矩阵的唯一正式执行器。
- 将绝大多数 `run_*_research.py` 迁移为 `.study.yaml + study_run + 可选 generated thin script`。
- 将活跃脚本面限制为 `backend/cli/main.py` 和按需生成的 `backend/scripts/generated/run_<study_id>.py`。
- 固化 `bus-first` 工作流：新逻辑先接总线，再定义 study，最后才允许生成薄脚本。
- 固化 `dual-output` 产物：每次实验都必须产出 machine bundle、human bundle 和 baseline append。
- 将 `FAIL` 实验也纳入 baseline 报告和 ledger，避免重复试错。

## Capabilities

### New Capabilities
- `study-definition-runner`: 定义 study 契约、study runner 和统一 CLI 命令面。
- `experiment-dual-output`: 定义 machine bundle、human bundle 和 NAC 机器读判断包。
- `script-surface-governance`: 定义脚本分类、薄脚本模板、活跃脚本面约束和 baseline 追加规则。

### Modified Capabilities
- 无

## Impact

- 影响 `backend/scripts/*`、未来 `backend/cli/*`、`backend/research/*` 和 experiment summary/baseline report 服务。
- 影响实验产物目录、baseline ledger 和基线报告写入流程。
- 影响 AI 和人工实验的默认工作方式。
- 不应改变实验口径、执行口径或 baseline 结果本身，只重构实验入口和产物协议。
