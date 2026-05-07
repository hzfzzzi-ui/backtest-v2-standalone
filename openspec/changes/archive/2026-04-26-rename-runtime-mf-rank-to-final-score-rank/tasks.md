## 1. Canonical runtime rank 边界
- [x] 1.1 在 candidate audit 与 debug plan 中新增 `final_score_value / final_score_rank / final_score_rank_*` canonical 字段；DoD：新产物可直接读到 canonical 语义；验证：focused unit/integration tests；风险：双写阶段字段语义不一致。
- [x] 1.2 在 daily accounting、metrics 与 artifact diagnostics 中优先消费 `final_score_rank*`，并保留 `mf_rank*` 回退；DoD：新旧产物都能聚合；验证：artifact/unit tests；风险：旧产物兼容断裂。

## 2. 兼容与说明
- [x] 2.1 保留旧 `mf_score / mf_rank / mf_rank*` 作为兼容别名，并补充最小说明；DoD：默认行为不变，旧脚本不坏；验证：selection/accounting tests；风险：用户继续把旧名字当正式语义。
- [x] 2.2 回填 change 说明、风险、回退与验证结论；DoD：tasks 与 notes 可独立说明此次只是命名治理；验证：artifacts 完整；风险：后续把此 change 误解成 moneyflow 接入。
