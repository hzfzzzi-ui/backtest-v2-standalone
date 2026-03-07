## Why

当前回测报告存在多处一致性问题：报告展示的区间、标的数量、策略参数与实际运行配置不一致，且存在中文乱码，导致研究结论不可复核、前后端口径不统一。该问题已影响“冠军配置”复验与实验对比，需要立即建立报告口径一致性约束并修复生成链路。

## What Changes

- 统一报告数据口径，报告中的区间/基准/标的数量/策略参数必须来自本次运行的最终配置与产物（而非模板默认或回退字段）。
- 修复服务器端报告生成中的中文乱码与字段映射错误，确保 `report.html` 可读且语义正确。
- 明确报告字段优先级：`run_config.json`/`run_meta.universe`/`perf.json`/`funnel.csv` 的取值顺序与冲突处理规则。
- 为关键摘要项增加一致性校验与可观测标记（数据来源字段），降低“看起来正确但口径漂移”的风险。
- 保持现有 API 路由与前端调用方式不变，不引入破坏性接口变更。

## Capabilities

### New Capabilities
- `report-consistency-contract`: 定义回测报告关键字段的数据来源优先级、冲突处理与可观测输出，确保报告可复核。

### Modified Capabilities
- `server-report-gen`: 调整报告生成要求，强制以运行时真实配置和产物为准，修复乱码与策略摘要错误展示。
- `single-run-pipeline`: 调整单次运行产物要求，确保 `run_meta` 记录可直接用于报告口径（区间、基准、Universe 统计）且与运行配置一致。
- `artifact-protocol-convergence`: 补充报告相关字段的一致性约束，规范 `perf/run_meta/funnel` 在报告层的映射规则。

## Impact

- 受影响代码：
  - `backend/core/report/report_generator.py`
  - `backend/api/endpoints/backtest_v2_artifacts.py`
  - `backend/api/endpoints/_experiment_runner_api.py`（仅与报告口径相关的元数据透传）
  - `frontend/assets/js/report.js`（与后端报告口径对齐）
- 受影响产物：`report.html`、`run_meta.json`（字段来源与一致性信息）
- 受影响系统：实验历史查看、报告导出、前端概览与报告交叉验证流程
- API 影响：无新增/删除接口；行为上强化“同一实验同一口径”
