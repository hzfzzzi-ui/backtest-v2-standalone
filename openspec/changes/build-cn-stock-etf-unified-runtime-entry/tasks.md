## 1. 配置编译与统一入口

- [ ] 1.1 扩展 semantic config / runtime config compile，使 `cfg_cn_stock_etf_v1` 能编译出组合级 governed 配置和两个 sleeve 的运行片段。DoD: compile 结果明确包含组合级上下文与股票/ETF sleeve 片段；验证: 配置编译单测与 config snapshot 断言；风险: 单 asset_scope 假设残留导致 ETF 或股票片段丢失。
- [ ] 1.2 为 unified runtime 定义正式请求入口与最小 payload 语义。DoD: 单次请求可区分 unified runtime 与旧单 sleeve 运行；验证: runtime request/service 单测；风险: 旧请求被误判为 unified runtime。

## 2. 运行编排与 Governor

- [ ] 2.1 实现 unified runtime orchestrator，在一次实验中同时拉起股票 alpha sleeve 与 ETF beta sleeve。DoD: 单次实验能得到两个 sleeve 的独立执行结果；验证: smoke run 产出两个 sleeve 摘要；风险: provider/read path 互相污染。
- [ ] 2.2 扩展 Governor/accounting，使其在同一实验中下发并收口两条 sleeve 的预算与部署状态。DoD: 组合级预算、sleeve_budget、budget_reason_codes 一致落到产物；验证: accounting/result bridge 单测；风险: 预算冲突导致部署语义漂移。

## 3. 产物、审计与前端结果

- [ ] 3.1 扩展 run_meta/audit/snapshot，使 unified runtime 同时暴露组合级与 sleeve 级摘要。DoD: `run_meta.json`、`audit.json`、snapshot 都能区分组合级/股票 sleeve/ETF sleeve；验证: artifact finalize 与 workbench snapshot 单测；风险: 前端把某条 sleeve 误当组合结果。
- [ ] 3.2 扩展 research audit，新增 unified runtime 的组合完整性与 sleeve 完整性判定。DoD: audit 能识别两条 sleeve 是否都实际运行；验证: research audit 单测；风险: 一条 sleeve 缺失但审计误判通过。

## 4. 前端锚点与工作台适配

- [ ] 4.1 将 `cfg_cn_stock_etf_v1` 从“研究组合模板”升级为“统一运行入口模板”，并保持前端可加载。DoD: 前端加载该配置后能触发 unified runtime；验证: config API 读取与前端 smoke；风险: 配置锚点与实际运行语义再度分叉。
- [ ] 4.2 调整结果工作台，使其显示组合级结果、股票 alpha sleeve 和 ETF beta sleeve 三层摘要。DoD: workbench 能稳定展示三层结果且文义正确；验证: 前端单测与截图检查；风险: 旧实验与 unified runtime 实验在 UI 上冲突。

## 5. 回归与验收

- [ ] 5.1 跑 unified runtime 最小 smoke，确认单次实验同时包含股票 alpha 与 ETF beta。DoD: 单个 `exp_id` 下存在组合级结果与两个 sleeve 摘要；验证: smoke run 产物检查；风险: 运行时间过长或只落单腿。
- [ ] 5.2 跑 A股单 sleeve 回归，确认 `baseline_V10.1` 与当前 ETF 单独运行不被破坏。DoD: 单 sleeve 回归无未解释行为漂移；验证: baseline compare 与 ETF smoke compare；风险: 为 unified runtime 改动破坏现有正式入口。
