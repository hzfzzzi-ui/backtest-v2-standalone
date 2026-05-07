## 1. 账户层 materialization 合同

- [x] 1.1 定义 `RISK_OFF` 账户层 budget materialization 输入与执行顺序，DoD：spec/design 明确 defense 优先、core beta 次之、bounded partial de-risk release；验证：delta spec 能独立表达该执行合同；风险：若顺序含糊，后续实现会再次滑回 ETF 局部补丁。
- [x] 1.2 将 `RISK_OFF` budget materialization 接入 runtime 主解释，DoD：`run_meta` 可区分预算成立、执行激活、执行拒绝；验证：主回放产物出现账户层 materialization 字段；风险：若只改 explain 不改 runtime，会再次形成双重真相。

## 2. 执行链落地

- [x] 2.1 在 `RISK_OFF` 下把账户层预算缺口接入正式执行链，DoD：系统能触发 bounded partial de-risk release 并按 defense → core beta 顺序 materialize；验证：reason code 和 execution path 能证明执行激活；风险：若 release 逻辑失控，会引入过度换手。
- [x] 2.2 保持本轮不修改 `TRANS_DOWN`、`stock alpha`、总暴露和主 regime，DoD：代码 diff 不扩散到非 `RISK_OFF` 主路径；验证：改前改后非 `RISK_OFF` 主指标与结构不被额外重写；风险：若边界失守，研究归因会重新失真。

## 3. explain / audit / 验收

- [x] 3.1 切 audit 与 explain 到账户层 materialization 叙事，DoD：`audit`、`experiment_query_service`、前端 governor/account allocator 面板能区分预算成立、执行激活、执行拒绝；验证：`audit.json` 与前端结果页一致；风险：若只切后端不切前端，用户仍会看到旧 ETF 局部叙事。
- [x] 3.2 用 `A_STOCK_ETF_V1` 回放复核 `MaxDD / Calmar / RISK_OFF 非零持仓率` 与 reject 原因，DoD：至少给出“是否真正改善执行落地”的明确判断；验证：改前改后指标、持仓率和 reason code 对比；风险：若只有结构变化没有行为变化，必须按 no-go 记录。结果：结构字段已落地，但 `RISK_OFF` 非零持仓率、平均暴露和主指标均不变，最新拒绝仍为 `ETF_BETA_RISK_OFF_CASH_DRIP_TOPUP_REJECT_CASH_TOO_SMALL`，本条 change 应按 no-go 处理，不建议归档为成功能力。
