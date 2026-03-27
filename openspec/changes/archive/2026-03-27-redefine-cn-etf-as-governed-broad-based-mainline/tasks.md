## 1. 合同与配置收口

- [x] 1.1 收口宽基 ETF 独立主线的配置 schema 与 contract owner，使 `strategy_role`、Governor 边界消费方式、exposure policy、controlled accumulation 与 fallback 语义成为唯一真相。DoD：前后端/研究入口可编译出一致 runtime 配置；验证：配置编译单测与 schema 单测通过；风险：旧 ETF study 兼容字段可能被破坏。
- [x] 1.2 在研究入口与 preset 摘要中显式标记“governed broad-based standalone mainline”，并禁止行业 ETF 通过本轮入口混入。DoD：研究入口能生成主线配置且边界错误可被显式抛出；验证：研究入口单测与 dry-run 编译通过；风险：现有 ETF preset 需要兼容迁移。

## 2. Governor 边界与 ETF 本地策略翻译

- [x] 2.1 在 ETF provider 中实现 Governor 边界到宽基 ETF 主线本地 policy 的翻译层，显式区分 Governor 边界、主线 enter/exit、deployability 与 controlled accumulation。DoD：provider 输出 target/min/actual/fallback/accumulation 原因链；验证：provider 单测覆盖不同状态区间；风险：旧辅助 sleeve 逻辑与新主线逻辑交叉污染。
- [x] 2.2 为宽基 ETF 主线实现受控承接与禁做边界，确保 `LIGHT`/受控 `TRANS_DOWN` 可解释承接，而 `RISK_OFF` 等禁做区间仍被严格阻断。DoD：存在明确状态带宽和 reason code；验证：研究样本产物、reason code 统计和 debug 行样本可读；风险：承接被做成无约束抄底。

## 3. 审计与产物可观测性

- [x] 3.1 扩展 `run_meta`、`audit.json` 和 ETF 汇总产物，显式拆分 Governor 统一边界与 ETF 主线本地决策。DoD：产物能回答“Governor 压制”与“ETF 主线主动不进场”的区别；验证：artifact/audit 单测通过；风险：前端或下游继续误把两层真相混在一起。
- [x] 3.2 为宽基 ETF 主线新增受控承接、deployability、fallback 连续性与 under-deploy 原因统计。DoD：summary / audit / reason_codes 至少有一处能看到这些统计；验证：研究审计单测与产物快照对比通过；风险：统计口径与实际交易逻辑不一致。

## 4. 研究验证与结论收口

- [x] 4.1 新建独立宽基 ETF 主线 study，对照旧 A0 主线运行最小 AB，不与个股 alpha 混跑。DoD：study 可 dry-run、可正式运行、产物齐全；验证：`study_run` 成功并生成 perf/nav/orders/run_meta/audit；风险：研究窗口或资产池边界与旧 A0 不可比。
- [x] 4.2 形成 compare/summary/implementation notes，明确这条新主线是否达到继续推进标准，并给出回退路径。DoD：有总结、风险、验证、回退；验证：OpenSpec validate 和 instructions apply 全通过；风险：只看到收益不看部署连续性与审计证据。
