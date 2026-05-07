## 1. 账户层 transition handoff 合同

- [x] 1.1 在账户层 runtime 中新增统一 `transition_action_handoff` 输出，覆盖四类 transition family；DoD: `run_meta.account_allocator_runtime` 可见 handoff；验证: `A_STOCK_ETF_V1` 回放检查 `run_meta.json`；风险: 若只覆盖局部状态会重新引入双语义。
- [x] 1.2 将 `state_transition_runtime` 与 `transition_action_handoff` 接入 unified combo runtime 装配；DoD: 主 runtime 不再只停留在 explain-only transition；验证: inspect `run_meta.runtime_truth_source` 与 handoff 字段；风险: 若仍保留旧二腿真相优先级，会导致 account allocator 只做旁路说明。

## 2. 执行层消费账户层 handoff

- [ ] 2.1 在 ETF 执行入口、day controls、candidate plan、accounting 中增加 handoff 消费入口，优先处理 `risk_on -> defensive`；DoD: 执行链能识别账户层 carry/de-risk/cash release/budget handoff 动作；验证: ETF standalone 回放与 reason code 检查；风险: 若继续先走旧 weak-state patch，会保留双重执行语义。
- [ ] 2.2 将旧 weak-state redeploy / cash-drip / materialization 路径降级为 diagnostics/reference；DoD: 新旧路径能在产物中区分主消费与参考诊断；验证: `run_meta` 与 `combo_truth` surface 对比；风险: 若直接删除旧路径，会丢失定位能力；若不降级，会继续争夺主解释权。

## 3. 可观测性与主叙事收口

- [x] 3.1 更新 audit、query 与前端结果模型，主面板优先展示账户层 transition consumption，旧 combo/weak-state 只进 diagnostics/reference 区；DoD: `audit.json`、`combo_truth`、前端 governor/account allocator 面板单叙事；验证: `get_experiment_surface_section(..., 'combo_truth')` 与前端最小回归；风险: 若展示层继续平铺两套叙事，用户仍会看到双真相。
- [ ] 3.2 为账户层 handoff 消费增加明确状态与拒绝原因字段；DoD: 可区分已消费、未消费、被拒绝、reference-only diagnostics；验证: 主回放产物 reason code 检查；风险: 若状态枚举不完整，会导致行为归因再次模糊。

## 4. 回放与收口

- [ ] 4.1 运行 ETF standalone 回放，验证账户层 handoff 已进入执行链且 reject 原因优先收敛到账户层消费；DoD: ETF standalone 产物能看到 handoff consumption 状态；验证: 对比 `run_meta.json` 和 `perf.json`；风险: 若行为仍完全不变，需要明确记为 no-go 而不是伪完成。
- [x] 4.2 运行 `A_STOCK_ETF_V1` 主回放与最小正式回归，确认主指标可归因且不引入新的 runtime 漂移；DoD: 主回放完成、最小正式回归通过；验证: `tests/run_minimal_formal_regression.ps1` 与实验指标对比；风险: 若把行为级变化和结构变化绑死，结论会不可归因。

> 当前验收结论：主 runtime 合同与主叙事已收口，但 ETF standalone 仍未产出 `handoff consumption`，旧 weak-state reject 原因仍在产物中占主线，因此本 change 当前应按 `no-go` 处理，不能伪装为已完成能力。
