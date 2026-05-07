## 1. Governor 合同重定义

- [x] 1.1 扩展 `backend/core/config/cn_a_governed_mainline.py` 的正式 sleeve budget 合同；DoD：Governor 能向正式 sleeve 输出 `strategic_floor_cap`、`tactical_overlay_cap`、`deployment_pace`、`hard_block_flags` 与 `defense_bias`，且旧 `target_exposure` 仅保留为聚合视图；验证：Governor 单测与 `run_meta/audit` 快照断言新增字段存在且语义清晰；风险：旧消费者仍假设只有单层 target，导致字段兼容性破裂。
- [x] 1.2 收口 `CN_STOCK_ETF_50_50` 等固定权重组合的正式身份；DoD：research combo 产物显式标记 `research_combo_only`，正式 Governor 路径不再默认回退到固定 50/50；验证：组合 run_meta/audit 回归覆盖 50/50 研究模式与正式 Governor 模式；风险：前端或查询服务继续把研究装配假设误读成正式预算真相。

## 2. ETF Stabilizer 语义实现

- [x] 2.1 将 `backend/core/config/etf_beta_contract.py` 的正式角色升级为 `strategic_beta_stabilizer`；DoD：contract 能显式区分 `core_accumulator`、`tactical_satellite`、`limited_defense`，并定义弱市下 floor/overlay 的正式边界；验证：contract 单测覆盖 `LIGHT`、`TRANS_DOWN`、`RISK_OFF` 与 Governor 硬阻断场景；风险：角色映射与现有三桶模板冲突，导致历史目标仓位大幅漂移。
- [x] 2.2 调整 `backend/core/engine_vector/cn_etf_beta_signal_provider.py` 与相关执行链，只允许对 `core_accumulator` 进行 Governor 节奏约束下的 paced accumulation；DoD：provider/runtime 能区分 floor 与 overlay 的买入、减仓和停买逻辑，不再把弱市承接写成无限制抄底；验证：provider/runtime 单测断言 `deployment_pace`、`hard_block_flags` 与各角色 ETF 的下单行为一致；风险：弱市语义过宽，实际会把 ETF 变成逆势主策略。

## 3. 产物、审计与对照

- [x] 3.1 扩展 `backend/core/audit/research_audit.py` 与 ETF 相关产物的分层归因；DoD：`audit.json`、`portfolio_daily.csv` 等正式产物能回答 `strategic_floor_target`、`tactical_overlay_target`、`actual_core_exposure`、`actual_satellite_exposure`、`actual_defense_exposure` 与 `hard_block_flags`；验证：审计单测覆盖正式 stabilizer 与 `research_combo_only` 两类实验；风险：字段变多但命名不清，反而降低可解释性。
- [x] 3.2 重跑 ETF-only 与 stock+ETF research combo 对照实验；DoD：形成一组正式 stabilizer 实验和一组 research combo 实验，对比 floor/overlay/actual exposure/交易数/回撤解释差异；验证：检查 `run_meta.json`、`audit.json`、`portfolio_daily.csv`、`orders.csv`；风险：行为变化明显但归因不清，导致 spec 无法支撑后续实现决策。
- [x] 3.3 完成 OpenSpec 校验与回退说明；DoD：`openspec validate --changes "governor-strategic-beta-stabilizer-contract"` 通过，且总结中写清受影响文件、验证命令与回退路径；验证：执行 OpenSpec 校验并确认 change `tasks` ready for apply；风险：spec 范围偷偷扩展到 denominator、资产池扩张或收益优化。
