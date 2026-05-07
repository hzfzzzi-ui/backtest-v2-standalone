## 1. 删除编译期 fallback

- [x] 1.1 从 unified combo 编译路径移除对 legacy `unified_runtime.sleeves[*]` 的主路径消费，保留 contract-only 解析。（DoD：`runner_config_bundle.py` 不再把 legacy sleeves 当主入口；验证：后端回放 `A_STOCK_ETF_V1` 结果不变；风险：contract 信息不完整导致编译失败）

## 2. 删除运行期 fallback

- [x] 2.1 从 unified combo 运行服务移除对 legacy `sleeves[*].semantic_config/runtime_config` 的 fallback 消费。（DoD：运行服务仅消费 contract compile_input；验证：前端回放结果不变；风险：运行期 contract 缺字段）

## 3. 收紧展示与审计口径

- [x] 3.1 调整前端与产物口径，明确 `research_custom_sleeves` 为历史 provenance，不再表述为当前主运行来源。（DoD：工作台文案与来源解析一致；验证：前端展示正常；风险：旧实验展示回退）

## 4. 回归与回退准备

- [x] 4.1 重跑后端与前端 `A_STOCK_ETF_V1`，确认 contract-only 路径继续复现 `cagr = 0.13307783712519594`。（DoD：前后端结果继续一致；验证：新实验产物；风险：误把数据缓存问题当合同漂移）
- [x] 4.2 记录回退方案，把 contract-first transitional mode 的恢复点写进任务说明。（DoD：回退路径清晰；验证：任务与设计文档一致；风险：删完 fallback 后无明确回退点）
