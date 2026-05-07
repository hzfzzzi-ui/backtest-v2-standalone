## 1. Boundary 对齐

- [x] 1.1 调整 `backend/core/config/etf_beta_contract.py` 中 formal `phase1_allocation_engine` 的 boundary 语义；DoD：formal Phase 1 在 `RISK_OFF` 且 Governor 仍给正预算时能保留 reduced allocation contract，不再把 `layering/fallback/targets` 静默压成零；验证：相关单测覆盖 `RISK_OFF` 正预算与显式风险阻断两类场景；风险：误把本轮修复扩展成新的 `controlled_accumulation` 研究。
- [x] 1.2 调整 `backend/core/engine_vector/cn_etf_beta_signal_provider.py` 的 formal Phase 1 deployability 判断顺序；DoD：formal profile 不再仅依赖 `_STATE_SLOT_CAPS` 决定 `NO_TRADE`，而是优先消费 Governor budget、execution flags 与三桶目标；验证：provider 单测覆盖 `RISK_OFF` reduced targets、Governor 硬阻断和 `TRANS_DOWN` 仍无 controlled accumulation；风险：影响旧研究 profile 的遗留行为。

## 2. 审计与产物

- [x] 2.1 扩展 formal ETF Phase 1 的 diagnostics / audit 字段，显式区分 `governor_boundary` 与 `local_boundary_decision`；DoD：零部署和低部署都能回答“是上游压的还是本地 boundary 选的”；验证：`research_audit` 或等价产物断言包含两层证据引用；风险：字段命名不清导致下游继续误解为新的上游真相。
- [x] 2.2 校正 formal study 配置与 runtime 元信息的一致性；DoD：`cn_etf_first_wave_core` 的 formal profile 在 run config、run meta 和 audit 摘要里都能体现当前 boundary 口径，且仍保持 `controlled_accumulation_mode=none`；验证：重跑后检查 `run_config.json`、`audit.json`、`portfolio_daily.csv` 关键字段；风险：配置和运行时快照再次漂移。

## 3. 回归与对照

- [x] 3.1 补齐单元测试和研究审计测试；DoD：新增或更新 contract/provider/audit 相关测试，锁定 `RISK_OFF` reduced allocation、Governor 硬阻断、formal profile 禁止受控承接三类行为；验证：受影响 pytest 子集全部通过；风险：测试只覆盖产物字段，未覆盖真实执行链。
- [x] 3.2 重跑 formal ETF study 并输出旧新对照；DoD：生成新的 formal 实验，比较 `requested_budget`、`targets`、`orders`、`budget_reason_codes` 与 `research_audit` 解释差异；验证：形成明确的行为差异结论，能说明是否完成 formal boundary 对齐；风险：行为变化存在但归因仍不清楚。
- [x] 3.3 完成 OpenSpec 校验与回退说明；DoD：`openspec validate --changes "align-cn-etf-phase1-formal-boundary-policy"` 通过，并在实现说明中写清回退文件与验证命令；验证：spec 校验通过且实现总结包含回退路径；风险：实现已完成但 spec 或回退策略未同步。
