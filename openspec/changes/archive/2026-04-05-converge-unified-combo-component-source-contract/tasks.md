## 1. 正式来源合同落地

- [x] 1.1 在 unified combo 编译路径中新增 `component_source_contract` 对象并保持现有回放结果不变。（DoD：`runner_config_bundle.py` 产出的 combo context 同时包含新合同对象与现有 provenance；验证：后端直跑 `A_STOCK_ETF_V1` 的 `cagr` 仍为 `0.13307783712519594`；风险：误改来源物化逻辑会把结果再次锁到错误版本）
- [x] 1.2 在 unified combo 运行产物中透传并固化 `component_source_contract`。（DoD：`run_meta.json` 与等效 runtime snapshot 中可见该对象；验证：前端或直读产物时可同时看到 `component_source_contract` 与 `component_source_mode=research_custom_sleeves`；风险：编译结果与运行产物字段不一致）

## 2. 过渡边界显式化

- [x] 2.1 为 `research_custom_sleeves` 增加显式过渡标记与注释性元数据，不改变现有行为。（DoD：运行产物能区分 formal contract 与 transitional provenance；验证：产物中 `transitional=true` 或等效字段存在；风险：调用方误把新增字段当 breaking change）
- [x] 2.2 更新本 change 的任务与规格引用，补充 cleanup 依赖的 replay anchor 说明。（DoD：本 change 文档与主 spec 口径一致；验证：`openspec status --change converge-unified-combo-component-source-contract --json` 显示 tasks 可 apply；风险：变更口径与已有文档冲突）

## 3. 回归验证

- [x] 3.1 重跑后端与前端 `A_STOCK_ETF_V1`，确认新合同对象不改变目标版本。（DoD：后端与前端结果继续对齐到 `e18e` 语义；验证：比较新旧 `perf.json` 与 `run_meta.json`；风险：并发 warmup 或前端缓存导致误判）
