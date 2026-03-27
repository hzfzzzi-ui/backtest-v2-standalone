## 1. 配置与合同收口

- [x] 1.1 为宽基 ETF governed exposure policy 增加唯一配置入口与 schema 字段（DoD：frontend semantic config -> runtime config -> provider 可读到统一字段；验证：schema/compiler 单测与最小 dry-run；风险：字段漂移或默认值污染旧 ETF 线）
- [x] 1.2 在 Governor / ETF contract 中收口宽基 ETF 的 target exposure、min deployable、layering、fallback 语义（DoD：run_meta 能稳定输出 canonical 字段；验证：contract 单测与 run_meta 快照；风险：与旧 ETF policy 混淆）

## 2. 宽基 ETF sleeve 暴露翻译

- [x] 2.1 在 ETF provider 中实现宽基 ETF sleeve 的本地暴露翻译，不改变 Governor 主状态真相（DoD：同一 `effective_state_5` 下能产出宽基 ETF 独立目标暴露；验证：provider 单测；风险：误改旧 A0 控制组行为）
- [x] 2.2 实现 `LIGHT / 受控 TRANS_DOWN / RISK_OFF` 下的分层承接与 fallback 路径（DoD：orders/debug/reason codes 能区分分层承接、fallback 与 under-deploy；验证：最小 smoke run + reason code 样本；风险：把受控承接误做成无限抄底）

## 3. 可观测性与审计

- [x] 3.1 为宽基 ETF 暴露政策补齐 `target/actual/fallback/layering/under_deploy` 审计字段（DoD：audit.json、run_meta.json、研究汇总都能解释暴露过程；验证：research audit 单测；风险：前后端解释口径不一致）
- [x] 3.2 为宽基 ETF 正式研究入口补齐“仅宽基、不含行业 ETF”的范围元信息（DoD：研究入口与产物都能明确标记本轮范围；验证：entry/config 单测；风险：行业 ETF 被静默混入）

## 4. 最小研究对照与结论

- [x] 4.1 以当前 A0 胜出版为控制组，跑宽基 ETF governed exposure policy 最小 AB（DoD：至少完成 target/min deployable/layering/fallback 的最小矩阵；验证：study_run 成功并产出 compare/summary；风险：一次性引入多个主变量导致不可归因）
- [x] 4.2 汇总研究结论并写明是否值得升格为新的 ETF 主研究线（DoD：implementation_notes 说明赢家、失败项、风险、回退；验证：OpenSpec validate + instructions apply；风险：把“暴露更合理”误判成“收益目标已成立”）
