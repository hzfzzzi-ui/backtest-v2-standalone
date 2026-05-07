## 1. 前端优先消费新合同

- [x] 1.1 将结果工作台的来源模式与组件来源解析切到 `component_source_contract` 优先。（DoD：helper/图组件优先看 contract；验证：页面可正常加载并完成回放；风险：旧字段与新字段并存导致展示优先级混乱）

## 2. 后端替换运行编译入口

- [x] 2.1 让 unified combo 编译路径优先从 `component_source_contract.components[*].compile_input` 解析组件输入。（DoD：`runner_config_bundle.py` contract-first；验证：后端回放 `A_STOCK_ETF_V1` 结果不变；风险：contract 与 legacy sleeves 不一致时漂移）
- [x] 2.2 让 unified combo 运行服务优先消费 `component_source_contract.components[*].compile_input`，legacy sleeves 退为 fallback。（DoD：运行服务 contract-first；验证：前端回放结果不变；风险：运行期 contract 不完整导致失败）

## 3. 回归验证

- [x] 3.1 重跑后端与前端 `A_STOCK_ETF_V1`，确认 `cagr` 继续等于 `0.13307783712519594`，且新 contract 中携带 `compile_input`。（DoD：前后端结果继续对齐；验证：新实验产物检查；风险：缓存/会话导致误判）
