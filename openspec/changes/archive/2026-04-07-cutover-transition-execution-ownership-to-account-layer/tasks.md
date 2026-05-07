## 1. 账户层 transition execution owner

- [x] 1.1 在账户层 runtime 与 unified combo 主装配中新增 `transition_execution_owner / status / reason / reject_reason / reference_paths`；DoD: `run_meta.account_allocator_runtime` 与主组合产物都能看到统一字段；验证: `A_STOCK_ETF_V1` 回放检查 `run_meta.json`；风险: 若只在 explain 层新增字段，仍会保留“新合同存在、旧执行主导”的双语义。
- [x] 1.2 为全部 transition family 输出统一 ownership 状态，未实现 family 也必须显式标记 `reference_only` 或 `not_implemented`；DoD: 不再只对单状态单独建语义；验证: inspect `transition_action_handoff` 与 `transition_execution_owner`；风险: 若合同范围不完整，会重新引入只改单状态的双真相。

## 2. 执行层 owner 硬切换

- [ ] 2.1 在 ETF 执行入口、day controls、candidate plan、accounting 中建立账户层 transition execution controller，并优先落 `risk_on -> defensive`；DoD: 执行链能从账户层 handoff 直接进入 `carry / de-risk / cash release / budget handoff`；验证: ETF standalone 回放检查新 owner reason code；风险: 若仍经由旧 weak-state 入口转发，只是换皮，不是 ownership cutover。
- [ ] 2.2 将 `state_edge_cash_release / riskoff_cash_drip_topup / riskoff_account_budget_materialization / weak_state_inter_rebalance_defense_redeploy` 降级为 diagnostics/reference-only；DoD: 旧路径不再产出主执行状态或主 reject；验证: `run_meta.json` 对比旧 reason code 仅出现在 reference 区；风险: 若降级不彻底，旧路径仍会争夺主 owner。

## 3. 主叙事与可观测性收口

- [x] 3.1 更新 audit、query 和前端结果模型，使账户层 transition execution 成为唯一主叙事；DoD: `audit.json`、`combo_truth`、前端 governor/account allocator 面板只展示账户层主执行状态；验证: `get_experiment_surface_section(..., 'combo_truth')` 与前端最小回归；风险: 若展示层仍平铺 combo/weak-state 文本，用户仍会看到双真相。
- [x] 3.2 为账户层 execution owner 增加完整状态枚举：`owned / consumed / rejected / reference_only / not_implemented`；DoD: 行为归因不再模糊；验证: 主回放产物 reason code 与 reject reason 检查；风险: 若状态枚举不完整，后续研究仍会无法判断 owner 是否真正切换。

## 4. 回放与 no-go 判定

- [ ] 4.1 运行 ETF standalone 回放，验证账户层 execution owner 已成为主执行 owner，旧 weak-state reject 降为 diagnostics/reference；DoD: ETF standalone 产物中主 owner/reject 来自账户层 execution；验证: 对比 `run_meta.json`、`perf.json` 和 reason code；风险: 若行为仍完全不变，必须明确记为 no-go，不能伪装为成功能力。
- [x] 4.2 运行 `A_STOCK_ETF_V1` 主回放与最小正式回归，确认主指标可归因且不引入新的 runtime 漂移；DoD: 主回放完成、最小正式回归通过；验证: `tests/run_minimal_formal_regression.ps1` 与实验指标对比；风险: 若结构切换与行为变化绑死但不可归因，这条 change 应停止推进。

> 当前阻塞结论：主组合 `account_allocator_runtime` 已完成 owner 收口，但 ETF standalone producer 仍未把 `account_transition_execution` 写入正式产物；因此 `2.1 / 2.2 / 4.1` 仍未通过，当前 change 不能归档。

## Current implementation note

- `ETF standalone formal_view` ����д�� `account_transition_execution`��д���������ѽ����
- �� `execution ownership` ��δ�����л����������ֶ���©�����ǵ�ǰ unified combo �ܹ�����ִ�ж��� sleeve�������˻��������û��ܡ�
- ����ζ�� `account-layer transition contract` ����������ط�֮�󣬲��ܷ���ӹ� standalone ETF ����ִ�� owner��
- �ֽ׶����� change Ӧ������Ϊ `no-go`�����Ǻ����� transition execution owner ���յ������˻�ִ�� runtime�������Ǽ���������� ETF sleeve��
